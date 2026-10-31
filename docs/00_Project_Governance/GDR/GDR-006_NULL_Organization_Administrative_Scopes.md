# GDR-006 — NULL-Organization Administrative Scopes (Kendra Mahila Sangha and Advisory Board)

## Document Metadata

| Attribute | Value |
|----------|-------|
| Decision Identifier | GDR-006 |
| Decision Title | NULL-Organization Administrative Scopes (Kendra Mahila Sangha and Advisory Board) |
| Decision Type | Governance Decision Record |
| Register | Governance Decision Register (GDR-001) |
| Decision Authority | NSS Governing Body (GOV-ROLE-006) |
| Approver | Project Steering Committee |
| Decision Status | Proposed |
| Effective Date | TBD (on ratification; implementation already in the working tree as of 2026-10-30) |
| Affected Documents | SOL-ADMIN-003 (ADMIN-BR-076/077), SOL-ADMIN-004, SOL-ADMIN-006, SOL-ORG-004 (ORG-BR-095), SOL-GOV-003, GDR-005 |
| Related Change Request | N/A (owner-directed decision, 2026-10-30) |

> **Ratification flag.** This decision was directed by the project owner on 2026-10-30 and is recorded here per GDR-001 (GDR-DEC-001). GDR-001 and GOV-ROLE-006 place final decision authority with the NSS Governing Body; no evidence of that body's approval is available in the repository, so Decision Status is `Proposed`, not `Approved`. Advance it to `Approved` (and then `Implemented`) only once the NSS Governing Body / Project Steering Committee ratification is confirmed, and record that in this document.

---

## 1. Background

Two admin-scope levels carry no `organization_pk` in `admin_scope`: `KENDRA_MAHILA_SANGHA` and `ADVISORY_BOARD`. Before this decision they resolved to no organization reach, which is what silenced their registers and pickers.

## 2. Decision

1. **Organization reach.** A scope whose `organization_pk` is NULL resolves, via `rbac_service.NULL_ORG_SCOPE_ORG_TYPE`, to every organization of a mapped type plus that organization's subtree:
   - `KENDRA_MAHILA_SANGHA` → every `MAHILA_SANGHA` organization (the central Kendra Mahila Sangha and the Sakha-level Mahila Sanghas) and their subtrees. Nothing above them (Kendra, a Sakha) is included.
   - `ADVISORY_BOARD` → the singleton `ADVISORY_BOARD` organization (GDR-005) and its subtree (none today).
2. **Body-level reach.** `rbac_service.NULL_ORG_SCOPE_BODY_TYPES` lets a NULL-org scope manage NSS-wide (NULL-organization) governance bodies of listed types only: `ADVISORY_BOARD` → `{ADVISORY_BOARD}`; `KENDRA_MAHILA_SANGHA` → `{MAHILA_PARICHALANA_MANDALI}` (the central Mahila Mandali). Every other NSS-wide body (e.g. Kendra Governing Body) still needs a global authority.
3. **Permissions.** `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` carries Kendra's operational set, 18 permissions (seed): `BOOTSTRAP_VIEW`, `FOUNDATION_VIEW`, `ORGANIZATION_VIEW`, `ORGANIZATION_MANAGE`, `PERSON_VIEW`, `PERSON_MANAGE`, `FAMILY_VIEW`, `FAMILY_MANAGE`, `MEMBERSHIP_VIEW`, `MEMBERSHIP_MANAGE`, `MEMBERSHIP_APPROVE`, `REPORT_VIEW`, `GOVERNANCE_VIEW`, `GOVERNANCE_MANAGE`, `CORRESPONDENCE_VIEW`, `CORRESPONDENCE_MANAGE`, `ATTENDANCE_VIEW`, `ATTENDANCE_MANAGE`. `NSS_ERP_ADVISORY_BOARD_ADMIN` carries the eight permissions listed in GDR-005 §2.6.
4. Neither level confers global reach: ADMIN-BR-076/077 stand unchanged. These roles remain scope-bounded; only NSS_ERP_ADMIN / NSS-WIDE is global.
5. Both roles are also §63 composite-grant targets (`ADVISORY_BOARD` President/Secretary; central `MAHILA_PARICHALANA_MANDALI` President/Joint Secretary).

## 3. Rationale

The two bodies are NSS-wide by Bye-Law design (no single parent organization), so "scope by organization_pk" cannot express their reach; resolving by organization type keeps reach bounded and configuration-driven (Configuration Over Hardcoding) without granting global authority.

## 4. Alternatives Considered

- **Make them NSS-WIDE.** Rejected — would violate ADMIN-BR-077.
- **Give each a real organization_pk in admin_scope.** Rejected for Mahila (many Mahila Sangha organizations; reach must follow new ones automatically).

## 5. Impact Assessment

SOL-ADMIN-003 (ADMIN-BR-076/077 clarification), SOL-ADMIN-004/-006 (role matrix), SOL-ORG-004 (ORG-BR-095 scope levels), SOL-GOV-003 (body-level reach).

## 6. Approval

Recorded under GDR-001; approval pending per the Ratification flag above.

---

# End of Document
