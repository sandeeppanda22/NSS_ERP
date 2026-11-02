"""
NSS ERP — Sakha re-parenting approval workflow (owner rule, 2026-10-30).

Re-parenting a Sakha or Sakha Asana (moving it under a different
Anchalika/Zilla Sangha — including the admin "Assign Sakha" action and the
initial move out of Kendra) must ALWAYS be approved, except when done by
  - a Kendra Governing Body member (UserContext.is_kendra_gb_member(): the §63
    auto-granted NSS_ERP_KENDRA_ADMIN composite scope, user_role_pk None), or
  - the NSS_ERP_ADMIN super administrator (UserContext.is_super_admin(), by
    role — owner 2026-10-30, supersedes the earlier "not exempt" decision),
who may do it directly (UserContext.can_reparent_sakha_directly()). A
role-assigned (non-GB) Kendra admin, scoped admins and office bearers get no
exemption. SAKHA_ASANA is treated exactly like SAKHA_SANGHA (owner: a Sakha
Asana is a Sakha Sangha without its own building — it has its own Governing
Body and President, so chain step 1 is resolved identically).

Chain (nss.organization_reparent_step) — owner decision 2026-10-31: "Sakha
President, then leaving Anchalika/Zilla President, then destination
Anchalika/Zilla President, then Kendra President":
  1  SAKHA_PRESIDENT          the moved Sakha's own President
  2  SOURCE_PARENT_PRESIDENT  the LEAVING (current) Anchalika/Zilla President —
                              does not exist (not a fallback, simply not
                              applicable) when the current parent is Kendra
                              (the unassigned flat state) or absent
  3  DEST_PARENT_PRESIDENT    the DESTINATION Anchalika/Zilla President
  4  KENDRA_PRESIDENT         the Kendra President (final)
A step with no governing body shell, no seated President (live seat incl. acting cover — see
seat_service), or whose seat the requester themself holds, is assigned to the
Kendra President instead — never auto-approved, never silently skipped.
Consecutive Kendra-President steps collapse into one. The Sakha's parent does
NOT change until the final step approves; apply_approved_reparent() then
re-validates and applies it atomically in the caller's transaction.

Approval authority (DECIDING a step) is the LIVE office seat only — no
NSS_ERP_ADMIN override, no permission-based override; the super-admin exemption
is only about skipping the chain by re-parenting directly. Shared by api/routers/admin.py (create /
supersede) and api/routers/org_reparent.py (list / detail / decide / cancel).
"""

from fastapi import HTTPException, status

from api.helpers import SAKHA_LIKE_ORG_TYPES, log_audit
from api.services.rbac_service import (
    UserContext,
    actor_scope_org_pks,
    org_subtree_pks,
)
from api.services.seat_service import (
    find_body_master_pk,
    live_seat_holder,
    person_holds_seat,
    seat_body_pks_held,
)

# Each org type can only have specific parent types — the frozen NSS Bye-Law
# hierarchy (docs/03_Solution/modules/organization/04_organization_business_rules.md).
# Lives here (moved from api/routers/admin.py, which re-exports it as
# _ALLOWED_PARENT_TYPES) so create, PATCH and the approved re-parent apply
# step enforce the exact same rule. See admin.py for the per-type rationale.
ALLOWED_PARENT_TYPES = {
    "ANCHALIKA_SANGHA": {"KENDRA"},
    "ZILLA_SANGHA": {"KENDRA"},
    "PATHA_CHAKRA": {"KENDRA"},
    "PARIBARIK_SANGHA": {"KENDRA"},
    "SAKHA_SANGHA": {"ANCHALIKA_SANGHA", "ZILLA_SANGHA"},
    "SAKHA_ASANA": {"ANCHALIKA_SANGHA", "ZILLA_SANGHA"},
    # Owner decision 2026-10-31 (GDR-008): a Sakha Asana hosts every wing a Sakha
    # Sangha can, so the wing parents are the shared Sakha-like set — never a
    # literal list (amends ORG-BR-091/092/094).
    "KUMARI_SANGHA": set(SAKHA_LIKE_ORG_TYPES),
    "SEVAK_SANGHA": set(SAKHA_LIKE_ORG_TYPES),
    # Two-tier by parent: KENDRA = the singleton central Mahila Sangha, a
    # Sakha-like parent = a local per-Sakha Mahila Sangha.
    "MAHILA_SANGHA": {"KENDRA", *SAKHA_LIKE_ORG_TYPES},
    "PARIBARIK_ASANA": set(SAKHA_LIKE_ORG_TYPES),
    # Singleton (owner decision 2026-10-30): seeded, never created; this entry
    # only constrains a parent reassignment through update_organization.
    "ADVISORY_BOARD": {"KENDRA"},
}

