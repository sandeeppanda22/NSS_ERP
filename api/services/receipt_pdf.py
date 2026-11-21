"""
NSS ERP — the downloadable PDF receipt of a payment made in the app (owner request 2026-11-17).

One implementation for every receipt: the member downloads their own (from the Pranami tab, any time) and an administrator downloads
any receipt of their scope. ``build_receipt_pdf`` takes plain data (see ``RECEIPT_FIELDS``) and returns the PDF bytes: the NSS logo, the
Sangha's name, a clearly numbered "Payment Receipt", who paid, what for, how much (in figures and in words, Indian numbering), the
mode and reference, who received it, and the footer that says it is computer-generated. A CANCELLED receipt is stamped.

The receipt is drawn from the stored financial_receipt / financial_transaction rows only; it never invents a field. Amounts are
written "Rs." because the standard PDF fonts have no rupee sign.
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from api.services import simple_pdf as pdf

LOGO_PATH = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "img" / "nss-logo-receipt.jpg"
LOGO_SIZE_PX = (520, 472)

ORG_NAME = "NILACHALA SARASWATA SANGHA"
ORG_PLACE = "Puri, Odisha"
# Quoted from the Bye-Law transcript (docs/01_Authoritative_References/NSS): "Nilachala Saraswata Sangha, Puri, vide Regn. No. 7391/390 of 1973-74".
ORG_REGISTRATION = "Regd. No. 7391/390 of 1973-74"

NAVY, GOLD, GREY, LIGHT, RED = "#1B2A4A", "#C8962E", "#6B7280", "#F3F4F6", "#B91C1C"

RECEIPT_FIELDS = (
    "receipt_number", "receipt_date", "amount", "status", "received_from", "sangha_sevi_id", "member_sangha", "head_name",
    "year_code", "payment_method_name", "instrument_reference", "received_by", "transaction_reference", "cancellation_reason",
)

_ONES = ("", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen",
         "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen")
_TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")


def _below_hundred(n: int) -> str:
    return _ONES[n] if n < 20 else (_TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else ""))


def _below_thousand(n: int) -> str:
    head, rest = divmod(n, 100)
    return " ".join(p for p in (f"{_ONES[head]} Hundred" if head else "", _below_hundred(rest) if rest else "") if p)


def amount_in_words(amount: Decimal) -> str:
    """'Rupees One Lakh Twenty Three Thousand Four Hundred Fifty Six and Fifty Paise Only' (Indian grouping; up to 99,99,99,999)."""
    amount = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount < 0:
        raise ValueError("amount must not be negative")
    rupees, paise = divmod(int(amount * 100), 100)
    if rupees >= 10 ** 11:
        raise ValueError("amount too large")
    parts = []
    for value, name in ((10 ** 7, "Crore"), (10 ** 5, "Lakh"), (1000, "Thousand")):
        chunk, rupees = divmod(rupees, value)
        if chunk:
            parts.append(f"{_below_hundred(chunk) if chunk < 100 else _below_thousand(chunk)} {name}")
    if rupees:
        parts.append(_below_thousand(rupees))
    words = " ".join(parts) or "Zero"
    tail = f" and {_below_hundred(paise)} Paise" if paise else ""
    return f"Rupees {words}{tail} Only"


def money(amount: Decimal) -> str:
    """'Rs. 1,23,456.50' - Indian digit grouping."""
    amount = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole, frac = f"{amount:.2f}".split(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"Rs. {sign}{whole}.{frac}"


def _date(d) -> str:
    if isinstance(d, (datetime, date)):
        return f"{d.day} {d.strftime('%b %Y')}"
    return str(d or "")


def _logo() -> bytes | None:
    try:
        return LOGO_PATH.read_bytes()
    except OSError:
        return None                                   # a missing logo must never stop a receipt being issued


def _now_ist(now: datetime | None) -> datetime:
    return (now or datetime.now(ZoneInfo("Asia/Kolkata"))).astimezone(ZoneInfo("Asia/Kolkata"))


def _page_with_header(doc, title: str):
    """A new A4 page with the double frame, the logo + Sangha heading and the navy title bar. Returns (page, left, right, width).
    Shared by the receipt and the payment summary so the two always look like one family."""
    page = doc.add_page()
    left, right = 48.0, pdf.A4[0] - 48.0
    width = right - left
    page.rect(26, 26, pdf.A4[0] - 52, pdf.A4[1] - 52, stroke=NAVY, line=1.2)
    page.rect(30, 30, pdf.A4[0] - 60, pdf.A4[1] - 60, stroke=GOLD, line=0.5)
    logo = _logo()
    if logo:
        page.image("Logo", logo, LOGO_SIZE_PX[0], LOGO_SIZE_PX[1], left, 52, 76, 69)
    text_x = left + 92
    page.text(text_x, 82, ORG_NAME, font="bold", size=19, colour=NAVY)
    page.text(text_x, 99, ORG_PLACE, size=10.5, colour=GREY)
    page.text(text_x, 113, ORG_REGISTRATION, size=9, colour=GREY)
    page.line(left, 134, right, 134, GOLD, 1.5)
    page.rect(left, 146, width, 30, fill=NAVY)
    page.text(left + width / 2, 166, title, font="bold", size=14, colour="#FFFFFF", align="center")
    return page, left, right, width


def _page_footer(page, left, right, now, *, line1: str, label: str) -> None:
    foot = pdf.A4[1] - 92
    page.line(left, foot, right, foot, "#D1D5DB", 0.6)
    page.text(left, foot + 16, line1, size=8.5, colour=GREY)
    page.text(left, foot + 29, f"Generated on {_date(now)}, {now.strftime('%H:%M')} IST from the NSS ERP. Keep it for your records.", size=8.5, colour=GREY)
    page.text(right, foot + 16, label, font="bold", size=8.5, colour=GREY, align="right")


def build_receipt_pdf(data: dict, *, now: datetime | None = None) -> bytes:
    """The receipt as PDF bytes. *data* has the keys of ``RECEIPT_FIELDS`` (missing / None ones are simply left off)."""
    missing = [k for k in ("receipt_number", "receipt_date", "amount") if data.get(k) in (None, "")]
    if missing:
        raise ValueError(f"receipt data is missing {', '.join(missing)}")
    now = _now_ist(now)
    cancelled = data.get("status") == "CANCELLED"
    number = str(data["receipt_number"])

    doc = pdf.Document(title=f"Payment Receipt {number}", author=ORG_NAME.title(), subject="Payment receipt")
    page, left, right, width = _page_with_header(doc, "PAYMENT RECEIPT")

    # receipt number + date
    page.text(left, 204, "Receipt No.", size=9, colour=GREY)
    page.text(left, 220, number, font="bold", size=14, colour=NAVY)
    page.text(right, 204, "Date", size=9, colour=GREY, align="right")
    page.text(right, 220, _date(data["receipt_date"]), font="bold", size=13, colour=NAVY, align="right")

    # details
    rows = [
        ("Received with thanks from", data.get("received_from")),
        ("Sangha Sevi ID", data.get("sangha_sevi_id")),
        ("Member of", data.get("member_sangha")),
        ("Towards", data.get("head_name")),
        ("Financial year", data.get("year_code")),
        ("Payment mode", data.get("payment_method_name")),
        ("Payment reference", data.get("instrument_reference")),
        ("Received by", data.get("received_by")),
        ("Transaction reference", data.get("transaction_reference")),
    ]
    rows = [(label, str(value)) for label, value in rows if value not in (None, "")]
    y = 244.0
    label_w = 150.0
    page.line(left, y, right, y, "#D1D5DB", 0.6)
    for label, value in rows:
        lines = pdf.wrap(value, "bold", 11, width - label_w - 12)
        h = max(30.0, 16.0 + 14.0 * len(lines))
        page.text(left + 6, y + 19, label, size=9.5, colour=GREY)
        for i, line in enumerate(lines):
            page.text(left + label_w, y + 19 + 14 * i, line, font="bold", size=11, colour="#111827")
        y += h
        page.line(left, y, right, y, "#E5E7EB", 0.5)

    # amount
    y += 18
    words = pdf.wrap(amount_in_words(data["amount"]), "regular", 10.5, width - 28)
    box_h = 64 + 14 * len(words)
    page.rect(left, y, width, box_h, fill=LIGHT, stroke=GOLD, line=1)
    page.text(left + 14, y + 20, "AMOUNT RECEIVED", font="bold", size=9, colour=GREY)
    page.text(left + 14, y + 46, money(data["amount"]), font="bold", size=24, colour=NAVY)
    for i, line in enumerate(words):
        page.text(left + 14, y + 66 + 14 * i, line, size=10.5, colour="#374151")
    # status stamp on the right of the amount box
    stamp, colour = ("CANCELLED", RED) if cancelled else ("PAID", "#047857")
    sw = pdf.text_width(stamp, "bold", 13) + 28
    page.rect(right - sw - 14, y + 18, sw, 28, stroke=colour, line=1.6)
    page.text(right - 14 - sw / 2, y + 37, stamp, font="bold", size=13, colour=colour, align="center")
    y += box_h + 22

    if cancelled:
        reason = data.get("cancellation_reason")
        page.text(left, y, "This receipt has been CANCELLED and is not valid." + (f" Reason: {reason}" if reason else ""), font="bold", size=10, colour=RED)
        y += 18

    if not cancelled:
        page.text(left, y, "Thank you for your contribution to the Sangha.", size=10.5, colour=NAVY)

    _page_footer(page, left, right, now, line1="This is a computer-generated receipt and does not require a signature.", label=f"Receipt {number}")

    if cancelled:
        page.rotated_text(pdf.A4[0] / 2, pdf.A4[1] / 2 - 20, "CANCELLED", size=96, colour=RED, degrees=33, opacity=0.15)
    return doc.render()


SUMMARY_FIELDS = ("request_reference", "paid_at", "paid_amount", "received_from", "sangha_sevi_id", "member_sangha", "paid_to",
                  "payment_method_name", "provider_payment_id")


def build_payment_summary_pdf(data: dict, items: list[dict], *, now: datetime | None = None) -> bytes:
    """
    One page that lists a payment made in ONE go for several contributions (owner request 2026-11-20): who paid, to whom, how, the total and,
    for each contribution, what it was for, its amount and its OWN receipt number. It is a printout only - it carries no receipt number of
    its own and says so, so the books and the receipt numbering are untouched. *items* are dicts with head_name, amount, receipt_number.
    """
    missing = [k for k in ("request_reference", "paid_amount") if data.get(k) in (None, "")]
    if missing:
        raise ValueError(f"payment data is missing {', '.join(missing)}")
    if not items:
        raise ValueError("a payment summary needs at least one item")
    now = _now_ist(now)
    ref = str(data["request_reference"])
    doc = pdf.Document(title=f"Payment Summary {ref}", author=ORG_NAME.title(), subject="Payment summary")
    page, left, right, width = _page_with_header(doc, "PAYMENT SUMMARY")

    page.text(left, 204, "Payment reference", size=9, colour=GREY)
    page.text(left, 220, ref, font="bold", size=14, colour=NAVY)
    page.text(right, 204, "Paid on", size=9, colour=GREY, align="right")
    page.text(right, 220, _date(data.get("paid_at")), font="bold", size=13, colour=NAVY, align="right")

    rows = [("Paid by", data.get("received_from")), ("Sangha Sevi ID", data.get("sangha_sevi_id")), ("Member of", data.get("member_sangha")),
            ("Paid to", data.get("paid_to")), ("Payment mode", data.get("payment_method_name")), ("Gateway reference", data.get("provider_payment_id"))]
    rows = [(label, str(value)) for label, value in rows if value not in (None, "")]
    y, label_w = 244.0, 150.0
    page.line(left, y, right, y, "#D1D5DB", 0.6)
    for label, value in rows:
        lines = pdf.wrap(value, "bold", 11, width - label_w - 12)
        h = max(28.0, 14.0 + 14.0 * len(lines))
        page.text(left + 6, y + 18, label, size=9.5, colour=GREY)
        for i, line in enumerate(lines):
            page.text(left + label_w, y + 18 + 14 * i, line, font="bold", size=11, colour="#111827")
        y += h
        page.line(left, y, right, y, "#E5E7EB", 0.5)

    # the contributions: # | towards | receipt no. | amount
    y += 18
    col_head, col_rcpt, col_amt = left + 28, left + 270, right - 8
    page.rect(left, y, width, 22, fill=LIGHT)
    page.text(left + 8, y + 15, "#", font="bold", size=9, colour=GREY)
    page.text(col_head, y + 15, "TOWARDS", font="bold", size=9, colour=GREY)
    page.text(col_rcpt, y + 15, "RECEIPT NO.", font="bold", size=9, colour=GREY)
    page.text(col_amt, y + 15, "AMOUNT", font="bold", size=9, colour=GREY, align="right")
    y += 22
    for n, it in enumerate(items, 1):
        lines = pdf.wrap(str(it.get("head_name") or ""), "regular", 10.5, col_rcpt - col_head - 10)
        h = max(24.0, 10.0 + 14.0 * len(lines))
        page.text(left + 8, y + 16, str(n), size=10.5, colour=GREY)
        for i, line in enumerate(lines):
            page.text(col_head, y + 16 + 14 * i, line, size=10.5, colour="#111827")
        page.text(col_rcpt, y + 16, str(it.get("receipt_number") or "-"), font="bold", size=10.5, colour=NAVY)
        page.text(col_amt, y + 16, money(it["amount"]), size=10.5, colour="#111827", align="right")
        y += h
        page.line(left, y, right, y, "#E5E7EB", 0.5)

    y += 16
    total_h = 60
    page.rect(left, y, width, total_h, fill=LIGHT, stroke=GOLD, line=1)
    page.text(left + 14, y + 20, "TOTAL PAID", font="bold", size=9, colour=GREY)
    page.text(left + 14, y + 46, money(data["paid_amount"]), font="bold", size=22, colour=NAVY)
    sw = pdf.text_width("PAID", "bold", 13) + 28
    page.rect(right - sw - 14, y + 16, sw, 28, stroke="#047857", line=1.6)
    page.text(right - 14 - sw / 2, y + 35, "PAID", font="bold", size=13, colour="#047857", align="center")
    y += total_h + 18
    for line in pdf.wrap("This is a summary of one payment, not a receipt and it carries no receipt number of its own: each contribution above has its own "
                         "numbered receipt, which you can download separately.", "regular", 9.5, width):
        page.text(left, y, line, size=9.5, colour="#374151")
        y += 13

    _page_footer(page, left, right, now, line1="This is a computer-generated summary and does not require a signature.", label=f"Payment {ref}")
    return doc.render()
