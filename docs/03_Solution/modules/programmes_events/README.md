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

`05_programmes_events_table_design.md` (`SOL-MOD21-005`) — physical table design. **7 candidate
common tables, none frozen DDL**: `programme_type`, `event`, `event_day`, `event_session`,
`event_registration`, `event_location`, `event_history`. `financial_scope` (Finance-owned),
attendance entities, and UPBS/Kishor/Sevak event extensions are explicitly **not** among these 7
and remain domain-owned. Note: this document's own header (`Version: 0.1.0` / `DRAFT — TABLE
DESIGN`) doesn't reflect how settled the table list now is relative to the reconciliation
closure below — the header undersells it.

## Related architecture docs

`docs/03_Solution/architecture/PROGRAMME_EVENT_DOMAIN_MODEL.md` (`SOL-EVT-001`) and
`EVENT_ENTITY_RECONCILIATION.md` (`SOL-EVT-002`) — the domain model and its reconciliation
against UPBS/Kishor/Sevak/Mahila/Finance/Attendance, before this module's own docs were
written. `PROGRAMMES_EVENTS_CROSS_MODULE_REVIEW.md` (`SOL-EVT-006`, v1.1.0 **FROZEN**) —
final compatibility review; every module in its compatibility matrix is COMPATIBLE (no hard
conflict, unlike the Governance/Mahila Mandali term-length conflict).

**Reconciliation gates closed:**
`PROGRAMMES_EVENTS_RECONCILIATION_DECISIONS.md` (`SOL-EVT-007`, v1.0.0, FROZEN) closed all 7
gates that SOL-EVT-006 had left open, resolving what used to be called "Ownership Ambiguity"
(Risk 3) and the "no frozen migration strategy" gap:
- Gate A: P&E owns a common Event entity — YES.
- Gates B/C/D: `upbs_event`, Kishor event identity, and Sevak event types all become
  **common-Event extensions** (absorbed, not left as separate domain tables and not merely
  referenced) — closing the migration-strategy question.
- Gate E: Event Session is optional, organiser-defined → frozen as `P&E-ARCH-002`.
- Gate F: Weekly Sangha Puja stays **Attendance-owned**, no P&E dependency, no change to
  Attendance's own docs.
- Gate G: Registration is common P&E infrastructure (configurable per event, financial
  transactions still Finance-owned) → frozen as `P&E-ARCH-001`.

`MODULE_DEPENDENCY_MAP.md` (`SOL-ARCH-007`) lists this as one of 22 modules (Assets &
Property is Module #22), "ARCHITECTURALLY JUSTIFIED / RECONCILIATION
COMPLETE (SOL-EVT-007)" per its own §61 status footer — but "Module #21 ownership formally
accepted" is still listed as an open precondition to the DB phase. Programme & Events sits at
Tier 7 of the 12-tier build order in `IMPLEMENTATION_DEPENDENCY_ORDER.md` (`SOL-ARCH-008`,
**FROZEN** as `IMPLEMENTATION-TIER-001`).

## Current Status

Design Complete (DRAFT) · ERD Drafted · Lifecycle Drafted · Business Rules Drafted · Table
Design Drafted, **7 candidate tables, cross-module reconciliation complete (SOL-EVT-007)
but still not frozen DDL** · SQL Implementation Not Started · no
`backend/programmes_events/` app exists · **formal Module #21 freeze itself remains the one
outstanding step** — reconciliation being complete is not the same as the module being frozen.
