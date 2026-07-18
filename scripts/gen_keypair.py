"""สร้างคู่กุญแจ Ed25519 สำหรับไลเซนต์ (รันครั้งเดียวฝั่งผู้ขาย)
เคารพ LICENSE_PRIVATE_KEY_PATH / LICENSE_PUBLIC_KEY_PATH เหมือนฝั่งอ่าน
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from envutil import load_dotenv  # noqa: E402

load_dotenv()

from license_core import private_key_path, public_key_path  # noqa: E402


def main() -> None:
    priv_path = private_key_path()
    pub_path = public_key_path()
    if priv_path.exists() and "--force" not in sys.argv:
        print(
            f"มี {priv_path} อยู่แล้ว — ใส่ --force ถ้าต้องการสร้างใหม่ (คีย์เก่าจะใช้ไม่ได้)",
            file=sys.stderr,
        )
        sys.exit(1)
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(
        priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    try:
        os.chmod(priv_path, 0o600)
    except OSError:
        pass
    pub_path.parent.mkdir(parents=True, exist_ok=True)
    pub_path.write_bytes(
        pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print("wrote", priv_path)
    print("wrote", pub_path)
    print("สำรอง private key ให้ปลอดภัย — อย่าใส่ใน image ลูกค้า")


if __name__ == "__main__":
    main()
