#!/usr/bin/env python3
"""
Print a fresh Aadhaar encryption key and hash pepper (GDR-011).

    python3 scripts/generate_aadhaar_keys.py [key_id]

Nothing is written to disk. Copy the two lines into ``api/.env`` (local) or the
Render environment, and keep a copy in the organisation's secret store: a lost
key makes every stored Aadhaar ciphertext unrecoverable, and a changed pepper
orphans every stored ``aadhaar_hash``.

Rotation: generate a new key with a NEW id, put it FIRST in
AADHAAR_ENCRYPTION_KEYS and keep the previous key(s) after it (decrypt-only).
New writes use the first key; old rows stay readable. Re-encrypting old rows
is out of scope (a future script). Never reuse the pepper as a key or vice versa.
"""

import base64
import re
import secrets
import sys


def main() -> int:
    key_id = sys.argv[1] if len(sys.argv) > 1 else "k1"
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", key_id):
        print("key_id must be 1-16 characters of A-Z a-z 0-9 _ -", file=sys.stderr)
        return 2
    key = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    pepper = secrets.token_urlsafe(48)
    print(f"AADHAAR_ENCRYPTION_KEYS={key_id}:{key}")
    print(f"AADHAAR_HASH_PEPPER={pepper}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
