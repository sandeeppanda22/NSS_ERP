"""
NSS ERP — api/services/aadhaar_service.py unit tests (GDR-011).

DB-free: no fixture here touches the database, so this module also runs with
``pytest --noconftest tests/api/test_aadhaar_service.py``. The AES-GCM tests
need the ``cryptography`` package and are skipped (not failed) without it; the
Verhoeff / normalise / mask / hash / missing-config tests never need it.
"""

import base64
import importlib.util
import os

import pytest
from fastapi import HTTPException

from api.config import settings
from api.services import aadhaar_service as svc

HAS_CRYPTO = importlib.util.find_spec("cryptography") is not None
needs_crypto = pytest.mark.skipif(not HAS_CRYPTO, reason="'cryptography' is not installed")

PERSON_A = "11111111-1111-1111-1111-111111111111"
PERSON_B = "22222222-2222-2222-2222-222222222222"


# ── helpers ──────────────────────────────────────────────────────────────

def verhoeff_check_digit(payload: str) -> str:
    """Reference generator (independent of the service's validator tables' use)."""
    for d in "0123456789":
        if svc.verhoeff_valid(payload + d):
            return d
    raise AssertionError("no check digit")


def make_aadhaar(first: str = "2", body: str = "3456789012") -> str:
    """A 12-digit number with a valid Verhoeff check digit."""
    payload = (first + body)[:11]
    return payload + verhoeff_check_digit(payload)


VALID = make_aadhaar()
VALID_B = make_aadhaar("9", "8765432109")


def b64key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(settings, "AADHAAR_ENCRYPTION_KEYS", f"k1:{b64key()}")
    monkeypatch.setattr(settings, "AADHAAR_HASH_PEPPER", "test-pepper-1")


@pytest.fixture
def no_keys(monkeypatch):
    monkeypatch.setattr(settings, "AADHAAR_ENCRYPTION_KEYS", "")
    monkeypatch.setattr(settings, "AADHAAR_HASH_PEPPER", "")


# ── Verhoeff ─────────────────────────────────────────────────────────────

class TestVerhoeff:
    def test_known_vectors(self):
        # Wikipedia / reference vectors: 236 + check digit 3; 12345 + 1.
        assert svc.verhoeff_valid("2363")
        assert svc.verhoeff_valid("123451")
        assert not svc.verhoeff_valid("2364")
        assert not svc.verhoeff_valid("123450")

    def test_generated_numbers_are_valid_and_single_digit_errors_are_caught(self):
        n = make_aadhaar()
        assert svc.verhoeff_valid(n)
        for i in range(12):
            for d in "0123456789":
                if d != n[i]:
                    assert not svc.verhoeff_valid(n[:i] + d + n[i + 1:])

    def test_adjacent_transposition_is_caught(self):
        n = make_aadhaar("2", "3456789012")
        for i in range(11):
            if n[i] != n[i + 1]:
                assert not svc.verhoeff_valid(n[:i] + n[i + 1] + n[i] + n[i + 2:])

    def test_non_digits_and_empty_are_invalid(self):
        for bad in ("", "12a4", "٢٣٦٣", " 2363"):
            assert not svc.verhoeff_valid(bad)


# ── normalise / validate ─────────────────────────────────────────────────

