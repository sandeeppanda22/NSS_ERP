# NSS ERP — Sevak Sangha Module Overview

**Document ID:** SOL-SEV-001  
**Version:** 2.0.0  
**Status:** DRAFT — CONSOLIDATION IN PROGRESS  
**Module:** Sevak Sangha  
**Module Code:** SEV

---

# 1. Purpose

The Sevak Sangha Module manages the NSS framework for Sevak participation, development, participation in Sevak Sangha activities, Seva engagement, and related operational events.

Sevak Sangha is an NSS institutional structure associated with:

- Training
- Volunteer development
- Service
- Character development
- Leadership development

It is not an NSS Membership Type and is not a separate membership identity.

The current business rules establish Sevak Sangha as an additional participation layer on top of the common NSS Person and Membership framework.

---

# 2. Institutional Nature

Sevak Sangha is:

```text
NSS Institution
      │
      ├── Training Organization
      ├── Volunteer Organization
      ├── Service Organization
      └── Leadership Development Platform
```

It is not:

```text
NSS Membership Type
Governance Body
Election Body
Separate Membership Identity
```

These distinctions are fundamental to the module architecture.

---

# 3. Historical Context

The project source records Sevak Sangha as an important NSS operational institution.

Historical references include:

### 1973

First Sevak Sangha recorded at:

```text
Naukona Sangha
Kendrapara District
18 Members
```

### 1987

```text
Ekamra Sevak Sangha
Satsikshya Mandir
Bhubaneswar
```

was established with a focus including:

* UPBS Volunteer Training
* Departmental Seva Training

### 1991

```text
Kendra Sevak Sangha
```

was established, with the Ekamra Sevak Sangha becoming part of the Kendra structure.

The historical material also records support for:

* Bhakta Sammilanis
* UPBS
* Social Initiatives
* Training Programs
* Volunteer Development

These historical details are retained as institutional context and are not themselves operational database rules.

---

# 4. Module Boundary

The Sevak module owns the lifecycle and participation of Sevaks.

It does not own the authoritative Person or NSS Membership identity.

Conceptually:

```text
Person
   │
   ▼
NSS Membership
   │
   ▼
Sangha Sevi ID
   │
   ▼
Sevak Participation
```

Therefore:

```text
Person ≠ Member
Member ≠ Sevak
Sevak ≠ Separate Membership
```

---

# 5. Relationship With Person

Person is the foundational identity.

The Sevak module references the existing Person record.

The Sevak module shall not create a duplicate person identity.

A person's:

* Name
* Date of Birth
* Gender
* Contact information
* Other Person-level identity information

remain owned by the Person module.

---

# 6. Relationship With NSS Membership

NSS Membership is mandatory for Sevak participation.

The Sevak module does not create a separate membership.

The relationship is:

```text
NSS Membership
       │
       ▼
Sangha Sevi ID
       │
       ▼
Sevak Participation
```

The existing NSS Membership Types remain authoritative:

```text
PROBATIONARY_MEMBER
REGULAR_MEMBER
ASSOCIATE_MEMBER
```

Sevak status must not duplicate these membership statuses.

---

# 7. Sangha Sevi ID

The Sangha Sevi ID remains the authoritative NSS Membership identity.

The Sevak module does not generate another permanent Sevak identity.

There is no separately frozen:

```text
SV000001
SV000002
...
```

identity.

The person's Sevak participation is associated with the existing Person and Membership identity.

---

# 8. Sevak Eligibility

Current frozen eligibility is based on NSS Membership.

Eligible persons include:

```text
Interested NSS Members
Existing Sevaks
```

NSS Membership is mandatory.

No non-member may be registered as a Sevak.

There is no additional Sevak-specific age restriction beyond the applicable NSS Membership eligibility rules.

The earlier conceptual classification of:

```text
Youth
Teenagers
Students
```

is not maintained as independent Sevak eligibility categories.

---

# 9. Sevak Enrollment

An eligible NSS Member may be directly enrolled as a Sevak.

The current workflow is:

```text
Eligible NSS Member
        │
        ▼
Authorized Enrollment
        │
        ▼
ACTIVE Sevak Participation
```

No separate application-review workflow is required by the current core Sevak enrollment rules.

Enrollment is:

* Authorized
* Recorded
* Auditable
* Historically preserved

---

# 10. Sevak Participation Status

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

Every participation has a start date.

---

# 11. Sevak Lifecycle

The core lifecycle is:

```text
NSS Membership
      │
      ▼
Eligibility
      │
      ▼
Sevak Enrollment
      │
      ▼
ACTIVE
      │
      ├───────────────┐
      │               │
      ▼               ▼
   INACTIVE         Transfer
      │               │
      │               ▼
      │        Old participation
      │          INACTIVE
      │               │
      │               ▼
      │         New Sakha Check
      │
      ▼
Reactivation Review
      │
      ├── Keep INACTIVE
      │
      └── Reactivate ACTIVE
```

Death is handled as a global Person/Membership lifecycle event:

```text
Person/Membership
      │
      ▼
DECEASED
      │
      ▼
Sevak Participation
      │
      ▼
INACTIVE
Reason = DECEASED
Source = SYSTEM
```

---

# 12. Inactivation

Manual inactivation requires a reason.

Manual reasons:

```text
NO_LONGER_PARTICIPATING
PERSONAL_REASON
LONG_TERM_ABSENCE
OTHER
```

System-generated reasons include:

```text
TRANSFERRED_TO_OTHER_SAKHA
DECEASED
```

System-generated inactivation requires no manual Sevak intervention.

---

# 13. Membership Transfer

Sevak association follows the member's current NSS Sakha.

There is no independent Sevak Transfer workflow.

When Membership transfers:

```text
Sakha A
   │
   ▼
Sakha B
```

the old participation is automatically:

```text
Status = INACTIVE
Reason = TRANSFERRED_TO_OTHER_SAKHA
Source = SYSTEM
```

If the new Sakha has a Sevak Sangha, a new current participation may be created.

If it does not, no new current local Sevak participation is created.

Historical records remain preserved.

---

# 14. Sakha Without Sevak Sangha

A Sakha may or may not have a Sevak Sangha.

If the member's current Sakha has no Sevak Sangha:

```text
No Current Local Sevak Participation
```

Previous Sevak history remains historical.

A member does not acquire another Sakha's Sevak participation simply by attending that Sakha's local Sevak Sangha session.

---

# 15. Death Lifecycle

Death is a global Person/Membership lifecycle event.

It is not a manually initiated Sevak operation.

When the authoritative Person/Membership lifecycle records:

```text
DECEASED
```

the Sevak participation automatically becomes:

```text
INACTIVE
Reason = DECEASED
Source = SYSTEM
```

The same deceased status is intended to be visible across applicable ERP identity/participation records, not only within the Sevak module.

---

# 16. Reactivation

Reactivation is:

```text
INACTIVE
      │
      ▼
Authorized Review
      │
      ▼
ACTIVE
```

Reactivation:

* Requires authorized human action.
* Does not require a reason.
* Does not change the original enrollment date.
* Must be audited.
* Preserves previous history.

Attendance never automatically reactivates a Sevak.

---

# 17. Reactivation Review

When an INACTIVE Sevak attends an applicable Sevak activity:

```text
Attendance
    │
    ▼
Reactivation Review Cycle
```

The system:

1. Records attendance.
2. Keeps the Sevak INACTIVE.
3. Creates or updates an OPEN review cycle.
4. Allows additional attendance to attach to the same OPEN cycle.
5. Allows an authorized user to review.
6. Allows the reviewer to:

   * Keep INACTIVE
   * Reactivate ACTIVE
7. Closes the review cycle after decision.
8. Preserves the closed cycle permanently.

Only one OPEN review cycle may exist for a Sevak at a time.

---

# 18. Attendance-Based Inactivity

There is no attendance-based automatic inactivity.

The previously considered two-month inactivity rule is withdrawn.

The ERP shall not automatically change:

```text
ACTIVE → INACTIVE
```

because of:

* Missed sessions
* Consecutive absences
* Lack of attendance for two months
* Missing Anchalika/Zilla Puja
* Any other attendance threshold

This is important because Sakha-level session frequency varies and Anchalika/Zilla Sevak Sangha Puja is typically approximately six-monthly.

---

# 19. Participation and Attendance

The following are separate concepts:

```text
Participation Status
Eligibility
Visibility
Attendance Intention
Probable Attendance
Actual Attendance
```

For example:

```text
ACTIVE
    ≠
Must Attend
```

and:

```text
Eligible
    ≠
Present
```

and:

```text
I'LL ATTEND
    ≠
PRESENT
```

---

# 20. Sevak Sangha Event Structure

There are currently two operational Sevak Sangha event types:

```text
SAKHA_SEVAK_SANGHA_SESSION
```

