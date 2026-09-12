"""Seller-only checkout service. Never bundle with the desktop application."""
import json
import os
import re
import sqlite3
import sys
import threading
import time
import uuid
from contextlib import closing, contextmanager
from pathlib import Path

import requests
import stripe
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from flask import Flask, jsonify, request, send_from_directory
from license_core import LICENSE_LIFETIME_DAYS, days_for_term_years, issue_license_key, load_private_key, load_public_key

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
EMAIL_RETRY_SECONDS = 23 * 3600
MAIL_CLAIM_SECONDS = 120


def plan_record(plan: str):
    return PLANS.get(plan) or LEGACY_PLANS.get(plan)


ROOT = Path(__file__).resolve().parent


def _install_private_key_from_env() -> None:
    """Railway/hosting: paste PEM into LICENSE_PRIVATE_KEY. Never commit the key.

    A bad value must not prevent the process from listening — otherwise Railway
    returns 502 for /api/sales/config and the seller cannot see that checkout
    is merely misconfigured.
    """
    pem = os.environ.get('LICENSE_PRIVATE_KEY', '').replace('\\n', '\n').strip()
    if not pem:
        return
    if 'BEGIN' not in pem:
        print('LICENSE_PRIVATE_KEY is set but is not a PEM; ignoring', file=sys.stderr, flush=True)
        return
    path = Path(os.environ.get('LICENSE_PRIVATE_KEY_FILE', '/tmp/ed25519_private.pem'))
    path.write_text(pem if pem.endswith('\n') else pem + '\n', encoding='ascii')
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    os.environ['LICENSE_PRIVATE_KEY_PATH'] = str(path)