class TestNormalise:
    def test_plain_spaced_and_hyphenated_forms(self):
        spaced = f"{VALID[:4]} {VALID[4:8]} {VALID[8:]}"
        hyphen = f"{VALID[:4]}-{VALID[4:8]}-{VALID[8:]}"
        assert svc.normalise_aadhaar(VALID) == VALID
        assert svc.normalise_aadhaar(spaced) == VALID
        assert svc.normalise_aadhaar(hyphen) == VALID
        assert svc.normalise_aadhaar(f"  {VALID}\t") == VALID

    @pytest.mark.parametrize("bad", [
        "", "   ", "1234", "23456789012", "2345678901234",   # wrong length
        "abcdefghijkl", "2345 6789 01x2",                      # non-digits
        "٢٣٤٥٦٧٨٩٠١٢٣",                                        # non-ASCII digits
    ])
    def test_malformed_is_rejected(self, bad):
        with pytest.raises(svc.AadhaarFormatError):
            svc.normalise_aadhaar(bad)

    def test_leading_zero_or_one_is_rejected_even_with_valid_checksum(self):
        for first in "01":
            n = make_aadhaar(first)
            assert svc.verhoeff_valid(n)
            with pytest.raises(svc.AadhaarFormatError):
                svc.normalise_aadhaar(n)

    def test_bad_checksum_is_rejected(self):
        bad = VALID[:-1] + str((int(VALID[-1]) + 1) % 10)
        with pytest.raises(svc.AadhaarFormatError):
            svc.normalise_aadhaar(bad)

    def test_non_string_is_rejected(self):
        with pytest.raises(svc.AadhaarFormatError):
            svc.normalise_aadhaar(234567890123)  # type: ignore[arg-type]

    def test_or_422_wrapper(self):
        with pytest.raises(HTTPException) as exc:
            svc.normalise_aadhaar_or_422("1234")
        assert exc.value.status_code == 422
        assert svc.normalise_aadhaar_or_422(VALID) == VALID

    def test_field_validator_semantics(self):
        assert svc.aadhaar_field_validator(None) is None
        assert svc.aadhaar_field_validator("") == ""
        assert svc.aadhaar_field_validator("   ") == ""
        assert svc.aadhaar_field_validator(f"{VALID[:4]} {VALID[4:]}") == VALID
        with pytest.raises(ValueError):
            svc.aadhaar_field_validator("1234")


class TestMask:
    def test_last4_and_mask(self):
        assert svc.last4_of(VALID) == VALID[-4:]
        assert svc.mask_aadhaar("1234") == "XXXX-XXXX-1234"
        assert svc.mask_aadhaar(None) is None
        assert svc.mask_aadhaar("") is None
        assert VALID[:8] not in svc.mask_aadhaar(VALID[-4:])


# ── configuration / 503 ──────────────────────────────────────────────────

class TestConfiguration:
    def test_missing_keys_is_503_with_clear_message(self, no_keys):
        with pytest.raises(HTTPException) as exc:
            svc.require_aadhaar_configured()
        assert exc.value.status_code == 503
        assert "not configured" in exc.value.detail

    def test_missing_pepper_only_is_503(self, keys, monkeypatch):
        monkeypatch.setattr(settings, "AADHAAR_HASH_PEPPER", "")
        with pytest.raises(HTTPException) as exc:
            svc.require_aadhaar_configured()
        assert exc.value.status_code == 503

    @pytest.mark.parametrize("spec", [
        "nocolon", "k1:not-base64!!", f"k1:{base64.b64encode(b'short').decode()}",
        f"bad id:{base64.b64encode(os.urandom(32)).decode()}",
    ])
    def test_malformed_keys_are_503_and_the_secret_is_not_echoed(self, monkeypatch, spec):
        monkeypatch.setattr(settings, "AADHAAR_ENCRYPTION_KEYS", spec)
        monkeypatch.setattr(settings, "AADHAAR_HASH_PEPPER", "p")
        with pytest.raises(HTTPException) as exc:
            svc.require_aadhaar_configured()
        assert exc.value.status_code == 503
        assert spec not in exc.value.detail

    def test_duplicate_key_id_is_rejected(self):
        k = b64key()
        with pytest.raises(svc.AadhaarConfigError):
            svc._parse_keys(f"k1:{k},k1:{b64key()}")

    def test_set_person_aadhaar_without_keys_is_503_and_never_writes(self, no_keys):
        class Cur:
            executed = []
            def execute(self, *a, **k):
                self.executed.append(a)
        cur = Cur()
        with pytest.raises(HTTPException) as exc:
            svc.set_person_aadhaar(cur, PERSON_A, VALID)
        assert exc.value.status_code == 503
        assert cur.executed == []           # no silent last-4-only fall-back

    def test_set_person_aadhaar_malformed_is_422_before_any_sql(self, keys):
        class Cur:
            executed = []
            def execute(self, *a, **k):
                self.executed.append(a)
        cur = Cur()
        with pytest.raises(HTTPException) as exc:
            svc.set_person_aadhaar(cur, PERSON_A, "1234")
        assert exc.value.status_code == 422
        assert cur.executed == []


