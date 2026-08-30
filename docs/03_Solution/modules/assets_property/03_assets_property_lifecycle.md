# NSS ERP — Assets & Property Lifecycle

**Document ID:** SOL-AP-003
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Assets & Property
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle states and transitions for entities
within the Assets & Property module.

The lifecycle is derived from source-established provisions. Where a state
or transition is an architectural interpretation rather than a statutory
requirement, it is explicitly marked.

---

# 2. Entities with Lifecycle

| Entity | Lifecycle Required | Reason |
|--------|-------------------|--------|
| Property | Yes | Immovable property has distinct operational states |
| Asset | Yes | Movable assets have distinct operational states |
| Custodianship | Yes | Custody is temporal — begins, persists, ends |
| Statutory Record | No | Static obligation record; no state machine |
| Maintenance Record | No | Event record; captured as history, not stateful |

---

# 3. Property Lifecycle

## 3.1 States

| State | Meaning |
|-------|---------|
| REGISTERED | Property identified and recorded in the ERP |
| ACTIVE | Property is in normal operational use/custody |
| UNDER_MAINTENANCE | Property is undergoing repair, improvement, or alteration |
| DISPOSED | Property has been permanently disposed of |

## 3.2 State Diagram

```text
REGISTERED
    │
    ▼
ACTIVE ◄────────────────┐
    │                    │
    ├───► UNDER_MAINTENANCE
    │         │
    │         └──► ACTIVE (return after maintenance)
    │
    ├───► DISPOSED (terminal)
    │
    └───► ACTIVE (after custodianship transfer — property remains ACTIVE;
                   the custodianship record changes, not the property state)
```

## 3.3 Source Basis

| Transition | Source |
|------------|--------|
| REGISTERED → ACTIVE | Architectural interpretation: property enters active state when custody is assigned |
| ACTIVE → UNDER_MAINTENANCE | Bye-Law: "proper maintenance and necessary improvements"; Mahila: "annual repair works both minor and major, necessary additions and alterations" |
| UNDER_MAINTENANCE → ACTIVE | Architectural interpretation: maintenance is temporary, property returns to active use |
| ACTIVE → DISPOSED | Mahila Bye-Law: "dispose of them in furtherance of the aims and objects" |

## 3.4 Important Distinctions

**UNDER_MAINTENANCE is not terminal.** It represents a temporary
operational condition. After maintenance completes, the property returns
to ACTIVE.

**Transfer is not a property state.** When custodianship changes, the
property itself remains ACTIVE. The custodianship record transitions
(see §5). The property does not enter a "TRANSFERRED" state.

**DISPOSED is terminal.** A disposed property cannot return to ACTIVE.

---

# 4. Asset Lifecycle

## 4.1 States

| State | Meaning |
|-------|---------|
| REGISTERED | Asset identified and recorded in the ERP |
| IN_CUSTODY | Asset is in normal operational use under a custodian |
| UNDER_MAINTENANCE | Asset is undergoing repair or servicing |
| RETIRED | Asset has been permanently retired/disposed of |

## 4.2 State Diagram

```text
REGISTERED
    │
    ▼
IN_CUSTODY ◄────────────────┐
    │                        │
    ├───► UNDER_MAINTENANCE  │
    │         │              │
    │         └──────────────┘ (return after maintenance)
    │
    ├───► RETIRED (terminal)
    │
    └───► IN_CUSTODY (after custodianship transfer — asset remains
                      IN_CUSTODY; the custodianship record changes)
```

## 4.3 Source Basis

| Transition | Source |
|------------|--------|
| REGISTERED → IN_CUSTODY | Architectural interpretation: asset enters custody when assigned |
| IN_CUSTODY → UNDER_MAINTENANCE | Bye-Law item 8: "proper upkeep and maintenance of the articles" |
| UNDER_MAINTENANCE → IN_CUSTODY | Architectural interpretation: maintenance is temporary |
| IN_CUSTODY → RETIRED | Architectural interpretation: assets have a finite useful life |

## 4.4 Important Distinctions

**UNDER_MAINTENANCE is not terminal.** Same principle as property.

**Transfer is not an asset state.** Same principle as property — the
custodianship record changes, not the asset state.

**RETIRED is terminal.** A retired asset cannot return to IN_CUSTODY.

