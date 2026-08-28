# NSS ERP — Other Sevak Event Rules

**Document ID:** SOL-SEV-EVENT-001  
**Version:** 1.0.0  
**Status:** DRAFT — CONSOLIDATION IN PROGRESS  
**Parent Module:** Sevak Sangha  
**Scope:** Future / Other Sevak Events

---

# 1. Purpose

This document defines the common framework for handling future Sevak-related events that are not currently covered by the two approved Sevak Sangha event types.

The currently defined Sevak Sangha event types are:

```text
SAKHA_SEVAK_SANGHA_SESSION

ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

These remain separately governed by:

```text
../sangha/01_sakha_sevak_sangha_session_rules.md

../sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md
```

The current project source does not define a third specific Sevak event type. Therefore, this document provides only the future-event framework and does not introduce an unapproved event type.

---

# 2. Current Event Types

At the current stage, the Sevak module recognizes two specific Sevak Sangha event types:

```text
SAKHA_SEVAK_SANGHA_SESSION
    ↓
Local Sakha Sevak Sangha activity
```

and:

```text
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
    ↓
Larger periodic Anchalika/Zilla gathering
```

These are distinct event types.

They must remain separately identifiable for:

* Eligibility
* Participation
* Attendance
* Notifications
* Reporting
* Dashboards
* History

---

# 3. No Unapproved Event Type

The ERP shall not introduce a new Sevak-specific event type merely because the generic event framework supports it.

A new Sevak event type shall require an approved business definition before it becomes an operational event type.

Therefore:

```text
Future Event Idea
      ↓
Business Definition
      ↓
Approval
      ↓
Event Type Master
      ↓
Operational Event
```

No specific future event is frozen by this document.

---

# 4. Future Event Type Definition

When a new Sevak event is approved, its Event Type definition should identify at least:

* Event Type Code
* Event Type Name
* Purpose
* Organizational Scope
* Eligible Participants
* Participation Rules
* Host Organization
* Location Rules
* Scheduling Rules
* Notification Rules
* Intention Rules
* Probable Attendance Rules, if applicable
* Actual Attendance Rules
* Cancellation Rules
* Rescheduling Rules
* Reconciliation Rules
* Completion Rules
* Correction Rules
* Visibility Rules
* Approval Authority

The final definition shall be maintained in a dedicated event-specific document where the event is sufficiently complex.

---

# 5. Event Type Should Be Master-Data Driven

Future event types should be represented through the ERP's event-type master rather than being hard-coded into application logic.

Conceptually:

```text
Event Type Master
        ↓
Approved Event Type
        ↓
Event Definition
        ↓
Event Instance
```

This allows the ERP to support future NSS activities without redesigning the entire event framework.

---

# 6. Event-Specific Business Rules

A future event shall not automatically inherit every rule from:

```text
SAKHA_SEVAK_SANGHA_SESSION
```

or:

```text
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

Instead, common event rules may be reused where applicable, while event-specific rules must be explicitly defined.

For example:

```text
Common
    ↓
Event lifecycle
Attendance
Audit
Notifications
```

may be reused.

But:

```text
Eligibility
Participation scope
Gender
Host
Frequency
Location
Approval
```

must be explicitly confirmed for the new event.

---

# 7. Event Creation

A future Sevak event shall be created only by an authorized user.

The event creation process shall identify:

* Event Type
* Organizational Scope
* Host Organization
* Date
* Time
* Location
* Applicable eligibility
* Event status

No recurring schedule shall be assumed unless specifically defined for that event type.

---

# 8. Host Organization

Where a future event requires a host organization, the host shall be explicitly recorded.

The host may be:

* Sakha
* Anchalika
* Zilla
* Kendra
* Another approved organizational unit

The applicable host level must be defined by the event-specific business rules.

The system shall not assume that every future Sevak event is hosted by a Sakha.

---

# 9. Location

Location rules shall be event-specific.

A future event may use:

```text
Registered Organization Location
```

or:

```text
Approved Event Venue
```

depending on its business rules.

If a registered organization location is used, the event should preserve a location snapshot for historical integrity.

---

# 10. Organizational Scope

A future event shall explicitly define its organizational scope.

Possible scopes may include:

```text
SAKHA
ANCHALIKA
ZILLA
KENDRA
MULTI_ORGANIZATION
```

The scope determines the initial eligibility population and administrative authority.

The scope shall not be inferred solely from the event name.

---

