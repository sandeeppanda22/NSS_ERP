"""
NSS ERP — Parichaya / Anumati Patra number: legacy-vs-new rule (GDR-009 §2A,
owner 2026-11-01) and the Darshaka-cannot-attend rule (§2B).

Rule under test: the card number follows the SAME explicit is_legacy_member
flag as the Local Sakha Number. A legacy member supplies the existing number,
strictly <seq>/<yyyy>/<yyyy+1> (any past/current year pair); anyone else
supplies none. Every member holds exactly one credential, minted at
enrolment when not legacy: the Anumati Patra (Darshaka) or the Parichaya
Patra (Regular/Associate; issue date pinned to Dola Purnima). The allocator
(next_credential_document_number) skips any number already issued, so a legacy
member's current-year card never collides with a minted one.

HTTP matrices live next to the endpoints: test_registration.py (register /
claim), test_claim_approval.py::TestApprovePatraNumberLegacyVsNew,
test_admin.py::TestCreateSanghaSeviCredentialNumber,
test_membership_change_request.py. This module covers the shared helpers.

Pure tests (format validator, validator with a stub cursor, allocator with a
stub cursor) need no DB. The rest use the real DB with per-test SAVEPOINT
rollback. Written but NOT yet run against a database (collect-only).
"""

import re
from datetime import date

import pytest
from fastapi import HTTPException

from api.helpers import (
    DARSHAKA_NO_ATTENDANCE_DETAIL,
    issue_credential_at_enrolment,
    next_credential_document_number,
    parse_legacy_patra_number,
    patra_card_type_for_membership_type,
    patra_number_exists,
    require_non_darshaka_for_attendance,
    resolve_legacy_patra_number,
)
from tests.registration_support import create_person_with_sangha_sevi

pytestmark = pytest.mark.integration

THIS_YEAR = date.today().year


# ── format validator (pure) ───────────────────────────────────────────────

class TestParseLegacyPatraNumber:
    @pytest.mark.parametrize("raw,expected", [
        ("345/2026/2027", "345/2026/2027"),
        ("  7/2025/2026  ", "7/2025/2026"),
        ("1/2000/2001", "1/2000/2001"),                 # DDL floor year
        (f"12/{THIS_YEAR}/{THIS_YEAR + 1}", f"12/{THIS_YEAR}/{THIS_YEAR + 1}"),  # current year
        ("999999999/2024/2025", "999999999/2024/2025"),
    ])
    def test_valid_numbers_are_canonical(self, raw, expected):
        assert parse_legacy_patra_number(raw) == expected

    @pytest.mark.parametrize("raw", [
        "", "   ", "345",                                # bare number: a card carries its years
        "345/2026", "345/2026/2027/2028",                # wrong segment count
        "0345/2026/2027",                                # leading zero
        "0/2026/2027", "-1/2026/2027", "+5/2026/2027",   # not a positive integer
        "3.5/2026/2027", "a/2026/2027", "3 4/2026/2027",
        "345/26/27", "345/20266/20267",                  # not four-digit years
        "345/2026/2028", "345/2027/2026", "345/2026/2026",  # not consecutive
        "345/1999/2000",                                 # before the 2000 floor
        f"345/{THIS_YEAR + 1}/{THIS_YEAR + 2}",          # in the future
        "١٢٣/2026/2027",                                 # non-ASCII digits
    ])
    def test_invalid_numbers_are_422(self, raw):
        with pytest.raises(HTTPException) as exc:
            parse_legacy_patra_number(raw, number_field="the_field")
        assert exc.value.status_code == 422
        assert "the_field" in exc.value.detail


# ── resolve_legacy_patra_number with a stub cursor (no DB) ────────────────

class _StubCur:
    """Answers patra_number_exists() SELECTs from a set of 'issued' numbers."""

    def __init__(self, issued=()):
        self.issued = set(issued)
        self._row = None
        self.queries = []

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        if "FROM nss.anumati_patra" in sql:
            org, number = params
            self._row = (1,) if (org, number) in self.issued else None
        elif "FROM nss.parichaya_patra" in sql:
            self._row = (1,) if (params[0],) in self.issued else None

    def fetchone(self):
        return self._row