_GB_BODY_TYPE_BY_PARENT_TYPE = {
    "ANCHALIKA_SANGHA": "ANCHALIKA_GOVERNING_BODY",
    "ZILLA_SANGHA": "ZILLA_GOVERNING_BODY",
}

ROLE_SAKHA_PRESIDENT = "SAKHA_PRESIDENT"
ROLE_SOURCE_PARENT_PRESIDENT = "SOURCE_PARENT_PRESIDENT"
ROLE_DEST_PARENT_PRESIDENT = "DEST_PARENT_PRESIDENT"
ROLE_KENDRA_PRESIDENT = "KENDRA_PRESIDENT"

# Only presidents sit on this chain.
_POSITION = "PRESIDENT"


# ═══════════════════════════════════════════════════════════════════════
# Rule + target validation
# ═══════════════════════════════════════════════════════════════════════

def requires_approval(user: UserContext, org_type_code: str) -> bool:
    """The owner rule: a SAKHA_SANGHA/SAKHA_ASANA re-parent needs the approval
    chain unless the actor is a Kendra Governing Body member or the
    NSS_ERP_ADMIN super administrator. Every other org type is unaffected
    (direct, as before)."""
    return org_type_code in SAKHA_LIKE_ORG_TYPES and not user.can_reparent_sakha_directly()


def validate_reparent_target(cur, organization_pk, org_type_code: str, new_parent_pk) -> str:
    """
    Validate moving *organization_pk* (of *org_type_code*) under
    *new_parent_pk*; return the normalized parent pk. Raises 404/422 with the
    messages update_organization has always used. Shared by the direct PATCH,
    the request-creation path and the final apply (re-validation).
    """
    new_parent_pk = str(new_parent_pk).strip() if new_parent_pk else None
    allowed_parents = ALLOWED_PARENT_TYPES.get(org_type_code)
    if not allowed_parents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"'{org_type_code}' organizations cannot be re-parented through this endpoint.",
        )
    if not new_parent_pk:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"'{org_type_code}' requires a parent organization of type "
                   f"{', '.join(sorted(allowed_parents))}.",
        )
    if new_parent_pk == str(organization_pk):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="An organization cannot be its own parent.",
        )
    cur.execute(
        """
        SELECT md.value_code
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE o.organization_pk = %s AND o.is_active = TRUE
        """,
        (new_parent_pk,),
    )
    parent_row = cur.fetchone()
    if parent_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent organization not found.",
        )
    if parent_row[0] not in allowed_parents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"'{org_type_code}' can only have parent of type "
                   f"{', '.join(sorted(allowed_parents))}. Got '{parent_row[0]}'.",
        )
    if new_parent_pk in org_subtree_pks(cur, organization_pk):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="An organization cannot be re-parented under one of its own descendants.",
        )
    return new_parent_pk


# ═══════════════════════════════════════════════════════════════════════
# Chain construction
# ═══════════════════════════════════════════════════════════════════════

def collapse_consecutive_kendra_steps(steps: list[dict]) -> list[dict]:
    """
    Collapse each run of consecutive Kendra-President steps (``is_kendra``
    True) into its LAST member — which keeps that step's role (the final step
    is always KENDRA_PRESIDENT) and absorbs the earlier ones' fallback
    reasons. Pure function (no DB) so the rule is unit-testable.
    """
    out: list[dict] = []
    for step in steps:
        step = dict(step)
        if out and out[-1]["is_kendra"] and step["is_kendra"]:
            prev = out.pop()
            reasons = [r for r in (prev.get("fallback_reason"), step.get("fallback_reason")) if r]
            step["fallback_reason"] = "; ".join(reasons)[:300] or None
        out.append(step)
    return out


