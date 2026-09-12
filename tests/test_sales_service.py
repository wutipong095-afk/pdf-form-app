import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sales_service as sales


def test_concurrent_startup_migrates_legacy_database_once(tmp_path, monkeypatch):
    import sqlite3
    import threading
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / 'legacy.db'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE orders (id TEXT PRIMARY KEY)')
        conn.execute("INSERT INTO orders VALUES ('existing-order')")
    conn.close()
    original_connect = sqlite3.connect
    inspected = threading.Barrier(2)

    class MigrationConnection(sqlite3.Connection):
        def execute(self, sql, *args):
            cursor = super().execute(sql, *args)
            if sql == 'PRAGMA table_info(orders)':
                rows = cursor.fetchall()
                if 'product' not in {row[1] for row in rows}:
                    # Without the migration lock, both workers read the old schema.
                    # With it, the first proceeds after the bounded wait while the
                    # second cannot inspect until the first has committed.
                    try:
                        inspected.wait(timeout=0.5)
                    except threading.BrokenBarrierError:
                        pass
                return rows
            return cursor

    monkeypatch.setattr(sales.sqlite3, 'connect',
                        lambda *a, **kw: original_connect(*a, **kw, factory=MigrationConnection))
    with ThreadPoolExecutor(max_workers=2) as pool:
        workers = [pool.submit(sales.create_app, {'TESTING': True, 'SALES_DB': str(path)})
                   for _ in range(2)]
        for worker in workers:
            assert worker.result(timeout=10) is not None
    with original_connect(path) as conn:
        columns = [row[1] for row in conn.execute('PRAGMA table_info(orders)')]
        assert columns.count('product') == 1
        assert columns.count('alerted') == 1
        assert conn.execute('SELECT id FROM orders').fetchone()[0] == 'existing-order'
    conn.close()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(sales, 'signing_keys_match', lambda: True)
    app = sales.create_app({'TESTING': True, 'SALES_DB': str(tmp_path / 'orders.db'),
        'SALES_ENABLED': True, 'SALES_ORIGIN': 'https://shop.example',
        'STRIPE_SECRET_KEY': 'sk_test_fake', 'STRIPE_WEBHOOK_SECRET': 'whsec_test',
        'RESEND_API_KEY': 'fake', 'SALES_FROM': 'shop@example.com',
        'SALES_ALERT_TO': 'seller@example.com', 'SALES_ADMIN_TOKEN': 'admin-test'})
    monkeypatch.setattr('license_core.load_private_key', lambda: object())
    session = SimpleNamespace(id='cs_test_order', url='https://checkout.stripe.com/test',
        payment_status='paid', mode='payment', currency='thb', amount_total=9900)
    create = Mock(return_value=session)
    monkeypatch.setattr(sales.stripe.checkout.Session, 'create', create)
    monkeypatch.setattr(sales.stripe.checkout.Session, 'retrieve', Mock(return_value=session))
    issue = Mock(return_value='TEST-LICENSE')
    monkeypatch.setattr(sales, 'issue_license_key', issue)
    mail = Mock(return_value=Mock())
    monkeypatch.setattr(sales.requests, 'post', mail)
    client = app.test_client()
    payload = dict(machine_id='0123456789ABCDEF', email='buyer@example.com', plan='1', request_id=str(uuid.uuid4()))
    session.client_reference_id = payload['request_id']
    return client, payload, session, create, issue, mail


def checkout(client, payload):
    return client.post('/api/sales/checkout', json=payload, headers={'Origin':'https://shop.example'})


def event(client, kind='checkout.session.completed', signature=True):
    body = json.dumps({'id':'evt_test', 'type':kind, 'data':{'object':{'id':'cs_test_order'}}}).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(b'whsec_test', timestamp.encode()+b'.'+body, hashlib.sha256).hexdigest()
    response = client.post('/api/sales/webhook', data=body, headers={'Stripe-Signature':f't={timestamp},v1={digest if signature else "bad"}'})
    if response.status_code == 200:
        try:
            client.application.drain_mail()
        except Exception:
            pass
    return response