class TestResolveLegacyPatraNumber:
    def test_legacy_with_valid_number_returns_canonical(self):
        assert resolve_legacy_patra_number(
            _StubCur(), True, " 345/2026/2027 ", card_type="PARICHAYA_PATRA") == "345/2026/2027"

    def test_legacy_without_number_is_422(self):
        for blank in (None, "", "  "):
            with pytest.raises(HTTPException) as exc:
                resolve_legacy_patra_number(_StubCur(), True, blank, card_type="PARICHAYA_PATRA",
                                            flag_field="f", number_field="n")
            assert exc.value.status_code == 422
            assert "n (Parichaya Patra number) is required when f is true" in exc.value.detail

    def test_new_member_with_a_number_is_422(self):
        with pytest.raises(HTTPException) as exc:
            resolve_legacy_patra_number(_StubCur(), False, "345/2026/2027",
                                        card_type="PARICHAYA_PATRA", number_field="n")
        assert exc.value.status_code == 422
        assert "n must be blank when is_legacy_member is false" in exc.value.detail

    @pytest.mark.parametrize("flag", [False, None])
    def test_new_member_without_a_number_returns_none(self, flag):
        assert resolve_legacy_patra_number(_StubCur(), flag, None, card_type="PARICHAYA_PATRA") is None
        assert resolve_legacy_patra_number(_StubCur(), flag, "  ", card_type="ANUMATI_PATRA") is None

    def test_already_issued_parichaya_number_is_409(self):
        with pytest.raises(HTTPException) as exc:
            resolve_legacy_patra_number(_StubCur({("345/2026/2027",)}), True, "345/2026/2027",
                                        card_type="PARICHAYA_PATRA")
        assert exc.value.status_code == 409

    def test_anumati_uniqueness_is_per_issuing_sakha(self):
        taken = {("sakha-a", "5/2025/2026")}
        with pytest.raises(HTTPException) as exc:
            resolve_legacy_patra_number(_StubCur(taken), True, "5/2025/2026",
                                        card_type="ANUMATI_PATRA", issuing_organization_pk="sakha-a")
        assert exc.value.status_code == 409
        # the same string in ANOTHER Sakha is a different, free number
        assert resolve_legacy_patra_number(
            _StubCur(taken), True, "5/2025/2026",
            card_type="ANUMATI_PATRA", issuing_organization_pk="sakha-b") == "5/2025/2026"


# ── allocator skips taken numbers (stub cursor, no DB) ────────────────────

class _CounterCur:
    """Counter upsert returns 1, 2, 3 ...; SELECTs answer from `issued`."""

    def __init__(self, issued):
        self.issued = set(issued)
        self.counter = 0
        self._row = None

    def execute(self, sql, params=()):
        if "credential_sequence_counter" in sql:
            self.counter += 1
            self._row = (self.counter,)
        elif "FROM nss.parichaya_patra" in sql:
            self._row = (1,) if params[0] in self.issued else None
        elif "FROM nss.anumati_patra" in sql:
            self._row = (1,) if params[1] in self.issued else None

    def fetchone(self):
        return self._row


class TestAllocatorSkipsTakenNumbers:
    AS_OF = date(2026, 6, 1)   # year pair 2026/2027

    def test_skips_a_legacy_number_in_the_same_year_without_reusing_any(self):
        cur = _CounterCur({"1/2026/2027", "2/2026/2027"})
        assert next_credential_document_number(cur, "PARICHAYA_PATRA", "kendra", self.AS_OF) == "3/2026/2027"
        assert cur.counter == 3           # 1 and 2 were consumed, never handed out

    def test_free_first_number_is_returned_directly(self):
        cur = _CounterCur(set())
        assert next_credential_document_number(cur, "PARICHAYA_PATRA", "kendra", self.AS_OF) == "1/2026/2027"

    def test_a_previous_year_legacy_number_never_blocks_the_new_year(self):
        cur = _CounterCur({"1/2025/2026"})
        assert next_credential_document_number(cur, "PARICHAYA_PATRA", "kendra", self.AS_OF) == "1/2026/2027"

    def test_anumati_skip_uses_the_sakha_scope(self):
        cur = _CounterCur({"1/2026/2027"})
        assert next_credential_document_number(cur, "ANUMATI_PATRA", "sakha-a", self.AS_OF) == "2/2026/2027"


# ── real DB ──────────────────────────────────────────────────────────────

@pytest.fixture
def types(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.value_code, md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.is_active = TRUE
          AND md.value_code IN ('REGULAR', 'ASSOCIATE', 'PROBATIONARY')
    """)
    out = {r[0]: str(r[1]) for r in cur.fetchall()}
    cur.close()
    if "REGULAR" not in out or "PROBATIONARY" not in out:
        pytest.skip("MEMBERSHIP_TYPE reference data missing.")
    return out


@pytest.fixture
def kendra_and_sakha(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk, md.value_code
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE o.is_active = TRUE AND md.value_code IN ('KENDRA', 'SAKHA_SANGHA')
        ORDER BY o.created_at
    """)
    rows = cur.fetchall()
    cur.close()
    kendra = next((str(r[0]) for r in rows if r[1] == "KENDRA"), None)
    sakhas = [str(r[0]) for r in rows if r[1] == "SAKHA_SANGHA"]
    if not kendra or len(sakhas) < 2:
        pytest.skip("Need a Kendra and two Sakhas.")
    return kendra, sakhas


