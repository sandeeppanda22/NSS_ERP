# NSS ERP — Sevak Participation Rules

**Document ID:** SOL-SEV-PART-001  
**Version:** 1.0.0  
**Status:** DRAFT — CONSOLIDATION IN PROGRESS  
**Parent Module:** Sevak Sangha  
**Scope:** Participation, Eligibility and Attendance

---

# 1. Purpose

This document defines the participation and attendance rules for Sevak Sangha activities.

It governs:

- Event participation eligibility
- Eligibility vs attendance
- ACTIVE and INACTIVE participation
- INACTIVE Sevak attendance
- Reactivation review
- Local Sakha participation
- Anchalika/Zilla participation
- Cross-Anchalika/Zilla participation
- Participant deduplication
- Attendance intention
- Probable attendance
- Actual attendance
- Attendance reconciliation

The Sevak lifecycle itself is defined in:

```text
03_sevak_lifecycle.md
```

Core Sevak business rules are defined in:

```text
05_sevak_business_rules.md
```

---

# 2. Fundamental Principle

The ERP shall maintain a strict distinction between:

```text
Participation Status
Eligibility
Visibility
Intention
Probable Attendance
Actual Attendance
```

These concepts are not interchangeable.

In particular:

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
I'll Attend
    ≠
Present
```

---

# 3. Current Sevak Event Types

The current operational Sevak event types are:

```text
SAKHA_SEVAK_SANGHA_SESSION
```

and:

```text
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

They are separate event types with separate operational scopes.

---

# 4. Sakha-Level Participation

A Sakha-Level Sevak Sangha Session is a local activity of the host Sakha.

Participation is therefore limited to the applicable local Sakha participation population.

The event is not a mechanism for creating cross-Sakha Sevak participation.

---

# 5. Local Sakha Participation Boundary

A member does not normally attend another Sakha's local Sevak Sangha Session as a participant of that other Sakha's Sevak Sangha.

Therefore:

```text
Member of Sakha A
        ↓
Sakha B local Sevak Sangha Session
        ↓
Does NOT create Sakha B Sevak participation
```

Attendance at another Sakha's local session shall not:

* Transfer Membership
* Transfer Sakha
* Create a new current Sevak association
* Create a cross-Sakha Sevak membership

The person's current Membership/Sakha remains authoritative.

---

# 6. Sakha-Level Eligibility

For a Sakha-Level Sevak Sangha Session, the broad eligible population is:

1. Eligible Sevaks associated with that Sakha.
2. Male NSS Members associated with that Sakha.

The system shall derive the eligible population automatically from authoritative records.

No manual participant list is required merely to establish eligibility.

---

# 7. Anchalika/Zilla Eligibility

For an Anchalika/Zilla Sevak Sangha Puja, the broad eligible population is:

1. All eligible Sevaks in that Anchalika/Zilla.
2. Male NSS Members in that Anchalika/Zilla.

The ERP shall automatically derive this population.

No pre-registration is required merely to establish eligibility.

---

# 8. Host Sakha Male Members

For an Anchalika/Zilla Sevak Sangha Puja, all male NSS Members of the host Sakha shall be included automatically in the participation planning population.

They do not need to separately select:

```text
I'LL ATTEND
```

merely to be included as host-Sakha participants.

---

# 9. Male Participation Rule

Participation in Sevak Sangha events is male-only.

This applies to:

* Sakha-Level Sevak Sangha Sessions
* Anchalika/Zilla Sevak Sangha Puja

Therefore:

```text
Sevak Sangha Event
        ↓
Male Participants
```

This rule applies to **event participation**.

It does not apply to Seva assignments.

---

# 10. Seva Is Separate

Seva is not restricted by the male-only Sevak Sangha participation rule.

Therefore:

```text
Sevak Sangha Participation
        ↓
Male participation
```

while:

```text
Seva Assignment
        ↓
Male or Female
```

subject to the applicable Seva Category eligibility and approval.

Detailed Seva rules are maintained separately.

---

# 11. ACTIVE Sevak Participation

An ACTIVE Sevak is eligible to participate in applicable Sevak Sangha activities according to the event-specific eligibility rules.

