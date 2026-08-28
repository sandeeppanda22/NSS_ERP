# NSS ERP — Sevak Sangha Core Business Rules

**Document ID:** SOL-SEV-004  
**Version:** 6.0.0  
**Status:** DRAFT — CONSOLIDATION IN PROGRESS  
**Parent Module:** Sevak Sangha  
**Scope:** Core Sevak Business Rules

---

# 1. Purpose

This document defines the core business rules governing Sevak Sangha participation.

It contains rules that belong to the Sevak identity, eligibility, lifecycle, membership relationship, status management, transfer, reactivation, history and core administration.

Detailed rules for operational activities are maintained separately.

---

# 2. Document Scope

This document covers:

- Institutional nature of Sevak Sangha
- Relationship with NSS Membership
- Eligibility
- Enrollment
- Participation status
- Inactivation
- Transfer
- Death
- Reactivation
- Enrollment history
- Sakha association history
- Administrative authority
- Governance status
- Training status
- Audit and history

The following are maintained separately:

```text
Participation
    → 04_sevak_participation_rules.md

Sakha-Level Sevak Sangha Session
    → sangha/01_sakha_sevak_sangha_session_rules.md

Anchalika/Zilla Sevak Sangha Puja
    → sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md

General Seva
    → seva/01_seva_business_rules.md

UPBS Seva
    → seva/02_upbs_seva_rules.md

Other/Future Events
    → events/01_other_sevak_event_rules.md
```

---

# 3. Institutional Rules

## SEV-001 — NSS Institution

Sevak Sangha is an institutional component of NSS.

It operates within the overall NSS organizational framework.

---

## SEV-002 — Training Organization

Sevak Sangha has a training and development dimension.

However, no mandatory formal training hierarchy is currently frozen.

---

## SEV-003 — Volunteer Organization

Sevak Sangha functions as a volunteer-development and participation structure within NSS.

---

## SEV-004 — Service Organization

Sevak Sangha provides a framework through which eligible members may participate in Seva.

Seva itself is governed separately.

---

## SEV-005 — Leadership Development

Sevak Sangha supports leadership development.

Leadership development does not create a separate membership category.

---

# 4. Organizational Nature

## SEV-006 — Not a Membership Category

`SEVAK` is not an NSS Membership Type.

The NSS Membership Types remain governed by the common Membership module.

A person does not receive a separate NSS Membership merely by becoming a Sevak.

---

## SEV-007 — Not a Governance Body

Sevak Sangha itself is not a separate governance body.

It shall not create an independent governance structure outside the common NSS Governance framework.

---

## SEV-008 — Governance May Exist Within

Where governance or office-bearing responsibilities exist within Sevak Sangha operations, they shall use the common NSS Governance and RBAC framework.

No separate Sevak governance architecture is created by this document.

---

# 5. Membership Rules

## SEV-009 — Common NSS Membership Applies

Sevak participation follows the common NSS Membership framework.

NSS Membership remains the authoritative membership relationship.

---

## SEV-010 — Sangha Sevi ID Is Authoritative

The Sangha Sevi ID is the authoritative NSS Membership identity.

Sevak participation does not create a second membership identity.

---

## SEV-011 — No Separate Membership Identity

There shall be:

```text
One Person
    ↓
One NSS Membership
    ↓
One Sangha Sevi ID
```

Sevak participation is associated with this existing identity.

---

## SEV-012 — NSS Membership Types

The common NSS Membership Types remain:

```text
PROBATIONARY_MEMBER
REGULAR_MEMBER
ASSOCIATE_MEMBER
```

Sevak status shall not duplicate these Membership Types.

---

# 6. Eligibility

## SEV-013 — Category Eligibility

Eligible persons are:

1. Interested NSS Members
2. Existing Sevaks

NSS Membership is mandatory.

No non-member may be registered as a Sevak.

The following are not independent Sevak eligibility categories:

```text
YOUTH
TEENAGER
STUDENT
```

---

## SEV-014 — Age Eligibility

There is no additional Sevak-specific age restriction beyond the applicable NSS Membership eligibility rules.

No independent Sevak:

```text
min_age
max_age
```

restriction is defined by this rule.

---

# 7. Enrollment

## SEV-015 — Direct Enrollment

An eligible NSS Member may be directly enrolled as a Sevak.

No separate application-review workflow is required by the core Sevak enrollment model.

An authorized user performs the enrollment action.

Enrollment shall be recorded and audited.

Enrollment does not create:

* New NSS Membership
* New Sangha Sevi ID
* Separate Person identity

---

# 8. Participation Status

## SEV-016 — Status Values

Sevak participation has only two status values:

```text
ACTIVE
INACTIVE
```

The following are not Sevak participation statuses:

```text
PROBATIONARY_SEVAK
REGULAR_SEVAK
COMPLETED
WITHDRAWN
```

Every Sevak participation record shall have a start date.

---

# 9. Inactivation Rules

## SEV-017 — No Automatic Inactivity

The system shall not automatically change:

```text
ACTIVE
    ↓
INACTIVE
```

because of non-attendance.

There is no attendance-based automatic inactivity trigger.

An authorized person performs manual inactivation unless an authoritative lifecycle event causes system-generated inactivation.

---

## SEV-018 — Follows NSS Membership Sakha

Sevak association follows the Member's current NSS Sakha.

There is no independent Sevak transfer workflow.

NSS Membership Transfer is authoritative.

When Membership transfers:

```text
Sakha A
    ↓
Sakha B
```

the Sevak association follows the applicable Membership lifecycle.

If the old Sakha participation becomes inactive:

```text
Status = INACTIVE
Source = SYSTEM
Reason = TRANSFERRED_TO_OTHER_SAKHA
```

No manual Sevak intervention is required.

If the new Sakha has a Sevak Sangha:

```text
New Sakha
    ↓
New Sevak Participation may be created
```

If the new Sakha has no Sevak Sangha:

```text
No new current Sevak participation
```

Historical participation remains preserved.

---

## SEV-019 — No Sevak Sangha in Current Sakha

If the current NSS Sakha does not have a Sevak Sangha:

* No current Sevak association exists for that Sakha.
* Previous Sevak history remains historical.
* The member does not acquire a current Sevak association with another Sakha.
* Local cross-Sakha Sevak participation is not created merely through attendance.

The separate rules for Anchalika/Zilla event participation are maintained in the relevant event document.

---

## SEV-020 — Historical Participation Preservation

When a Sevak becomes INACTIVE, the previous participation record shall remain available as historical information.

Inactivation does not physically delete:

* Enrollment
* Participation history
* Sakha association history
* Attendance history
* Reactivation review history

---

## SEV-021 — Mandatory Inactivation Reason

When an ACTIVE Sevak is manually changed to INACTIVE, a reason is mandatory.

### Manual source

```text
Inactivation Source = MANUAL
```

Permitted reasons:

```text
NO_LONGER_PARTICIPATING
PERSONAL_REASON
LONG_TERM_ABSENCE
OTHER
```

### System source

System-generated inactivation may use:

```text
TRANSFERRED_TO_OTHER_SAKHA
DECEASED
```

The database shall preserve the inactivation source.

System-generated inactivation requires no manual Sevak intervention.

---

## SEV-022 — Death-Triggered Inactivation

When the Person/Membership lifecycle marks the person as:

```text
DECEASED
```

the Sevak participation is automatically changed to:

```text
INACTIVE
```

with:

```text
Reason = DECEASED
Source = SYSTEM
```

No manual Sevak approval is required.

Death is a global Person lifecycle event and is not a Sevak-specific event.

---

# 10. Reactivation Rules

## SEV-023 — Reactivation Is Authorized

Reactivation means:

```text
INACTIVE
    ↓
ACTIVE
```

Reactivation is performed manually by an authorized user.

Reactivation shall be audited.

No reason is mandatory for reactivation.

Previous historical records remain unchanged.

Attendance does not itself perform reactivation.

---

## SEV-024 — Reactivation Review Cycle

When an INACTIVE Sevak attends an eligible Sevak activity, a reactivation review cycle is created or updated.

Rules:

1. INACTIVE Sevak attends.
2. Attendance is recorded normally.
3. Sevak remains INACTIVE.
4. An open reactivation review cycle is created if none exists.
5. Only one OPEN review cycle may exist per Sevak.
6. Additional attendance while the cycle is OPEN attaches to the existing cycle.
7. An authorized user reviews the cycle.
8. Reviewer may:

   * Keep INACTIVE
   * Reactivate to ACTIVE
9. No reason is mandatory for reactivation.
10. Once reviewed, the cycle becomes CLOSED.
11. Closed cycles remain permanently in history.
12. If still INACTIVE and the Sevak later attends after the previous cycle is closed, a new review cycle may be created.

Attendance never automatically changes Sevak status.

---

## SEV-025 — No Attendance-Based Automatic Reactivation

Attendance shall never perform:

```text
INACTIVE + ATTENDANCE
    =
ACTIVE
```

automatically.

Reactivation requires an authorized human decision.

The detailed participation/attendance behavior is maintained in:

```text
04_sevak_participation_rules.md
```

---

## SEV-026 — No Attendance-Based Inactivity Threshold

