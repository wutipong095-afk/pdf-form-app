# FormDD: Stripe Test Mode end-to-end runbook

A concrete, do-this-in-order checklist for validating the whole purchase flow in
**Stripe test mode** before enabling live charges. It turns the "Before live
launch" bullets in [STRIPE_SALES_SETUP.md](STRIPE_SALES_SETUP.md) into steps you
can actually run. No live money or live email is involved.

Goal: **test payment → automatic email → activate the key on the target machine**,
plus the failure paths (declined, cancelled, duplicate webhook, delayed payment,
email outage).

## 0. Prerequisites

- **Stripe test keys** from the Stripe dashboard in *Test mode*: `sk_test_...`.
- **Stripe CLI** (`stripe login`) to forward webhooks to localhost:
  https://docs.stripe.com/stripe-cli
- **Resend API key** + a **verified sender domain** (a test key and a real inbox
  you control for `to:`). Resend acceptance is not inbox delivery — watch the
  Resend dashboard.
- **License signing key**: the seller's existing `ed25519` private PEM. It must
  match the public key shipped in the FormDD build you will activate against.
  Never mint a replacement key just for testing an installed app.
- A **FormDD desktop install** (or the app running locally) to read a real 16-hex
  **machine ID** and to paste the key into license settings.

## 1. Configure the seller service (test mode)

Copy the sample and fill test values (never commit real keys):

```bash
cp sales.env.example test.sales.env
```

Set in `test.sales.env`:

```
SALES_ENABLED=true
SALES_ORIGIN=http://127.0.0.1:5080
SALES_DB=data/sales/test-orders.sqlite
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=            # filled in step 2 from the Stripe CLI
RESEND_API_KEY=...
SALES_FROM=FormDD <noreply@your-verified-domain>
LICENSE_PRIVATE_KEY_PATH=keys/ed25519_private.pem
```

Install seller deps once (seller machine only): `pip install -r requirements-sales.txt`.

## 2. Forward webhooks with the Stripe CLI

In a separate terminal:

```bash
stripe listen --forward-to 127.0.0.1:5080/api/sales/webhook
```

It prints a webhook signing secret (`whsec_...`). Put that in
`STRIPE_WEBHOOK_SECRET` in `test.sales.env`. Keep this terminal running — it
relays events and lets you replay them.

## 3. Run the service

```bash
python scripts/run_sales_test.py --check   # validate test.sales.env (presence only)
python scripts/run_sales_test.py           # start the service in test mode
```

The runner loads `test.sales.env`, refuses a non-`sk_test_` key, and starts the
service on http://127.0.0.1:5080 (it also serves the `website/` pages, so the
pricing page is at http://127.0.0.1:5080/pricing.html). Confirm it is enabled:

```bash
curl -s http://127.0.0.1:5080/api/sales/config      # -> {"enabled": true}
```

If `enabled` is false, one of `SALES_ENABLED / STRIPE_SECRET_KEY /
STRIPE_WEBHOOK_SECRET / RESEND_API_KEY / SALES_FROM` is missing.

## 4. Happy path — pay, receive, activate

1. In FormDD, open license settings and copy the **16-hex machine ID**.
2. Open `http://127.0.0.1:5080/pricing.html#machine_id=<MACHINE_ID>`.
   Confirm the **Stripe form** is pre-filled with the ID (and the fragment is
   dropped from the URL). Pick a plan.
3. Click through to Stripe and pay with test card **`4242 4242 4242 4242`**, any
   future expiry, any CVC, any postcode.
4. Watch the `stripe listen` terminal: `checkout.session.completed` →
   forwarded → `200`.
5. Check the order and that the key was issued and emailed:

   ```bash
   sqlite3 data/sales/test-orders.sqlite \
     "SELECT id, plan, paid, sent, substr(license,1,16) FROM orders;"
   # expect paid=1, sent=1, a license value
   ```
6. Confirm the email arrives in the test inbox (and in the Resend dashboard) with
   the activation key.
7. Paste the key into FormDD license settings. Confirm it **activates** and the
   **expiry matches the plan** (1/3/5/10 years). Confirm the same key is
   **rejected on a different machine** (machine-bound).

## 5. Failure and edge paths (must all pass)

- **Declined card** `4000 0000 0000 0002`: no order becomes `paid`, no email.
- **Requires authentication** `4000 0025 0000 3155`: complete the 3DS prompt →
  fulfils like the happy path.
- **Cancellation**: cancel on the Stripe page → returns to
  `pricing.html?payment=cancelled#purchase`; no key issued.
- **Duplicate webhook**: replay the event and confirm **one** email / one key:

  ```bash
  stripe events resend <evt_id>        # or trigger checkout.session.completed
  # expect sent stays 1, no second email (Resend idempotency key)
  ```
- **Delayed payment** (PromptPay, if enabled on the account): the success page
  shows "waiting"; fulfilment happens on
  `checkout.session.async_payment_succeeded`.
- **Email outage**: temporarily set a bad `RESEND_API_KEY`, pay once → webhook
  returns `500` and Stripe retries; the key is already stored (`paid=1, sent=0`).
  Restore the key → next retry sends. Confirm the key/email are unchanged
  (same Resend idempotency key). After 23 h the service stops retrying and logs
  a manual-reconcile line instead of looping `500`s.
- **Tamper checks**: these are covered by `tests/test_sales_service.py`
  (amount/currency/reference mismatch never issues a key; forged webhook → 400).

## 6. Go-live (separate, deliberate step)

Only after every case above passes:

1. Swap to **live** `sk_live_...` and a **live** webhook endpoint + its own
   `whsec_...` (configured in the Stripe dashboard, not the CLI).
2. Point `SALES_ORIGIN` at the real HTTPS origin; confirm the verified live
   sender domain.
3. Behind a production WSGI server + HTTPS, persistent DB with backups, and edge
   rate limiting on `/api/sales/checkout`.
4. Do **one** real low-risk purchase end to end, then open checkout to customers.

Never bundle `sales_service.py`, payment secrets, or the signing key into the
Windows installer. Never ask a customer to pay again to recover a missing email —
resend the stored key.