def _resolve_chain_step(cur, *, role, body_type_code, org_pk, label, requester_person_pk, kendra_body_pk, kendra_holder):
    """One non-final step: the org's own President, or the Kendra President
    fallback (no body / no seated President / the requester holds the seat)."""
    body_pk = find_body_master_pk(cur, body_type_code, org_pk)
    reason = None
    holder = None
    if body_pk is None:
        reason = f"{label}: no governing body"
    else:
        holder = live_seat_holder(cur, body_pk, _POSITION)
        if holder is None:
            reason = f"{label}: no seated President"
        elif person_holds_seat(cur, body_pk, requester_person_pk, _POSITION):
            reason = f"{label}: requester holds the seat"
    if reason is None:
        return {
            "role": role, "is_kendra": False, "organization_pk": org_pk,
            "body_master_pk": body_pk, "position_master_pk": holder[1],
            "person_pk": holder[0], "fallback_reason": None,
        }
    return {
        "role": role, "is_kendra": True, "organization_pk": None,
        "body_master_pk": kendra_body_pk, "position_master_pk": kendra_holder[1],
        "person_pk": kendra_holder[0], "fallback_reason": reason,
    }


def _org_type_code(cur, organization_pk) -> str | None:
    cur.execute(
        """
        SELECT md.value_code
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE o.organization_pk = %s
        """,
        (str(organization_pk),),
    )
    row = cur.fetchone()
    return row[0] if row else None


def build_approval_chain(cur, *, sakha_pk, dest_parent_pk, requester_person_pk, from_parent_pk=None) -> list[dict]:
    """
    The ordered approval steps for moving *sakha_pk* from *from_parent_pk*
    (its current parent; None/Kendra = no leaving Anchalika/Zilla step) under
    *dest_parent_pk* (see module docstring). Each step dict: role, organization_pk,
    body_master_pk, position_master_pk, person_pk, fallback_reason,
    is_kendra. Raises 422 if the Kendra Governing Body has no seated
    President — the final step can never be skipped or auto-approved.
    """
    kendra_body_pk = find_body_master_pk(cur, "KENDRA_GOVERNING_BODY", None)
    kendra_holder = live_seat_holder(cur, kendra_body_pk, _POSITION) if kendra_body_pk else None
    if kendra_holder is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The Kendra Governing Body has no seated President, so a Sakha re-parent "
                   "request cannot be routed for approval.",
        )

    dest_type = _org_type_code(cur, dest_parent_pk)
    dest_body_type = _GB_BODY_TYPE_BY_PARENT_TYPE.get(dest_type)

    common = dict(
        requester_person_pk=requester_person_pk,
        kendra_body_pk=kendra_body_pk, kendra_holder=kendra_holder,
    )
    steps = [
        _resolve_chain_step(
            cur, role=ROLE_SAKHA_PRESIDENT, body_type_code="SAKHA_GOVERNING_BODY",
            org_pk=str(sakha_pk), label="Sakha President", **common,
        ),
    ]
    # Step 2: the LEAVING Anchalika/Zilla President. Only exists when the current
    # parent is an Anchalika/Zilla (a Kendra/absent parent => not applicable).
    source_type = _org_type_code(cur, from_parent_pk) if from_parent_pk else None
    source_body_type = _GB_BODY_TYPE_BY_PARENT_TYPE.get(source_type)
    if source_body_type is not None:
        steps.append(
            _resolve_chain_step(
                cur, role=ROLE_SOURCE_PARENT_PRESIDENT, body_type_code=source_body_type,
                org_pk=str(from_parent_pk), label="Leaving parent President", **common,
            )
        )
    if dest_body_type is None:
        # validate_reparent_target() already restricts Sakha parents to
        # Anchalika/Zilla; kept defensive rather than silently skipping.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"No governing body type for destination parent type '{dest_type}'.",
        )
    steps.append(
        _resolve_chain_step(
            cur, role=ROLE_DEST_PARENT_PRESIDENT, body_type_code=dest_body_type,
            org_pk=str(dest_parent_pk), label="Destination parent President", **common,
        )
    )
    steps.append({
        "role": ROLE_KENDRA_PRESIDENT, "is_kendra": True, "organization_pk": None,
        "body_master_pk": kendra_body_pk, "position_master_pk": kendra_holder[1],
        "person_pk": kendra_holder[0], "fallback_reason": None,
    })
    return collapse_consecutive_kendra_steps(steps)