**RETIRED vs DISPOSED:** Assets use "RETIRED" rather than "DISPOSED"
because movable assets are typically retired from service rather than
legally disposed of in the way immovable property might be. This is an
architectural naming choice, not a source-mandated distinction.

---

# 5. Custodianship Lifecycle

## 5.1 States

| State | Meaning |
|-------|---------|
| ASSIGNED | Custodianship record created; custody begins |
| ACTIVE | Custodian currently holds operational responsibility |
| ENDED | Custodianship has concluded |

## 5.2 State Diagram

```text
ASSIGNED
    │
    ▼
ACTIVE
    │
    ▼
ENDED (terminal)
```

## 5.3 ENDED Triggers

A custodianship may end due to:

| Trigger | Source |
|---------|--------|
| Transfer of custody to another organization unit | Bye-Law item 12: custodianship by Sakha office-bearers implies assignability |
| Organizational restructuring | Architectural interpretation |
| Dissolution (Mahila) | Mahila Bye-Law: "remaining property vests in Kendra Sangha" |
| Other statutory change | Architectural interpretation |

## 5.4 New Custodianship on End

When a custodianship record transitions to ENDED, a new custodianship
record is created for the incoming custodian:

```text
Custodianship A: ACTIVE → ENDED
Custodianship B: ASSIGNED → ACTIVE (new custodian)
```

This preserves complete custody history.

## 5.5 Source Basis

| Concept | Source |
|---------|--------|
| Custodianship assigned | "custodian of all the properties" (Bye-Law §C); "Office-bearers of these Sakha Sanghas will function as the custodians" (Bye-Law item 12) |
| Custodianship ended by dissolution | "remaining property vests in Kendra Sangha" (Mahila Bye-Law §12) |
| Custodianship transfer | Architectural interpretation from source-established custodian assignment |

---

# 6. Lifecycle Rules

## 6.1 General Rules

| Rule | Description |
|------|-------------|
| AP-LIF-001 | A property/asset must have at least one custodianship record before transitioning to ACTIVE/IN_CUSTODY |
| AP-LIF-002 | UNDER_MAINTENANCE is always temporary; the entity must return to ACTIVE/IN_CUSTODY or transition to DISPOSED/RETIRED |
| AP-LIF-003 | Terminal states (DISPOSED, RETIRED, ENDED) are irreversible |
| AP-LIF-004 | Custodianship transfer does not change property/asset state |
| AP-LIF-005 | A property/asset may have only one ACTIVE custodianship at any time |

## 6.2 Financial Consequences of Lifecycle Events

Per FIN-ARCH-001, lifecycle events may have financial consequences but
do not own financial transactions:

| Lifecycle Event | Financial Consequence (Finance-owned) |
|-----------------|--------------------------------------|
| Acquisition (REGISTERED) | Purchase transaction |
| Maintenance | Expense transaction |
| Disposal | Disposal proceeds or write-off |
| Statutory obligation payment | Tax/revenue payment |

---

# 7. What Is NOT Established by Source

The following lifecycle aspects are **not established** by the Bye-Law
source material:

```text
Exact maintenance duration tracking
Maintenance scheduling or recurring maintenance cycles
Asset depreciation lifecycle
Insurance lifecycle
Condition grading / deterioration lifecycle
Inspection lifecycle
Warranty lifecycle
```

These would require additional business rules if needed in the future.

---

# 8. Relationship to Other Module Lifecycles

| Module | Relationship |
|--------|-------------|
| Organization | Custodian organization has its own lifecycle; if an org is dissolved/deactivated, custodianship must be reassigned |
| Finance | Financial transactions have their own lifecycle in the Finance module |
| Governance | Authority for acquisition/disposal follows Governance lifecycle |

---

# 9. State Storage

The exact physical representation of lifecycle state belongs in Table
Design (document 05).

Conceptual expectation:

```text
property.status     → current property state
asset.status        → current asset state
custodianship       → effective_from / effective_to + status
```

History of state transitions may be captured through:

- module-owned `_history` tables (per Data Change Architecture);
- audit columns (created_at, updated_at);
- the custodianship entity itself (which is inherently historical).

---

# 10. Status

DOCUMENT STATUS:

```
DRAFT — SOURCE ALIGNED
```

VERSION:

```
1.0.0
```