and:

```text
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

They are separate event types.

Their detailed rules are maintained in:

```text
sangha/01_sakha_sevak_sangha_session_rules.md

sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md
```

---

# 21. Sakha-Level Sevak Sangha

A Sakha may have its own Sevak Sangha.

Where it exists:

* Sessions generally occur after Sunday Sangha Puja.
* Frequency depends on the individual Sakha.
* It is not necessarily every Sunday.
* There is no fixed universal recurring schedule.

The event is a local Sakha activity.

Cross-Sakha Sevak participation is not created through attendance at another Sakha's local session.

---

# 22. Anchalika/Zilla Sevak Sangha Puja

The Anchalika/Zilla event is a larger Sevak Sangha gathering.

Current operational understanding:

```text
Anchalika/Zilla
      │
      ▼
Sevak Sangha Puja
      │
      ▼
Hosted by a Sakha within that area
```

It typically occurs approximately once every six months.

The frequency is configurable and is not hard-coded.

The host Sakha is the host/venue and does not become the participant's organizational affiliation.

---

# 23. Cross-Anchalika/Zilla Participation

A Sevak from another Anchalika/Zilla may attend a permitted Anchalika/Zilla Sevak Sangha Puja.

This does not change:

* Membership
* Current Sakha
* Anchalika
* Zilla
* Sevak association

Therefore:

```text
Cross-Anchalika/Zilla Attendance
        ≠
Membership Transfer
```

---

# 24. Event Eligibility

The system automatically derives eligible participants from authoritative records.

For Anchalika/Zilla events:

```text
Eligible Sevaks in Anchalika/Zilla
+
Male NSS Members in Anchalika/Zilla
```

For Sakha-level events:

```text
Eligible Sevaks of Sakha
+
Male NSS Members of Sakha
```

No manual list is required merely to establish eligibility.

---

# 25. Male Participation Rule

Sevak Sangha event participation is male-only.

This applies to:

```text
Sakha-Level Sevak Sangha
Anchalika/Zilla Sevak Sangha Puja
```

This rule is specific to Sevak Sangha participation.

It does not apply to Seva assignments.

---

# 26. Seva Relationship

Seva is a separate operational layer.

```text
Sevak Participation
        │
        └──────► Seva Assignment(s)
```

Seva Assignment is not the same as Sevak participation status.

A Sevak may have multiple Seva Assignments.

---

# 27. Seva Gender Rule

Sevak Sangha event participation is male-only.

Seva assignments are not gender-restricted by the Sevak Sangha rule.

Therefore:

```text
Sevak Sangha Participation
        ↓
Male participants
```

while:

```text
Seva Assignment
        ↓
Male or Female
```

subject to the applicable Seva Category eligibility and approval rules.

---

# 28. Sakha Seva

Regular Sakha Seva follows the approved Seva workflow:

```text
Sevak
   ↓
Seva Category
   ↓
Seva Head
   ↓
Sakha President
   ↓
Approved Assignment
```

Seva may originate from:

```text
SEVAK_REQUEST
```

or:

```text
SEVA_HEAD_RECOMMENDATION
```

---

# 29. UPBS Seva

UPBS Seva has its own approval workflow:

```text
Sevak
   ↓
UPBS Seva Category
   ↓
UPBS Seva Head
   ↓
Kendra
   ↓
Parichalak / President
   ↓
Approved Assignment
```

UPBS Seva is maintained separately from regular Sakha Seva.

---

# 30. Multiple Seva Assignments

A Sevak may have multiple active Seva Assignments simultaneously.

For example:

```text
Sevak
 ├── Sakha Seva A
 ├── Sakha Seva B
 └── UPBS Seva
```

Each assignment has its own:

* Category
* Approval
* Status
* Effective date
* History
* Audit trail

One assignment does not automatically approve, reject, activate or terminate another.

---

# 31. Seva After Sevak Inactivation

When a Sevak becomes INACTIVE:

```text
Sevak
ACTIVE → INACTIVE
```

existing Seva Assignments are not automatically terminated.

Each active assignment is flagged for review by the applicable Seva authority.

The result may be:

```text
CONTINUE
```

or:

```text
END / INACTIVE
```

Sevak status and Seva Assignment status remain independent.

---

# 32. Seva After Membership Transfer

Membership Transfer changes current Sakha.

It does not create an independent Sevak Transfer workflow.

Sakha-specific Seva associated with the old Sakha becomes historical.

A new Sakha Seva requires a new request/approval process.

UPBS Seva is not automatically terminated by Membership Transfer and follows the applicable UPBS/Kendra review process.

---

# 33. Training

Training is an organizational capability of Sevak Sangha.

Possible areas include:

```text
Sadachara
Seva Training
Volunteer Development
UPBS Volunteer Training
Leadership Development
```

However, there is currently no formal mandatory training hierarchy.

The following progression is not frozen:

```text
Orientation
   ↓