# ═══════════════════════════════════════════════════════════════════════
# Create / supersede / cancel / decide / apply
# ═══════════════════════════════════════════════════════════════════════

def open_request_pk(cur, sakha_pk) -> str | None:
    cur.execute(
        """
        SELECT organization_reparent_request_pk
        FROM nss.organization_reparent_request
        WHERE sakha_organization_pk = %s AND request_status = 'PENDING' AND is_active = TRUE
        """,
        (str(sakha_pk),),
    )
    row = cur.fetchone()
    return str(row[0]) if row else None


def _audit(cur, user: UserContext | None, *, action, table, pk, summary, detail=None):
    log_audit(
        cur, action=action, table_name=table, record_pk=str(pk),
        actor_pk=user.actor_pk if user else None,
        actor_user_account_pk=str(user.user_account_pk) if user else None,
        module="organization", summary=summary, detail=detail,
    )


def create_reparent_request(cur, user: UserContext, *, sakha_pk, to_parent_pk, reason: str | None) -> str:
    """
    File a re-parent request + its approval chain; the Sakha's parent is NOT
    changed. *to_parent_pk* must already be validated
    (validate_reparent_target). 409 if the Sakha already has an open request.
    Returns the new request pk.
    """
    if open_request_pk(cur, sakha_pk):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Sakha already has a re-parent request awaiting approval. "
                   "Cancel it or wait for its decision before filing another.",
        )
    cur.execute(
        "SELECT parent_organization_pk FROM nss.organization WHERE organization_pk = %s",
        (str(sakha_pk),),
    )
    from_parent_pk = cur.fetchone()[0]
    if from_parent_pk is not None and str(from_parent_pk) == str(to_parent_pk):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The Sakha is already under that parent.",
        )

    chain = build_approval_chain(
        cur, sakha_pk=sakha_pk, dest_parent_pk=to_parent_pk, requester_person_pk=user.person_pk,
        from_parent_pk=from_parent_pk,
    )
    cur.execute(
        """
        INSERT INTO nss.organization_reparent_request (
            sakha_organization_pk, from_parent_organization_pk, to_parent_organization_pk,
            requested_by_user_account_pk, requested_by_person_pk, requested_by_sangha_sevi_pk,
            request_reason, created_by_sangha_sevi_pk
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING organization_reparent_request_pk
        """,
        (
            str(sakha_pk), str(from_parent_pk) if from_parent_pk else None, str(to_parent_pk),
            str(user.user_account_pk), str(user.person_pk), user.actor_pk,
            (reason or "").strip() or None, user.actor_pk,
        ),
    )
    request_pk = str(cur.fetchone()[0])
    _audit(cur, user, action="CREATE", table="organization_reparent_request", pk=request_pk,
           summary="Sakha re-parent request filed (awaiting approval chain)")

    for order, step in enumerate(chain, start=1):
        cur.execute(
            """
            INSERT INTO nss.organization_reparent_step (
                organization_reparent_request_pk, step_order, step_role,
                assigned_organization_pk, assigned_body_master_pk, assigned_position_master_pk,
                assigned_person_pk, fallback_reason, created_by_sangha_sevi_pk
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING organization_reparent_step_pk
            """,
            (
                request_pk, order, step["role"], step["organization_pk"],
                step["body_master_pk"], step["position_master_pk"], step["person_pk"],
                step["fallback_reason"], user.actor_pk,
            ),
        )
        _audit(cur, user, action="CREATE", table="organization_reparent_step", pk=cur.fetchone()[0],
               summary=f"Step {order}: {step['role']}"
                       + (f" ({step['fallback_reason']})" if step["fallback_reason"] else ""))
    return request_pk


