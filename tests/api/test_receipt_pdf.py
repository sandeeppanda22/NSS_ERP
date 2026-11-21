"""
PDF receipts (owner request 2026-11-17) - the DB-free parts: the Indian-numbering helpers, the dependency-free PDF writer (a real,
well-formed file: header, xref offsets, fonts, the logo passed through), the receipt page and the two download endpoints (ownership,
status rules, headers) against a stand-in cursor. Runs with ``--noconftest``; the end-to-end download is in test_finance_receipt_pdf.py.
"""

import re
import struct
import zlib
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from api.services import receipt_pdf as RP
from api.services import simple_pdf as pdf

D = Decimal

SAMPLE = {
    "receipt_number": "RCT123", "receipt_date": date(2026, 11, 17), "amount": D("1250.50"), "status": "ISSUED",
    "received_from": "Sandeep Panda", "sangha_sevi_id": "SS1752", "member_sangha": "Ekamra Saraswata Sangha (Sakha Sangha)",
    "head_name": "Annual Pranami", "year_code": "2026-27", "payment_method_name": "UPI", "instrument_reference": "pay_Qx81hH7sd8f9G2",
    "received_by": "Ekamra Saraswata Sangha", "transaction_reference": "FTX456", "cancellation_reason": None,
}


def streams(data: bytes) -> list[bytes]:
    """The decompressed Flate streams of a PDF (the page contents)."""
    out = []
    for m in re.finditer(rb"/Filter /FlateDecode >>\nstream\n(.*?)\nendstream", data, re.S):
        out.append(zlib.decompress(m.group(1)))
    return out


def page_text(data: bytes) -> str:
    """Every string shown on the page, in order (the (...) operands of Tj)."""
    shown = re.findall(r"\((.*?)(?<!\\)\) Tj", b"\n".join(streams(data)).decode("latin-1"))
    return "\n".join(re.sub(r"\\([()\\])", r"\1", t) for t in shown)


class TestAmountInWords:
    @pytest.mark.parametrize("amount, words", [
        ("0", "Rupees Zero Only"),
        ("1", "Rupees One Only"),
        ("19", "Rupees Nineteen Only"),
        ("20", "Rupees Twenty Only"),
        ("21", "Rupees Twenty One Only"),
        ("100", "Rupees One Hundred Only"),
        ("101", "Rupees One Hundred One Only"),
        ("999", "Rupees Nine Hundred Ninety Nine Only"),
        ("1000", "Rupees One Thousand Only"),
        ("1250.50", "Rupees One Thousand Two Hundred Fifty and Fifty Paise Only"),
        ("99999.99", "Rupees Ninety Nine Thousand Nine Hundred Ninety Nine and Ninety Nine Paise Only"),
        ("100000", "Rupees One Lakh Only"),
        ("123456", "Rupees One Lakh Twenty Three Thousand Four Hundred Fifty Six Only"),
        ("1234567.5", "Rupees Twelve Lakh Thirty Four Thousand Five Hundred Sixty Seven and Fifty Paise Only"),
        ("10000000", "Rupees One Crore Only"),
        ("250000000", "Rupees Twenty Five Crore Only"),
        ("0.01", "Rupees Zero and One Paise Only"),
        ("5.05", "Rupees Five and Five Paise Only"),
        ("12000000.01", "Rupees One Crore Twenty Lakh and One Paise Only"),
    ])
    def test_words(self, amount, words):
        assert RP.amount_in_words(D(amount)) == words

    def test_the_largest_supported_amount(self):
        assert RP.amount_in_words(D("9999999999.99")).startswith("Rupees Nine Hundred Ninety Nine Crore")

    @pytest.mark.parametrize("bad", ["-1", "100000000000"])
    def test_negative_and_absurd_amounts_are_refused(self, bad):
        with pytest.raises(ValueError):
            RP.amount_in_words(D(bad))

    def test_a_third_decimal_is_rounded_not_dropped(self):
        assert RP.amount_in_words(D("1.005")) == RP.amount_in_words(D("1.01"))