def _insert_parichaya(cur, sangha_sevi_id, number):
    cur.execute("SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE sangha_sevi_id = %s", (sangha_sevi_id,))
    ss_pk = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO nss.parichaya_patra (sangha_sevi_pk, document_number, issue_date, valid_from, valid_to, status) "
        "VALUES (%s, %s, DATE '2025-03-14', DATE '2025-03-14', DATE '2026-03-03', 'EXPIRED')",
        (ss_pk, number),
    )
    return ss_pk


class TestAllocatorAgainstTheRealTable:
    def test_minted_number_skips_a_legacy_number_of_the_same_year(self, write_conn, kendra_and_sakha):
        kendra, sakhas = kendra_and_sakha
        cur = write_conn.cursor()
        as_of = date(2031, 6, 1)    # a year no real data uses; counter row is rolled back
        _, ss_id = create_person_with_sangha_sevi(write_conn, sakhas[0], "PNA")
        _insert_parichaya(cur, ss_id, "1/2031/2032")
        minted = next_credential_document_number(cur, "PARICHAYA_PATRA", kendra, as_of)
        assert minted == "2/2031/2032"
        assert patra_number_exists(cur, "PARICHAYA_PATRA", "1/2031/2032")
        # and the next one continues from there — nothing is handed out twice
        assert next_credential_document_number(cur, "PARICHAYA_PATRA", kendra, as_of) == "3/2031/2032"

    def test_parichaya_is_nss_unique_but_anumati_is_per_sakha(self, write_conn, kendra_and_sakha):
        kendra, sakhas = kendra_and_sakha
        cur = write_conn.cursor()
        _, ss_id = create_person_with_sangha_sevi(write_conn, sakhas[0], "PNB")
        ss_pk = _insert_parichaya(cur, ss_id, "77/2030/2031")
        cur.execute(
            "INSERT INTO nss.anumati_patra (sangha_sevi_pk, issuing_organization_pk, document_number, "
            "issue_date, valid_from, valid_to, status) VALUES (%s, %s, '77/2030/2031', "
            "DATE '2030-05-01', DATE '2030-05-01', DATE '2031-05-01', 'EXPIRED')",
            (ss_pk, sakhas[0]),
        )
        assert patra_number_exists(cur, "PARICHAYA_PATRA", "77/2030/2031")           # NSS-wide
        assert patra_number_exists(cur, "ANUMATI_PATRA", "77/2030/2031", sakhas[0])  # that Sakha
        assert not patra_number_exists(cur, "ANUMATI_PATRA", "77/2030/2031", sakhas[1])  # another Sakha