def _close_request(cur, request_pk, *, new_status, decided_by_person_pk, remarks, actor_user: UserContext | None):
    cur.execute(
        """
        UPDATE nss.organization_reparent_request
        SET request_status = %s, decided_at = NOW(), decided_by_person_pk = %s,
            decision_remarks = %s, updated_at = NOW(), updated_by_sangha_sevi_pk = %s
        WHERE organization_reparent_request_pk = %s
        """,
        (new_status, str(decided_by_person_pk) if decided_by_person_pk else None, remarks,
         actor_user.actor_pk if actor_user else None, str(request_pk)),
    )


def supersede_open_request(cur, user: UserContext, sakha_pk, *, remarks: str) -> str | None:
    """An exempt actor (Kendra GB member / NSS_ERP_ADMIN) changed the parent directly: close any open
    request for the Sakha as CANCELLED (system close) so it can never
    later overwrite the direct change. Returns the closed request pk."""
    pk = open_request_pk(cur, sakha_pk)
    if pk:
        _close_request(cur, pk, new_status="CANCELLED", decided_by_person_pk=None,
                       remarks=remarks, actor_user=user)
        _audit(cur, user, action="STATUS_CHANGE", table="organization_reparent_request", pk=pk,
               summary="Re-parent request cancelled (superseded by a direct Kendra GB change)")
    return pk


def cancel_request(cur, user: UserContext, request_pk, remarks: str | None) -> None:
    """Requester or an exempt actor (Kendra GB member / NSS_ERP_ADMIN) cancels a PENDING request."""
    cur.execute(
        """
        SELECT request_status, requested_by_person_pk
        FROM nss.organization_reparent_request
        WHERE organization_reparent_request_pk = %s AND is_active = TRUE
        FOR UPDATE
        """,
        (str(request_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Re-parent request not found.")
    if row[0] != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"This request is already {row[0]}.",
        )
    is_requester = str(row[1]) == str(user.person_pk)
    if not (is_requester or user.can_reparent_sakha_directly()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the requester, a Kendra Governing Body member or the NSS_ERP_ADMIN may cancel this request.",
        )
    _close_request(cur, request_pk, new_status="CANCELLED", decided_by_person_pk=user.person_pk,
                   remarks=(remarks or "").strip() or None, actor_user=user)
    _audit(cur, user, action="STATUS_CHANGE", table="organization_reparent_request", pk=request_pk,
           summary="Re-parent request cancelled")


def decide_step(cur, user: UserContext, request_pk, step_pk, decision: str, remarks: str | None) -> None:
    """
    Decide one step. Rules: request PENDING; step PENDING; every earlier step
    APPROVED; the caller currently holds the step's assigned seat (live, incl.
    acting cover — nothing else, no admin override); the caller is not the
    requester. REJECT closes the request REJECTED. APPROVE of the final step
    applies the parent change (apply_approved_reparent).
    """
    cur.execute(
        """
        SELECT request_status, requested_by_person_pk, sakha_organization_pk, to_parent_organization_pk
        FROM nss.organization_reparent_request
        WHERE organization_reparent_request_pk = %s AND is_active = TRUE
        FOR UPDATE
        """,
        (str(request_pk),),
    )
    req = cur.fetchone()
    if req is None:
        raise HTTPException(status_code=404, detail="Re-parent request not found.")
    req_status, requester_pk, sakha_pk, to_parent_pk = req
    if req_status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"This request is already {req_status}.",
        )

    cur.execute(
        """
        SELECT organization_reparent_step_pk, step_order, step_status,
               assigned_body_master_pk, step_role
        FROM nss.organization_reparent_step
        WHERE organization_reparent_request_pk = %s AND is_active = TRUE
        ORDER BY step_order
        """,
        (str(request_pk),),
    )
    steps = cur.fetchall()
    target = next((s for s in steps if str(s[0]) == str(step_pk)), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Approval step not found.")
    if target[2] != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"This step is already {target[2]}.",
        )
    if any(s[1] < target[1] and s[2] != "APPROVED" for s in steps):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="An earlier approval step must be approved first.",
        )
    if user.person_pk is not None and str(requester_pk) == str(user.person_pk):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot decide a step of your own re-parent request.",
        )
    if not person_holds_seat(cur, target[3], user.person_pk, _POSITION):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not currently hold the President seat this step is assigned to.",
        )

    new_status = "APPROVED" if decision == "APPROVE" else "REJECTED"
    remarks = (remarks or "").strip() or None
    cur.execute(
        """
        UPDATE nss.organization_reparent_step
        SET step_status = %s, decided_by_person_pk = %s, decided_at = NOW(), remarks = %s,
            updated_at = NOW(), updated_by_sangha_sevi_pk = %s
        WHERE organization_reparent_step_pk = %s
        """,
        (new_status, str(user.person_pk), remarks, user.actor_pk, str(step_pk)),
    )
    _audit(cur, user, action="APPROVE" if decision == "APPROVE" else "REJECT",
           table="organization_reparent_step", pk=step_pk,
           summary=f"Re-parent step {target[1]} ({target[4]}) {new_status.lower()}",
           detail={"remarks": remarks} if remarks else None)

    if decision == "REJECT":
        _close_request(cur, request_pk, new_status="REJECTED", decided_by_person_pk=user.person_pk,
                       remarks=remarks, actor_user=user)
        _audit(cur, user, action="REJECT", table="organization_reparent_request", pk=request_pk,
               summary="Re-parent request rejected", detail={"remarks": remarks})
        return

    if target[1] == max(s[1] for s in steps):
        apply_approved_reparent(cur, user, request_pk, sakha_pk, to_parent_pk, remarks)