def test_paid_and_duplicate_events_send_once(setup):
    client, payload, session, create, issue, mail = setup
    assert checkout(client, payload).status_code == 200
    assert checkout(client, payload).status_code == 200
    assert create.call_count == 1
    assert event(client).status_code == 200
    assert event(client, 'checkout.session.async_payment_succeeded').status_code == 200
    issue.assert_called_once_with(payload['machine_id'], days=365)
    assert mail.call_count == 1
    assert mail.call_args.kwargs['json']['to'] == [payload['email']]


@pytest.mark.parametrize('change', [{'machine_id':'bad'}, {'plan':'0'}, {'email':'a\r\nb@example.com'}, {'request_id':'bad'}])
def test_invalid_input_rejected(setup, change):
    client, payload, _, create, *_ = setup
    assert checkout(client, payload | change).status_code == 400
    create.assert_not_called()


def test_forged_webhook_rejected(setup):
    client, payload, _, _, issue, mail = setup
    checkout(client, payload)
    assert event(client, signature=False).status_code == 400
    issue.assert_not_called(); mail.assert_not_called()


@pytest.mark.parametrize('property,value', [('amount_total',1), ('currency','usd'), ('client_reference_id','another')])
def test_mismatched_payment_never_issues(setup, property, value):
    client, payload, session, _, issue, mail = setup
    checkout(client, payload); setattr(session, property, value)
    assert event(client).status_code == 500
    issue.assert_not_called(); mail.assert_not_called()


def test_unpaid_then_paid(setup):
    client, payload, session, _, issue, mail = setup
    checkout(client, payload); session.payment_status = 'unpaid'
    assert event(client).status_code == 200
    issue.assert_not_called()
    session.payment_status = 'paid'
    assert event(client, 'checkout.session.async_payment_succeeded').status_code == 200
    assert mail.call_count == 1


def test_email_failure_reuses_key_and_delivery_id(setup):
    client, payload, _, _, issue, mail = setup
    checkout(client, payload)
    mail.side_effect = [RuntimeError('timeout'), Mock()]
    assert event(client).status_code == 200
    assert event(client).status_code == 200
    assert issue.call_count == 1
    assert mail.call_args_list[0].kwargs == mail.call_args_list[1].kwargs


def test_cross_origin_rejected(setup):
    client, payload, _, create, *_ = setup
    assert client.post('/api/sales/checkout', json=payload).status_code == 403
    create.assert_not_called()


def test_bad_license_private_key_env_does_not_block_boot(tmp_path, monkeypatch):
    monkeypatch.setenv('LICENSE_PRIVATE_KEY', 'keys/ed25519_private.pem')
    app = sales.create_app({'TESTING': True, 'SALES_DB': str(tmp_path / 'orders.db'),
        'SALES_ENABLED': False, 'SALES_ORIGIN': 'https://shop.example'})
    client = app.test_client()
    assert client.get('/api/sales/config').get_json() == {'enabled': False}


def test_sales_origin_can_call_from_the_website(setup):
    client, *_ = setup
    config = client.get('/api/sales/config', headers={'Origin': 'https://shop.example'})
    assert config.status_code == 200
    assert config.headers['Access-Control-Allow-Origin'] == 'https://shop.example'
    preflight = client.open('/api/sales/checkout', method='OPTIONS',
                            headers={'Origin': 'https://shop.example'})
    assert preflight.status_code == 204
    assert preflight.headers['Access-Control-Allow-Origin'] == 'https://shop.example'


def test_checkout_holds_no_db_lock_during_stripe_call(setup, tmp_path):
    import sqlite3
    client, payload, session, create, *_ = setup
    db_path = str(tmp_path / 'orders.db')
    probe = {}

    def slow_stripe(*args, **kwargs):
        # While Stripe is "slow", another connection must still be able to write.
        # A short busy timeout makes a held lock fail fast instead of hanging.
        other = sqlite3.connect(db_path, timeout=0.5)
        try:
            other.execute('BEGIN IMMEDIATE')
            other.execute('UPDATE orders SET amount=amount WHERE id=?', (payload['request_id'],))
            other.commit()
            probe['ok'] = True
        except sqlite3.OperationalError as exc:
            probe['ok'] = False
            probe['error'] = str(exc)
        finally:
            other.close()
        return session

    create.side_effect = slow_stripe
    assert checkout(client, payload).status_code == 200
    assert probe.get('ok') is True, probe