# ── hash ─────────────────────────────────────────────────────────────────

class TestHash:
    def test_hash_is_64_hex_deterministic_and_pepper_dependent(self, keys, monkeypatch):
        h = svc.hash_aadhaar(VALID)
        assert len(h) == 64 and int(h, 16) >= 0
        assert svc.hash_aadhaar(VALID) == h
        assert svc.hash_aadhaar(VALID_B) != h
        monkeypatch.setattr(settings, "AADHAAR_HASH_PEPPER", "another-pepper")
        assert svc.hash_aadhaar(VALID) != h

    def test_hash_is_not_a_bare_sha256(self, keys):
        import hashlib
        assert svc.hash_aadhaar(VALID) != hashlib.sha256(VALID.encode()).hexdigest()

    def test_hash_without_pepper_raises_config_error(self, no_keys):
        with pytest.raises(svc.AadhaarConfigError):
            svc.hash_aadhaar(VALID)


# ── AES-256-GCM ──────────────────────────────────────────────────────────

@needs_crypto
class TestEncryption:
    def test_round_trip_and_blob_shape(self, keys):
        blob = svc.encrypt_aadhaar(VALID, PERSON_A)
        assert isinstance(blob, bytes)
        text = blob.decode()
        assert text.startswith("v1:k1:") and text.count(":") == 3
        assert VALID not in text and VALID[-4:] not in text.split(":")[0]
        assert svc.decrypt_aadhaar(blob, PERSON_A) == VALID

    def test_accepts_memoryview_and_str_as_read_back_from_postgres(self, keys):
        blob = svc.encrypt_aadhaar(VALID, PERSON_A)
        assert svc.decrypt_aadhaar(memoryview(blob), PERSON_A) == VALID
        assert svc.decrypt_aadhaar(blob.decode(), PERSON_A) == VALID

    def test_nonce_is_random_so_ciphertexts_differ(self, keys):
        assert svc.encrypt_aadhaar(VALID, PERSON_A) != svc.encrypt_aadhaar(VALID, PERSON_A)

    def test_ciphertext_tampering_is_detected(self, keys):
        v, kid, nonce, ct = svc.encrypt_aadhaar(VALID, PERSON_A).decode().split(":")
        raw = bytearray(base64.b64decode(ct))
        raw[0] ^= 0x01
        tampered = ":".join((v, kid, nonce, base64.b64encode(bytes(raw)).decode())).encode()
        with pytest.raises(svc.AadhaarDecryptionError):
            svc.decrypt_aadhaar(tampered, PERSON_A)

    def test_blob_moved_to_another_person_fails(self, keys):
        blob = svc.encrypt_aadhaar(VALID, PERSON_A)
        with pytest.raises(svc.AadhaarDecryptionError):
            svc.decrypt_aadhaar(blob, PERSON_B)

    def test_wrong_key_fails_and_error_carries_no_value(self, keys, monkeypatch):
        blob = svc.encrypt_aadhaar(VALID, PERSON_A)
        monkeypatch.setattr(settings, "AADHAAR_ENCRYPTION_KEYS", f"k1:{b64key()}")
        with pytest.raises(svc.AadhaarDecryptionError) as exc:
            svc.decrypt_aadhaar(blob, PERSON_A)
        assert VALID not in str(exc.value)

    def test_unknown_key_id_and_malformed_blobs_fail_cleanly(self, keys):
        for bad in (b"", b"garbage", b"v2:k1:AAAA:AAAA", b"v1:zz:AAAA:AAAA",
                    b"v1:k1:!!!:AAAA", b"v1:k1:AAAA"):
            with pytest.raises(svc.AadhaarDecryptionError):
                svc.decrypt_aadhaar(bad, PERSON_A)

    def test_key_rotation_old_rows_stay_readable_and_new_rows_use_new_key(self, monkeypatch):
        k1, k2 = b64key(), b64key()
        monkeypatch.setattr(settings, "AADHAAR_ENCRYPTION_KEYS", f"k1:{k1}")
        monkeypatch.setattr(settings, "AADHAAR_HASH_PEPPER", "p")
        old = svc.encrypt_aadhaar(VALID, PERSON_A)
        monkeypatch.setattr(settings, "AADHAAR_ENCRYPTION_KEYS", f"k2:{k2},k1:{k1}")
        new = svc.encrypt_aadhaar(VALID_B, PERSON_A)
        assert old.startswith(b"v1:k1:") and new.startswith(b"v1:k2:")
        assert svc.decrypt_aadhaar(old, PERSON_A) == VALID
        assert svc.decrypt_aadhaar(new, PERSON_A) == VALID_B
        # a retired key (removed from the list) can no longer decrypt
        monkeypatch.setattr(settings, "AADHAAR_ENCRYPTION_KEYS", f"k2:{k2}")
        with pytest.raises(svc.AadhaarDecryptionError):
            svc.decrypt_aadhaar(old, PERSON_A)

    def test_encrypt_without_keys_raises_config_error(self, no_keys):
        with pytest.raises(svc.AadhaarConfigError):
            svc.encrypt_aadhaar(VALID, PERSON_A)


