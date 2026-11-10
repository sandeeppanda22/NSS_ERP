"""
NSS ERP — Bye-Law disbursement controls for Kendra and central Mahila Sangha money.

ONE home for the rules that decide HOW money may leave those two bodies, so the
payment and transfer endpoints share a single implementation:

  KENDRA  NSS Bye-Law F[b], F[c](i)-(v), F[A](vi), Duties of the Treasurer (7)(b)
          1. the Governing Body approves the scheme (resolution reference + date)
          2. the PRESIDENT gives a written order for it
          3. the TREASURER disburses; funds are operated JOINTLY with the
             SECRETARY, so a second, different office-bearer countersigns
          4. the money goes only to a permitted purpose (F[c](ii)-(v))
  MAHILA  Mahila Sangha Bye-Law 7(ii), 7(iii): no President's order, but a
          Governing Body resolution for every item (7(iii)(i)), consultation
          with the Parichalak (7(iii)(a)), a permitted purpose, and joint
          operation by the Treasurer and the Secretary.

Every other level (Anchalika, Zilla, Sakha, events) has NO rule here: its
authorization matrix is PENDING (FIN-BR-044) and must not be invented from the
Kendra rules, so ``basis_for_org`` returns None and nothing is enforced.

The steps stay SEPARATE (FIN-BR-040): scheme approval, the President's order
and the Treasurer's disbursement are three recorded facts, never one generic
approval. The Treasurer / Secretary / President are the office-bearers
CURRENTLY seated (acting cover counts) — the Bye-Law gives the power to the
office, not to a permission or to the super administrator, so there is no
override: a vacant seat blocks the disbursement until it is filled.

Tables: nss.finance_disbursement_authority (ddl/14_finance/13_...). Purposes:
master_data category DISBURSEMENT_PURPOSE (KENDRA_* / MAHILA_* prefix).
"""

from datetime import date

from fastapi import HTTPException, status

from api.helpers import CENTRAL_MAHILA_ORG_TYPE, CENTRAL_MAHILA_PARENT_TYPE
from api.services import seat_service

KENDRA, MAHILA = "KENDRA", "MAHILA"

# The governing body whose officers sign, per Bye-Law (NSS-wide, no organization).
BODY_TYPE = {KENDRA: "KENDRA_GOVERNING_BODY", MAHILA: "MAHILA_PARICHALANA_MANDALI"}
BODY_LABEL = {KENDRA: "Kendra Governing Body", MAHILA: "Mahila Sangha Governing Body"}

PURPOSE_CATEGORY = "DISBURSEMENT_PURPOSE"
# F[A](vi): publication money is spent "in consultation with the Parichalak".
PARICHALAK_PURPOSES = frozenset({"KENDRA_SATSIKSHYA_BISTAR"})

# Which lifecycle step is the disbursement, per kind: moving to START is the
# Treasurer's act; moving to FINISH needs the Secretary's countersignature too.
# The statuses an authority may be edited / countersigned in:
KIND_STEPS = {
    "payment": {"start": "INITIATED", "finish": "COMPLETED", "open": ("DRAFT", "APPROVED")},
    "transfer": {"start": "EXECUTED", "finish": "COMPLETED", "open": ("DRAFT", "PENDING_APPROVAL", "APPROVED")},
}
_TARGET_COLUMN = {"payment": "financial_payment_pk", "transfer": "financial_transfer_pk"}

_COLUMNS = """
    a.finance_disbursement_authority_pk, a.financial_payment_pk, a.financial_transfer_pk, a.bye_law_basis,
    a.resolution_reference, a.resolution_date, a.scheme_description,
    md.value_code AS purpose_code, md.value_name AS purpose_name, a.parichalak_consulted,
    a.president_order_reference, a.president_order_date, a.president_person_pk,
    a.treasurer_person_pk, a.treasurer_signed_at, a.secretary_person_pk, a.secretary_signed_at
"""


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


# ═══════════════════════════════════════════════════════════════════════
# Which Bye-Law governs this money?
# ═══════════════════════════════════════════════════════════════════════