class TestMoney:
    @pytest.mark.parametrize("amount, text", [
        ("0", "Rs. 0.00"), ("0.5", "Rs. 0.50"), ("999.99", "Rs. 999.99"), ("1000", "Rs. 1,000.00"), ("12345", "Rs. 12,345.00"),
        ("123456.5", "Rs. 1,23,456.50"), ("12345678", "Rs. 1,23,45,678.00"), ("100000", "Rs. 1,00,000.00"), ("-2500", "Rs. -2,500.00"),
    ])
    def test_indian_grouping(self, amount, text):
        assert RP.money(D(amount)) == text


class TestEncodingAndMeasuring:
    def test_cp1252_is_kept_and_the_rest_becomes_a_question_mark(self):
        assert pdf.encode("Café") == b"Caf\xe9"
        assert pdf.encode("₹ 500") == b"? 500"                    # the rupee sign has no glyph in the standard fonts
        assert pdf.encode("ଓଡି") == b"???"                # Odia
        assert pdf.encode("a\nb\tc\rd") == b"a b c d"

    def test_known_widths(self):
        assert pdf.text_width("A", "regular", 1000) == 667 and pdf.text_width("A", "bold", 1000) == 722
        assert pdf.text_width("AAA", "regular", 10) == pytest.approx(20.01)
        assert pdf.text_width("", "bold", 12) == 0

    def test_wrap_respects_the_width(self):
        text = "Nilachala Saraswata Sangha " * 6
        for line in pdf.wrap(text, "bold", 11, 200):
            assert pdf.text_width(line, "bold", 11) <= 200

    def test_a_word_longer_than_the_line_is_split(self):
        lines = pdf.wrap("W" * 80, "regular", 10, 100)
        assert len(lines) > 1 and all(pdf.text_width(l, "regular", 10) <= 100 for l in lines) and "".join(lines) == "W" * 80

    def test_wrap_keeps_explicit_paragraphs_and_empty_text(self):
        assert pdf.wrap("one\ntwo", "regular", 10, 500) == ["one", "two"]
        assert pdf.wrap("", "regular", 10, 100) == [""]

    def test_the_metrics_tables_cover_every_code(self):
        from api.services import _pdf_metrics as m

        assert len(m.HELVETICA) == len(m.HELVETICA_BOLD) == 224 and m.HELVETICA[0] == 278
        assert all(b >= a - 400 for a, b in zip(m.HELVETICA[1:95], m.HELVETICA_BOLD[1:95])), "bold is never much narrower than regular"