class TestSetPersonAadhaarSql:
    """set_person_aadhaar() against a fake cursor: what it writes, in which order."""

    class Cur:
        def __init__(self, duplicate=False):
            self.duplicate = duplicate
            self.calls = []
            self.rowcount = 1
        def execute(self, sql, params=None):
            self.calls.append((sql, params))
        def fetchone(self):
            return (1,) if self.duplicate else None

    @needs_crypto
    def test_stores_ciphertext_hash_and_derived_last4(self, keys):
        cur = self.Cur()
        assert svc.set_person_aadhaar(cur, PERSON_A, f"{VALID[:4]} {VALID[4:8]} {VALID[8:]}",
                                      updated_by_sangha_sevi_pk="SS") is True
        sql, params = cur.calls[-1]
        assert "aadhaar_encrypted = %s" in sql and "aadhaar_hash = %s" in sql
        enc, hashed, last4 = params[0], params[1], params[2]
        assert enc != VALID.encode() and VALID.encode() not in enc
        assert last4 == VALID[-4:] and hashed == svc.hash_aadhaar(VALID)
        assert svc.decrypt_aadhaar(enc, PERSON_A) == VALID

    @needs_crypto
    def test_duplicate_is_409_and_nothing_is_updated(self, keys):
        cur = self.Cur(duplicate=True)
        with pytest.raises(HTTPException) as exc:
            svc.set_person_aadhaar(cur, PERSON_A, VALID)
        assert exc.value.status_code == 409
        assert not any("UPDATE" in c[0] for c in cur.calls)

    def test_blank_clears_all_three_columns(self, no_keys):
        cur = self.Cur()
        svc.set_person_aadhaar(cur, PERSON_A, "")
        sql, params = cur.calls[-1]
        assert params[:3] == [None, None, None]
        cur2 = self.Cur()
        svc.set_person_aadhaar(cur2, PERSON_A, None)
        assert cur2.calls[-1][1][:3] == [None, None, None]
