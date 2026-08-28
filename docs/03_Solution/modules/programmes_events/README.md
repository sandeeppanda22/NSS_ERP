# NSS ERP Programmes & Events Module (Module #21)

Status: DRAFT — Version 0.1.0. Module is "ARCHITECTURALLY JUSTIFIED" per the cross-module
review below, but "FORMAL MODULE FREEZE PENDING" — nothing here is frozen, unlike most other
module doc sets which carry a `SOURCE ALIGNED` content-freeze tag. This module has no
corresponding `backend/` Django app.

---

## Scope

Models a two-level **Programme Type → Event Instance** structure: a Programme Type (e.g.
`KISHOR_PUJA`, `JANMOUTSABA`, `SARADIYA_ALOCHANA_CHAKRA`, `UPBS`, `RASOUTSABA`) is a reusable
definition; each yearly occurrence (e.g. "UPBS 2027") is an independent Event Instance with its
own lifecycle, organizer, location, and sessions. Two frozen boundaries carried over from
Organization/Governance conventions: **Organizer is always an Organization** (Kendra/Sakha/
Patha Chakra), never an Event Location; **Patha Chakra is an Organization Type**, not a
Programme/Event Type.

## Documents

`01_programmes_events_module_overview.md` (`SOL-MOD21-001`) — module purpose, scope, the
Programme Type / Event Instance split.

`02_programmes_events_erd.md` (`SOL-MOD21-002`) — entity relationship design; §11 states
"Organization ≠ Event Location."

`03_programmes_events_lifecycle.md` (`SOL-MOD21-003`) — lifecycle states for programme types
and event instances.

`04_programmes_events_business_rules.md` (`SOL-MOD21-004`) — business rules, including
BR-067 (Governance Roles Are Not Application Roles — ERP-FROZEN/CROSS-MODULE, consistent with
Administration's RBAC framework).

`05_programmes_events_table_design.md` (`SOL-MOD21-005`) — physical table design. **5 candidate
common tables, none frozen**: `programme_type`, `event`, `event_session`, `event_location`,
`event_history`. `financial_scope` (Finance-owned), attendance entities, and UPBS/Kishor/Sevak
event extensions are explicitly **not** among these 5 and remain domain-owned.

## Related architecture docs

`docs/03_Solution/architecture/PROGRAMME_EVENT_DOMAIN_MODEL.md` (`SOL-EVT-001`) and
`EVENT_ENTITY_RECONCILIATION.md` (`SOL-EVT-002`) — the domain model and its reconciliation
against UPBS/Kishor/Sevak/Mahila/Finance/Attendance, before this module's own docs were
written. `PROGRAMMES_EVENTS_CROSS_MODULE_REVIEW.md` (`SOL-EVT-006`) — final compatibility
review; every module in its compatibility matrix is marked COMPATIBLE (no hard conflict, unlike
the Governance/Mahila Mandali term-length conflict), but flags open/deferred risks: "Ownership
Ambiguity" (Risk 3 — a common Event table could end up shared without a clear owner) and no
frozen migration strategy for whether `upbs_event`/Kishor event identity/Sevak events get
absorbed into the common tables or merely reference them. `MODULE_DEPENDENCY_MAP.md`
(`SOL-ARCH-007`) lists this as module 21 of 21, "PROPOSED — NOT FROZEN." Programme & Events
sits at Tier 7 of the 12 PROPOSED tiers in `IMPLEMENTATION_DEPENDENCY_ORDER.md` (`SOL-ARCH-008`),
"PROPOSED / IMPLEMENTATION DEFERRED."

## Current Status

Design Complete (DRAFT) · ERD Drafted · Lifecycle Drafted · Business Rules Drafted · Table
Design Drafted, **all 5 candidate tables NOT FROZEN** · SQL Implementation Not Started · no
`backend/programmes_events/` app exists