def apply_approved_reparent(cur, user: UserContext, request_pk, sakha_pk, to_parent_pk, remarks) -> bool:
    """
    The final approval landed: re-validate NOW (Sakha still active and still a
    Sakha/Sakha Asana, target active + allowed parent type + not self/descendant, not
    already the parent) and apply the parent change in the caller's
    transaction. If re-validation fails the request is closed CANCELLED with a
    system remark and nothing changes. Returns True when applied.
    """
    problem = None
    cur.execute(
        """
        SELECT md.value_code, o.parent_organization_pk
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE o.organization_pk = %s AND o.is_active = TRUE
        FOR UPDATE OF o
        """,
        (str(sakha_pk),),
    )
    sakha = cur.fetchone()
    if sakha is None:
        problem = "the Sakha is no longer active"
    elif sakha[0] not in SAKHA_LIKE_ORG_TYPES:
        problem = f"the organization is no longer a Sakha or Sakha Asana ({sakha[0]})"
    elif sakha[1] is not None and str(sakha[1]) == str(to_parent_pk):
        problem = "the Sakha is already under the requested parent"
    else:
        try:
            validate_reparent_target(cur, sakha_pk, sakha[0], str(to_parent_pk))
        except HTTPException as exc:
            problem = str(exc.detail)

    if problem:
        _close_request(cur, request_pk, new_status="CANCELLED", decided_by_person_pk=None,
                       remarks=f"System: final approval could not be applied — {problem}.",
                       actor_user=user)
        _audit(cur, user, action="STATUS_CHANGE", table="organization_reparent_request", pk=request_pk,
               summary="Re-parent request cancelled (re-validation failed at apply)",
               detail={"reason": problem})
        return False

    cur.execute(
        """
        UPDATE nss.organization SET parent_organization_pk = %s, updated_at = NOW()
        WHERE organization_pk = %s
        """,
        (str(to_parent_pk), str(sakha_pk)),
    )
    _close_request(cur, request_pk, new_status="APPROVED", decided_by_person_pk=user.person_pk,
                   remarks=remarks, actor_user=user)
    _audit(cur, user, action="APPROVE", table="organization_reparent_request", pk=request_pk,
           summary="Re-parent request approved; Sakha parent changed",
           detail={"sakha_organization_pk": str(sakha_pk), "to_parent_organization_pk": str(to_parent_pk)})
    _audit(cur, user, action="UPDATE", table="organization", pk=sakha_pk,
           summary="Sakha re-parented (approved request)")
    return True