def test_stalled_delivery_stops_retrying_after_window(setup, tmp_path):
    import sqlite3
    client, payload, _, _, issue, mail = setup
    checkout(client, payload)
    mail.side_effect = RuntimeError('email provider down')
    # Payment is persisted and Stripe gets 200; email is a later job.
    assert event(client).status_code == 200
    # Backdate the retry window so the next drain is past the 23h cutoff.
    db = sqlite3.connect(str(tmp_path / 'orders.db'))
    db.execute('UPDATE orders SET email_started = email_started - ?', (24 * 3600,))
    db.commit()
    db.close()
    mail.reset_mock()
    mail.side_effect = None
    # Customer email is not retried with the expired idempotency key. The seller
    # is alerted instead; the paid key stays on the order for a manual resend.
    assert event(client).status_code == 200
    assert mail.call_count == 1
    assert mail.call_args.kwargs['headers']['Idempotency-Key'] == 'alert-' + payload['request_id']
    assert mail.call_args.kwargs['json']['to'] == ['seller@example.com']
    assert issue.call_count == 1
    row = sqlite3.connect(str(tmp_path / 'orders.db')).execute(
        'SELECT paid, sent, license, alerted FROM orders').fetchone()
    assert row[0] == 1 and row[1] == 0 and row[2] and row[3] == 1


@pytest.mark.parametrize('plan', ['lt', 'lt3'])
def test_lifetime_plans_charge_and_issue_lifetime_days(setup, plan):
    client, payload, session, create, issue, mail = setup
    spec = sales.PLANS[plan]
    session.amount_total = spec['amount']
    body = payload | {'plan': plan}
    assert checkout(client, body).status_code == 200
    assert create.call_args.kwargs['line_items'][0]['price_data']['unit_amount'] == spec['amount']
    assert event(client).status_code == 200
    issue.assert_called_once_with(body['machine_id'], days=spec['days'])
    assert mail.call_count == 1


def test_retired_plan_cannot_start_checkout(setup):
    client, payload, _, create, *_ = setup
    assert checkout(client, payload | {'plan': '3'}).status_code == 400
    create.assert_not_called()


def test_retired_plan_still_fulfills_after_delist(setup, tmp_path):
    import sqlite3
    client, payload, session, _, issue, mail = setup
    spec = sales.LEGACY_PLANS['3']
    session.amount_total = spec['amount']
    db = sqlite3.connect(tmp_path / 'orders.db')
    db.execute(
        'INSERT INTO orders(id,machine,email,plan,amount,session) VALUES(?,?,?,?,?,?)',
        (payload['request_id'], payload['machine_id'], payload['email'], '3', spec['amount'], session.id))
    db.commit()
    db.close()
    assert event(client).status_code == 200
    issue.assert_called_once_with(payload['machine_id'], days=spec['days'])
    assert mail.call_count == 1
    assert spec['label'] in mail.call_args.kwargs['json']['text']


def test_stale_catalog_price_without_snapshot_requires_new_request(setup, tmp_path):
    import sqlite3
    client, payload, _, create, *_ = setup
    db = sqlite3.connect(tmp_path / 'orders.db')
    db.execute(
        'INSERT INTO orders(id,machine,email,plan,amount) VALUES(?,?,?,?,?)',
        (payload['request_id'], payload['machine_id'], payload['email'], '1', 14900))
    db.commit()
    db.close()
    response = checkout(client, payload)
    assert response.status_code == 409
    create.assert_not_called()
    amount = sqlite3.connect(tmp_path / 'orders.db').execute('SELECT amount FROM orders').fetchone()[0]
    assert amount == 14900


def test_existing_session_is_not_repriced(setup, tmp_path):
    import sqlite3
    client, payload, session, create, issue, mail = setup
    session.amount_total = 14900
    db = sqlite3.connect(tmp_path / 'orders.db')
    db.execute(
        'INSERT INTO orders(id,machine,email,plan,amount,session) VALUES(?,?,?,?,?,?)',
        (payload['request_id'], payload['machine_id'], payload['email'], '1', 14900, session.id))
    db.commit()
    db.close()
    assert checkout(client, payload).status_code == 200
    create.assert_not_called()
    amount = sqlite3.connect(tmp_path / 'orders.db').execute('SELECT amount FROM orders').fetchone()[0]
    assert amount == 14900
    assert event(client).status_code == 200
    issue.assert_called_once_with(payload['machine_id'], days=365)
    assert mail.call_count == 1


