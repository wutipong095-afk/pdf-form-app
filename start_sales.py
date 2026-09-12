"""Start the seller checkout app. Used by Dockerfile.sales so boot errors show in Railway logs."""
from __future__ import annotations

import os
import sys
import traceback

port = int(os.environ.get("PORT") or "8080")
print(f"sales listening on 0.0.0.0:{port}", flush=True)
try:
    from sales_service import create_app
    app = create_app()
except Exception:
    traceback.print_exc()
    sys.exit(1)
