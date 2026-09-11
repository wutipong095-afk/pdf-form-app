# FormDD Stripe Test Mode — E2E test results

Results log for validating the FormDD purchase flow (system from PR #38) in
**Stripe Test Mode**, following the runbook in
[STRIPE_TEST_MODE.md](STRIPE_TEST_MODE.md). No secrets appear in this file.

- **Branch:** `test/stripe-test-mode-e2e`
- **Commit under test:** `7638631` (branched from `master` `041ef95`, which contains
  the merged sales service, PR #38)
- **Run date (UTC):** 2026-09-11
- **Tester environment:** Windows, Stripe CLI `1.50.10` present, stripe SDK `14.1.0`,
  requests `2.32.3`.

## Status summary

| Layer | Method | Result |
|---|---|---|
| License issue/verify/expiry/machine-binding/tamper | **Real crypto**, throwaway test keypair | ✅ Pass |
| Checkout validation, webhook signature, mismatch, duplicate, delayed payment, email-failure retry, no-lock-across-Stripe, 23 h stop | **Mock** (Stripe + Resend mocked) | ✅ 14/14 pass |
| Web checkout → real Stripe test card → real webhook → real email → activation in app | **Real E2E in test mode** | ⛔ **Not run — blocked on credentials** (see below) |

**Go-live verdict: NOT ready to accept real payments.** The application logic and
the license-signing layer are verified, but the real end-to-end path in Stripe
Test Mode (real Stripe checkout, real webhook delivery, real email inbox, and key
activation in the app) has **not** been executed because the required test
credentials are not available to the tester. Do not enable live charges until
section C is completed on real test-mode services.

---

## A. License layer — REAL crypto (throwaway test keypair)

Uses `license_core` directly with a **throwaway Ed25519 keypair generated in a
scratch directory** — NOT the production signing key, and no key material or full
activatable key is printed. This exercises the real signing/verification code, so
it is not a mock; it simply does not use the shipped key.

| Case | Expected | Actual |
|---|---|---|
| Issue plan 1 y | expiry today+365, valid sig, machine match | expires today+365, sig OK, match OK |
| Issue plan 3 y | expiry today+1095 | expires today+1095, OK |
| Issue plan 5 y | expiry today+1825 | expires today+1825, OK |
| Issue plan 10 y | expiry today+3650 | expires today+3650, OK |
| Verify with a different machine ID | rejected (wrong machine) | rejected ✅ |
| Verify a key with one signature char flipped | rejected (bad signature) | rejected ✅ |

Evidence: verification returned `sig OK / machine match OK` and the expected
`expires`/`days_left` for every plan; mismatched-machine and tampered-signature
keys both raised a validation error. (Key strings withheld.)

**Note on the real signing key:** `license_public.pem` is committed (shipped in the
app) and the seller's private PEM is present locally but never read or printed by
this test. Activating a key produced by the *real* key on a *real* FormDD build is
part of section C.

## B. Application logic — MOCK (Stripe and Resend mocked)

`tests/test_sales_service.py`, 14 tests, all pass. **These mock the Stripe SDK and
the Resend HTTP call — they are unit/logic tests, not real E2E.** Mapping to scope:

| Scope item | Test(s) | Result |
|---|---|---|
| Input validation (machine/plan/email/request id) | `test_invalid_input_rejected` (4 cases) | ✅ |
| Cross-origin checkout blocked | `test_cross_origin_rejected` | ✅ |
| Forged webhook signature rejected | `test_forged_webhook_rejected` | ✅ |
| Amount / currency / reference mismatch never issues a key | `test_mismatched_payment_never_issues` (3 cases) | ✅ |
| Duplicate webhook → one key, one email | `test_paid_and_duplicate_events_send_once` | ✅ |
| Delayed payment (async_payment_succeeded) | `test_unpaid_then_paid` | ✅ |
| Email failure → retry reuses same key + delivery id (no duplicate key, no expiry change) | `test_email_failure_reuses_key_and_delivery_id` | ✅ |
| No DB write-lock held across the Stripe call | `test_checkout_holds_no_db_lock_during_stripe_call` | ✅ |
| Retry window (23 h) stops instead of looping 500s; key stays paid/unsent | `test_stalled_delivery_stops_retrying_after_window` | ✅ |

Not covered by unit tests (inherently browser/real, belongs in section C):
**payment cancellation** (Stripe-hosted redirect to `cancel_url`) and truly
**concurrent live webhook deliveries** (idempotency is guarded by `BEGIN IMMEDIATE`
+ the `sent` flag + Resend idempotency key, and is exercised by the duplicate and
lock tests, but not against the live Stripe event stream).

## C. Real E2E in Stripe Test Mode — PENDING (blocked)

Not executed. Requires credentials/permissions the tester does not have. Needed to
proceed (test mode only; **do not paste secrets into chat — place them in a local,
untracked `test.sales.env`** and confirm here that it is set):

1. **Stripe test secret key** `sk_test_...` in `test.sales.env`.
2. **Stripe CLI authenticated** to your test account (`stripe login`) so
   `stripe listen --forward-to 127.0.0.1:5080/api/sales/webhook` can supply the
   `whsec_...` webhook secret.
3. **Resend API key** + a **verified sender domain** for `SALES_FROM`.
4. **A test recipient email you own and confirm here** (the `to:` address). Per the
   task, test email must go only to an address you specify — never a real customer.
5. **License signing:** confirm `LICENSE_PRIVATE_KEY_PATH` points at the seller PEM
   whose public half is the shipped `license_public.pem` (for activation in a real
   build), or provide a dev build that trusts a test public key.
6. **A FormDD build/machine** to paste the key into (with its current license state
   backed up first, restored after — per scope #4).

Once these are in place, run the section-4/5 steps in
[STRIPE_TEST_MODE.md](STRIPE_TEST_MODE.md) and record here: order id, plan, amount,
machine id match, webhook event ids, Resend delivery id, key expiry, and the
activation result — without exposing secrets or full activatable keys.

## D. PR #31 dependency check

PR #31 ("Move the four GitHub-provided actions off the Node 20 runtime") changes
only `.github/workflows/ci.yml` and `.github/workflows/release.yml`. It is a CI
runner change and **not a dependency** of this local, Stripe-CLI-based E2E test.
Proceeding without it.

## E. Limitations / open items

- Real Stripe/email/activation E2E (section C) is outstanding and is the gate for
  accepting real money.
- Local full-suite `pytest` on this Windows box hits a `pytest_asyncio` + default
  temp-dir permission issue unrelated to this code; the sales suite passes when run
  directly (`pytest tests/test_sales_service.py`). CI (Linux) is unaffected.
- No live charge, live webhook, or customer email was created during this work.
