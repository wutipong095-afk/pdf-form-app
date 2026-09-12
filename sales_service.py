"""Seller-only checkout service. Never bundle with the desktop application."""
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from pathlib import Path

import requests
import stripe
from flask import Flask, jsonify, request, send_from_directory
from license_core import LICENSE_LIFETIME_DAYS, days_for_term_years, issue_license_key

# amount is Stripe unit_amount in satang. days is written into the issued key.
PLANS = {
    '1': {
        'amount': 9900,
        'days': days_for_term_years(1),
        'label': '1 ปี',
        'product': 'FormDD 1 ปี / 1 เครื่อง',
    },
    'lt': {
        'amount': 29900,
        'days': LICENSE_LIFETIME_DAYS,
        'label': 'ซื้อขาด (LT)',
        'product': 'FormDD ซื้อขาด (LT) — เวอร์ชันนั้นตลอดไป / 1 เครื่อง',
    },
    'lt3': {
        'amount': 49900,
        'days': LICENSE_LIFETIME_DAYS,
        'label': 'ซื้อขาด + อัปเดต 3 ปี',
        'product': 'FormDD ซื้อขาด + major update 3 ปี / 1 เครื่อง',
    },
}
# Closed for new checkout. Kept so a session opened before the catalog change
# can still issue a key and email after payment.
LEGACY_PLANS = {
    '3': {
        'amount': 35000,
        'days': days_for_term_years(3),
        'label': '3 ปี',
        'product': 'FormDD 3 ปี / 1 เครื่อง',
    },
    '5': {
        'amount': 50000,
        'days': days_for_term_years(5),
        'label': '5 ปี',
        'product': 'FormDD 5 ปี / 1 เครื่อง',
    },
    '10': {
        'amount': 100000,
        'days': days_for_term_years(10),
        'label': '10 ปี',
        'product': 'FormDD 10 ปี / 1 เครื่อง',
    },
}


def plan_record(plan: str):
    return PLANS.get(plan) or LEGACY_PLANS.get(plan)
ROOT = Path(__file__).resolve().parent


def _install_private_key_from_env() -> None:
    """Railway/hosting: paste PEM into LICENSE_PRIVATE_KEY. Never commit the key."""
    pem = os.environ.get('LICENSE_PRIVATE_KEY', '').replace('\\n', '\n').strip()
    if not pem:
        return
    if 'BEGIN' not in pem:
        raise RuntimeError('LICENSE_PRIVATE_KEY must be a PEM private key')
    path = Path(os.environ.get('LICENSE_PRIVATE_KEY_FILE', '/tmp/ed25519_private.pem'))
    path.write_text(pem if pem.endswith('\n') else pem + '\n', encoding='ascii')
    os.chmod(path, 0o600)
    os.environ['LICENSE_PRIVATE_KEY_PATH'] = str(path)