Basic
   ↓
Advanced
   ↓
Leadership
```

Training shall therefore not be used as a mandatory lifecycle gate.

---

# 34. Orientation

Orientation may be conducted as an operational activity.

However:

* It is not a Sevak participation status.
* It is not mandatory for ACTIVE status under current rules.
* It does not automatically create Seva.
* It does not automatically create a governance position.

Any future formal orientation workflow shall be separately documented.

---

# 35. Volunteer Development

Volunteer development is an objective of Sevak Sangha.

It is not a separate participation status.

Conceptually:

```text
Training
   ↓
Volunteer Development
   ↓
Service Participation
```

This is an organizational development pathway rather than a mandatory database lifecycle.

---

# 36. Leadership Development

Sevak Sangha supports leadership development through:

* Service
* Volunteer responsibilities
* Organizational experience
* Training where applicable

The exact executive/leadership structure remains pending.

Any actual governance position must use the common NSS Governance framework.

---

# 37. UPBS Volunteer Relationship

Sevak Sangha may support UPBS Volunteer preparation/training.

However, UPBS registration and operational ownership remain with the UPBS module.

Therefore:

```text
Sevak Sangha
      ↓
Possible UPBS Volunteer Preparation
      ↓
UPBS Module
      ↓
UPBS Volunteer Registration / Operations
```

Sevak status does not itself make a person a registered UPBS Volunteer.

---

# 38. Kishor Relationship

A possible Kishor → Sevak pathway may exist.

However, it is not automatic.

The transition must follow:

* Applicable Kishor rules
* NSS Membership rules
* Sevak eligibility
* Authorized enrollment

Therefore:

```text
Kishor
   ↓
Possible Future Transition
   ↓
NSS Membership
   ↓
Sevak Eligibility
   ↓
Sevak Enrollment
```

No automatic conversion is defined.

---

# 39. Governance

Sevak Sangha may have organizational leadership/governance structures.

However, the following remain pending:

```text
Executive Positions
Selection / Election
Term Duration
Exact Body Structure
```

The provisional body type is:

```text
SEVAK_SANGHA_EXECUTIVE
```

Where governance is implemented, the common Unified Governance Model shall be used.

---

# 40. Event Management

Events use the common ERP Event framework.

The current Sevak event lifecycle is:

```text
DRAFT
   ↓
PUBLISHED / CONFIRMED
   ↓
EVENT
   ↓
ATTENDANCE
   ↓
RECONCILIATION
   ↓
COMPLETED
```

An event may also be:

```text
CANCELLED
```

or:

```text
RESCHEDULED
```

---

# 41. Event Publication

A Sevak event becomes member-facing only when:

```text
PUBLISHED / CONFIRMED
```

Before publication:

```text
DRAFT
```

means:

* Not visible as a confirmed member event.
* No normal participant notifications.
* Event remains editable by authorized users.

After publication:

* Applicable dashboard visibility becomes active.
* Notifications are sent.
* Respective Sanghas are notified.

---

# 42. Attendance Intention

Where enabled, members may indicate:

```text
I'M INTERESTED / I'LL ATTEND
```

or:

```text
I WON'T BE ATTENDING
```

The response is optional.

No response is a valid state.

Intention is for organizational planning and does not constitute actual attendance.

---

# 43. Probable Attendance

The host Sangha can see:

```text
Probable Attendance Count
+
Individual Probable Participant Details
```

Probable attendance may include:

1. Applicable Sevaks, including ACTIVE and INACTIVE Sevaks.
2. Host Sakha's male NSS Members.
3. Other eligible male NSS Members who indicate `I'LL ATTEND`.
4. Permitted cross-Anchalika/Zilla Sevaks.

All participants are deduplicated by Person.

---

# 44. Three Attendance Populations

The host shall distinguish:

```text
TOTAL ELIGIBLE
        ↓
PROBABLE ATTENDANCE
        ↓
ACTUAL ATTENDANCE
```

These are not interchangeable.

