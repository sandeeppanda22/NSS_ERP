# GDR-005 — Advisory Board as a Singleton Organization

## Document Metadata

| Attribute | Value |
|----------|-------|
| Decision Identifier | GDR-005 |
| Decision Title | Advisory Board as a Singleton Organization |
| Decision Type | Governance Decision Record |
| Register | Governance Decision Register (GDR-001) |
| Decision Authority | NSS Governing Body (GOV-ROLE-006) |
| Approver | Project Steering Committee |
| Decision Status | Proposed |
| Effective Date | TBD (on ratification; implementation already in the working tree as of 2026-10-30) |
| Affected Documents | STD-03 (Master Data Catalog), SOL-ORG-001/002/004/005, ORGANIZATION_API_CONTRACT, SOL-ADMIN-004/-006 (role/permission matrix), SOL-GOV-003 |
| Related Change Request | N/A (owner-directed decision, 2026-10-30) |

> **Ratification flag.** This decision was directed by the project owner on 2026-10-30 and is recorded here per GDR-001 (GDR-DEC-001). GDR-001 and GOV-ROLE-006 place final decision authority with the NSS Governing Body; no evidence of that body's approval is available in the repository, so Decision Status is `Proposed`, not `Approved`. Advance it to `Approved` (and then `Implemented`) only once the NSS Governing Body / Project Steering Committee ratification is confirmed, and record that in this document.

---

## 1. Background

The Advisory Board existed only as a NSS-wide governance body (`body_master`, type `ADVISORY_BOARD`, `organization_pk IS NULL`) with seats nominated by Sakhas. It had no organization record and therefore no correspondence register, no `short_code` for reference numbers, and no organizational scope for its administrator role `NSS_ERP_ADVISORY_BOARD_ADMIN`.

## 2. Decision

1. A 14th `ORGANIZATION_TYPE` master-data value, **`ADVISORY_BOARD`** ("Advisory Board"), is added to the Organization type list.
2. Exactly one organization of that type exists: `organization_name` "Advisory Board", `organization_code` **`ADB`**, `short_code` **`NSSAB`**, parent = the Kendra organization (parent matrix: `ADVISORY_BOARD` → `KENDRA` only). It is seeded, never user-created.
3. The **governance body** called Advisory Board stays NSS-wide (`organization_pk IS NULL`) and is deliberately **not** linked to this organization. The organization exists to own the Advisory Board's correspondence register. The §63 composite-grant rule and the Sakha-nomination logic depend on the body staying NULL-organization.
4. `organization_name` of the `ADVISORY_BOARD` organization is **immutable for every actor** (including NSS_ERP_ADMIN); an attempt is refused with HTTP 422. Contact fields (phone, email, website, etc.) remain editable by scope-allowed holders.
5. A database trigger (`nss.fn_enforce_organization_singleton`, `database/ddl/02_organization/08_organization_singleton_trigger.sql`) refuses a second **active** `ADVISORY_BOARD` organization on INSERT or on UPDATE of type / active flag / parent. *(Owner amendment 2026-10-30: the trigger was generalised from the original ADVISORY_BOARD-only `fn_enforce_advisory_board_singleton`, which is dropped idempotently; see item 7.)*
6. `NSS_ERP_ADVISORY_BOARD_ADMIN` holds eight permissions (from `database/seed/00_bootstrap/03_role_permission.sql`): `GOVERNANCE_VIEW`, `GOVERNANCE_MANAGE`, `MEMBERSHIP_VIEW`, `CORRESPONDENCE_VIEW`, `CORRESPONDENCE_MANAGE`, `ORGANIZATION_VIEW`, `FOUNDATION_VIEW`, `PERSON_VIEW`. `GOVERNANCE_MANAGE` is confined server-side to ADVISORY_BOARD-type bodies. Its admin-scope level `ADVISORY_BOARD` resolves to the Advisory Board organization (see GDR-006).

7. **Singleton organizations (owner amendment, 2026-10-30).** The owner states that each of the following is single in NSS, and the trigger plus the API check (`api/helpers.py` `SINGLETON_ORG_TYPES` / `require_singleton_slot_free`, used by `create_organization` and `update_organization`) refuse a second **active** organization for each: (a) type `KENDRA`; (b) type `NILACHALA_KUTIRA`; (c) type `SMRUTI_MANDIRA`; (d) type `ADVISORY_BOARD`; (e) the central (NSS/Kendra) Mahila Sangha, defined as *an active organization of type `MAHILA_SANGHA` whose parent is a `KENDRA`-type organization*. `MAHILA_SANGHA` is also the type of the many local per-Sakha Mahila Sanghas (parent = a Sakha), which stay unrestricted. The trigger fires on INSERT and on UPDATE OF type / `is_active` / parent, and in the function only when a relevant column actually changed, so unrelated updates are never blocked. Creating the trigger never scans existing rows, so a build on a database that already holds a duplicate does not fail; only NEW offending writes are blocked. Live data is checked with the diagnostic SELECT in `database/scripts/README.md`.

## 3. Rationale

- Gives the Advisory Board a correspondence register using the existing org-based register model rather than a special case.
- Keeping the body NULL-organization preserves the NSS-wide, Sakha-nominated composition model already built.
- An immutable name and a DB-level singleton protect an institution defined by the Bye-Law from accidental rename or duplication.

## 4. Alternatives Considered

- **Link the existing body to the new organization.** Rejected — breaks the NULL-org §63 grant rule and the missing-nominations logic.
- **Enforce the singleton in the API only.** Rejected — owner required a DB-level guard.
- **Apply the singleton trigger to all apex types.** Originally not done (scope limited to `ADVISORY_BOARD`); adopted by the owner's 2026-10-30 amendment (item 7), extended to the central Mahila Sangha.

## 5. Impact Assessment

- STD-03 `ORGANIZATION_TYPE` gains a value (14 types).
- Organization module docs: type list, parent matrix (ORG-BR-087..095) and new rules ORG-BR-106..108 (see SOL-ORG-004 §36).
- ORGANIZATION_API_CONTRACT: type count.
- Administration role/permission matrix: `NSS_ERP_ADVISORY_BOARD_ADMIN` rows.
- Schema table count is unchanged by this decision (71 tables after the re-parent tables added the same day).

## 6. Approval

Recorded under GDR-001; approval pending per the Ratification flag above.

---

# End of Document
