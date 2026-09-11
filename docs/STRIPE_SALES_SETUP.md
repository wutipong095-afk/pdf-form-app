# FormDD: Stripe checkout and automatic license email

## Architecture

`sales_service.py` is a seller-only Flask service, separate from the desktop application.
It serves the existing website for local preview and provides `/api/sales/*`.
The current Cloudflare Pages static deployment alone cannot run this Python service.
Deploy the service to a Python host and route `/api/sales/*` on the website's origin to it,
or host the website and service together behind HTTPS. Do not deploy the repository root
as public static files. Keep the existing download and update URLs intact.

## Required seller configuration

- `SALES_ENABLED=true` enables checkout. Default is disabled.
- `SALES_ORIGIN`: exact public origin, e.g. `https://formdd.xambrain.com`.
- `STRIPE_SECRET_KEY`: start with a Stripe test key.
- `STRIPE_WEBHOOK_SECRET`: secret for this endpoint and mode.
- `RESEND_API_KEY`: Resend email API key.
- `SALES_FROM`: sender on a verified Resend domain.
- `SALES_DB`: persistent SQLite database path outside the public directory.
- License signing key: use the existing `license_core` private-key configuration.
  Set `LICENSE_PRIVATE_KEY_PATH` to the seller's existing private PEM file.
  It must match the public key shipped in the customer's desktop app.
  Never create a replacement key for production without a migration plan.

Install `requirements-sales.txt` on the seller server only. Run `python sales_service.py`
for local preview at http://127.0.0.1:5080. Use a production WSGI server behind HTTPS
for production, persistent storage, backups, and edge rate limiting on checkout.
Do not package this service, payment secrets, or signing keys into the Windows installer.

## Payment and email flow

The browser sends email, 16-character machine ID, plan, and a request UUID.
Prices are selected on the server: THB 99 (1 year), 299 (lifetime of that version: bug/security fixes, no new major), 499 (lifetime + major updates for 3 years).
Stripe hosts the payment form. The success page is not proof of payment.

Configure `/api/sales/webhook` for `checkout.session.completed` and
`checkout.session.async_payment_succeeded`. The official Stripe SDK verifies the raw
payload signature. The service retrieves the Session and checks payment status,
currency, amount, and order reference before issuing a machine-bound key.
The key is saved before email delivery. Duplicate notifications reuse the key and
the Resend idempotency key; sent orders are skipped.

Resend acceptance is not proof of inbox delivery. Monitor bounces in Resend.
After an ambiguous email failure, automatic retries stop after 23 hours to avoid
retrying beyond the provider's 24-hour idempotency window. Check Resend delivery
history before manually resending the stored key. A pending webhook returns HTTP 500
so Stripe can retry. Monitor failed webhooks and reconcile orders with `paid=1,sent=0`.
Never ask the customer to pay again to recover a missing email.

## Before live launch

1. Configure test-mode Stripe, signing key, verified sender, persistent database.
2. Test successful and declined payments, cancellation, repeated webhook delivery,
   delayed confirmation, email outages, and receipt of the actual key in a test inbox.
3. Activate a test-generated key on the intended machine and check the expiry.
4. Confirm pricing, refund/privacy terms, support process, and production sender.
5. Configure live keys and the live webhook separately, then enable checkout.

No live charge or email was sent during development. Automated tests mock Stripe and
email delivery; real provider integration still requires seller credentials.

English pricing continues to use the existing quotation/email flow. Thai Stripe
plans do not replace the separate USD price list.

References: https://docs.stripe.com/checkout/fulfillment,
https://docs.stripe.com/webhooks, https://resend.com/docs/dashboard/emails/idempotency-keys