class TestIssueCredentialAtEnrolment:
    """Associate vs Darshaka, legacy vs new — the enrolment-time credential step."""

    WINDOW = dict(issue_date=date(2025, 3, 14), valid_from=date(2025, 3, 14), valid_to=date(2026, 3, 3))

    def _enrol(self, write_conn, org, type_pk, label, **kw):
        _, ss_id = create_person_with_sangha_sevi(write_conn, org, label)
        cur = write_conn.cursor()
        cur.execute("SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE sangha_sevi_id = %s", (ss_id,))
        ss_pk = str(cur.fetchone()[0])
        return issue_credential_at_enrolment(
            cur, sangha_sevi_pk=ss_pk, membership_type_pk=type_pk, organization_pk=org,
            **self.WINDOW, **kw,
        ), cur, ss_pk

    def test_new_regular_gets_a_minted_parichaya(self, write_conn, kendra_and_sakha, types):
        _, sakhas = kendra_and_sakha
        (card_type, _pk, number), cur, ss_pk = self._enrol(
            write_conn, sakhas[0], types["REGULAR"], "ICA1", is_legacy_member=False)
        assert card_type == "PARICHAYA_PATRA"
        assert re.fullmatch(r"[1-9]\d*/\d{4}/\d{4}", number)
        cur.execute("SELECT COUNT(*) FROM nss.anumati_patra WHERE sangha_sevi_pk = %s", (ss_pk,))
        assert cur.fetchone()[0] == 0

    def test_legacy_regular_records_the_existing_parichaya(self, write_conn, kendra_and_sakha, types):
        _, sakhas = kendra_and_sakha
        (card_type, _pk, number), cur, ss_pk = self._enrol(
            write_conn, sakhas[0], types["REGULAR"], "ICA2",
            is_legacy_member=True, document_number="4242/2024/2025")
        assert (card_type, number) == ("PARICHAYA_PATRA", "4242/2024/2025")
        cur.execute("SELECT document_number FROM nss.parichaya_patra WHERE sangha_sevi_pk = %s", (ss_pk,))
        assert cur.fetchone()[0] == "4242/2024/2025"

    def test_associate_gets_parichaya_never_anumati(self, write_conn, kendra_and_sakha, types):
        if "ASSOCIATE" not in types:
            pytest.skip("No ASSOCIATE membership type.")
        _, sakhas = kendra_and_sakha
        (card_type, _pk, number), cur, ss_pk = self._enrol(
            write_conn, sakhas[0], types["ASSOCIATE"], "ICA3",
            is_legacy_member=True, document_number="4343/2024/2025")
        assert card_type == "PARICHAYA_PATRA"
        cur.execute("SELECT COUNT(*) FROM nss.anumati_patra WHERE sangha_sevi_pk = %s", (ss_pk,))
        assert cur.fetchone()[0] == 0

    def test_new_associate_gets_a_minted_parichaya_not_anumati(self, write_conn, kendra_and_sakha, types):
        if "ASSOCIATE" not in types:
            pytest.skip("No ASSOCIATE membership type.")
        _, sakhas = kendra_and_sakha
        (card_type, _pk, _number), cur, ss_pk = self._enrol(
            write_conn, sakhas[0], types["ASSOCIATE"], "ICA4", is_legacy_member=False)
        assert card_type == "PARICHAYA_PATRA"
        cur.execute("SELECT COUNT(*) FROM nss.anumati_patra WHERE sangha_sevi_pk = %s", (ss_pk,))
        assert cur.fetchone()[0] == 0

    def test_new_darshaka_gets_a_minted_anumati(self, write_conn, kendra_and_sakha, types):
        _, sakhas = kendra_and_sakha
        (card_type, _pk, number), cur, ss_pk = self._enrol(
            write_conn, sakhas[0], types["PROBATIONARY"], "ICA5", is_legacy_member=False)
        assert card_type == "ANUMATI_PATRA"
        assert re.fullmatch(r"[1-9]\d*/\d{4}/\d{4}", number)
        cur.execute("SELECT COUNT(*) FROM nss.parichaya_patra WHERE sangha_sevi_pk = %s", (ss_pk,))
        assert cur.fetchone()[0] == 0

    def test_legacy_darshaka_records_the_existing_anumati(self, write_conn, kendra_and_sakha, types):
        _, sakhas = kendra_and_sakha
        (card_type, _pk, number), _, _ = self._enrol(
            write_conn, sakhas[0], types["PROBATIONARY"], "ICA6",
            is_legacy_member=True, document_number="31/2024/2025")
        assert (card_type, number) == ("ANUMATI_PATRA", "31/2024/2025")

    def test_duplicate_legacy_parichaya_is_409_from_the_issue_choke_point(
        self, write_conn, kendra_and_sakha, types
    ):
        _, sakhas = kendra_and_sakha
        self._enrol(write_conn, sakhas[0], types["REGULAR"], "ICA7",
                    is_legacy_member=True, document_number="5151/2024/2025")
        with pytest.raises(HTTPException) as exc:
            self._enrol(write_conn, sakhas[1], types["REGULAR"], "ICA8",
                        is_legacy_member=True, document_number="5151/2024/2025")
        assert exc.value.status_code == 409


class TestDarshakaCannotAttendAnotherSakha:
    def test_probationary_is_refused_with_the_fixed_message(self, write_conn, types):
        cur = write_conn.cursor()
        assert patra_card_type_for_membership_type(cur, types["PROBATIONARY"]) == "ANUMATI_PATRA"
        with pytest.raises(HTTPException) as exc:
            require_non_darshaka_for_attendance(cur, types["PROBATIONARY"])
        assert exc.value.status_code == 422
        assert exc.value.detail == DARSHAKA_NO_ATTENDANCE_DETAIL
        assert "must transfer to it; use Sakha Transfer" in exc.value.detail

    @pytest.mark.parametrize("code", ["REGULAR", "ASSOCIATE"])
    def test_regular_and_associate_may_attend(self, write_conn, types, code):
        if code not in types:
            pytest.skip(f"No {code} membership type.")
        require_non_darshaka_for_attendance(write_conn.cursor(), types[code])