# 11. Eligibility

Eligibility shall be defined independently for each future event type.

The system may derive eligibility from authoritative:

* Person records
* NSS Membership
* Sangha Sevi ID
* Current Sakha
* Anchalika
* Zilla
* Sevak participation
* Other approved participation records

Eligibility must be calculated from authoritative records rather than manually maintained lists wherever practical.

---

# 12. Eligibility vs Attendance

The common distinction shall remain:

```text
Eligibility
    ≠
Attendance
```

A person being eligible does not mean the person attended.

Actual attendance must be recorded separately.

---

# 13. Eligibility vs Visibility

A future event may be visible on the Member Dashboard even when a member is not eligible to participate.

Therefore:

```text
Visibility
    ≠
Eligibility
```

The event-specific rules shall determine who may see the event and who may participate.

---

# 14. Participation Intention

A future event may support optional attendance intention.

Where enabled, the event may provide:

```text
I'M INTERESTED / I'LL ATTEND

I WON'T BE ATTENDING
```

The intention mechanism shall be used for planning where appropriate.

Intention does not constitute actual attendance.

The event-specific document shall define whether intention is available.

---

# 15. No Response

Where intention is enabled:

```text
NO RESPONSE
```

shall remain a valid state.

It shall not automatically mean:

```text
I WON'T BE ATTENDING
```

This follows the common Sevak event intention model already frozen for current events.

---

# 16. Probable Attendance

A future event may use probable attendance if organizational planning requires it.

If probable attendance is enabled, the event-specific rules shall define:

* Who is automatically included
* Who is included based on intention
* Who is excluded
* Whether cross-organizational participants are included
* Whether the host can see individual names
* Whether the host can see aggregate counts

Probable attendance shall remain separate from actual attendance.

---

# 17. Actual Attendance

Actual attendance shall remain independent of probable attendance.

Therefore:

```text
Probable Attendance
        ≠
Actual Attendance
```

A legitimate participant who was not previously included in probable attendance may still be recorded as actually present where the event rules permit.

This follows the current Sevak event framework.

---

# 18. One Person — One Participant

Where a future event maintains a participant list:

```text
One Person
    ↓
One Participant Record
    ↓
One Attendance Record
```

A person qualifying through multiple eligibility conditions shall still appear only once.

This follows the existing Sevak unique-participant principle.

---

# 19. INACTIVE Sevak Participation

An INACTIVE Sevak is not automatically prohibited from attending a Sevak-related event.

Where the future event permits Sevak participation, an INACTIVE Sevak may attend unless the event-specific rules explicitly establish otherwise.

Where attendance by an INACTIVE Sevak occurs:

```text
Attendance
    ↓
Status remains INACTIVE
    ↓
Reactivation Review
```

Attendance shall never automatically reactivate the Sevak.

This follows the common Sevak Participation Rules.

---

# 20. Reactivation Review

Where a future event permits INACTIVE Sevak participation, attendance shall use the common reactivation-review mechanism.

The system shall:

1. Record attendance.
2. Keep Sevak status unchanged.
3. Create or attach to an open reactivation review cycle.
4. Allow authorized human review.
5. Preserve the review history.

The future event shall not implement its own independent reactivation mechanism.

---

# 21. Cross-Organizational Participation

A future event may permit participants from organizations outside its primary organizational scope.

If so, the event-specific rules must explicitly define:

* Which outside participants are eligible.
* Whether intention is required.
* Whether probable attendance includes them.
* Whether approval is required.
* How attendance is recorded.

Participation in another organization's event shall not automatically change:

* NSS Membership
* Current Sakha
* Anchalika
* Zilla
* Sevak association

Attendance is not Membership Transfer.

---

# 22. No Automatic Organizational Transfer

Participation in any future event shall not automatically change the person's organizational affiliation.

Therefore:

```text
Event Attendance
      ≠
Membership Transfer
```

and:

```text
Event Attendance
      ≠
Sevak Transfer
```

NSS Membership Transfer remains the authoritative mechanism for current Sakha changes.

---

# 23. Event Lifecycle

Where applicable, a future event may use the common lifecycle:

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

Alternative lifecycle:

```text
DRAFT
   ↓
PUBLISHED / CONFIRMED
   ↓
CANCELLED
```

or:

```text
PUBLISHED / CONFIRMED
   ↓
RESCHEDULED
   ↓
New Date / Time
```

The event-specific rules may extend this lifecycle where necessary.