class TestThePdfFileIsWellFormed:
    @pytest.fixture(scope="class")
    def data(self):
        return RP.build_receipt_pdf(SAMPLE)

    def test_header_and_trailer(self, data):
        assert data.startswith(b"%PDF-1.4\n") and data.rstrip().endswith(b"%%EOF")

    def test_every_xref_offset_points_at_its_object(self, data):
        xref = int(re.search(rb"startxref\n(\d+)\n%%EOF", data).group(1))
        assert data[xref:xref + 4] == b"xref"
        count = int(re.match(rb"xref\n0 (\d+)\n", data[xref:]).group(1))
        entries = re.findall(rb"(\d{10}) (\d{5}) ([nf]) \n", data[xref:])
        assert len(entries) == count and entries[0][2] == b"f"
        for number, (offset, _gen, kind) in enumerate(entries[1:], start=1):
            assert kind == b"n" and data[int(offset):].startswith(b"%d 0 obj\n" % number), number

    def test_the_catalog_pages_and_info_exist(self, data):
        assert re.search(rb"/Type /Catalog /Pages \d+ 0 R", data) and b"/Type /Pages" in data and b"/Count 1" in data
        assert b"/MediaBox [0 0 595.28 841.89]" in data
        assert b"/Title (Payment Receipt RCT123)" in data and b"/Producer (NSS ERP)" in data

    def test_the_two_standard_fonts_are_declared_without_embedding(self, data):
        assert b"/BaseFont /Helvetica " in data and b"/BaseFont /Helvetica-Bold " in data and b"/FontFile" not in data
        assert data.count(b"/Encoding /WinAnsiEncoding") == 2

    def test_the_logo_jpeg_is_embedded_untouched(self, data):
        logo = RP.LOGO_PATH.read_bytes()
        assert logo[:3] == b"\xff\xd8\xff" and b"/Filter /DCTDecode" in data and logo in data

    def test_the_logo_asset_matches_the_size_the_page_declares(self):
        raw = RP.LOGO_PATH.read_bytes()
        i = 2
        while i < len(raw):
            marker = raw[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack(">HH", raw[i + 5:i + 9])
                break
            i += 2 + struct.unpack(">H", raw[i + 2:i + 4])[0]
        assert (width, height) == RP.LOGO_SIZE_PX
        assert f"/Width {width} /Height {height}".encode() in RP.build_receipt_pdf(SAMPLE)

    def test_a_missing_logo_still_gives_a_receipt(self, monkeypatch, tmp_path):
        monkeypatch.setattr(RP, "LOGO_PATH", tmp_path / "gone.jpg")
        out = RP.build_receipt_pdf(SAMPLE)
        assert out.startswith(b"%PDF") and b"/DCTDecode" not in out and "RCT123" in page_text(out)


class TestTheReceiptPage:
    def text(self, **over):
        return page_text(RP.build_receipt_pdf({**SAMPLE, **over}))

    def test_everything_a_member_expects_is_on_the_page(self):
        t = self.text()
        for needle in ("NILACHALA SARASWATA SANGHA", "Puri, Odisha", "Regd. No. 7391/390 of 1973-74", "PAYMENT RECEIPT", "RCT123", "17 Nov 2026",
                       "Sandeep Panda", "SS1752", "Ekamra Saraswata Sangha (Sakha Sangha)", "Annual Pranami", "2026-27", "UPI", "pay_Qx81hH7sd8f9G2",
                       "FTX456", "AMOUNT RECEIVED", "Rs. 1,250.50", "Rupees One Thousand Two Hundred Fifty and Fifty Paise Only", "PAID",
                       "computer-generated receipt", "Thank you for your contribution"):
            assert needle in t, needle

    def test_a_field_with_no_value_is_left_off_not_printed_as_none(self):
        t = self.text(sangha_sevi_id=None, instrument_reference="", member_sangha=None)
        assert "None" not in t and "Sangha Sevi ID" not in t and "Payment reference" not in t and "Member of" not in t

    def test_a_cancelled_receipt_is_stamped_and_has_no_thank_you(self):
        t = self.text(status="CANCELLED", cancellation_reason="Entered twice")
        assert t.count("CANCELLED") >= 3 and "Entered twice" in t and "not valid" in t
        assert "Thank you for your contribution" not in t and "PAID" not in t.replace("PAYMENT", "")
        assert b"/GS1 gs" in b"\n".join(streams(RP.build_receipt_pdf({**SAMPLE, "status": "CANCELLED"})))        # the faint watermark

    def test_an_issued_receipt_has_no_watermark(self):
        assert b"/GS1 gs" not in b"\n".join(streams(RP.build_receipt_pdf(SAMPLE)))

    def test_parentheses_and_backslashes_in_a_name_cannot_break_the_page(self):
        out = RP.build_receipt_pdf({**SAMPLE, "received_from": r"A (B) \ C ) ( Tj ET /F1 99 Tf"})
        assert out.startswith(b"%PDF") and r"A \(B\) \\ C \) \( Tj ET /F1 99 Tf" in b"\n".join(streams(out)).decode("latin-1")

    def test_a_very_long_name_wraps_inside_the_page(self):
        out = RP.build_receipt_pdf({**SAMPLE, "received_from": "Name " * 60})
        content = b"\n".join(streams(out)).decode("latin-1")
        assert content.count("Name Name") >= 2                           # several wrapped lines, none beyond the right margin below
        for x in re.findall(r"Td \(", content):
            pass
        for m in re.finditer(r"/F2 11 Tf ([\d.]+) ([\d.]+) Td \((.*?)(?<!\\)\) Tj", content):
            assert float(m.group(1)) + pdf.text_width(m.group(3).replace("\\", ""), "bold", 11) <= pdf.A4[0] - 48 + 0.5

    def test_non_latin_text_is_replaced_not_crashing(self):
        t = self.text(received_from="ରାମ Das")
        assert "?" in t and "Das" in t

    @pytest.mark.parametrize("field", ["receipt_number", "receipt_date", "amount"])
    def test_the_three_essentials_are_required(self, field):
        with pytest.raises(ValueError):
            RP.build_receipt_pdf({**SAMPLE, field: None})

    def test_the_generation_time_is_in_indian_time(self):
        when = datetime(2026, 11, 17, 4, 30, tzinfo=ZoneInfo("UTC"))
        assert "10:00 IST" in page_text(RP.build_receipt_pdf(SAMPLE, now=when))

    def test_a_string_date_and_a_float_like_amount_are_accepted(self):
        out = RP.build_receipt_pdf({**SAMPLE, "receipt_date": "2026-11-17", "amount": "99.5"})
        assert "Rs. 99.50" in page_text(out)


# ═══════════════════════════════════════════════════════════════════════
# The two endpoints, with a stand-in database
# ═══════════════════════════════════════════════════════════════════════

class Conn:
    @contextmanager
    def cursor(self):
        yield object()


class User:
    def __init__(self, person_pk=None, actor_pk=None):
        self.person_pk, self.actor_pk = person_pk, actor_pk


def row(**over):
    base = {**SAMPLE, "financial_receipt_pk": "r1", "txn_person_pk": "person-1", "txn_sangha_sevi_pk": "sevi-1", "txn_status": "POSTED",
            "receipt_person_pk": None, "scope_organization_pk": "org-1"}
    base.update(over)
    return base


@pytest.fixture
def endpoints(monkeypatch):
    from api.routers import finance as F
    from api.routers import finance_receipt_pdf as R

    state = {"row": row(), "scope_checks": []}
    monkeypatch.setattr(F, "_fetch_one", lambda cur: state["row"])
    monkeypatch.setattr(R.F, "_fetch_one", lambda cur: state["row"])
    monkeypatch.setattr(R.F, "_require_org_access", lambda cur, user, org, action: state["scope_checks"].append((org, action)))
    original = Conn.cursor

    @contextmanager
    def cursor(self):
        class Cur:
            def execute(self, *a, **k):
                pass
        yield Cur()

    monkeypatch.setattr(Conn, "cursor", cursor)
    state["R"] = R
    yield state
    monkeypatch.setattr(Conn, "cursor", original)


class TestMemberDownload:
    def call(self, ep, user):
        return ep["R"].my_receipt_pdf("00000000-0000-0000-0000-000000000001", user, Conn())

    def test_the_owner_by_person_gets_the_pdf(self, endpoints):
        r = self.call(endpoints, User(person_pk="person-1"))
        assert r.media_type == "application/pdf" and r.body.startswith(b"%PDF")
        assert r.headers["content-disposition"] == 'attachment; filename="NSS-Receipt-RCT123.pdf"'
        assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"

    def test_the_owner_by_sangha_sevi_gets_the_pdf(self, endpoints):
        endpoints["row"] = row(txn_person_pk=None)
        assert self.call(endpoints, User(person_pk="someone", actor_pk="sevi-1")).body.startswith(b"%PDF")

    @pytest.mark.parametrize("user", [User(person_pk="other", actor_pk="other-sevi"), User(), User(person_pk=None, actor_pk=None)])
    def test_anyone_else_gets_a_plain_404(self, endpoints, user):
        with pytest.raises(HTTPException) as e:
            self.call(endpoints, user)
        assert e.value.status_code in (404, 422) and "Receipt" in str(e.value.detail)

    @pytest.mark.parametrize("over", [{"status": "DRAFT"}, {"status": "CANCELLED"}, {"txn_status": "PENDING_APPROVAL"}, {"txn_status": "DRAFT"}])
    def test_a_receipt_that_is_not_issued_and_counted_is_a_404_for_the_member(self, endpoints, over):
        endpoints["row"] = row(**over)
        with pytest.raises(HTTPException) as e:
            self.call(endpoints, User(person_pk="person-1"))
        assert e.value.status_code == 404

    def test_an_unknown_receipt_is_a_404(self, endpoints):
        endpoints["row"] = None
        with pytest.raises(HTTPException) as e:
            self.call(endpoints, User(person_pk="person-1"))
        assert e.value.status_code == 404

    def test_a_settled_entry_is_still_downloadable(self, endpoints):
        endpoints["row"] = row(txn_status="SETTLED")
        assert self.call(endpoints, User(person_pk="person-1")).body.startswith(b"%PDF")

    def test_a_person_with_no_id_never_matches_an_entry_with_no_person(self, endpoints):
        endpoints["row"] = row(txn_person_pk=None, txn_sangha_sevi_pk=None)
        with pytest.raises(HTTPException):
            self.call(endpoints, User())


class TestAdminDownload:
    def call(self, ep, user=None):
        return ep["R"].receipt_pdf_for_admin("00000000-0000-0000-0000-000000000001", user or User(), Conn())

    def test_the_scope_of_the_receipt_is_checked(self, endpoints):
        self.call(endpoints)
        assert endpoints["scope_checks"] == [("org-1", "download this receipt")]

    def test_a_cancelled_receipt_can_be_downloaded_and_is_stamped(self, endpoints):
        endpoints["row"] = row(status="CANCELLED", cancellation_reason="Duplicate")
        assert "not valid" in page_text(self.call(endpoints).body)

    def test_a_draft_is_not_a_receipt_yet(self, endpoints):
        endpoints["row"] = row(status="DRAFT")
        with pytest.raises(HTTPException) as e:
            self.call(endpoints)
        assert e.value.status_code == 422 and "issue" in e.value.detail.lower()

    def test_an_unknown_receipt_is_a_404_before_any_scope_check(self, endpoints):
        endpoints["row"] = None
        with pytest.raises(HTTPException) as e:
            self.call(endpoints)
        assert e.value.status_code == 404 and endpoints["scope_checks"] == []

    def test_a_scope_refusal_stops_the_download(self, endpoints, monkeypatch):
        def refuse(cur, user, org, action):
            raise HTTPException(status_code=403, detail="no")

        monkeypatch.setattr(endpoints["R"].F, "_require_org_access", refuse)
        with pytest.raises(HTTPException) as e:
            self.call(endpoints)
        assert e.value.status_code == 403


class TestHeadersAndWiring:
    def test_the_file_name_cannot_carry_a_header_injection(self):
        from api.routers import finance_receipt_pdf as R

        r = R._pdf_response(row(receipt_number='RCT1"; x=1\r\nSet-Cookie: a=b'))
        assert r.headers["content-disposition"] == 'attachment; filename="NSS-Receipt-RCT1x1Set-Cookiea.pdf"' or "\n" not in r.headers["content-disposition"]
        assert "\r" not in r.headers["content-disposition"] and "Set-Cookie:" not in r.headers["content-disposition"]

    def test_an_empty_number_still_gets_a_name(self):
        from api.routers import finance_receipt_pdf as R

        assert 'filename="NSS-Receipt-receipt.pdf"' in R._pdf_response(row(receipt_number="!!!")).headers["content-disposition"]

    def test_the_routes_and_their_gates(self):
        import inspect

        from api.main import app
        from api.routers import finance_receipt_pdf as R

        routes = {(m, r.path): r for r in app.routes if getattr(r, "methods", None) for m in r.methods}
        member = routes[("GET", "/api/v1/finance/my-pranami/receipts/{receipt_pk}/pdf")]
        admin = routes[("GET", "/api/v1/finance/receipts/{receipt_pk}/pdf")]
        assert "get_current_user" in {getattr(d.call, "__name__", "") for d in member.dependant.dependencies}
        assert inspect.signature(R.receipt_pdf_for_admin).parameters["user"].default.dependency is R._VIEW

    def test_the_member_query_asks_for_nothing_it_does_not_need(self):
        from api.routers import finance_receipt_pdf as R

        sql = " ".join(R._SELECT.split())
        for forbidden in ("password", "aadhaar", "date_of_birth", "gateway_credential", "mobile", "email"):
            assert forbidden not in sql.lower(), forbidden
        assert "r.is_active = TRUE AND t.is_active = TRUE" in sql

    def test_the_selected_columns_cover_every_receipt_field(self):
        from api.routers import finance_receipt_pdf as R

        sql = " ".join(R._SELECT.split())
        for field in RP.RECEIPT_FIELDS:
            assert re.search(rf"\b{field}\b", sql), field

    def test_the_member_receipt_ids_are_exposed_by_the_member_models_only(self):
        from api.schemas.finance import MyPayment, MyPranamiReceipt, ReceiptResponse

        assert "financial_receipt_pk" in MyPayment.model_fields and "financial_receipt_pk" in MyPranamiReceipt.model_fields
        assert "financial_receipt_pk" in ReceiptResponse.model_fields


class TestPaymentSummary:
    """The one-page summary of a payment that covered several contributions (owner 2026-11-20): a printout, never a receipt."""

    DATA = {"request_reference": "UPR123", "paid_at": datetime(2026, 11, 21, 10, 30), "paid_amount": Decimal("1350.00"), "received_from": "Sandeep Panda",
            "sangha_sevi_id": "SS2", "member_sangha": "Ekamra Saraswata Sangha", "paid_to": "Ekamra Saraswata Sangha",
            "payment_method_name": "Card (credit / debit)", "provider_payment_id": "pay_Nx7"}
    ITEMS = [{"head_name": "Annual Pranami", "amount": Decimal("500.00"), "receipt_number": "RCT101"},
             {"head_name": "Membership subscription", "amount": Decimal("110.00"), "receipt_number": "RCT102"},
             {"head_name": "Rasa Utsav", "amount": Decimal("740.00"), "receipt_number": "RCT103"}]

    def test_it_is_a_valid_pdf_naming_every_contribution_and_its_own_receipt(self):
        from api.services.receipt_pdf import build_payment_summary_pdf

        body = build_payment_summary_pdf(self.DATA, self.ITEMS)
        assert body.startswith(b"%PDF-") and body.rstrip().endswith(b"%%EOF")
        text = page_text(body)
        for needle in ("PAYMENT SUMMARY", "UPR123", "RCT101", "RCT102", "RCT103", "Annual Pranami", "Rs. 1,350.00", "not a receipt"):
            assert needle in text, needle
        assert "PAYMENT RECEIPT" not in text                          # it must never pass for a receipt

    def test_it_refuses_to_draw_a_summary_without_a_reference_an_amount_or_items(self):
        from api.services.receipt_pdf import build_payment_summary_pdf

        with pytest.raises(ValueError):
            build_payment_summary_pdf({**self.DATA, "request_reference": None}, self.ITEMS)
        with pytest.raises(ValueError):
            build_payment_summary_pdf({**self.DATA, "paid_amount": None}, self.ITEMS)
        with pytest.raises(ValueError):
            build_payment_summary_pdf(self.DATA, [])

    def test_the_receipt_and_the_summary_share_one_header_and_footer(self):
        import inspect

        from api.services import receipt_pdf

        assert "_page_with_header(doc," in inspect.getsource(receipt_pdf.build_receipt_pdf)
        assert "_page_with_header(doc," in inspect.getsource(receipt_pdf.build_payment_summary_pdf)
        assert "_page_footer(" in inspect.getsource(receipt_pdf.build_receipt_pdf) and "_page_footer(" in inspect.getsource(receipt_pdf.build_payment_summary_pdf)