# ═══════════════════════════════════════════════════════════════════════
# Reads: visibility + payload
# ═══════════════════════════════════════════════════════════════════════

def visibility_clause(cur, user: UserContext) -> tuple[str, list]:
    """
    SQL fragment (alias ``r`` = organization_reparent_request) limiting rows to
    what *user* may see: exempt actors (Kendra GB members, NSS_ERP_ADMIN) and globally-scoped admins see all;
    everyone else sees requests they filed, requests with a step assigned to a
    seat they hold, and requests whose Sakha is inside their admin scope.
    """
    if user.can_reparent_sakha_directly():
        return "TRUE", []
    scope = actor_scope_org_pks(cur, user)
    if scope is None:
        return "TRUE", []
    parts = ["r.requested_by_person_pk = %s"]
    params: list = [str(user.person_pk)]
    held = seat_body_pks_held(cur, user.person_pk, _POSITION)
    if held:
        parts.append(
            "EXISTS (SELECT 1 FROM nss.organization_reparent_step vs "
            "WHERE vs.organization_reparent_request_pk = r.organization_reparent_request_pk "
            "AND vs.is_active = TRUE AND vs.assigned_body_master_pk = ANY(%s::uuid[]))"
        )
        params.append(sorted(held))
    if scope:
        parts.append("r.sakha_organization_pk = ANY(%s::uuid[])")
        params.append(sorted(scope))
    return "(" + " OR ".join(parts) + ")", params


def awaiting_decision_clause(cur, user: UserContext) -> tuple[str, list]:
    """SQL fragment (alias ``r``): requests with a step the caller can decide
    right now (PENDING, earlier steps all APPROVED, caller holds the seat,
    caller is not the requester). ("FALSE", []) when the caller holds no
    President seat."""
    held = seat_body_pks_held(cur, user.person_pk, _POSITION)
    if not held:
        return "FALSE", []
    return (
        "(r.request_status = 'PENDING' AND r.requested_by_person_pk <> %s AND EXISTS ("
        "SELECT 1 FROM nss.organization_reparent_step ds "
        "WHERE ds.organization_reparent_request_pk = r.organization_reparent_request_pk "
        "AND ds.is_active = TRUE AND ds.step_status = 'PENDING' "
        "AND ds.assigned_body_master_pk = ANY(%s::uuid[]) "
        "AND NOT EXISTS (SELECT 1 FROM nss.organization_reparent_step es "
        "WHERE es.organization_reparent_request_pk = ds.organization_reparent_request_pk "
        "AND es.is_active = TRUE AND es.step_order < ds.step_order AND es.step_status <> 'APPROVED')))",
        [str(user.person_pk), sorted(held)],
    )


_NAME = "TRIM(CONCAT_WS(' ', {a}.first_name, {a}.middle_name, {a}.last_name))"