def signing_keys_match() -> bool:
    """True if the seller private key is the pair of license_public.pem in the app."""
    try:
        private = load_private_key()
        public = load_public_key()
        issued = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        shipped = public.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return issued == shipped
    except Exception:
        return False


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
        SALES_ALERT_TO=os.environ.get('SALES_ALERT_TO', ''),
        SALES_ADMIN_TOKEN=os.environ.get('SALES_ADMIN_TOKEN', ''),
        SALES_ENABLED=os.environ.get('SALES_ENABLED') == 'true',
        SALES_MAIL_POLL=float(os.environ.get('SALES_MAIL_POLL', '5')),
        # Optional: pin the Stripe API version so behaviour cannot drift when the
        # account default changes. Leave empty to use the account/SDK default.
        STRIPE_API_VERSION=os.environ.get('STRIPE_API_VERSION', ''),
        TESTING=False,
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
        if 'alerted' not in cols:
            conn.execute('ALTER TABLE orders ADD COLUMN alerted INTEGER NOT NULL DEFAULT 0')
        for name, kind in (('mail_claim', 'TEXT'), ('mail_claim_until', 'REAL'),
                           ('recovery_started', 'REAL')):
            if name not in cols:
                conn.execute(f'ALTER TABLE orders ADD COLUMN {name} {kind}')

    def ready():
        return app.config['SALES_ENABLED'] and all(app.config[k] for k in (
            'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET', 'RESEND_API_KEY', 'SALES_FROM'
        )) and signing_keys_match()

    def admin_ok():
        token = app.config['SALES_ADMIN_TOKEN']
        if not token:
            return False
        return request.headers.get('Authorization') == 'Bearer ' + token

    def license_email_body(order):
        spec = plan_record(order['plan'])
        label = spec['label'] if spec else order['plan']
        return (
            f"ขอบคุณที่สั่งซื้อ FormDD\nOrder: {order['id']}\n"
            f"Machine ID: {order['machine']}\nPlan: {label}\n\n{order['license']}\n\n"
            "เปิดโปรแกรม ไปที่ตั้งค่าไลเซนต์ แล้ววางคีย์นี้\n"
            "Open FormDD license settings and paste this key.\n"
            "Support: formdd@xambrain.com"
        )

    def post_resend(to, subject, text, idempotency):
        result = requests.post(
            'https://api.resend.com/emails', timeout=20,
            headers={'Authorization': 'Bearer ' + app.config['RESEND_API_KEY'],
                     'Idempotency-Key': idempotency},
            json={'from': app.config['SALES_FROM'], 'to': [to],
                  'subject': subject, 'text': text})
        result.raise_for_status()

    def alert_seller(order):
        dest = (app.config['SALES_ALERT_TO'] or app.config['SALES_FROM']).strip()
        if not dest:
            app.logger.error('Unsent paid order %s has no SALES_ALERT_TO / SALES_FROM', order['id'])
            return
        post_resend(
            dest,
            'FormDD: คีย์ค้างส่ง / unpaid email',
            (
                f"จ่ายแล้วแต่ส่งคีย์ให้ลูกค้าไม่สำเร็จ\n"
                f"Order: {order['id']}\nCustomer: {order['email']}\n"
                f"Machine ID: {order['machine']}\n"
                f"ส่งซ้ำ: POST /api/sales/resend with this order id\n\n{order['license']}"
            ),
            'alert-' + order['id'],
        )
        with use_db() as conn:
            conn.execute('UPDATE orders SET alerted=1 WHERE id=?', (order['id'],))

    def send_customer(order_id, manual=False):
        # Claim in SQLite, not a process-local lock: workers and admin requests
        # share ownership, including after a restart. Never hold a DB lock over HTTP.
        claim = uuid.uuid4().hex
        now = time.time()
        with use_db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            order = conn.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
            if not order or not order['paid'] or not order['license']:
                return 'missing'
            if order['sent']:
                return 'sent'
            if (order['mail_claim_until'] or 0) > now:
                return 'busy'
            started = order['email_started'] or now
            recovery = order['recovery_started']
            if now - started > EMAIL_RETRY_SECONDS:
                if not manual:
                    return 'expired'
                if recovery and now - recovery > EMAIL_RETRY_SECONDS:
                    # Delivery may have succeeded before a crash. Do not reuse a
                    # provider key after its deduplication window has elapsed.
                    return 'review'
                recovery = recovery or now
            delivery = ('license-resend-' if recovery else 'license-') + order_id
            conn.execute(
                'UPDATE orders SET mail_claim=?,mail_claim_until=?,email_started=?,recovery_started=? WHERE id=?',
                (claim, now + MAIL_CLAIM_SECONDS, started, recovery, order_id))
        try:
            post_resend(order['email'], 'FormDD: คีย์เปิดใช้งาน / Activation key',
                        license_email_body(order), delivery)
            with use_db() as conn:
                conn.execute('UPDATE orders SET sent=1 WHERE id=? AND mail_claim=?', (order_id, claim))
            return 'sent'
        finally:
            with use_db() as conn:
                conn.execute('UPDATE orders SET mail_claim=NULL,mail_claim_until=NULL WHERE id=? AND mail_claim=?',
                             (order_id, claim))

    def drain_mail():
        """Send or alert for paid orders that still lack a customer email."""
        with closing(db()) as conn:
            pending = conn.execute(
                'SELECT * FROM orders WHERE paid=1 AND sent=0 AND license IS NOT NULL'
            ).fetchall()
        now = time.time()
        for order in pending:
            started = order['email_started'] or now
            if now - started > EMAIL_RETRY_SECONDS:
                if not order['alerted']:
                    try:
                        alert_seller(order)
                    except Exception:
                        app.logger.exception('Seller alert failed for order %s', order['id'])
                continue
            try:
                send_customer(order['id'])
            except Exception:
                app.logger.exception('Customer license email pending for order %s', order['id'])

    app.drain_mail = drain_mail

    if not app.config.get('TESTING'):
        def mail_loop():
            while True:
                try:
                    drain_mail()
                except Exception:
                    app.logger.exception('Mail worker')
                time.sleep(max(1.0, float(app.config['SALES_MAIL_POLL'])))
        threading.Thread(target=mail_loop, name='sales-mail', daemon=True).start()

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
            if not signing_keys_match():
                return jsonify(error='ระบบออกคีย์ยังไม่พร้อม กรุณาติดต่อผู้ขาย'), 503
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
        """Record a paid order and issue the key. Email is a later drain_mail job."""
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

    @app.post('/api/sales/webhook')
    def webhook():
        secret = app.config['STRIPE_WEBHOOK_SECRET']
        if not secret: return jsonify(error='Not configured'), 503
        try:
            event = stripe.Webhook.construct_event(request.get_data(), request.headers.get('Stripe-Signature', ''), secret)
        except (ValueError, stripe.SignatureVerificationError):
            return jsonify(error='Invalid signature'), 400
        if event.type in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
            try:
                fulfill(event.data.object.id)
            except Exception:
                app.logger.exception('Fulfillment pending; Stripe event %s requires retry or seller review', event.id)
                return jsonify(error='Fulfillment pending'), 500
        return jsonify(received=True)

    @app.get('/api/sales/unsent')
    def unsent():
        if not admin_ok():
            return jsonify(error='Not found'), 404
        with closing(db()) as conn:
            rows = conn.execute(
                'SELECT id,email,machine,plan,paid,sent,alerted,email_started FROM orders '
                'WHERE paid=1 AND sent=0 ORDER BY email_started'
            ).fetchall()
        return jsonify(orders=[dict(row) for row in rows])

    @app.post('/api/sales/resend')
    def resend():
        if not admin_ok():
            return jsonify(error='Not found'), 404
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify(error='Invalid request'), 400
        order_id = str(data.get('order_id', '')).strip()
        with closing(db()) as conn:
            order = conn.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
        if not order or not order['paid'] or not order['license']:
            return jsonify(error='Order not found'), 404
        if order['sent']:
            return jsonify(ok=True, already=True)
        try:
            state = send_customer(order_id, manual=True)
        except Exception:
            app.logger.exception('Manual delivery pending for order %s', order_id)
            return jsonify(error='Email delivery pending; retry safely'), 502
        if state in ('busy', 'review'):
            return jsonify(error='Delivery in progress' if state == 'busy' else
                           'Check provider delivery history before further recovery'), 409
        if state == 'missing':
            return jsonify(error='Order not found'), 404
        return jsonify(ok=True)

    @app.get('/')
    def home(): return send_from_directory(ROOT / 'website', 'index.html')

    @app.get('/<path:name>')
    def assets(name): return send_from_directory(ROOT / 'website', name)

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5080, debug=False)