def test_stale_price_with_snapshot_charges_snapshot_not_new_price(setup, tmp_path):
    # Reviewer #2, exact repro: a 1-year order frozen at the OLD 149 THB price with
    # a product snapshot but no Stripe session yet, retried after the catalog dropped
    # to 99. The retry must build the Session at the stored 149 (so the paid amount
    # matches on the webhook), never the new 99 — otherwise the customer pays but the
    # webhook rejects with "Payment mismatch" and no key is issued.
    import sqlite3
    client, payload, session, create, issue, mail = setup
    old_amount = 14900
    session.amount_total = old_amount
    db = sqlite3.connect(tmp_path / 'orders.db')
    db.execute(
        'INSERT INTO orders(id,machine,email,plan,amount,product) VALUES(?,?,?,?,?,?)',
        (payload['request_id'], payload['machine_id'], payload['email'], '1', old_amount, 'FormDD 1 ปี / 1 เครื่อง'))
    db.commit()
    db.close()
    assert sales.PLANS['1']['amount'] == 9900  # catalog has since dropped
    assert checkout(client, payload).status_code == 200
    assert create.call_args.kwargs['line_items'][0]['price_data']['unit_amount'] == old_amount
    assert event(client).status_code == 200
    issue.assert_called_once_with(payload['machine_id'], days=365)
    assert mail.call_count == 1


def test_retry_keeps_params_if_stripe_created_but_session_not_saved(setup, tmp_path):
    import sqlite3
    client, payload, session, create, issue, mail = setup
    spec = sales.PLANS['1']
    session.amount_total = spec['amount']
    db = sqlite3.connect(tmp_path / 'orders.db')
    db.execute(
        'INSERT INTO orders(id,machine,email,plan,amount,product) VALUES(?,?,?,?,?,?)',
        (payload['request_id'], payload['machine_id'], payload['email'], '1', spec['amount'], spec['product']))
    db.execute(
        'CREATE TRIGGER deny_session_write BEFORE UPDATE OF session ON orders '
        "BEGIN SELECT RAISE(FAIL, 'lost write after stripe create'); END")
    db.commit()
    db.close()

    assert checkout(client, payload).status_code == 502
    row = sqlite3.connect(tmp_path / 'orders.db').execute(
        'SELECT amount, session, product FROM orders').fetchone()
    assert row[0] == spec['amount'] and row[1] is None and row[2] == spec['product']

    db = sqlite3.connect(tmp_path / 'orders.db')
    db.execute('DROP TRIGGER deny_session_write')
    db.commit()
    db.close()

    assert checkout(client, payload).status_code == 200
    assert create.call_count == 2
    keys = [call.kwargs['idempotency_key'] for call in create.call_args_list]
    amounts = [call.kwargs['line_items'][0]['price_data']['unit_amount'] for call in create.call_args_list]
    names = [call.kwargs['line_items'][0]['price_data']['product_data']['name'] for call in create.call_args_list]
    assert keys[0] == keys[1] == 'checkout-' + payload['request_id']
    assert amounts == [spec['amount'], spec['amount']]
    assert names == [spec['product'], spec['product']]
    assert event(client).status_code == 200
    issue.assert_called_once_with(payload['machine_id'], days=spec['days'])
    assert mail.call_count == 1