def build_request_payload(cur, request_pk, user: UserContext | None = None, *, held_body_pks=None) -> dict | None:
    """The ReparentRequestResponse dict for one request (None if missing).
    *user* makes the viewer_can_* flags real; *held_body_pks* lets list
    callers pass the viewer's President seats once instead of per row."""
    cur.execute(
        f"""
        SELECT r.organization_reparent_request_pk, r.sakha_organization_pk, so.organization_name,
               so.organization_code, r.from_parent_organization_pk, fo.organization_name,
               r.to_parent_organization_pk, tpo.organization_name, r.request_status,
               r.request_reason, r.requested_by_person_pk, {_NAME.format(a='rp')},
               ss.sangha_sevi_id, r.decided_at, r.decided_by_person_pk, {_NAME.format(a='dp')},
               r.decision_remarks, r.created_at
        FROM nss.organization_reparent_request r
        JOIN nss.organization so ON so.organization_pk = r.sakha_organization_pk
        LEFT JOIN nss.organization fo ON fo.organization_pk = r.from_parent_organization_pk
        JOIN nss.organization tpo ON tpo.organization_pk = r.to_parent_organization_pk
        JOIN nss.person rp ON rp.person_pk = r.requested_by_person_pk
        LEFT JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = r.requested_by_sangha_sevi_pk
        LEFT JOIN nss.person dp ON dp.person_pk = r.decided_by_person_pk
        WHERE r.organization_reparent_request_pk = %s AND r.is_active = TRUE
        """,
        (str(request_pk),),
    )
    r = cur.fetchone()
    if r is None:
        return None

    cur.execute(
        f"""
        SELECT s.organization_reparent_step_pk, s.step_order, s.step_role, s.step_status,
               s.assigned_body_master_pk, bm.body_name, s.assigned_organization_pk,
               ao.organization_name, pm.position_code, pm.position_name,
               s.assigned_person_pk, {_NAME.format(a='ap')},
               s.fallback_reason, s.decided_by_person_pk, {_NAME.format(a='dp')},
               s.decided_at, s.remarks
        FROM nss.organization_reparent_step s
        JOIN nss.body_master bm ON bm.body_master_pk = s.assigned_body_master_pk
        JOIN nss.position_master pm ON pm.position_master_pk = s.assigned_position_master_pk
        LEFT JOIN nss.organization ao ON ao.organization_pk = s.assigned_organization_pk
        LEFT JOIN nss.person ap ON ap.person_pk = s.assigned_person_pk
        LEFT JOIN nss.person dp ON dp.person_pk = s.decided_by_person_pk
        WHERE s.organization_reparent_request_pk = %s AND s.is_active = TRUE
        ORDER BY s.step_order
        """,
        (str(request_pk),),
    )
    step_rows = cur.fetchall()

    viewer_pk = str(user.person_pk) if user is not None and user.person_pk else None
    is_pending = r[8] == "PENDING"
    viewer_is_requester = viewer_pk is not None and viewer_pk == str(r[10])
    if viewer_pk is not None and held_body_pks is None:
        held_body_pks = seat_body_pks_held(cur, viewer_pk, _POSITION)
    held = {str(x) for x in (held_body_pks or ())}

    steps = []
    earlier_all_approved = True
    for s in step_rows:
        can = bool(
            is_pending and s[3] == "PENDING" and earlier_all_approved
            and not viewer_is_requester and str(s[4]) in held
        )
        if s[3] != "APPROVED":
            earlier_all_approved = False
        steps.append({
            "organization_reparent_step_pk": s[0], "step_order": s[1], "step_role": s[2],
            "step_status": s[3], "assigned_body_master_pk": s[4], "assigned_body_name": s[5],
            "assigned_organization_pk": s[6], "assigned_organization_name": s[7],
            "assigned_position_code": s[8], "assigned_position_name": s[9],
            "assigned_person_pk": s[10], "assigned_person_name": s[11] or None,
            "fallback_reason": s[12], "decided_by_person_pk": s[13],
            "decided_by_person_name": s[14] or None, "decided_at": s[15], "remarks": s[16],
            "viewer_can_decide": can,
        })

    return {
        "organization_reparent_request_pk": r[0], "sakha_organization_pk": r[1],
        "sakha_organization_name": r[2], "sakha_organization_code": r[3],
        "from_parent_organization_pk": r[4], "from_parent_organization_name": r[5],
        "to_parent_organization_pk": r[6], "to_parent_organization_name": r[7],
        "request_status": r[8], "request_reason": r[9],
        "requested_by_person_pk": r[10], "requested_by_person_name": r[11] or None,
        "requested_by_sangha_sevi_id": r[12], "decided_at": r[13],
        "decided_by_person_pk": r[14], "decided_by_person_name": r[15] or None,
        "decision_remarks": r[16], "created_at": r[17], "steps": steps,
        "viewer_can_cancel": bool(
            is_pending and user is not None and (viewer_is_requester or user.can_reparent_sakha_directly())
        ),
    }
