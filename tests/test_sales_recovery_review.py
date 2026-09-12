"""Recovery checks with isolated SQLite and simulated payment/email providers."""
import hashlib
import hmac
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import sales_service as sales
from test_sales_service import setup, checkout


def paid_webhook(client):
    body = json.dumps({'id': 'evt_recovery', 'type': 'checkout.session.completed',
                       'data': {'object': {'id': 'cs_test_order'}}}).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(b'whsec_test', timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
    return client.post('/api/sales/webhook', data=body,
                       headers={'Stripe-Signature': f't={timestamp},v1={digest}'})


def test_restart_recovers_paid_mail_without_another_webhook(setup):
    client, payload, _, _, issue, mail = setup
    assert checkout(client, payload).status_code == 200
    assert paid_webhook(client).status_code == 200
    mail.assert_not_called()
    restarted = sales.create_app(dict(client.application.config))
    restarted.drain_mail()
    restarted.drain_mail()
    assert mail.call_count == 1
    assert issue.call_count == 1
    assert 'TEST-LICENSE' in mail.call_args.kwargs['json']['text']
    with sqlite3.connect(restarted.config['SALES_DB']) as conn:
        assert conn.execute('SELECT paid,sent FROM orders').fetchone() == (1, 1)


def test_slow_background_mail_does_not_block_checkout(setup):
    client, payload, _, _, _, mail = setup
    assert checkout(client, payload).status_code == 200
    assert paid_webhook(client).status_code == 200
    entered, release = threading.Event(), threading.Event()

    def slow_mail(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return Mock()

    mail.side_effect = slow_mail
    with ThreadPoolExecutor(max_workers=2) as pool:
        worker = pool.submit(client.application.drain_mail)
        try:
            assert entered.wait(2)
            def retry_checkout():
                with client.application.test_client() as other:
                    return checkout(other, payload).status_code
            assert pool.submit(retry_checkout).result(timeout=2) == 200
        finally:
            release.set()
        worker.result(timeout=2)


def test_restart_preserves_expired_mail_and_alerts_once(setup):
    client, payload, _, _, _, mail = setup
    assert checkout(client, payload).status_code == 200
    assert paid_webhook(client).status_code == 200
    with sqlite3.connect(client.application.config['SALES_DB']) as conn:
        conn.execute('UPDATE orders SET email_started=?', (time.time() - 24 * 3600,))
    restarted = sales.create_app(dict(client.application.config))
    restarted.drain_mail()
    restarted.drain_mail()
    assert mail.call_count == 1
    assert mail.call_args.kwargs['json']['to'] == ['seller@example.com']
    assert mail.call_args.kwargs['headers']['Idempotency-Key'] == 'alert-' + payload['request_id']


def test_admin_and_background_delivery_do_not_duplicate_customer_email(setup):
    client, payload, _, _, _, mail = setup
    assert checkout(client, payload).status_code == 200
    assert paid_webhook(client).status_code == 200
    entered, release = threading.Event(), threading.Event()
    deliveries = set()

    def provider(*args, **kwargs):
        delivery_id = kwargs['headers']['Idempotency-Key']
        if delivery_id == 'license-' + payload['request_id']:
            entered.set()
            assert release.wait(5)
        deliveries.add(delivery_id)
        return Mock()

    mail.side_effect = provider
    with ThreadPoolExecutor(max_workers=1) as pool:
        worker = pool.submit(client.application.drain_mail)
        try:
            assert entered.wait(2)
            response = client.post('/api/sales/resend', json={'order_id': payload['request_id']},
                                   headers={'Authorization': 'Bearer admin-test'})
            assert response.status_code in (200, 202, 409)
        finally:
            release.set()
        worker.result(timeout=2)
    assert len(deliveries) == 1, f'Provider receives distinct delivery IDs: {deliveries}'


def test_ambiguous_send_then_manual_retry_reuses_delivery_id(setup):
    client, payload, _, _, _, mail = setup
    checkout(client, payload)
    paid_webhook(client)
    mail.side_effect = TimeoutError('Provider may have accepted the email')
    client.application.drain_mail()
    original = mail.call_args.kwargs['headers']['Idempotency-Key']
    mail.side_effect = None
    response = client.post('/api/sales/resend', json={'order_id': payload['request_id']},
                           headers={'Authorization': 'Bearer admin-test'})
    assert response.status_code == 200
    assert mail.call_args.kwargs['headers']['Idempotency-Key'] == original


def test_restart_recovers_abandoned_claim_after_expiry(setup):
    client, payload, _, _, _, mail = setup
    checkout(client, payload)
    paid_webhook(client)
    with sqlite3.connect(client.application.config['SALES_DB']) as conn:
        conn.execute('UPDATE orders SET mail_claim=?,mail_claim_until=?',
                     ('crashed-worker', time.time() + 120))
    restarted = sales.create_app(dict(client.application.config))
    restarted.drain_mail()
    mail.assert_not_called()
    with sqlite3.connect(client.application.config['SALES_DB']) as conn:
        conn.execute('UPDATE orders SET mail_claim_until=?', (time.time() - 1,))
    restarted.drain_mail()
    assert mail.call_count == 1
    with sqlite3.connect(client.application.config['SALES_DB']) as conn:
        assert conn.execute('SELECT sent,mail_claim FROM orders').fetchone() == (1, None)


def test_manual_recovery_does_not_retry_beyond_deduplication_window(setup):
    client, payload, _, _, _, mail = setup
    checkout(client, payload)
    paid_webhook(client)
    with sqlite3.connect(client.application.config['SALES_DB']) as conn:
        conn.execute('UPDATE orders SET email_started=?', (time.time() - 48 * 3600,))
    mail.side_effect = TimeoutError('Ambiguous recovery delivery')
    headers = {'Authorization': 'Bearer admin-test'}
    assert client.post('/api/sales/resend', json={'order_id': payload['request_id']},
                       headers=headers).status_code == 502
    with sqlite3.connect(client.application.config['SALES_DB']) as conn:
        conn.execute('UPDATE orders SET recovery_started=?', (time.time() - 24 * 3600,))
    mail.reset_mock()
    assert client.post('/api/sales/resend', json={'order_id': payload['request_id']},
                       headers=headers).status_code == 409
    mail.assert_not_called()
