"""Seller-only checkout service. Never bundle with the desktop application."""
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path

import requests
import stripe
from flask import Flask, jsonify, request, send_from_directory
from license_core import issue_license_key, days_for_term_years

PLANS = {'1': 14900, '3': 35000, '5': 50000, '10': 100000}
ROOT = Path(__file__).resolve().parent


def create_app(config=None):
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
    )
    if config: app.config.update(config)
    Path(app.config['SALES_DB']).parent.mkdir(parents=True, exist_ok=True)

    def db():
        conn = sqlite3.connect(app.config['SALES_DB'], timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    with db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY, machine TEXT NOT NULL, email TEXT NOT NULL,
            plan TEXT NOT NULL, amount INTEGER NOT NULL, session TEXT UNIQUE,
            license TEXT, paid INTEGER NOT NULL DEFAULT 0,
            email_started REAL, sent INTEGER NOT NULL DEFAULT 0)''')

    def ready():
        return app.config['SALES_ENABLED'] and all(app.config[k] for k in (
            'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET', 'RESEND_API_KEY', 'SALES_FROM'))

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        if request.path.startswith('/api/'): response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/sales/config')
    def settings():
        return jsonify(enabled=bool(ready()))

    @app.post('/api/sales/checkout')
    def checkout():
        if not ready(): return jsonify(error='ระบบชำระเงินยังไม่เปิดใช้งาน กรุณาติดต่อผู้ขาย'), 503
        if request.headers.get('Origin') != app.config['SALES_ORIGIN']:
            return jsonify(error='Invalid origin'), 403
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict): return jsonify(error='Invalid request'), 400
        mid = str(data.get('machine_id', '')).strip().upper()
        email = str(data.get('email', '')).strip()
        plan = str(data.get('plan', ''))
        order_id = str(data.get('request_id', ''))
        if not re.fullmatch(r'[A-F0-9]{16}', mid) or plan not in PLANS:
            return jsonify(error='กรุณาตรวจรหัสเครื่องและแผนที่เลือก'), 400
        if len(email) > 254 or not re.fullmatch(r'[^\s@<>\r\n]+@[^\s@<>\r\n]+\.[^\s@<>\r\n]+', email):
            return jsonify(error='กรุณาตรวจอีเมล'), 400
        try: uuid.UUID(order_id)
        except ValueError: return jsonify(error='Invalid request ID'), 400
        try:
            # Refuse payment if the seller's signing key is unavailable.
            from license_core import load_private_key
            load_private_key()
            with db() as conn:
                conn.execute('INSERT OR IGNORE INTO orders(id,machine,email,plan,amount) VALUES(?,?,?,?,?)',
                             (order_id, mid, email, plan, PLANS[plan]))
                order = conn.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
                if (order['machine'], order['email'], order['plan']) != (mid, email, plan):
                    return jsonify(error='ข้อมูลเปลี่ยน กรุณาเริ่มรายการใหม่'), 409
                if order['session']:
                    session = stripe.checkout.Session.retrieve(order['session'], api_key=app.config['STRIPE_SECRET_KEY'])
                else:
                    session = stripe.checkout.Session.create(
                        api_key=app.config['STRIPE_SECRET_KEY'], idempotency_key='checkout-' + order_id,
                        mode='payment', customer_email=email, client_reference_id=order_id,
                        metadata={'order_id': order_id},
                        line_items=[{'price_data': {'currency': 'thb', 'unit_amount': PLANS[plan],
                            'product_data': {'name': f'FormDD {plan} years / 1 PC'}}, 'quantity': 1}],
                        success_url=app.config['SALES_ORIGIN'] + '/payment.html',
                        cancel_url=app.config['SALES_ORIGIN'] + '/pricing.html?payment=cancelled#purchase')
                    conn.execute('UPDATE orders SET session=? WHERE id=?', (session.id, order_id))
            if not session.url: return jsonify(error='รายการนี้สิ้นสุดแล้ว กรุณาเริ่มรายการใหม่'), 409
            return jsonify(url=session.url)
        except Exception:
            app.logger.error('Checkout failed; inspect seller configuration or Stripe dashboard')
            return jsonify(error='สร้างรายการชำระเงินไม่สำเร็จ กรุณาลองใหม่หรือติดต่อผู้ขาย'), 502

    def fulfill(session_id):
        session = stripe.checkout.Session.retrieve(session_id, api_key=app.config['STRIPE_SECRET_KEY'])
        if session.payment_status != 'paid': return
        with db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            order = conn.execute('SELECT * FROM orders WHERE session=?', (session_id,)).fetchone()
            if not order: raise ValueError('Unknown order')
            if session.mode != 'payment' or session.currency != 'thb' or session.amount_total != order['amount']:
                raise ValueError('Payment mismatch')
            if session.client_reference_id != order['id']: raise ValueError('Reference mismatch')
            if order['sent']: return
            key = order['license'] or issue_license_key(order['machine'], days=days_for_term_years(int(order['plan'])))
            started = order['email_started'] or time.time()
            conn.execute('UPDATE orders SET paid=1,license=?,email_started=? WHERE id=?', (key, started, order['id']))
        # The key is durable before contacting the email provider. Retries reuse it.
        with db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            order = conn.execute('SELECT * FROM orders WHERE session=?', (session_id,)).fetchone()
            if order['sent']: return
            if time.time() - order['email_started'] > 23 * 3600:
                raise RuntimeError('Email retry window expired; seller must reconcile delivery')
            result = requests.post('https://api.resend.com/emails', timeout=20,
                headers={'Authorization': 'Bearer ' + app.config['RESEND_API_KEY'],
                         'Idempotency-Key': 'license-' + order['id']},
                json={'from': app.config['SALES_FROM'], 'to': [order['email']],
                      'subject': 'FormDD: คีย์เปิดใช้งาน / Activation key',
                      'text': f"ขอบคุณที่สั่งซื้อ FormDD\nOrder: {order['id']}\nMachine ID: {order['machine']}\nPlan: {order['plan']} years\n\n{order['license']}\n\nเปิดโปรแกรม ไปที่ตั้งค่าไลเซนต์ แล้ววางคีย์นี้\nOpen FormDD license settings and paste this key.\nSupport: formdd@xambrain.com"})
            result.raise_for_status()
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
                app.logger.error('Fulfillment pending; Stripe event %s requires retry or seller review', event.id)
                return jsonify(error='Fulfillment pending'), 500
        return jsonify(received=True)

    @app.get('/')
    def home(): return send_from_directory(ROOT / 'website', 'index.html')

    @app.get('/<path:name>')
    def assets(name): return send_from_directory(ROOT / 'website', name)

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5080, debug=False)
