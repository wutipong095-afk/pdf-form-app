import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sales_service as sales


@pytest.fixture
def setup(tmp_path, monkeypatch):
    app = sales.create_app({'TESTING': True, 'SALES_DB': str(tmp_path / 'orders.db'),
        'SALES_ENABLED': True, 'SALES_ORIGIN': 'https://shop.example',
        'STRIPE_SECRET_KEY': 'sk_test_fake', 'STRIPE_WEBHOOK_SECRET': 'whsec_test',
        'RESEND_API_KEY': 'fake', 'SALES_FROM': 'shop@example.com'})
    monkeypatch.setattr('license_core.load_private_key', lambda: object())
    session = SimpleNamespace(id='cs_test_order', url='https://checkout.stripe.com/test',
        payment_status='paid', mode='payment', currency='thb', amount_total=14900)
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
    return client.post('/api/sales/webhook', data=body, headers={'Stripe-Signature':f't={timestamp},v1={digest if signature else "bad"}'})


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
    assert event(client).status_code == 500
    assert event(client).status_code == 200
    assert issue.call_count == 1
    assert mail.call_args_list[0].kwargs == mail.call_args_list[1].kwargs


def test_cross_origin_rejected(setup):
    client, payload, _, create, *_ = setup
    assert client.post('/api/sales/checkout', json=payload).status_code == 403
    create.assert_not_called()


def test_stalled_delivery_stops_retrying_after_window(setup, tmp_path):
    import sqlite3
    client, payload, _, _, issue, mail = setup
    checkout(client, payload)
    mail.side_effect = RuntimeError('email provider down')
    # First delivery attempt fails -> 500 so Stripe retries; the key is issued and
    # email_started is recorded.
    assert event(client).status_code == 500
    # Backdate the retry window so the next attempt is past the 23h cutoff.
    db = sqlite3.connect(str(tmp_path / 'orders.db'))
    db.execute('UPDATE orders SET email_started = email_started - ?', (24 * 3600,))
    db.commit()
    db.close()
    mail.reset_mock()
    mail.side_effect = None
    # Now the webhook returns 200 (give up) instead of looping 500s forever, and
    # does not send again. The paid, issued key stays on the order for the seller.
    assert event(client).status_code == 200
    mail.assert_not_called()
    assert issue.call_count == 1
    row = sqlite3.connect(str(tmp_path / 'orders.db')).execute(
        'SELECT paid, sent, license FROM orders').fetchone()
    assert row[0] == 1 and row[1] == 0 and row[2]