ACTIVE status does not mean mandatory attendance.

Therefore:

```text
ACTIVE Sevak
    ↓
May Attend
```

not:

```text
ACTIVE Sevak
    ↓
Must Attend
```

---

# 12. INACTIVE Sevak Participation

An INACTIVE Sevak may still attend a Sevak Sangha event where the applicable event rules permit participation.

Therefore:

```text
INACTIVE Sevak
        ↓
May Attend
```

INACTIVE status does not by itself prohibit attendance.

---

# 13. Attendance Does Not Reactivate

When an INACTIVE Sevak attends:

```text
Attendance Recorded
        ↓
Status remains INACTIVE
```

The ERP shall never automatically perform:

```text
INACTIVE + ATTENDANCE
        =
ACTIVE
```

Reactivation requires an authorized human decision.

---

# 14. INACTIVE Attendance Review

When an INACTIVE Sevak attends an applicable Sevak activity:

1. Attendance is recorded normally.
2. Sevak status remains INACTIVE.
3. The system creates or updates a reactivation review cycle.
4. Only one OPEN review cycle may exist for the Sevak.
5. Additional attendance while the cycle is OPEN attaches to the existing cycle.
6. An authorized user reviews the cycle.
7. Reviewer may:

   * Keep the Sevak INACTIVE
   * Reactivate the Sevak to ACTIVE
8. Once reviewed, the cycle becomes CLOSED.
9. Closed review cycles remain permanently in history.
10. If the Sevak remains INACTIVE and later attends after the previous cycle is closed, a new review cycle may be created.

---

# 15. No Automatic Inactivity

Attendance shall never automatically change:

```text
ACTIVE
    ↓
INACTIVE
```

There is no attendance threshold.

The ERP shall not automatically inactivate a Sevak because of:

* Missed Sakha sessions
* Consecutive absences
* Missing Sunday sessions
* Missing Anchalika/Zilla Puja
* Number of months without attendance

---

# 16. Two-Month Rule Withdrawn

The previously considered two-month inactivity rule is withdrawn.

No automatic:

```text
No Attendance for 2 Months
        ↓
INACTIVE
```

rule shall be implemented.

The reason is that:

* Sakha-level session frequency varies by Sakha.
* Anchalika/Zilla Sevak Sangha Puja is typically approximately six-monthly.
* Attendance patterns therefore cannot be treated as a universal inactivity trigger.

---

# 17. Eligibility Does Not Equal Attendance

The ERP shall maintain separate records for:

```text
Eligible Participant
```

and:

```text
Actual Attendee
```

A person may be eligible and absent.

Example:

```text
Eligible
   ↓
Did Not Attend
```

This is valid.

---

# 18. One Person — One Participant

A person shall appear only once in an event participant list.

If the person qualifies through multiple criteria, the participant list must be deduplicated.

Example:

```text
Person
├── Eligible Sevak
└── Male NSS Member
```

Result:

```text
One Participant
```

not two.

---

# 19. One Person — One Attendance Record

For a given event:

```text
One Person
      ↓
Maximum One Attendance Record
```

The system shall prevent duplicate attendance records for the same person and event.

---

# 20. Cross-Anchalika/Zilla Participation

A Sevak from another Anchalika/Zilla may attend an Anchalika/Zilla Sevak Sangha Puja.

Example:

```text
Sevak
  ↓
Anchalika A
  ↓
Event hosted by
Anchalika B
  ↓
May Attend
```

This is permitted event participation.

---

# 21. Cross-Anchalika/Zilla Does Not Transfer Affiliation

Cross-Anchalika/Zilla attendance does not change:

* NSS Membership
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

and:

```text
Cross-Anchalika/Zilla Attendance
        ≠
Sevak Transfer
```

---

# 22. Cross-Anchalika/Zilla Probable Attendance

A Sevak from another Anchalika/Zilla who indicates an intention to attend may be included in the host's probable attendance planning.

The person's original organizational affiliation remains unchanged.

---

# 23. Visibility

Published/confirmed NSS events may be visible on the Member Dashboard according to the common Event framework.

Visibility does not mean eligibility.

Therefore:

```text
Visible Event
    ≠
Eligible Participant
```

The Member Dashboard may show an event to a member even where that member cannot participate.

---

# 24. Event Publication

A Sevak event becomes an active member-facing event only when explicitly:

```text
PUBLISHED / CONFIRMED
```

Before publication:

```text
DRAFT
```

means:

* Not a confirmed member-facing event.
* No normal participant notification.
* Event may be edited by authorized users.

After publication:

* Applicable dashboard visibility becomes active.
* Applicable notifications are sent.
* Participation planning becomes active.

---

# 25. Sangha Notification

Once an event is:

```text
PUBLISHED / CONFIRMED
```

the respective Sanghas shall be notified according to the event's organizational scope.

The notification shall contain applicable:

* Event information
* Date
* Time
* Host
* Location
* Participation information

---

# 26. Attendance Intention

Where enabled by the event framework, members may optionally indicate:

```text
I'M INTERESTED / I'LL ATTEND
```

or:

```text
I WON'T BE ATTENDING
```

The intention is for organizational planning.

Examples include:

* Seating
* Food
* Transport
* Other arrangements

---

# 27. Intention Is Optional

A member is not required to submit an intention.

Therefore:

```text
No Response
```

is a valid state.

No response shall not be interpreted as:

```text
I WON'T BE ATTENDING
```

---

# 28. Intention Does Not Equal Attendance

The system shall not treat:

```text
I'LL ATTEND
```

as:

```text
PRESENT
```

Actual attendance must be separately recorded.

Likewise:

```text
I WON'T BE ATTENDING
```

does not prevent legitimate attendance if the person later attends and is otherwise permitted to participate.

---

# 29. Intention Does Not Restrict Attendance

An intention response is a planning mechanism.

It does not itself establish a participation prohibition.

Therefore:

```text
I WON'T BE ATTENDING
        ↓
Does not technically prevent
legitimate actual attendance
```

where the person is otherwise eligible/permitted.

---

# 30. Intention Before Event

The intention may be changed before the event according to the event framework.

The latest applicable intention is used for current planning.

Historical intention changes shall remain auditable where required.

---

# 31. Rescheduling and Intention

If an event is rescheduled:

```text
Original Event
    ↓
New Date / Time
```

members shall be asked to confirm their intention again.

Previous intention is retained historically.

It shall not simply be overwritten.

Example:

```text
Original:
I'LL ATTEND

Event Rescheduled

New:
Please confirm again
```

---

# 32. Probable Attendance

Probable attendance is a planning population.

It is separate from:

```text
Total Eligible
```

and:

```text
Actual Attendance
```

The host Sangha shall be able to see:

1. Probable attendance count.
2. Individual probable participant names/details.

---

# 33. Probable Attendance Composition

For the applicable Anchalika/Zilla event, probable attendance consists of:

### 1. Sevak Participants

All applicable Sevak participants:

```text
ACTIVE
+
INACTIVE
```

are automatically included according to the event eligibility rules.

They do not need to submit:

```text
I'LL ATTEND
```

merely to be included as Sevak probable participants.

---

### 2. Host Sakha Male Members

Host Sakha male NSS Members are automatically included.

They do not need to submit:

```text
I'LL ATTEND
```

merely to be included in host participation planning.

---

### 3. Other Eligible Male NSS Members

Other eligible male NSS Members are included in probable attendance when they indicate:

```text
I'LL ATTEND
```

---

### 4. Cross-Anchalika/Zilla Sevaks

Permitted Sevaks from another Anchalika/Zilla may be included in probable attendance when applicable, particularly when they indicate their intention to attend.

---

# 34. Probable Attendance Exclusions

Probable attendance excludes, as applicable:

* Sevaks who explicitly indicate `I WON'T BE ATTENDING`.
* Non-Sevak members who provide no response.
* Non-Sevak members who explicitly indicate `I WON'T BE ATTENDING`.
* Persons who are not otherwise eligible/permitted to participate.

All probable participants are deduplicated by Person.

---

# 35. Three Attendance Numbers

The host Sangha shall distinguish:

```text
TOTAL ELIGIBLE
        ↓
PROBABLE ATTENDANCE
        ↓
ACTUAL ATTENDANCE
```

These are separate numbers.

They shall never be treated as interchangeable.

---

# 36. Total Eligible

`TOTAL ELIGIBLE` represents the automatically derived eligible population.

It answers:

```text
Who is eligible?
```

It does not answer:

```text
Who intends to attend?
```

or:

```text
Who actually attended?
```

---

# 37. Probable Attendance

`PROBABLE ATTENDANCE` represents the current planning estimate.

It answers:

```text
Who is reasonably expected to attend?
```

It is not an attendance record.

---

# 38. Actual Attendance

`ACTUAL ATTENDANCE` represents people who actually participated in the event.

It is the authoritative source for attendance reporting.

---

# 39. Actual Attendance Not Restricted to Probable List

A person may attend even if the person was not previously included in probable attendance.

Example:

```text
Eligible
   ↓
No intention
   ↓
Not in probable list
   ↓
Actually attends
   ↓
PRESENT
```

This is valid where the person is otherwise permitted to participate.

The ERP must therefore allow legitimate actual attendees to be recorded even when they were not on the probable list.

---

# 40. Attendance Reconciliation

After the event ends, attendance enters the applicable reconciliation period.

During reconciliation, authorized organizers may:

* Complete missing attendance.
* Add legitimate attendees.
* Correct attendance through the permitted workflow.
* Reconcile probable vs actual attendance.
* Ensure INACTIVE attendance generates the required reactivation-review flag.

The event does not become immediately immutable merely because the scheduled end time has passed.

---

# 41. Event Completion

An event may be marked:

```text
COMPLETED
```

after attendance reconciliation is complete.

Completion may be:

```text
Manual
```

or:

```text
Automatic after configurable maximum period
```

The maximum reconciliation period is configurable.

---

# 42. Completed Event

After completion:

* Actual attendance is preserved.
* Participant history is preserved.
* Intention history is preserved.
* Probable attendance remains available for comparison.
* Reactivation review history remains preserved.
* Normal editing is restricted.

Historical information shall not be physically deleted.

---

# 43. Post-Completion Corrections

After completion, normal editing is locked.

Attendance corrections must use the centralized ERP correction workflow.

The correction shall preserve:

* Original value
* Requested value
* Reason
* Requester
* Request timestamp
* Approver
* Approval timestamp
* Final value
* Audit trail

The requester shall not approve their own correction.

---

# 44. Cancellation

A published/confirmed event may be cancelled according to the event lifecycle.

When cancelled:

```text
Status = CANCELLED
```

The event remains historically preserved.

Cancellation shall:

* Remove it from applicable upcoming views.
* Prevent new attendance after cancellation effective time.
* Preserve existing intention records.
* Preserve event history.
* Trigger applicable notifications.
* Be audited.

---

# 45. Post-Start Cancellation

Cancellation may occur after the scheduled start time where authorized.

If attendance has already been recorded:

```text
Recorded Attendance
        ↓
Permanently Preserved
```

The cancellation shall not delete attendance already recorded.

No new attendance shall be accepted after the cancellation effective time.

---

# 46. Rescheduling

A published/confirmed event may be rescheduled according to the event lifecycle.

The same event identity is retained.

The system preserves:

* Original date/time
* New date/time
* Rescheduling history
* Existing intention history
* Attendance already recorded
* Audit history

Members shall be asked to reconfirm their intention for the new date.

---

# 47. Event Identity

Rescheduling shall not create a completely unrelated new event.

Conceptually:

```text
Event ID: EVT-001

Original Date
     ↓
Rescheduled Date
     ↓
Same Event ID
```

The complete scheduling history remains available.

---

# 48. Participation and Membership Transfer

Event participation shall never perform a Membership Transfer.

If a member attends an event in another organizational area:

```text
Attendance
    ↓
No Membership Transfer
```

Membership Transfer remains the authoritative process for changing current Sakha.

---

# 49. Participation and Sevak Transfer

There is no independent Sevak Transfer generated by event attendance.

Current Sevak association follows the Membership lifecycle.

The event system shall not create a new Sevak association merely because a person attended an event.

