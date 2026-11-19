"""
Downloadable PDF receipts (owner request 2026-11-17), end to end against a database: a member pays by UPI (the MOCK gateway signs its
own webhook), the app books it and issues the receipt, and the member - and an administrator - download it as a PDF, as often as they
like. Real integration tests (nothing mocked). The PDF text is read back by inflating the page stream.
"""

import re
import zlib

import pytest

from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    FAKE_UUID,
    _login_headers,
    admin_h,
    admin_user,
    ensure_open_year_covering_today,
    kendra_admin,
    kendra_h,
    mock_gateway,
    move,
    new_member,
    other_admin,
    other_admin_h,
    other_org_pk,
    pay_request,
    plain_member,
    plain_member_h,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
    upi_world,
    viewer_h,
    viewer_user,
)


@pytest.fixture
def plain_member(write_conn, register_org_pk):
    return new_member(write_conn, register_org_pk, "FinPdf")


@pytest.fixture
def plain_member_h(client, plain_member):
    return _login_headers(client, plain_member["sangha_sevi_id"], plain_member["password"])


@pytest.fixture(autouse=True)
def _a_financial_year_covers_today(write_conn):
    ensure_open_year_covering_today(write_conn)


def page_text(data: bytes) -> str:
    content = b"\n".join(zlib.decompress(m.group(1)) for m in re.finditer(rb"/Filter /FlateDecode >>\nstream\n(.*?)\nendstream", data, re.S)).decode("latin-1")
    return "\n".join(re.sub(r"\\([()\\])", r"\1", t) for t in re.findall(r"\((.*?)(?<!\\)\) Tj", content))


def paid_receipt(client, admin_h, mock_gateway, member_h, head, amount="300.00") -> dict:
    """The member pays *head*; returns {"receipt_pk", "receipt_number", "txn_pk", "request"} once the signed webhook has booked it."""
    r = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": head["finance_head_pk"], "amount": amount}, headers=member_h)
    assert r.status_code == 201, r.text
    full = client.get(f"{BASE}/payment-requests/{r.json()['upi_payment_request_pk']}", headers=admin_h).json()
    assert pay_request(client, mock_gateway, full).status_code == 200
    full = client.get(f"{BASE}/payment-requests/{full['upi_payment_request_pk']}", headers=admin_h).json()
    assert full["status"] == "PAID" and full["receipt_number"], full
    mine = client.get(f"{BASE}/my-pranami", headers=member_h).json()["items"]
    item = next(i for i in mine if i["transaction_reference"] == full["transaction_reference"])
    return {"receipt_pk": item["receipts"][0]["financial_receipt_pk"], "receipt_number": full["receipt_number"],
            "txn_pk": client.get(f"{BASE}/transactions", params={"q": full["transaction_reference"]}, headers=admin_h).json()["items"][0]["financial_transaction_pk"],
            "request": full}


@pytest.fixture
def paid(client, admin_h, register_org_pk, mock_gateway, plain_member_h):
    u = upi_world(client, admin_h, register_org_pk, mock_gateway)
    return {**paid_receipt(client, admin_h, mock_gateway, plain_member_h, u["head"]), "world": u}


def mine(pk) -> str:
    return f"{BASE}/my-pranami/receipts/{pk}/pdf"