---

# 24. Draft

A future event in `DRAFT` status shall not be treated as a published member-facing event.

Normal draft behavior:

* Not shown as a confirmed upcoming event.
* No member notification.
* Editable by authorized users.
* May be prepared internally.

---

# 25. Published / Confirmed

The event becomes member-facing only when explicitly marked:

```text
PUBLISHED / CONFIRMED
```

At that point, the applicable:

* Dashboard visibility
* Notifications
* Intention
* Participation planning

may become active.

The exact behavior shall be event-specific.

---

# 26. Notifications

Notifications shall be triggered according to the event lifecycle and event-specific rules.

At minimum, where applicable, notifications may be generated for:

* Publication
* Cancellation
* Rescheduling
* Important event changes

A draft event shall not generate normal participant notifications.

---

# 27. Cancellation

A future event may support cancellation.

If enabled:

```text
Event
    ↓
CANCELLED
```

The event record shall remain historically preserved.

Cancellation should:

* Remove the event from applicable upcoming views.
* Prevent new attendance after the cancellation effective time.
* Preserve existing intentions.
* Preserve event history.
* Generate applicable notifications.
* Be audited.

---

# 28. Post-Start Cancellation

Where the event rules permit cancellation after start:

```text
Attendance Already Recorded
        ↓
Preserved
```

Attendance already recorded shall not be deleted merely because the event was subsequently cancelled.

No new attendance shall be recorded after the cancellation effective time.

---

# 29. Rescheduling

Where an event permits rescheduling:

* The same event identity should be retained.
* Original date/time shall remain in history.
* New date/time shall be recorded.
* Rescheduling action shall be audited.
* Members shall be notified where applicable.
* Intention shall be reconfirmed where intention is enabled.

These principles are already part of the current Sevak event framework.

---

# 30. Reconfirmation

If an event is rescheduled and supports attendance intention:

```text
Original Date
    ↓
Original Intention
    ↓
Event Rescheduled
    ↓
New Date
    ↓
New Intention Requested
```

The previous intention shall remain historical.

The new intention applies to the new date.

---

# 31. Attendance Reconciliation

Where reconciliation is applicable, the event shall remain open after the scheduled end time for a configurable period.

During reconciliation, authorized users may:

* Complete missing attendance.
* Add legitimate attendees.
* Correct attendance through permitted workflows.
* Reconcile probable and actual attendance.
* Generate required reactivation-review flags.

The event shall not become immediately immutable merely because its scheduled end time has passed.

---

# 32. Completion

A future event may be manually completed by an authorized organizer.

It may also support automatic completion after a configurable maximum reconciliation period.

The maximum period shall not be hard-coded by this framework document.

---

# 33. Completed Event

Once completed:

* Event remains available in history.
* Attendance remains preserved.
* Intention history remains preserved.
* Participant history remains preserved.
* Scheduling history remains preserved.
* Notifications remain auditable.
* Normal editing is restricted.

Completion shall never physically delete historical records.

---

# 34. Post-Completion Correction

After completion, normal editing shall be restricted.

Corrections shall use the centralized ERP correction workflow.

The correction must preserve:

* Original value
* Requested value
* Reason
* Requester
* Request timestamp
* Approver(s)
* Approval timestamp
* Final value
* Audit trail

The requester shall not approve their own correction.

The current Sevak framework already requires centralized post-completion correction and approval.

---

# 35. Approval Authority

A future event shall use the centralized NSS ERP RBAC and approval framework.

The event-specific document shall define any additional approval requirements.

The system should be able to determine approval from:

```text
Event Type
+
Organizational Level
+
Requester Role
+
Required Approver Role(s)
+
Approval Sequence
```

This follows the current event correction authority framework.

---

# 36. Event Visibility After Completion

A future event may provide generic completed-event information to members.

Possible information includes:

* Event Name
* Date
* Event Type
* Host
* Location
* Organizational scope
* General participation summary

Detailed individual attendance visibility is not automatically granted.

It remains subject to:

* RBAC
* Privacy
* Reports
* Event-specific rules

The current Sevak rules explicitly leave detailed member-facing result visibility subject to future centralized standards.

---

# 37. Relationship With Seva

A future Sevak event is not automatically a Seva assignment.

```text
Event Attendance
    ≠
Seva Assignment
```

If the event includes Seva activities, those assignments must be handled through the Seva framework.

Relevant rules:

```text
../seva/01_seva_business_rules.md

../seva/02_upbs_seva_rules.md
```

---

# 38. Relationship With Sakha-Level Session

A future event shall not be classified as:

```text
SAKHA_SEVAK_SANGHA_SESSION
```

unless it actually satisfies the approved Sakha-Level Session definition.

The Sakha-Level rules remain in:

```text
../sangha/01_sakha_sevak_sangha_session_rules.md
```

---

# 39. Relationship With Anchalika/Zilla Puja

A future event shall not be classified as:

```text
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

unless it satisfies the approved Anchalika/Zilla event definition.

The Anchalika/Zilla rules remain in:

```text
../sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md
```

---

# 40. Audit and History

All future event actions shall be auditable.

Depending on the event, this may include:

* Event creation
* Event type
* Eligibility generation
* Publication
* Notifications
* Intention
* Probable attendance
* Attendance
* Cancellation
* Rescheduling
* Reconciliation
* Completion
* Corrections
* Approvals
* Reactivation review

Historical event information shall not be physically deleted.

---

# 41. No Hard-Coded Future Rules

This framework shall not hard-code assumptions about future events.

In particular, it shall not assume:

* Fixed frequency
* Fixed host level
* Fixed location model
* Fixed participant gender
* Fixed eligibility
* Fixed organizational scope
* Fixed approval chain
* Fixed intention requirement
* Fixed probable-attendance model

These must be defined when the future event is approved.

---

# 42. Future Event Definition Process

When NSS introduces a new Sevak event:

```text
New Event Proposal
        ↓
Business Rule Definition
        ↓
Eligibility Definition
        ↓
Organizational Scope
        ↓
Host / Location Definition
        ↓
Lifecycle Definition
        ↓
Approval / RBAC Definition
        ↓
Event Type Master
        ↓
Dedicated Event Rules Document
        ↓
Implementation
```

The event shall not proceed directly from proposal to database implementation.

---

# 43. Dedicated Event Documentation

If a future event has sufficiently complex business rules, it should receive its own document.

For example:

```text
events/
├── 01_other_sevak_event_rules.md
├── 02_<future_event>_rules.md
└── 03_<another_future_event>_rules.md
```

The exact file name shall be chosen when the event is approved.

---

# 44. Current Frozen Boundary

At this stage, this document does **not** define any additional operational Sevak event.

The only approved Sevak-specific event types are:

```text
SAKHA_SEVAK_SANGHA_SESSION

ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

This document therefore remains a framework for future expansion.

---

# 45. Frozen Principles

The following principles are approved:

* The Sevak module supports future event expansion.
* New event types must be explicitly defined before operational use.
* Event types should be master-data driven.
* Event-specific rules must be explicitly documented.
* No unapproved future event type is introduced by this document.
* Current Sevak event types remain distinct.
* Eligibility and attendance remain separate.
* Visibility and eligibility remain separate.
* Intention and attendance remain separate.
* Probable attendance and actual attendance remain separate where probable attendance is used.
* One person shall have one participant representation per event where participant records are used.
* INACTIVE Sevaks may participate where the event permits Sevak participation.
* INACTIVE attendance does not automatically reactivate a Sevak.
* Reactivation uses the common Sevak review mechanism.
* Event attendance does not change Membership or organizational affiliation.
* Future events may permit cross-organizational participation only when explicitly defined.
* Event lifecycle may use the common DRAFT → PUBLISHED/CONFIRMED → ATTENDANCE → RECONCILIATION → COMPLETED model.
* Cancellation and rescheduling preserve historical event identity.
* Rescheduling requires intention reconfirmation where intention is enabled.
* Post-start cancellation preserves attendance already recorded.
* Completion preserves event and attendance history.
* Post-completion corrections use centralized approval and audit.
* Future event approval uses centralized RBAC/authority rules.
* Seva remains separate from event participation.
* Historical records are never physically deleted.
* Future event rules shall not be silently inferred from existing event types.

---

# 46. Related Documents

```text
../01_sevak_module_overview.md
../02_sevak_erd.md
../03_sevak_lifecycle.md
../04_sevak_participation_rules.md
../05_sevak_business_rules.md
../06_sevak_table_design.md

../sangha/01_sakha_sevak_sangha_session_rules.md
../sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md

../seva/01_seva_business_rules.md
../seva/02_upbs_seva_rules.md

../../administration/
../../attendance/
../../membership/
../../reports/
```

---

# End of Document