def _write_ed25519_pair(tmp_path, matching=True):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

    private = Ed25519PrivateKey.generate()
    public = private.public_key() if matching else Ed25519PrivateKey.generate().public_key()
    priv_pem = tmp_path / 'priv.pem'
    pub_pem = tmp_path / 'pub.pem'
    priv_pem.write_bytes(private.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    pub_pem.write_bytes(public.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
    return priv_pem, pub_pem


def test_signing_keys_match_uses_ephemeral_pair(tmp_path, monkeypatch):
    from license_core import load_public_key

    try:
        priv_pem, pub_pem = _write_ed25519_pair(tmp_path, matching=True)
        monkeypatch.setenv('LICENSE_PRIVATE_KEY_PATH', str(priv_pem))
        monkeypatch.setenv('LICENSE_PUBLIC_KEY_PATH', str(pub_pem))
        load_public_key.cache_clear()
        assert sales.signing_keys_match() is True

        other = tmp_path / 'other'
        other.mkdir()
        _, other_pub = _write_ed25519_pair(other, matching=False)
        monkeypatch.setenv('LICENSE_PUBLIC_KEY_PATH', str(other_pub))
        load_public_key.cache_clear()
        assert sales.signing_keys_match() is False
    finally:
        load_public_key.cache_clear()


def test_mismatched_signing_keys_disable_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(sales, 'signing_keys_match', lambda: False)
    app = sales.create_app({'TESTING': True, 'SALES_DB': str(tmp_path / 'orders.db'),
        'SALES_ENABLED': True, 'SALES_ORIGIN': 'https://shop.example',
        'STRIPE_SECRET_KEY': 'sk_test_fake', 'STRIPE_WEBHOOK_SECRET': 'whsec_test',
        'RESEND_API_KEY': 'fake', 'SALES_FROM': 'shop@example.com'})
    client = app.test_client()
    assert client.get('/api/sales/config').get_json() == {'enabled': False}
    payload = dict(machine_id='0123456789ABCDEF', email='buyer@example.com',
                   plan='1', request_id=str(uuid.uuid4()))
    assert checkout(client, payload).status_code == 503


def test_admin_lists_unsent_and_resends_after_window(setup, tmp_path):
    import sqlite3
    client, payload, _, _, _, mail = setup
    checkout(client, payload)
    mail.side_effect = RuntimeError('email provider down')
    assert event(client).status_code == 200
    db = sqlite3.connect(str(tmp_path / 'orders.db'))
    db.execute('UPDATE orders SET email_started = email_started - ?', (24 * 3600,))
    db.commit()
    db.close()
    mail.reset_mock()
    mail.side_effect = None
    assert event(client).status_code == 200

    hidden = client.get('/api/sales/unsent')
    assert hidden.status_code == 404
    listed = client.get('/api/sales/unsent', headers={'Authorization': 'Bearer admin-test'})
    assert listed.status_code == 200
    orders = listed.get_json()['orders']
    assert len(orders) == 1
    assert orders[0]['id'] == payload['request_id']
    assert orders[0]['sent'] == 0 and orders[0]['alerted'] == 1
    assert 'license' not in orders[0]

    mail.reset_mock()
    resent = client.post('/api/sales/resend', json={'order_id': payload['request_id']},
                         headers={'Authorization': 'Bearer admin-test'})
    assert resent.status_code == 200
    assert mail.call_args.kwargs['headers']['Idempotency-Key'] == 'license-resend-' + payload['request_id']
    assert mail.call_args.kwargs['json']['to'] == [payload['email']]
    already = client.post('/api/sales/resend', json={'order_id': payload['request_id']},
                          headers={'Authorization': 'Bearer admin-test'})
    assert already.get_json() == {'ok': True, 'already': True}


def test_empty_admin_token_hides_recovery_routes(tmp_path, monkeypatch):
    monkeypatch.setattr(sales, 'signing_keys_match', lambda: True)
    app = sales.create_app({'TESTING': True, 'SALES_DB': str(tmp_path / 'orders.db'),
        'SALES_ENABLED': True, 'SALES_ORIGIN': 'https://shop.example',
        'STRIPE_SECRET_KEY': 'sk_test_fake', 'STRIPE_WEBHOOK_SECRET': 'whsec_test',
        'RESEND_API_KEY': 'fake', 'SALES_FROM': 'shop@example.com',
        'SALES_ADMIN_TOKEN': ''})
    client = app.test_client()
    assert client.get('/api/sales/unsent', headers={'Authorization': 'Bearer anything'}).status_code == 404
    assert client.post('/api/sales/resend', json={'order_id': 'x'},
                       headers={'Authorization': 'Bearer anything'}).status_code == 404