Actual attendance is not restricted to the probable attendance list.

---

# 45. Event Rescheduling

When an event is rescheduled:

* Same event identity is retained.
* New date/time is recorded.
* Historical scheduling information is preserved.
* Members are notified.
* Intention must be reconfirmed for the new date.
* Previous intention remains historical.
* Probable attendance is recalculated from current information.

---

# 46. Event Cancellation

A published/confirmed event may be cancelled.

Cancellation:

* Changes status to `CANCELLED`.
* Preserves event history.
* Removes it from applicable upcoming views.
* Prevents new attendance after cancellation.
* Preserves existing intention history.
* Generates applicable notifications.
* Is audited.

If cancellation occurs after event start, attendance already recorded remains preserved.

---

# 47. Event Completion

After the event ends, attendance remains open for reconciliation.

During reconciliation, authorized organizers may:

* Complete missing attendance.
* Add legitimate attendees.
* Correct permitted attendance errors.
* Reconcile probable vs actual attendance.
* Ensure INACTIVE attendance generates the appropriate reactivation review.

The event may then become:

```text
COMPLETED
```

or may automatically complete after the configurable reconciliation period.

---

# 48. Post-Completion Corrections

Once an event is completed, normal editing is restricted.

Corrections use the centralized ERP correction/audit workflow.

The correction preserves:

* Original value
* Requested value
* Reason
* Requester
* Request timestamp
* Approver
* Approval timestamp
* Final value
* Audit trail

The requester cannot approve their own correction.

---

# 49. RBAC

The Sevak module uses the existing NSS ERP RBAC framework.

No separate Sevak permission architecture is created.

Organizational scope may include:

```text
SAKHA
ANCHALIKA
ZILLA
KENDRA
```

Applicable permissions may include:

* Sevak enrollment
* Inactivation
* Reactivation review
* Reactivation
* Event management
* Attendance management
* Seva management

The detailed permission matrix remains centrally owned by Administration/RBAC.

---

# 50. Audit and History

The module follows the project-wide principle:

```text
HISTORY NEVER DELETED
```

Historical records include:

* Enrollment
* Status changes
* Inactivation
* Transfer
* Death-triggered inactivation
* Reactivation
* Reactivation review
* Sakha association
* Event participation
* Attendance
* Intention
* Seva assignments
* Approval history

Physical deletion of historical business records is prohibited.

---

# 51. Configuration Over Hardcoding

The module follows:

```text
CONFIGURATION OVER HARDCODING
```

Examples:

* Event frequency
* Event types
* Seva Categories
* Organizational scope
* Reconciliation period
* Approval configuration
* Applicable eligibility rules

The current approximate six-month Anchalika/Zilla frequency is operational guidance, not a hard-coded six-month recurrence.

---

# 52. Module Responsibilities

The Sevak module is responsible for:

```text
Sevak Enrollment
Sevak Participation
Sevak Lifecycle
Sevak Status
Sakha Association History
Reactivation Review
Sevak Event Participation
Sevak Event Attendance
Seva Assignment Integration
Sevak-specific Reporting Inputs
```

---

# 53. Module Does Not Own

The Sevak module does not own:

```text
Person Identity
NSS Membership Identity
Sangha Sevi ID Generation
General Membership Lifecycle
Global Death Identity
Membership Transfer Authority
UPBS Registration
Central RBAC
General Governance Framework
```

These remain owned by their respective modules.

---

# 54. Module Relationship Map

```text
                    ┌─────────────────┐
                    │     PERSON      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   MEMBERSHIP    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  SANGHA SEVI ID │
                    └────────┬────────┘
                             │
                             ▼
                 ┌────────────────────────┐
                 │   SEVAK PARTICIPATION  │
                 └───────────┬────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
     Lifecycle          Participation        Seva
          │                  │                  │
          │                  │                  ├── Sakha Seva
          │                  │                  └── UPBS Seva
          │                  │
          │                  ├── Sakha Session
          │                  └── Anchalika/Zilla Puja
          │
          ├── ACTIVE
          ├── INACTIVE
          ├── Transfer
          ├── Death
          └── Reactivation
```

---

# 55. Detailed Document Structure

The Sevak module is divided into the following documents:

```text
sevak/
│
├── 01_sevak_module_overview.md
│
├── 02_sevak_erd.md
│
├── 03_sevak_lifecycle.md
│
├── 04_sevak_participation_rules.md
│
├── 05_sevak_business_rules.md
│
├── 06_sevak_table_design.md
│
├── sangha/
│   ├── 01_sakha_sevak_sangha_session_rules.md
│   └── 02_anchalika_zilla_sevak_sangha_puja_rules.md
│
├── seva/
│   ├── 01_seva_business_rules.md
│   └── 02_upbs_seva_rules.md
│
└── events/
    └── 01_other_sevak_event_rules.md
```

---

# 56. Document Ownership

### Module Overview

```text
01_sevak_module_overview.md
```

Defines the module boundary and architecture.

### ERD

```text
02_sevak_erd.md
```

Defines conceptual entities and relationships.

### Lifecycle

```text
03_sevak_lifecycle.md
```

Defines lifecycle transitions.

### Participation

```text
04_sevak_participation_rules.md
```

Defines event participation and attendance behavior.

### Core Business Rules

```text
05_sevak_business_rules.md
```

Defines core Sevak business rules not delegated to specialized documents.

### Table Design

```text
06_sevak_table_design.md
```

Defines the final PostgreSQL table design.

---

# 57. Specialized Documents

### Sakha-Level Session

```text
sangha/01_sakha_sevak_sangha_session_rules.md
```

### Anchalika/Zilla Puja

```text
sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md
```

### General Seva

```text
seva/01_seva_business_rules.md
```

### UPBS Seva

```text
seva/02_upbs_seva_rules.md
```

### Future/Other Sevak Events

```text
events/01_other_sevak_event_rules.md
```

The specialized documents own their detailed business rules and should not be duplicated in the module overview.

---

# 58. Current Frozen Principles

The Sevak module currently follows these core principles:

* Sevak Sangha is an NSS institution.
* It is a training, volunteer, service and leadership-development organization.
* Sevak is not an NSS Membership Type.
* NSS Membership is mandatory.
* Sangha Sevi ID remains authoritative.
* No separate Sevak ID is frozen.
* Direct Sevak enrollment is permitted.
* Sevak status is ACTIVE or INACTIVE.
* No additional Sevak-specific age restriction exists.
* Manual inactivation requires a reason.
* Transfer-triggered inactivation is automatic.
* Death-triggered inactivation is automatic.
* No independent Sevak Transfer workflow exists.
* Sevak association follows current NSS Membership Sakha.
* Historical participation is preserved.
* INACTIVE does not automatically prohibit participation.
* Attendance does not automatically reactivate.
* Reactivation requires authorized human action.
* No attendance-based automatic inactivity exists.
* The two-month inactivity rule is withdrawn.
* Sakha-level and Anchalika/Zilla-level Sevak activities are distinct.
* Cross-Sakha participation is not created through local Sakha sessions.
* Cross-Anchalika/Zilla participation is permitted for applicable larger events.
* Sevak Sangha event participation is male-only.
* Seva assignments are not gender-restricted by the Sevak Sangha rule.
* Seva Assignment status is independent from Sevak status.
* Multiple Seva Assignments are permitted.
* UPBS Seva follows its separate approval process.
* Training hierarchy is not currently mandatory.
* Governance structure remains partially pending.
* Existing ERP RBAC is used.
* History is never physically deleted.
* Configuration is preferred over hardcoding.
* Auditability is mandatory.

---

# 59. Pending Areas

The following remain outside the currently frozen operational model:

```text
Executive Structure / Positions
Selection / Election Model
Term Duration
Formal Training Hierarchy
Certification / Recognition
Detailed Kishor → Sevak Transition
```

These must be explicitly approved before being converted into frozen business rules.

---

# 60. Completion Criteria for Module Freeze

The Sevak module can be considered fully documentation-ready when:

```text
✓ Module Overview
✓ Participation Rules
✓ Sakha Session Rules
✓ Anchalika/Zilla Puja Rules
✓ General Seva Rules
✓ UPBS Seva Rules
✓ Other Event Framework
✓ Core Business Rules
✓ Lifecycle
✓ ERD
✓ Table Design
```

have been reviewed together for consistency.

The current migration has completed the first eight documents.

The remaining documentation work is:

```text
Step 09 → Module Overview
Step 10 → ERD
Step 11 → Table Design
```

---

# 61. Related Modules

The Sevak module integrates with:

```text
Person
Membership
Organization
Attendance
Governance
Administration / RBAC
Seva
UPBS
Reports & Analytics
```

The Sevak module does not replace or duplicate the authoritative data owned by these modules.

---

# End of Document