---

# 50. Participation and Seva

Participation in a Sevak event does not automatically create Seva.

Therefore:

```text
Event Attendance
    ≠
Seva Assignment
```

If Seva is performed during an event, it must be recorded through the applicable Seva workflow.

---

# 51. Participation History

The ERP shall preserve participation history including:

* Event
* Event Type
* Participant
* Organizational affiliation at event time
* Intention
* Probable participation
* Actual attendance
* Attendance corrections
* Reactivation review generated from attendance

Historical records shall remain available.

---

# 52. Audit

The following participation actions shall be auditable:

* Eligibility generation
* Participant inclusion
* Intention response
* Intention change
* Probable attendance calculation
* Attendance recording
* Attendance correction
* Event cancellation
* Event rescheduling
* Event completion
* Reactivation review generation
* Reactivation review decision

---

# 53. Participation Rules Summary

```text
Eligibility
    ↓
Who may participate

Visibility
    ↓
Who can see the event

Intention
    ↓
Who says they plan to attend

Probable Attendance
    ↓
Who is reasonably expected to attend

Actual Attendance
    ↓
Who actually attended
```

These five concepts remain separate.

---

# 54. Frozen Principles

The following participation principles are frozen:

* Participation status and attendance are separate.
* ACTIVE does not mean mandatory attendance.
* INACTIVE does not automatically prohibit attendance.
* Attendance does not automatically reactivate an INACTIVE Sevak.
* INACTIVE attendance creates or updates a reactivation review cycle.
* Only one OPEN reactivation review cycle may exist per Sevak.
* Additional attendance attaches to the existing open cycle.
* Authorized human review determines reactivation.
* No reason is mandatory for reactivation.
* Closed review cycles remain historical.
* No attendance-based automatic inactivity exists.
* The previously proposed two-month inactivity threshold is withdrawn.
* Sakha-level Sevak Sangha participation is local to the applicable Sakha.
* A member does not acquire cross-Sakha Sevak participation by attending another Sakha's local session.
* Anchalika/Zilla-level events may permit cross-Anchalika/Zilla Sevak participation.
* Cross-Anchalika/Zilla attendance does not change organizational affiliation.
* Sevak Sangha event participation is male-only.
* Seva assignment is separate and may include Male or Female participants subject to Seva rules.
* Eligibility is automatically derived from authoritative records.
* Eligibility does not equal attendance.
* One person appears only once per event.
* One person has at most one attendance record per event.
* Published/confirmed events are member-facing.
* Respective Sanghas are notified after publication.
* Attendance intention is optional.
* `I'LL ATTEND` does not equal actual attendance.
* `I WON'T BE ATTENDING` does not itself prohibit legitimate attendance.
* No response is not interpreted as `I WON'T BE ATTENDING`.
* Rescheduling requires intention reconfirmation.
* Previous intention remains historical.
* Host can see probable attendance count and individual details.
* Probable attendance is separate from total eligible.
* Probable attendance is separate from actual attendance.
* Actual attendance is not restricted to the probable list.
* Host Sakha male members are automatically included in applicable probable attendance.
* Eligible Sevaks are automatically included in applicable probable attendance.
* Other eligible male NSS Members may enter probable attendance through `I'LL ATTEND`.
* Event attendance does not transfer Membership.
* Event attendance does not create a Sevak transfer.
* Event attendance does not automatically create Seva.
* Attendance reconciliation occurs before final event closure.
* Completed attendance is preserved.
* Historical participation records are never physically deleted.
* All participation and attendance changes are auditable.

---

# 55. Related Documents

```text
01_sevak_module_overview.md
02_sevak_erd.md
03_sevak_lifecycle.md
05_sevak_business_rules.md
06_sevak_table_design.md

sangha/
├── 01_sakha_sevak_sangha_session_rules.md
└── 02_anchalika_zilla_sevak_sangha_puja_rules.md

seva/
├── 01_seva_business_rules.md
└── 02_upbs_seva_rules.md

events/
└── 01_other_sevak_event_rules.md
```

Related modules:

```text
Person
Membership
Attendance
Administration / RBAC
Reports
```

---

# End of Document