The previously considered two-month inactivity threshold is withdrawn.

No automatic inactivity threshold is implemented based on:

* Number of missed sessions
* Number of months without attendance
* Absence from Anchalika/Zilla Puja
* Absence from Sakha sessions

No attendance-based automatic inactivity mechanism exists.

---

# 11. Core Operational Relationship

## SEV-027 — Sevak Participation and Events Are Separate

Sevak participation status does not itself determine attendance.

The following remain separate:

```text
Participation Status
Eligibility
Event Visibility
Attendance Intention
Probable Attendance
Actual Attendance
```

Detailed rules are maintained in:

```text
04_sevak_participation_rules.md
```

---

# 12. Administrative Authority

## SEV-028 — Existing ERP RBAC

Sevak operations use the existing NSS ERP RBAC and organizational scope.

No separate Sevak-specific permission architecture is created at this stage.

Applicable organizational scopes include:

```text
SAKHA
ANCHALIKA
ZILLA
KENDRA
```

The permission matrix is maintained centrally by the Administration/RBAC module.

---

## SEV-029 — Authorized Sevak Actions

Depending on organizational scope and assigned permissions, authorized users may perform applicable actions including:

* Direct Sevak enrollment
* Manual ACTIVE → INACTIVE
* Inactivation reason entry
* Reactivation review
* INACTIVE → ACTIVE
* Sakha-level Sevak operations
* Anchalika/Zilla Sevak event operations
* Event creation
* Event publication
* Event management
* Attendance management

Specific office-bearer permissions are not hard-coded in this document.

---

# 13. Lifecycle References

## SEV-030 — Person and Membership Lifecycle Integration

Transfer and Death lifecycle events are authoritative external lifecycle events for Sevak participation.

Transfer follows:

```text
NSS Membership Lifecycle
```

Death follows:

```text
Person / Membership Lifecycle
```

The Sevak module consumes those lifecycle changes rather than creating independent transfer/death processes.

---

# 14. Governance Rules

## SEV-031 — Governance Status

Sevak governance rules are not fully frozen.

The following remain pending:

```text
Executive Positions
Selection / Election
Term Duration
Body Type
```

Where governance bodies are eventually defined, the common NSS Governance framework shall be used.

The provisional body type is:

```text
SEVAK_SANGHA_EXECUTIVE
```

No separate governance model is frozen by this document.

---

# 15. Training Rules

## SEV-032 — No Mandatory Training Hierarchy

No formal mandatory training hierarchy is currently frozen.

The following progression is not an active business rule:

```text
Orientation
    ↓
Basic
    ↓
Advanced
    ↓
Leadership
```

Training may exist as a future optional capability.

Previously proposed mandatory training tables are not frozen.

---

# 16. Enrollment and Association History

## SEV-033 — First Sevak Enrollment Date

The First Sevak Enrollment Date represents the date the person was first enrolled as a Sevak.

It is permanent.

It shall not change because of:

* Membership Transfer
* Sakha change
* Inactivation
* Reactivation

Example:

```text
First Sevak Enrollment Date
        =
01-Jan-2020
```

After transfer and reactivation, the date remains:

```text
01-Jan-2020
```

---

## SEV-034 — Sakha Association History

Sakha association shall be maintained as effective-dated history.

Example:

```text
Sakha A
01-Jan-2020 → 15-Aug-2026

Sakha B
15-Aug-2026 → Current
```

The current Sakha association is derived from the applicable active/current history record.

Historical associations shall never be deleted.

---

# 17. Seva Relationship

## SEV-035 — Seva Is Separate From Sevak Status

Seva participation is separate from:

```text
Sevak ACTIVE / INACTIVE
```

A Sevak may have Seva Assignments subject to the applicable Seva approval process.

Sevak status does not automatically approve or terminate every Seva Assignment.

Detailed rules are maintained in:

```text
seva/01_seva_business_rules.md
seva/02_upbs_seva_rules.md
```

---

## SEV-036 — Seva Assignment Is Independent

A Seva Assignment has its own:

* Category
* Approval
* Status
* Effective date
* History
* Audit trail

A Sevak may have multiple Seva Assignments.

One assignment does not automatically change another assignment.

---

# 18. Event Relationship

## SEV-037 — Two Current Sevak Sangha Event Types

The current approved Sevak Sangha event types are:

```text
SAKHA_SEVAK_SANGHA_SESSION
```

and:

```text
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

They are separate event types.

They have separate detailed rules for:

* Eligibility
* Participation
* Scheduling
* Notifications
* Attendance
* Reporting
* Dashboard behavior

Detailed rules are maintained in:

```text
sangha/01_sakha_sevak_sangha_session_rules.md
sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md
```

---

# 19. Other Event Framework

## SEV-038 — Future Sevak Events

The ERP may support future Sevak-related event types.

However, no additional specific Sevak event type is currently frozen.

A future event requires:

1. Business definition
2. Eligibility definition
3. Organizational scope
4. Host/location definition
5. Lifecycle definition
6. Approval/RBAC definition
7. Event Type Master entry
8. Event-specific documentation

Detailed framework is maintained in:

```text
events/01_other_sevak_event_rules.md
```

---

# 20. History and Audit

## SEV-039 — Historical Preservation

Historical Sevak information shall be preserved.

This includes:

* Enrollment
* Status changes
* Inactivation
* Reactivation
* Reactivation review
* Sakha association
* Event participation
* Seva assignments
* Approval history

Historical records shall not be physically deleted merely because their current status is inactive or ended.

---

## SEV-040 — Auditability

The following actions shall be auditable:

* Sevak enrollment
* Status changes
* Inactivation reason
* Inactivation source
* Reactivation
* Reactivation review
* Membership Transfer impact
* Death-triggered inactivation
* Sakha association changes
* Event-related administrative actions
* Seva-related actions

Audit requirements follow the common NSS ERP Audit Standards.

---

# 21. Core Business Principles

The following principles are consolidated from the existing Sevak business rules:

* Sevak Sangha is part of NSS.
* Sevak is not an NSS Membership Type.
* Sevak Sangha is not itself a governance body.
* Common NSS Membership applies.
* Sangha Sevi ID remains authoritative.
* No separate Sevak membership identity exists.
* NSS Membership is mandatory for Sevak participation.
* Eligible persons are Interested NSS Members and Existing Sevaks.
* No additional Sevak-specific age restriction is defined.
* Direct enrollment is permitted for eligible members.
* Sevak status values are ACTIVE and INACTIVE only.
* No attendance-based automatic inactivity exists.
* Manual inactivation requires a reason.
* Transfer-triggered inactivation is system-generated.
* Death-triggered inactivation is system-generated.
* NSS Membership Transfer is authoritative for Sakha changes.
* There is no independent Sevak transfer workflow.
* A Sakha may have no Sevak Sangha.
* Historical participation is preserved.
* INACTIVE does not automatically prohibit participation.
* Attendance does not automatically reactivate a Sevak.
* INACTIVE attendance can create a reactivation review cycle.
* Only one open reactivation review cycle may exist per Sevak.
* Reactivation requires authorized human action.
* Reactivation does not require a reason.
* The previously considered two-month inactivity threshold is withdrawn.
* First Sevak Enrollment Date is permanent.
* Sakha association is effective-dated history.
* Sevak status and Seva Assignment status are independent.
* Multiple Seva Assignments are permitted.
* Seva Categories are master-data driven.
* Seva rules are maintained separately.
* Two current Sevak Sangha event types are recognized.
* Sakha and Anchalika/Zilla event rules are maintained separately.
* Future event types require explicit business definition.
* Existing ERP RBAC governs Sevak permissions.
* Governance rules remain partially pending.
* No mandatory training hierarchy is currently frozen.
* Historical records are never physically deleted.
* Auditability is mandatory.

---

# 22. SEV Identifier Consolidation

The previous version of this document contained identifier collisions.

The source contains:

```text
SEV-024
```

for both:

```text
Sevak Reactivation
```

and:

```text
Status Does Not Prohibit Attendance
```

It also contains:

```text
SEV-025
```

for both:

```text
Reactivation Review Cycle
```

and:

```text
Attendance by INACTIVE Sevak
```

Additionally:

```text
SEV-032
```

was used for both:

```text
Cross-Anchalika/Zilla Attendance
```

and:

```text
Existing ERP RBAC
```

These collisions existed in the source and are not silently ignored.

For the consolidated document:

* The original core lifecycle identifiers are retained.
* Event-specific attendance identifiers are no longer used in this core document.
* Event-specific rules are maintained in their dedicated documents.
* The final cross-document SEV identifier registry shall be finalized after all migrated rules have been reviewed.
* No new SEV identifier shall be invented merely to hide an unresolved historical collision.

---

# 23. Related Documents

```text
04_sevak_participation_rules.md

sangha/
├── 01_sakha_sevak_sangha_session_rules.md
└── 02_anchalika_zilla_sevak_sangha_puja_rules.md

seva/
├── 01_seva_business_rules.md
└── 02_upbs_seva_rules.md

events/
└── 01_other_sevak_event_rules.md
```

Related core modules:

```text
../../membership/
../../attendance/
../../administration/
../../reports/
```

---

# End of Document