def create_app(config=None):
    _install_private_key_from_env()
    app = Flask(__name__, static_folder=None)
    app.config.update(
        MAX_CONTENT_LENGTH=65536,
        SALES_DB=os.environ.get('SALES_DB', str(ROOT / 'data/sales/orders.sqlite')),
        SALES_ORIGIN=os.environ.get('SALES_ORIGIN', 'http://127.0.0.1:5080'),
        STRIPE_SECRET_KEY=os.environ.get('STRIPE_SECRET_KEY', ''),
        STRIPE_WEBHOOK_SECRET=os.environ.get('STRIPE_WEBHOOK_SECRET', ''),
        RESEND_API_KEY=os.environ.get('RESEND_API_KEY', ''),
        SALES_FROM=os.environ.get('SALES_FROM', ''),
        SALES_ENABLED=os.environ.get('SALES_ENABLED') == 'true',
        # Optional: pin the Stripe API version so behaviour cannot drift when the
        # account default changes. Leave empty to use the account/SDK default.
        STRIPE_API_VERSION=os.environ.get('STRIPE_API_VERSION', ''),
    )
    if config: app.config.update(config)
    if app.config['STRIPE_API_VERSION']:
        stripe.api_version = app.config['STRIPE_API_VERSION']
    Path(app.config['SALES_DB']).parent.mkdir(parents=True, exist_ok=True)

    def db():
        conn = sqlite3.connect(app.config['SALES_DB'], timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def use_db():
        # `with sqlite3.connect(...)` commits/rolls back but never closes the
        # connection. Own it here so every request releases its handle.
        conn = db()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    with use_db() as conn:
        # Serialize schema inspection and migration across starting workers.
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('''CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY, machine TEXT NOT NULL, email TEXT NOT NULL,
            plan TEXT NOT NULL, amount INTEGER NOT NULL, session TEXT UNIQUE,
            license TEXT, paid INTEGER NOT NULL DEFAULT 0,
            email_started REAL, sent INTEGER NOT NULL DEFAULT 0)''')
        cols = {row[1] for row in conn.execute('PRAGMA table_info(orders)')}
        if 'product' not in cols:
            conn.execute('ALTER TABLE orders ADD COLUMN product TEXT')

    def ready():
        return app.config['SALES_ENABLED'] and all(app.config[k] for k in (
            'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET', 'RESEND_API_KEY', 'SALES_FROM'))

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        if request.path.startswith('/api/'): response.headers['Cache-Control'] = 'no-store'
        origin = request.headers.get('Origin')
        if origin == app.config['SALES_ORIGIN'] and request.path.startswith('/api/sales/'):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Vary'] = 'Origin'
        return response

    @app.route('/api/sales/config', methods=['GET', 'OPTIONS'])
    def settings():
        if request.method == 'OPTIONS':
            return '', 204
        return jsonify(enabled=bool(ready()))

    @app.route('/api/sales/checkout', methods=['POST', 'OPTIONS'])
    def checkout():
        if request.method == 'OPTIONS':
            return '', 204
        if not ready(): return jsonify(error='ระบบชำระเงินยังไม่เปิดใช้งาน กรุณาติดต่อผู้ขาย'), 503
        if request.headers.get('Origin') != app.config['SALES_ORIGIN']:
            return jsonify(error='Invalid origin'), 403
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict): return jsonify(error='Invalid request'), 400
        mid = str(data.get('machine_id', '')).strip().upper()
        email = str(data.get('email', '')).strip()
        plan = str(data.get('plan', ''))
        order_id = str(data.get('request_id', ''))
        spec = PLANS.get(plan)
        if not re.fullmatch(r'[A-F0-9]{16}', mid):
            return jsonify(error='กรุณาตรวจรหัสเครื่อง 16 ตัว'), 400
        if spec is None:
            return jsonify(error='กรุณาเลือกแผนที่เปิดขาย'), 400
        if len(email) > 254 or not re.fullmatch(r'[^\s@<>\r\n]+@[^\s@<>\r\n]+\.[^\s@<>\r\n]+', email):
            return jsonify(error='กรุณาตรวจอีเมล'), 400
        try: uuid.UUID(order_id)
        except ValueError: return jsonify(error='Invalid request ID'), 400
        try:
            # Refuse payment if the seller's signing key is unavailable.
            from license_core import load_private_key
            load_private_key()
            # Persist the order and read back its state in one short transaction,
            # BEFORE any Stripe network call, so no write lock is held while Stripe
            # is slow. INSERT OR IGNORE keeps this idempotent per request_id.
            # Amount and product are frozen on first insert so a retry after a lost
            # Session write reuses the same Stripe idempotency parameters.
            with use_db() as conn:
                conn.execute(
                    'INSERT OR IGNORE INTO orders(id,machine,email,plan,amount,product) VALUES(?,?,?,?,?,?)',
                    (order_id, mid, email, plan, spec['amount'], spec['product']))
                order = conn.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
                if (order['machine'], order['email'], order['plan']) != (mid, email, plan):
                    order = None
            if order is None:
                return jsonify(error='ข้อมูลเปลี่ยน กรุณาเริ่มรายการใหม่'), 409
            stored_product = (order['product'] or '').strip()
            if not order['session'] and not stored_product and order['amount'] != spec['amount']:
                # Pre-catalog row: we cannot replay the original Stripe params.
                return jsonify(error='รายการนี้ต้องเริ่มใหม่ กรุณารีเฟรชหน้าแล้วลองอีกครั้ง'), 409
            product = stored_product or spec['product']
            if order['session']:
                session = stripe.checkout.Session.retrieve(order['session'], api_key=app.config['STRIPE_SECRET_KEY'])
            else:
                session = stripe.checkout.Session.create(
                    api_key=app.config['STRIPE_SECRET_KEY'], idempotency_key='checkout-' + order_id,
                    mode='payment', customer_email=email, client_reference_id=order_id,
                    metadata={'order_id': order_id},
                    line_items=[{'price_data': {'currency': 'thb', 'unit_amount': order['amount'],
                        'product_data': {'name': product}}, 'quantity': 1}],
                    success_url=app.config['SALES_ORIGIN'] + '/payment.html',
                    cancel_url=app.config['SALES_ORIGIN'] + '/pricing.html?payment=cancelled#purchase')
                # Store the session only if none was set meanwhile. The idempotency
                # key guarantees a concurrent create returns this same session, so a
                # racing request that already stored it wins harmlessly.
                with use_db() as conn:
                    conn.execute('UPDATE orders SET session=? WHERE id=? AND session IS NULL', (session.id, order_id))
            if not session.url: return jsonify(error='รายการนี้สิ้นสุดแล้ว กรุณาเริ่มรายการใหม่'), 409
            return jsonify(url=session.url)
        except Exception:
            app.logger.exception('Checkout failed; inspect seller configuration or Stripe dashboard')
            return jsonify(error='สร้างรายการชำระเงินไม่สำเร็จ กรุณาลองใหม่หรือติดต่อผู้ขาย'), 502

    def fulfill(session_id):
        session = stripe.checkout.Session.retrieve(session_id, api_key=app.config['STRIPE_SECRET_KEY'])
        if session.payment_status != 'paid': return
        with use_db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            order = conn.execute('SELECT * FROM orders WHERE session=?', (session_id,)).fetchone()
            if not order: raise ValueError('Unknown order')
            if session.mode != 'payment' or session.currency != 'thb' or session.amount_total != order['amount']:
                raise ValueError('Payment mismatch')
            if session.client_reference_id != order['id']: raise ValueError('Reference mismatch')
            if order['sent']: return
            spec = plan_record(order['plan'])
            if spec is None: raise ValueError('Unknown plan')
            key = order['license'] or issue_license_key(order['machine'], days=spec['days'])
            started = order['email_started'] or time.time()
            conn.execute('UPDATE orders SET paid=1,license=?,email_started=? WHERE id=?', (key, started, order['id']))
        # The key is durable and committed. Contact the email provider WITHOUT
        # holding a write lock, so concurrent checkouts are never blocked on the
        # network call. Resend's Idempotency-Key makes a retried send reuse the
        # same delivery, so it is safe to send outside the transaction.
        with closing(db()) as conn:
            order = conn.execute('SELECT * FROM orders WHERE session=?', (session_id,)).fetchone()
        if order['sent']: return
        if time.time() - order['email_started'] > 23 * 3600:
            # Stop retrying instead of returning 500 forever (which eventually makes
            # Stripe disable the endpoint and blocks future orders too). The key is
            # paid and issued; a seller reconciles unsent paid orders (paid=1,sent=0).
            app.logger.error('Email retry window expired for order %s; key issued but not emailed — seller must send it manually', order['id'])
            return
        result = requests.post('https://api.resend.com/emails', timeout=20,
            headers={'Authorization': 'Bearer ' + app.config['RESEND_API_KEY'],
                     'Idempotency-Key': 'license-' + order['id']},
            json={'from': app.config['SALES_FROM'], 'to': [order['email']],
                  'subject': 'FormDD: คีย์เปิดใช้งาน / Activation key',
                  'text': f"ขอบคุณที่สั่งซื้อ FormDD\nOrder: {order['id']}\nMachine ID: {order['machine']}\nPlan: {plan_record(order['plan'])['label']}\n\n{order['license']}\n\nเปิดโปรแกรม ไปที่ตั้งค่าไลเซนต์ แล้ววางคีย์นี้\nOpen FormDD license settings and paste this key.\nSupport: formdd@xambrain.com"})
        result.raise_for_status()
        with use_db() as conn:
            conn.execute('UPDATE orders SET sent=1 WHERE id=?', (order['id'],))

    @app.post('/api/sales/webhook')
    def webhook():
        secret = app.config['STRIPE_WEBHOOK_SECRET']
        if not secret: return jsonify(error='Not configured'), 503
        try:
            event = stripe.Webhook.construct_event(request.get_data(), request.headers.get('Stripe-Signature', ''), secret)
        except (ValueError, stripe.SignatureVerificationError):
            return jsonify(error='Invalid signature'), 400
        if event.type in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
            try: fulfill(event.data.object.id)
            except Exception:
                app.logger.exception('Fulfillment pending; Stripe event %s requires retry or seller review', event.id)
                return jsonify(error='Fulfillment pending'), 500
        return jsonify(received=True)

    @app.get('/')
    def home(): return send_from_directory(ROOT / 'website', 'index.html')

    @app.get('/<path:name>')
    def assets(name): return send_from_directory(ROOT / 'website', name)

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5080, debug=False)
