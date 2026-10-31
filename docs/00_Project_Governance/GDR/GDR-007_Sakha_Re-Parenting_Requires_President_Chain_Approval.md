# GDR-007 — Sakha Re-Parenting Requires President-Chain Approval

## Document Metadata

| Attribute | Value |
|----------|-------|
| Decision Identifier | GDR-007 |
| Decision Title | Sakha Re-Parenting Requires President-Chain Approval |
| Decision Type | Governance Decision Record |
| Register | Governance Decision Register (GDR-001) |
| Decision Authority | NSS Governing Body (GOV-ROLE-006) |
| Approver | Project Steering Committee |
| Decision Status | Proposed |
| Effective Date | TBD (on ratification; implementation already in the working tree as of 2026-10-30) |
| Affected Documents | SOL-ORG-004 (ORG-BR-090, new ORG-BR-109), SOL-ADMIN-003 (ADMIN-BR-043/077), ORGANIZATION_API_CONTRACT, GDR-006 |
| Related Change Request | N/A (owner-directed decision, 2026-10-30) |

> **Ratification flag.** This decision was directed by the project owner on 2026-10-30 and is recorded here per GDR-001 (GDR-DEC-001). GDR-001 and GOV-ROLE-006 place final decision authority with the NSS Governing Body; no evidence of that body's approval is available in the repository, so Decision Status is `Proposed`, not `Approved`. Advance it to `Approved` (and then `Implemented`) only once the NSS Governing Body / Project Steering Committee ratification is confirmed, and record that in this document.

---

## 1. Background

Moving a Sakha Sangha (or Sakha Asana — the owner treats the two as the same in current practice) under a different Anchalika/Zilla Sangha (including the first move out of Kendra, and the admin "Assign Sakha" action) was applied directly by any admin with scope.

## 2. Decision

1. Re-parenting a `SAKHA_SANGHA` **or `SAKHA_ASANA`** is applied **directly only** for a Kendra Governing Body member or the `NSS_ERP_ADMIN` super administrator (items 2-3). For every other actor it is a request that must be approved along the President chain: (1) the moved Sakha's own President → (2) the **leaving** (current) Anchalika/Zilla President → (3) the **destination** Anchalika/Zilla President → (4) the Kendra President (final) — owner amendment 2026-10-31, wording: "Sakha President, then leaving Anchalika/Zilla President, then destination Anchalika/Zilla President, then Kendra President". If the Sakha's current parent is the Kendra (the unassigned flat state — no leaving Anchalika/Zilla exists) step 2 does not exist (not a fallback; it is simply not applicable); if the source and destination are the same body the request is refused ("already under that parent"). Fallback and collapse apply to each existing step exactly as before (consecutive Kendra-President steps collapse into one). A Sakha Asana has its own Governing Body and President exactly like a Sakha Sangha, so step 1 is resolved identically for it. A step with no seated President (live seat, acting cover included), or whose seat the requester holds, is assigned to the Kendra President (fallback); it is never auto-approved or skipped. The Sakha's parent does not change until the final step approves.
2. **Definition of Kendra Governing Body member:** a person holding the §63 auto-granted composite `NSS_ERP_KENDRA_ADMIN` scope (live `KENDRA_GOVERNING_BODY` seat, any position, active or acting delegate; synthetic scope with no `user_role` row). A `user_role`-assigned `NSS_ERP_KENDRA_ADMIN` is not a member.
3. **The `NSS_ERP_ADMIN` super administrator is exempt** (owner amendment, 2026-10-30, superseding the earlier "deliberately not exempt" wording of this record). The exemption is decided by **role** — an `NSS_ERP_ADMIN` scope (`UserContext.is_super_admin()`) — never by a hard-coded login or Sangha Sevi ID, so it covers the seeded bootstrap administrator and any other holder of the role. Everyone else — scoped admins, office bearers, and a manually-assigned (non-Governing-Body) Kendra Administrator — goes through the chain. The exemption only concerns *re-parenting directly*; **deciding** a chain step still requires the live office seat (no permission or role override), and the requester can never decide their own request. Consequently NSS_ERP_ADMIN remains the sole blanket authority of ADMIN-BR-043/077 and this operation is no exception to it.
4. Non-Sakha organization types and all other PATCH fields are unaffected.

5. **Sakha Asana is a full Sakha** (owner decision, 2026-10-31): `SAKHA_ASANA` counts as a Sakha everywhere — this chain (step 1 is the Asana's own `SAKHA_GOVERNING_BODY` President), membership (MBR-038A), Advisory Board representation, attendance, correspondence and the public/member Sakha pickers — through one shared definition per layer (`api/helpers.py::SAKHA_LIKE_ORG_TYPES`, `nss.fn_is_sakha_like_org_type()`, `NSS.SAKHA_LIKE_ORG_TYPES`). Deliberately type-specific rules (ORG-BR-096 creation whitelist, ORG-BR-098 premises attribute, id-sequence/code generation, and — at the time of this record — the wing parenting rules ORG-BR-091/092/094) are unchanged.

> **Amendment (2026-10-31, owner-directed, GDR-008):** the wing parenting rules ORG-BR-091/092/094 are no longer exempt from item 5: a Sakha Asana hosts every wing a Sakha Sangha can. See GDR-008.

## 3. Rationale

A Sakha's affiliation changes the territorial structure the Bye-Law assigns to elected office bearers; it should be consented to by those bearers, not by a system administrator.

## 4. Alternatives Considered

- **Exempt NSS_ERP_ADMIN.** Initially rejected by the owner; adopted by the owner's 2026-10-30 amendment (item 3).
- **Exempt any Kendra admin role.** Rejected — membership of the Governing Body, not the ERP role, is the criterion.

## 5. Impact Assessment

SOL-ORG-004 (new rule), ORGANIZATION_API_CONTRACT (202 response on re-parent), SOL-ADMIN-003 (ADMIN-BR-043/077 amendment notes — NSS_ERP_ADMIN remains global). Tables `organization_reparent_request` and `organization_reparent_step` added (71 tables). The 2026-10-31 amendment adds the `SOURCE_PARENT_PRESIDENT` step role (`organization_reparent_step.step_role` CHECK widened, `step_order` 1..4; existing databases take `ddl/02_organization/09_organization_reparent_step_source_role_patch.sql`).

## 6. Approval

Recorded under GDR-001; approval pending per the Ratification flag above.

---

# End of Document