class TestTheMemberDownloadsTheirOwnReceipt:
    def test_a_paid_payment_has_a_pdf_receipt_with_the_details(self, client, paid, plain_member, plain_member_h, register_org_pk):
        r = client.get(mine(paid["receipt_pk"]), headers=plain_member_h)
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF-1.4")
        assert r.headers["content-disposition"] == f'attachment; filename="NSS-Receipt-{paid["receipt_number"]}.pdf"'
        assert r.headers["cache-control"] == "no-store"
        text = page_text(r.content)
        for needle in ("NILACHALA SARASWATA SANGHA", "PAYMENT RECEIPT", paid["receipt_number"], plain_member["sangha_sevi_id"],
                       "UPI Pranami", "Rs. 300.00", "Rupees Three Hundred Only", "UPI", paid["request"]["transaction_reference"], "PAID"):
            assert needle in text, needle

    def test_the_receipt_can_be_downloaded_again_and_again(self, client, paid, plain_member_h):
        first = client.get(mine(paid["receipt_pk"]), headers=plain_member_h)
        second = client.get(mine(paid["receipt_pk"]), headers=plain_member_h)
        assert first.status_code == second.status_code == 200
        assert page_text(first.content).split("Generated on")[0] == page_text(second.content).split("Generated on")[0]

    def test_the_receipt_id_the_pranami_tab_uses_is_the_one_that_downloads(self, client, paid, plain_member_h):
        history = client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"]
        receipt = history[0]["receipts"][0]
        assert receipt["receipt_number"] == paid["receipt_number"]
        assert client.get(mine(receipt["financial_receipt_pk"]), headers=plain_member_h).status_code == 200

    def test_the_payment_panel_gets_the_receipt_id_when_the_payment_is_paid(self, client, paid, plain_member_h):
        done = client.get(f"{BASE}/my-pranami/requests/{paid['request']['upi_payment_request_pk']}", headers=plain_member_h).json()
        assert done["status"] == "PAID" and done["financial_receipt_pk"] == paid["receipt_pk"]
        assert client.get(mine(done["financial_receipt_pk"]), headers=plain_member_h).status_code == 200

    def test_the_receipt_names_where_the_money_went(self, client, paid, plain_member_h):
        text = page_text(client.get(mine(paid["receipt_pk"]), headers=plain_member_h).content)
        org = paid["world"]["head"]["organization_name"]
        assert org and org in text                                         # "Received by" the Sakha that owns the head

    def test_a_pending_payment_has_no_receipt_yet(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        r = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": u["head"]["finance_head_pk"], "amount": "10.00"}, headers=plain_member_h).json()
        assert r["receipt_number"] is None and r["financial_receipt_pk"] is None


class TestOnlyTheOwnerCanDownload:
    def test_another_member_gets_a_404(self, client, paid, write_conn, register_org_pk):
        other = new_member(write_conn, register_org_pk, "FinPdfOther")
        h = _login_headers(client, other["sangha_sevi_id"], other["password"])
        assert client.get(mine(paid["receipt_pk"]), headers=h).status_code == 404

    def test_an_administrator_is_not_the_owner_either(self, client, paid, admin_h):
        assert client.get(mine(paid["receipt_pk"]), headers=admin_h).status_code == 404       # admins use the admin route below

    def test_no_login_is_401(self, client, paid):
        assert client.get(mine(paid["receipt_pk"])).status_code == 401

    def test_unknown_and_malformed_ids(self, client, plain_member_h):
        assert client.get(mine(FAKE_UUID), headers=plain_member_h).status_code == 404
        assert client.get(f"{BASE}/my-pranami/receipts/not-a-uuid/pdf", headers=plain_member_h).status_code == 422


class TestAdministrators:
    def admin_url(self, pk) -> str:
        return f"{BASE}/receipts/{pk}/pdf"

    def test_an_administrator_with_scope_downloads_it(self, client, paid, admin_h, sakha_admin_h, viewer_h):
        for headers in (admin_h, sakha_admin_h, viewer_h):                  # FINANCE_VIEW inside the Sakha is enough
            r = client.get(self.admin_url(paid["receipt_pk"]), headers=headers)
            assert r.status_code == 200 and r.content.startswith(b"%PDF"), r.status_code

    def test_the_same_content_as_the_member_gets(self, client, paid, admin_h, plain_member_h):
        a = page_text(client.get(self.admin_url(paid["receipt_pk"]), headers=admin_h).content).split("Generated on")[0]
        m = page_text(client.get(mine(paid["receipt_pk"]), headers=plain_member_h).content).split("Generated on")[0]
        assert a == m

    def test_another_sakhas_admin_and_a_member_are_refused(self, client, paid, other_admin_h, plain_member_h):
        assert client.get(self.admin_url(paid["receipt_pk"]), headers=other_admin_h).status_code == 403
        assert client.get(self.admin_url(paid["receipt_pk"]), headers=plain_member_h).status_code == 403
        assert client.get(self.admin_url(paid["receipt_pk"])).status_code == 401

    def test_unknown_receipt(self, client, admin_h):
        assert client.get(self.admin_url(FAKE_UUID), headers=admin_h).status_code == 404


class TestCancelledAndDraftReceipts:
    def test_a_cancelled_receipt_is_stamped_for_the_admin_and_gone_for_the_member(self, client, paid, admin_h, plain_member_h):
        move(client, admin_h, "receipts", paid["receipt_pk"], "CANCELLED", remarks="Entered twice")
        text = page_text(client.get(f"{BASE}/receipts/{paid['receipt_pk']}/pdf", headers=admin_h).content)
        assert text.count("CANCELLED") >= 3 and "Entered twice" in text and "not valid" in text
        assert client.get(mine(paid["receipt_pk"]), headers=plain_member_h).status_code == 404

    def test_a_draft_receipt_is_not_downloadable_until_it_is_issued(self, client, paid, admin_h, plain_member_h):
        move(client, admin_h, "receipts", paid["receipt_pk"], "CANCELLED", remarks="Replacing it")
        draft = client.post(f"{BASE}/transactions/{paid['txn_pk']}/receipts", json={"receipt_date": paid["request"]["paid_at"][:10], "amount": "300.00"}, headers=admin_h)
        assert draft.status_code == 201, draft.text
        pk = draft.json()["financial_receipt_pk"]
        assert client.get(f"{BASE}/receipts/{pk}/pdf", headers=admin_h).status_code == 422
        assert client.get(mine(pk), headers=plain_member_h).status_code == 404
        move(client, admin_h, "receipts", pk, "ISSUED")
        assert client.get(f"{BASE}/receipts/{pk}/pdf", headers=admin_h).status_code == 200
        assert client.get(mine(pk), headers=plain_member_h).status_code == 200