def basis_for_org(cur, organization_pk) -> str | None:
    """KENDRA for the Kendra Sangha, MAHILA for the central Mahila Sangha (a MAHILA_SANGHA whose
    parent is the Kendra), otherwise None (FIN-BR-044: no rule is invented for other levels)."""
    if organization_pk is None:
        return None
    cur.execute(
        """
        SELECT md.value_code, pmd.value_code
          FROM nss.organization o
          JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
          LEFT JOIN nss.organization po ON po.organization_pk = o.parent_organization_pk
          LEFT JOIN nss.master_data pmd ON pmd.master_data_pk = po.organization_type_master_data_pk
         WHERE o.organization_pk = %s
        """,
        (str(organization_pk),),
    )
    row = cur.fetchone()
    if row is None:
        return None
    org_type, parent_type = row
    if org_type == "KENDRA":
        return KENDRA
    if org_type == CENTRAL_MAHILA_ORG_TYPE and parent_type == CENTRAL_MAHILA_PARENT_TYPE:
        return MAHILA
    return None


def seat_holder(cur, basis: str, position_code: str) -> str | None:
    """person_pk of whoever CURRENTLY sits in *position_code* on the governing body of *basis*, else None."""
    body_pk = seat_service.find_body_master_pk(cur, BODY_TYPE[basis], None)
    if body_pk is None:
        return None
    holder = seat_service.live_seat_holder(cur, body_pk, position_code)
    return holder[0] if holder else None


def _require_seated(cur, basis: str, position_code: str, label: str) -> str:
    holder = seat_holder(cur, basis, position_code)
    if holder is None:
        raise _invalid(f"The {label} seat of the {BODY_LABEL[basis]} is vacant; the Bye-Law gives this power to that office, so it cannot proceed.")
    return holder


# ═══════════════════════════════════════════════════════════════════════
# Reading
# ═══════════════════════════════════════════════════════════════════════

def load(cur, kind: str, pk) -> dict | None:
    cur.execute(
        f"""
        SELECT {_COLUMNS}
          FROM nss.finance_disbursement_authority a
          JOIN nss.master_data md ON md.master_data_pk = a.purpose_master_data_pk
         WHERE a.{_TARGET_COLUMN[kind]} = %s AND a.is_active = TRUE
        """,
        (str(pk),),
    )
    row = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], row)) if row else None


def purposes(cur, basis: str | None = None) -> list[dict]:
    """Permitted purposes (admin-extendable master_data); *basis* limits them to the Bye-Law's prefix."""
    cur.execute(
        """
        SELECT md.value_code, md.value_name
          FROM nss.master_data md
          JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
         WHERE mc.category_code = %s AND md.is_active = TRUE
         ORDER BY md.display_order, md.value_name
        """,
        (PURPOSE_CATEGORY,),
    )
    rows = [{"code": c, "name": n} for c, n in cur.fetchall()]
    return [r for r in rows if basis is None or r["code"].startswith(f"{basis}_")]


def requirements(basis: str) -> list[str]:
    """Plain-language list of what the Bye-Law demands, for the UI and the API response."""
    steps = [
        "Governing Body resolution approving the scheme (reference and date)",
        "A permitted purpose",
    ]
    if basis == KENDRA:
        steps.append("The President's written order (Treasurer duty 7(b))")
    else:
        steps.append("Consultation with the Parichalak (Mahila Bye-Law 7(iii)(a))")
    steps += ["Disbursement by the Treasurer", "Countersignature by the Secretary (funds are operated jointly)"]
    return steps


def describe(cur, kind: str, pk, basis: str | None, status_now: str) -> dict:
    """The state of the controls for one payment / transfer: whether they apply, the record, what is missing."""
    if basis is None:
        return {"applies": False, "bye_law_basis": None, "requirements": [], "authority": None, "next_step": None,
                "note": "No Bye-Law disbursement rule applies to this level (authorization matrix PENDING, FIN-BR-044)."}
    auth = load(cur, kind, pk)
    steps = KIND_STEPS[kind]
    if auth is None:
        nxt = "Record the Governing Body resolution" + (" and the President's order" if basis == KENDRA else "")
    elif auth["treasurer_signed_at"] is None:
        nxt = f"The Treasurer disburses ({steps['start']})"
    elif auth["secretary_signed_at"] is None:
        nxt = "The Secretary countersigns"
    else:
        nxt = None
    return {"applies": True, "bye_law_basis": basis, "requirements": requirements(basis), "authority": auth,
            "next_step": nxt, "status": status_now}


