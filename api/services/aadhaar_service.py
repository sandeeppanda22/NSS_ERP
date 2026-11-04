"""
NSS ERP — Aadhaar service (GDR-011, status Proposed).

The ONE place that normalises, validates, encrypts, decrypts, hashes and masks
an Aadhaar number, and the ONE writer of the three ``nss.person`` Aadhaar
columns (``set_person_aadhaar``). Routers/helpers never touch the columns or
the crypto directly.

Scheme
------
* ``aadhaar_encrypted`` (BYTEA) — the UTF-8 bytes of a versioned blob
  ``v1:<key_id>:<b64 nonce>:<b64 ciphertext+tag>``. AES-256-GCM, a fresh random
  96-bit nonce per encryption, associated data = the person_pk string (a blob
  copied onto another person's row fails authentication).
* ``aadhaar_hash`` (VARCHAR 64) — HMAC-SHA256 hex digest of the 12 digits keyed
  with ``AADHAAR_HASH_PEPPER`` (a secret SEPARATE from the encryption keys);
  backs the existing ``uq_person_aadhaar_hash`` unique index. Never returned.
* ``aadhaar_last4`` — derived from the digits, never supplied by a client.

Keys (``api/config.py``): ``AADHAAR_ENCRYPTION_KEYS`` = ``key_id:base64(32
bytes)`` pairs, comma separated; the FIRST encrypts, the rest only decrypt (key
rotation). Without keys/pepper the app still starts; capturing a full number
raises HTTP 503 (never a silent last-4-only fall-back).

``cryptography`` is imported lazily so a missing wheel degrades to the same 503
instead of stopping the whole API.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import os
import re

from fastapi import HTTPException, status

from api.config import settings

logger = logging.getLogger("nss.aadhaar")

BLOB_VERSION = "v1"
KEY_BYTES = 32
NONCE_BYTES = 12
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")

CONFIG_503 = (
    "Aadhaar capture is not available: encryption keys are not configured on "
    "the server. Contact the system administrator."
)
MALFORMED_MESSAGE = (
    "Aadhaar number must be exactly 12 digits (spaces or hyphens allowed), "
    "must not start with 0 or 1 and must pass the Verhoeff checksum."
)


class AadhaarFormatError(ValueError):
    """The supplied value is not a valid Aadhaar number."""


class AadhaarConfigError(RuntimeError):
    """Keys/pepper (or the cryptography library) are missing or malformed."""


class AadhaarDecryptionError(RuntimeError):
    """Stored ciphertext could not be authenticated/decrypted (never carries a value)."""


# ── Verhoeff checksum ───────────────────────────────────────────────────

_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def verhoeff_valid(digits: str) -> bool:
    """True when *digits* (all decimal digits, check digit last) passes Verhoeff."""
    if not digits or not digits.isascii() or not digits.isdigit():
        return False
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


# ── Normalise / validate / mask ─────────────────────────────────────────

def normalise_aadhaar(raw: str) -> str:
    """
    Return the 12 plain digits of *raw* (spaces and hyphens stripped).

    Raises AadhaarFormatError unless the result is exactly 12 ASCII digits,
    does not start with 0 or 1, and passes the Verhoeff checksum.
    """
    if not isinstance(raw, str):
        raise AadhaarFormatError(MALFORMED_MESSAGE)
    digits = re.sub(r"[\s-]", "", raw)
    if (
        len(digits) != 12
        or not digits.isascii()
        or not digits.isdigit()
        or digits[0] in "01"
        or not verhoeff_valid(digits)
    ):
        raise AadhaarFormatError(MALFORMED_MESSAGE)
    return digits


def normalise_aadhaar_or_422(raw: str) -> str:
    """normalise_aadhaar() with the failure mapped to HTTP 422."""
    try:
        return normalise_aadhaar(raw)
    except AadhaarFormatError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


def aadhaar_field_validator(value: str | None) -> str | None:
    """
    Pydantic ``field_validator`` body shared by every request schema that
    accepts ``aadhaar_number``: None stays None (omitted), blank stays ""
    (means "clear" where the schema is a PATCH), anything else is normalised
    to its 12 digits or rejected with a 422 (ValueError).
    """
    if value is None:
        return None
    if not value.strip():
        return ""
    return normalise_aadhaar(value)


def last4_of(digits: str) -> str:
    return digits[-4:]


def mask_aadhaar(last4: str | None) -> str | None:
    """Display form ``XXXX-XXXX-1234`` for a stored last-4 (None stays None)."""
    return f"XXXX-XXXX-{last4}" if last4 else None


# ── Configuration ───────────────────────────────────────────────────────

def _parse_keys(spec: str) -> list[tuple[str, bytes]]:
    keys: list[tuple[str, bytes]] = []
    for item in (spec or "").split(","):
        item = item.strip()
        if not item:
            continue
        key_id, sep, b64 = item.partition(":")
        if not sep or not _KEY_ID_RE.match(key_id):
            raise AadhaarConfigError("AADHAAR_ENCRYPTION_KEYS entry is not 'key_id:base64key'.")
        try:
            raw = base64.b64decode(b64.strip(), validate=True)
        except (binascii.Error, ValueError):
            raise AadhaarConfigError("AADHAAR_ENCRYPTION_KEYS contains invalid base64.")
        if len(raw) != KEY_BYTES:
            raise AadhaarConfigError("AADHAAR_ENCRYPTION_KEYS keys must be exactly 32 bytes.")
        if any(k == key_id for k, _ in keys):
            raise AadhaarConfigError("AADHAAR_ENCRYPTION_KEYS repeats a key_id.")
        keys.append((key_id, raw))
    if not keys:
        raise AadhaarConfigError("AADHAAR_ENCRYPTION_KEYS is not set.")
    return keys


def _keys() -> list[tuple[str, bytes]]:
    return _parse_keys(settings.AADHAAR_ENCRYPTION_KEYS)


def _pepper() -> bytes:
    pepper = settings.AADHAAR_HASH_PEPPER
    if not pepper:
        raise AadhaarConfigError("AADHAAR_HASH_PEPPER is not set.")
    return pepper.encode("utf-8")


def _aesgcm(key: bytes):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        raise AadhaarConfigError("The 'cryptography' package is not installed.")
    return AESGCM(key)


def require_aadhaar_configured() -> None:
    """Raise HTTP 503 (with a clear, secret-free message) unless keys + pepper + library work."""
    try:
        _keys()
        _pepper()
        _aesgcm(b"\x00" * KEY_BYTES)
    except AadhaarConfigError as exc:
        logger.error("Aadhaar capture unavailable: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=CONFIG_503)


# ── Crypto primitives ───────────────────────────────────────────────────

def hash_aadhaar(digits: str) -> str:
    """HMAC-SHA256 (pepper) hex digest — the lookup/uniqueness value."""
    return hmac.new(_pepper(), digits.encode("ascii"), hashlib.sha256).hexdigest()


def encrypt_aadhaar(digits: str, person_pk) -> bytes:
    """Encrypt *digits* for *person_pk* with the ACTIVE key; returns the blob as bytes."""
    key_id, key = _keys()[0]
    nonce = os.urandom(NONCE_BYTES)
    ct = _aesgcm(key).encrypt(nonce, digits.encode("ascii"), str(person_pk).encode("ascii"))
    blob = ":".join((
        BLOB_VERSION, key_id,
        base64.b64encode(nonce).decode("ascii"),
        base64.b64encode(ct).decode("ascii"),
    ))
    return blob.encode("ascii")


def decrypt_aadhaar(blob, person_pk) -> str:
    """
    Decrypt a stored blob (bytes / memoryview / str) for *person_pk*.

    Raises AadhaarConfigError when the keys/library are unavailable and
    AadhaarDecryptionError for anything else (bad format, unknown key id,
    tampering, wrong person) — the exception text never carries a value.
    """
    try:
        text = bytes(blob).decode("ascii") if not isinstance(blob, str) else blob
        version, key_id, b64_nonce, b64_ct = text.split(":")
        if version != BLOB_VERSION:
            raise ValueError("version")
        nonce = base64.b64decode(b64_nonce, validate=True)
        ct = base64.b64decode(b64_ct, validate=True)
    except (ValueError, binascii.Error, UnicodeDecodeError, TypeError):
        raise AadhaarDecryptionError("Stored Aadhaar blob is malformed.")
    key = dict(_keys()).get(key_id)
    if key is None:
        raise AadhaarDecryptionError("Stored Aadhaar was encrypted with an unknown key id.")
    try:
        plain = _aesgcm(key).decrypt(nonce, ct, str(person_pk).encode("ascii"))
        return plain.decode("ascii")
    except AadhaarConfigError:
        raise
    except Exception:  # InvalidTag and friends — deliberately not chained (no value leakage)
        raise AadhaarDecryptionError("Stored Aadhaar failed authentication.") from None


# ── The one writer ──────────────────────────────────────────────────────

def set_person_aadhaar(cur, person_pk, raw: str | None, *, updated_by_sangha_sevi_pk=None) -> bool:
    """
    Store (or clear) the full Aadhaar of *person_pk* — the single writer of
    ``person.aadhaar_encrypted`` / ``aadhaar_hash`` / ``aadhaar_last4``.

    * ``raw`` is None or blank -> all three columns set to NULL (clears).
    * Otherwise: 422 on a malformed number, 503 when keys are not configured,
      409 when another ACTIVE-or-not person already holds the same number
      (the existing ``uq_person_aadhaar_hash`` rule; the message never names
      the other person). Returns True when a row was updated.
    """
    cleared = raw is None or not str(raw).strip()
    if cleared:
        enc = hashed = last4 = None
    else:
        digits = normalise_aadhaar_or_422(raw)
        require_aadhaar_configured()
        hashed = hash_aadhaar(digits)
        cur.execute(
            "SELECT 1 FROM nss.person WHERE aadhaar_hash = %s AND person_pk <> %s LIMIT 1",
            (hashed, str(person_pk)),
        )
        if cur.fetchone() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This Aadhaar number is already on record for another person. "
                    "If you are already registered, contact your Sakha administrator."
                ),
            )
        enc = encrypt_aadhaar(digits, person_pk)
        last4 = last4_of(digits)
    sets = ["aadhaar_encrypted = %s", "aadhaar_hash = %s", "aadhaar_last4 = %s", "updated_at = NOW()"]
    params: list = [enc, hashed, last4]
    if updated_by_sangha_sevi_pk is not None:
        sets.append("updated_by_sangha_sevi_pk = %s")
        params.append(str(updated_by_sangha_sevi_pk))
    params.append(str(person_pk))
    cur.execute(
        f"UPDATE nss.person SET {', '.join(sets)} WHERE person_pk = %s AND is_active = TRUE",
        params,
    )
    return cur.rowcount > 0
