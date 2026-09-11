"""Local Stripe *test mode* runner for sales_service.

Loads `test.sales.env` (never committed) and starts the seller service on
http://127.0.0.1:5080 for end-to-end testing with the Stripe CLI. Test mode only —
this helper refuses a live Stripe secret key so it can never touch real money.

Usage (from the repo root):
    python scripts/run_sales_test.py --check   # validate config, print readiness, exit
    python scripts/run_sales_test.py           # validate, then run the service

It prints only whether each value is set, never the values themselves.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from envutil import load_dotenv  # noqa: E402

ENV_FILE = ROOT / "test.sales.env"
HOST, PORT = "127.0.0.1", 5080
EXPECTED_ORIGIN = f"http://{HOST}:{PORT}"

# Needed for ready() to enable checkout. STRIPE_WEBHOOK_SECRET is filled from
# `stripe listen` after this starts, so it is allowed to be empty at --check time.
REQUIRED = ["SALES_ENABLED", "STRIPE_SECRET_KEY", "RESEND_API_KEY", "SALES_FROM"]
RUNTIME = ["STRIPE_WEBHOOK_SECRET"]


def _signing_key_matches() -> bool | None:
    """True/False if the private key matches the shipped public key; None if missing."""
    try:
        from cryptography.hazmat.primitives import serialization

        priv_path = Path(os.environ.get("LICENSE_PRIVATE_KEY_PATH", ROOT / "keys/ed25519_private.pem"))
        pub_path = ROOT / "license_public.pem"
        if not priv_path.exists() or not pub_path.exists():
            return None
        priv = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
        pub = serialization.load_pem_public_key(pub_path.read_bytes())
        raw = serialization.Encoding.Raw, serialization.PublicFormat.Raw
        return priv.public_key().public_bytes(*raw) == pub.public_bytes(*raw)
    except Exception:
        return None


def preflight() -> bool:
    print(f"config file: {ENV_FILE.name} {'found' if ENV_FILE.exists() else 'MISSING (copy sales.env.example)'}")
    ok = True
    for name in REQUIRED:
        present = bool(os.environ.get(name, "").strip())
        print(f"  {name}: {'set' if present else 'MISSING'}")
        ok = ok and present
    for name in RUNTIME:
        present = bool(os.environ.get(name, "").strip())
        print(f"  {name}: {'set' if present else 'empty (fill from `stripe listen`)'}")

    secret = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if secret and not secret.startswith("sk_test_"):
        print("  STRIPE_SECRET_KEY: NOT a test key (must start with sk_test_) - refusing")
        ok = False

    origin = os.environ.get("SALES_ORIGIN", "").strip()
    if origin != EXPECTED_ORIGIN:
        print(f"  SALES_ORIGIN: '{origin or '(unset)'}' - for local testing set {EXPECTED_ORIGIN}")
        ok = False

    match = _signing_key_matches()
    print(f"  signing key matches shipped license_public.pem: "
          f"{'yes' if match else 'NO - issued keys will not activate' if match is False else 'unknown (key file missing)'}")
    ok = ok and match is True
    return ok


def main() -> None:
    load_dotenv(ENV_FILE)
    check_only = "--check" in sys.argv
    ready = preflight()
    if check_only:
        print("\nreadiness:", "OK — ready to run" if ready else "incomplete (see above)")
        sys.exit(0 if ready else 1)
    if not ready:
        print("\nRefusing to start: config incomplete. Run with --check for details.", file=sys.stderr)
        sys.exit(1)
    import sales_service

    print(f"\nStarting seller service (TEST MODE) on {EXPECTED_ORIGIN}")
    print("In another terminal: stripe listen --forward-to 127.0.0.1:5080/api/sales/webhook")
    sales_service.create_app().run(host=HOST, port=PORT, debug=False)


if __name__ == "__main__":
    main()