# ═══════════════════════════════════════════════════════════════════════
# Writing the authority (steps 1 and 2)
# ═══════════════════════════════════════════════════════════════════════

def _purpose_pk(cur, basis: str, code: str) -> str:
    code = (code or "").strip().upper()
    if not code.startswith(f"{basis}_"):
        raise _invalid(f"The purpose must be one permitted for the {BODY_LABEL[basis]} (code starting {basis}_).")
    cur.execute(
        """
        SELECT md.master_data_pk
          FROM nss.master_data md JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
         WHERE mc.category_code = %s AND md.value_code = %s AND md.is_active = TRUE
        """,
        (PURPOSE_CATEGORY, code),
    )
    row = cur.fetchone()
    if row is None:
        raise _invalid(f"Unknown disbursement purpose '{code}'.")
    return str(row[0])


def record(cur, actor_pk, kind: str, pk, basis: str, status_now: str, data: dict) -> None:
    """Create or replace the resolution / purpose / President's-order facts. Locked once the Treasurer has signed."""
    steps = KIND_STEPS[kind]
    if status_now not in steps["open"]:
        raise _invalid(f"The authority can no longer be changed: the {kind} is {status_now}.")
    existing = load(cur, kind, pk)
    if existing and existing["treasurer_signed_at"] is not None:
        raise _invalid("The Treasurer has already signed; the authority can no longer be changed.")

    reference = (data.get("resolution_reference") or "").strip()
    scheme = (data.get("scheme_description") or "").strip()
    if not reference or not scheme:
        raise _invalid("The Governing Body resolution reference and the scheme description are required (Bye-Law F[c](i), Mahila 7(iii)(i)).")
    resolution_date = data["resolution_date"]
    today = date.today()
    if resolution_date > today:
        raise _invalid("The resolution date cannot be in the future.")
    purpose_code = (data.get("purpose_code") or "").strip().upper()
    purpose_pk = _purpose_pk(cur, basis, purpose_code)

    consulted = bool(data.get("parichalak_consulted"))
    if basis == MAHILA or purpose_code in PARICHALAK_PURPOSES:
        if not consulted:
            raise _invalid("The Bye-Law requires consultation with the Parichalak for this expenditure (Mahila 7(iii)(a); NSS F[A](vi)).")

    order_ref = order_date = president = None
    if basis == KENDRA:
        order_ref = (data.get("president_order_reference") or "").strip()
        order_date = data.get("president_order_date")
        if not order_ref or order_date is None:
            raise _invalid("The President's written order (reference and date) is required before the Treasurer may disburse (Bye-Law, Treasurer duty 7(b)).")
        if order_date < resolution_date:
            raise _invalid("The President's order cannot predate the resolution it executes.")
        if order_date > today:
            raise _invalid("The order date cannot be in the future.")
        president = _require_seated(cur, KENDRA, "PRESIDENT", "President")

    values = (basis, reference, resolution_date, scheme, purpose_pk, consulted, order_ref, order_date, president)
    if existing:
        cur.execute(
            """
            UPDATE nss.finance_disbursement_authority
               SET bye_law_basis = %s, resolution_reference = %s, resolution_date = %s, scheme_description = %s,
                   purpose_master_data_pk = %s, parichalak_consulted = %s, president_order_reference = %s,
                   president_order_date = %s, president_person_pk = %s, updated_at = NOW(), updated_by_sangha_sevi_pk = %s
             WHERE finance_disbursement_authority_pk = %s
            """,
            values + (actor_pk, str(existing["finance_disbursement_authority_pk"])),
        )
    else:
        cur.execute(
            f"""
            INSERT INTO nss.finance_disbursement_authority
                (bye_law_basis, resolution_reference, resolution_date, scheme_description, purpose_master_data_pk,
                 parichalak_consulted, president_order_reference, president_order_date, president_person_pk,
                 {_TARGET_COLUMN[kind]}, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            values + (str(pk), actor_pk),
        )


# ═══════════════════════════════════════════════════════════════════════
# Signing (step 3) — called from the transition endpoints and /countersign
# ═══════════════════════════════════════════════════════════════════════

def _complete_or_raise(cur, kind: str, pk, basis: str) -> dict:
    auth = load(cur, kind, pk)
    if auth is None:
        raise _invalid(
            "Money of the " + BODY_LABEL[basis] + " can leave only on a Governing Body resolution"
            + (" and the President's written order" if basis == KENDRA else "")
            + ". Record the authority first (FIN-BR-040)."
        )
    return auth


def enforce_transition(cur, actor_person_pk, kind: str, pk, org_pk, current: str, target: str) -> None:
    """Gate a payment / transfer status change. No-op for levels without a Bye-Law rule or for steps that move
    no money. Moving to the START status is the Treasurer's act and stamps their signature; moving to FINISH
    needs the Secretary's countersignature too."""
    steps = KIND_STEPS[kind]
    if target not in (steps["start"], steps["finish"]):
        return
    basis = basis_for_org(cur, org_pk)
    if basis is None:
        return
    auth = _complete_or_raise(cur, kind, pk, basis)
    if target == steps["start"]:
        treasurer = _require_seated(cur, basis, "TREASURER", "Treasurer")
        if str(actor_person_pk) != treasurer:
            raise _forbidden(f"Only the {BODY_LABEL[basis]} Treasurer may disburse these funds (Bye-Law: Treasurer duty 7(b), F[b]).")
        if auth["secretary_person_pk"] is not None and str(auth["secretary_person_pk"]) == treasurer:
            raise _invalid("The Treasurer and the Secretary must be different office-bearers.")
        cur.execute(
            "UPDATE nss.finance_disbursement_authority SET treasurer_person_pk = %s, treasurer_signed_at = NOW(), "
            "updated_at = NOW() WHERE finance_disbursement_authority_pk = %s",
            (treasurer, str(auth["finance_disbursement_authority_pk"])),
        )
    else:
        if auth["treasurer_signed_at"] is None or auth["secretary_signed_at"] is None:
            raise _invalid("Funds are operated jointly: both the Treasurer and the Secretary must have signed before this can be completed (Bye-Law F[b], Mahila 7(ii)).")


def countersign(cur, actor_person_pk, kind: str, pk, org_pk, status_now: str) -> None:
    """The Secretary's countersignature, after the Treasurer has disbursed."""
    basis = basis_for_org(cur, org_pk)
    if basis is None:
        raise _invalid("No Bye-Law joint-operation rule applies to this level.")
    steps = KIND_STEPS[kind]
    if status_now != steps["start"]:
        raise _invalid(f"The Secretary countersigns once the {kind} is {steps['start']}; this one is {status_now}.")
    auth = _complete_or_raise(cur, kind, pk, basis)
    if auth["treasurer_signed_at"] is None:
        raise _invalid("The Treasurer has not signed yet.")
    if auth["secretary_signed_at"] is not None:
        raise _invalid("The Secretary has already countersigned.")
    secretary = _require_seated(cur, basis, "SECRETARY", "Secretary")
    if str(actor_person_pk) != secretary:
        raise _forbidden(f"Only the {BODY_LABEL[basis]} Secretary may countersign (Bye-Law F[b], Mahila 7(ii)).")
    if str(auth["treasurer_person_pk"]) == secretary:
        raise _invalid("The Treasurer and the Secretary must be different office-bearers.")
    cur.execute(
        "UPDATE nss.finance_disbursement_authority SET secretary_person_pk = %s, secretary_signed_at = NOW(), "
        "updated_at = NOW() WHERE finance_disbursement_authority_pk = %s",
        (secretary, str(auth["finance_disbursement_authority_pk"])),
    )
