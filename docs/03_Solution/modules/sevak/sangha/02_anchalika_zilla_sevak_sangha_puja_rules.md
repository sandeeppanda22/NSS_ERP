# NSS ERP — Anchalika/Zilla-Level Sevak Sangha Puja Rules

**Document ID:** SOL-SEV-SANGHA-002  
**Version:** 1.0.0  
**Status:** DRAFT — CONSOLIDATION IN PROGRESS  
**Parent Module:** Sevak Sangha  
**Scope:** Anchalika/Zilla-Level Sevak Sangha Puja

---

# 1. Purpose

This document defines the business rules for an **Anchalika/Zilla-Level Sevak Sangha Puja**.

This is a larger Sevak Sangha gathering organized at the Anchalika or Zilla level.

It is operationally distinct from:

- Sakha-Level Sevak Sangha Sessions
- Seva Assignments
- UPBS Seva
- Other NSS Events

---

# 2. Event Type

The ERP event type shall be:

```text
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

This event type shall not be used for regular Sakha-Level Sevak Sangha Sessions.

The two event types shall remain separately identifiable in:

* Attendance
* Eligibility
* Notifications
* Dashboards
* Reporting
* Event history

---

# 3. Organizational Scope

An Anchalika/Zilla Sevak Sangha Puja is organized for a defined:

* Anchalika, or
* Zilla

The event shall have an explicit organizational scope.

The organizing Anchalika/Zilla is the authoritative organizational context for eligibility.

---

# 4. Frequency

There is no fixed universal recurrence rule.

The event is typically conducted approximately once every six months.

The frequency shall remain configurable.

The ERP shall not hard-code:

```text
6 months
```

as an immutable recurrence interval.

The system shall support the organizationally configured frequency.

---

# 5. Host Sakha

An Anchalika/Zilla Sevak Sangha Puja shall have a registered Sakha as the host.

The host Sakha is the physical venue for the event.

Hosting the event does **not** change the organizational affiliation of participants.

For example:

```text
Anchalika/Zilla
       ↓
Host Sakha A
       ↓
Sevak Sangha Puja
```

Sakha A becomes the host/venue, but participants continue to belong to their respective Sakhas and organizational areas.

---

# 6. Host Location

The registered location of the host Sakha shall automatically be used as the event location.

No separate venue override is required for the normal event model.

The system shall preserve a location snapshot at event creation.

Therefore:

```text
Host Sakha
    ↓
Registered Location
    ↓
Event Location Snapshot
```

A later change to the Sakha's registered location shall not alter the historical event location.

---

# 7. Event Creation

The event is created manually by an authorized user.

The ERP shall not automatically generate recurring Anchalika/Zilla Puja events.

Event creation shall include at least:

* Event Type
* Organizing Anchalika/Zilla
* Host Sakha
* Scheduled date
* Scheduled start time
* Scheduled end time
* Event location derived from host Sakha
* Event status

---

# 8. Event Lifecycle

The event shall follow the common event lifecycle:

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
   ↓
Reconfirm Intention
   ↓
Event
```

Historical event identity shall be preserved throughout the lifecycle.

---

# 9. Draft State

While the event is in:

```text
DRAFT
```

it is not a published event.

During `DRAFT`:

* It is not presented as a confirmed upcoming event to members.
* Member-facing event notification is not triggered.
* The organizer may prepare and edit the event.
* Eligibility may be calculated internally for preparation.

---

# 10. Published / Confirmed State

The event becomes an active member-facing event only when explicitly marked:

```text
PUBLISHED / CONFIRMED
```

Only after publication/confirmation:

* The event becomes visible on applicable Member Dashboards.
* Applicable notifications are sent.
* The respective Sanghas are notified.
* Members may respond to the event.
* Event participation planning becomes active.

Publication is therefore an explicit administrative action.

---

# 11. Notification to Respective Sanghas

Once the event is:

```text
PUBLISHED / CONFIRMED
```

the respective organizational units shall be notified.

The notification shall identify, as applicable:

* Event
* Date
* Time
* Host Sakha
* Location
* Organizing Anchalika/Zilla
* Participation information

The notification shall not be sent merely because a draft event was created.

---

# 12. Member Dashboard Visibility

Every published/confirmed NSS event that is applicable under the common Event framework should be visible through the Member Dashboard.

Therefore, an Anchalika/Zilla Sevak Sangha Puja shall appear as a member-facing event once published/confirmed.

Visibility does not itself mean eligibility.

The ERP shall keep the following concepts separate:

```text
Visibility
Eligibility
Intention
Probable Attendance
Actual Attendance
```

---

# 13. Primary Eligibility

The system shall automatically derive the primary eligible participant population from authoritative Person, Membership and Sevak records.

For an Anchalika/Zilla Sevak Sangha Puja, the eligible participant population consists of:

1. All eligible Sevaks associated with the organizing Anchalika/Zilla.
2. Male NSS Members associated with the organizing Anchalika/Zilla.

No manual pre-registration is required for these automatically eligible populations.

---

# 14. Eligible Sevaks

All eligible Sevaks belonging to the organizing Anchalika/Zilla shall automatically appear in the eligible participant population.

This includes:

```text
ACTIVE Sevaks
INACTIVE Sevaks
```

where otherwise eligible.

An INACTIVE Sevak is not automatically prohibited from attending.

Attendance by an INACTIVE Sevak follows the common Sevak Participation Rules and may trigger a reactivation review.

---

# 15. Male NSS Members

Male NSS Members associated with the organizing Anchalika/Zilla are included in the eligible participant population.

Female NSS Members are not included solely because of NSS Membership for this Sevak Sangha Puja.

This restriction applies to participation in the Sevak Sangha Puja.

It does not restrict Seva assignment.

Seva is governed separately by:

```text
../seva/01_seva_business_rules.md
```

---

# 16. Host Sakha Male Members

All male NSS Members of the host Sakha shall be included for participation planning.

This ensures that the host Sakha's male membership can participate in the event even when the host Sakha is not being treated as the only organizational source of participants.

Host Sakha male members do not need to separately indicate "I WILL ATTEND" merely to appear in the host's participation planning population.

---

# 17. Cross-Anchalika/Zilla Sevak Attendance

A Sevak belonging to another Anchalika/Zilla may attend a published Anchalika/Zilla Sevak Sangha Puja.

For example:

```text
Sevak
  ↓
Anchalika A
  ↓
Event hosted by Anchalika B
  ↓
May attend
```

Such attendance:

* does not transfer Membership;
* does not transfer Sakha;
* does not change Anchalika/Zilla affiliation;
* does not create a new Sevak association;
* remains associated with the person's existing organizational identity.

Cross-Anchalika/Zilla attendance is therefore an **event participation exception**, not an organizational transfer.

---

# 18. Eligibility vs Cross-Area Attendance

The system shall distinguish between:

```text
Primary Event Eligibility
```

and:

```text
Permitted Cross-Area Attendance
```

A Sevak from another Anchalika/Zilla may attend even though the person is not part of the event's primary organizational eligibility population.

The event record shall preserve the person's actual organizational affiliation.

---

# 19. Unique Participant Rule

A person shall appear only once in the participant list for the event.

If the same person qualifies through multiple conditions, the system shall deduplicate the participant list.

Example:

```text
Person
├── Eligible Sevak
└── Male NSS Member
```

The participant list contains:

```text
1 Person
```

not two entries.

The same person shall have at most one attendance record for the event.

---

# 20. Eligibility Does Not Equal Attendance

The automatically generated eligible list is not the attendance list.

Therefore:

```text
Eligible
   ≠
Present
```

A person may be eligible but not attend.

Actual attendance is recorded separately.

---

# 21. Event Attendance Intention

Members may optionally indicate their intention to attend.

The available responses are:

```text
I'M INTERESTED / I'LL ATTEND
I WON'T BE ATTENDING
```

The intention response is:

* Optional
* Changeable before the event
* Intended primarily for organizational planning

The system shall preserve the latest applicable intention while retaining historical changes where required by the audit framework.

---

# 22. No Response

No response is a valid state.

The system shall not interpret:

```text
NO RESPONSE
```

as:

```text
I WON'T BE ATTENDING
```

Therefore:

```text
No Response
    ≠
Won't Attend
```

---

# 23. Intention Does Not Equal Attendance

An intention response is not an attendance record.

Therefore:

```text
I'LL ATTEND
    ≠
PRESENT
```

and:

```text
I WON'T BE ATTENDING
    ≠
Attendance Prohibited
```

Actual attendance remains authoritative for attendance reporting.

---

# 24. Probable Attendance

Probable attendance is a planning figure used by the host Sangha.

The host Sangha shall be able to see both:

1. Probable attendance count.
2. Individual probable participant names/details.

The host shall therefore have both aggregate and individual planning information.

---

# 25. Probable Attendance Composition

For the organizing event, probable attendance shall include:

### A. Sevak Sangha Members

Eligible Sevak Sangha members associated with the organizing Anchalika/Zilla are included automatically.

This includes:

```text
ACTIVE Sevaks
INACTIVE Sevaks
```

subject to their eligibility.

They do not need to separately mark "I'll attend" merely to be included as probable Sevak participation.

---

### B. Host Sakha Male Members

Male NSS Members of the host Sakha are included automatically for participation planning.

They do not need to separately mark "I'll attend" merely to appear in the host's probable participation population.

---

### C. Other Eligible Male NSS Members

Other eligible male NSS Members who are not automatically included through the above categories become part of probable attendance when they explicitly indicate:

```text
I'LL ATTEND
```

---

### D. Cross-Anchalika/Zilla Sevaks

A Sevak from another Anchalika/Zilla may attend.

Where the cross-area Sevak indicates an intention to attend, the person may be included in the host's probable attendance planning.

Cross-area participation does not alter organizational affiliation.

---

# 26. Probable Attendance Exclusions

Probable attendance shall exclude, as applicable:

* Persons who explicitly indicate `I WON'T BE ATTENDING`.
* Non-Sevak members who provide no attendance intention.
* Persons who are neither eligible nor otherwise permitted to participate.
* Duplicate representations of the same person.

A person may nevertheless be recorded as actual attendance if the applicable event rules permit the person to attend.

---

# 27. Three Attendance Numbers

The host shall be able to distinguish at least three different numbers:

```text
TOTAL ELIGIBLE
        ↓
PROBABLE ATTENDANCE
        ↓
ACTUAL ATTENDANCE
```

These numbers shall never be treated as interchangeable.

### Total Eligible

The automatically derived eligible population.

### Probable Attendance

The planning population based on automatic Sevak/host-member inclusion and applicable intention responses.

### Actual Attendance

The people who actually participated.

---

# 28. Actual Attendance Not Restricted to Probable List

Actual attendance shall not be restricted to the probable attendance list.

For example:

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

The ERP must therefore allow legitimate actual attendees to be recorded even when they were not previously included in probable attendance.

---

# 29. INACTIVE Sevak Attendance

An INACTIVE Sevak may attend the Anchalika/Zilla Sevak Sangha Puja.

When such attendance is recorded:

```text
Attendance
   ↓
Status remains INACTIVE
   ↓
Reactivation Review
```

The system shall not automatically reactivate the Sevak.

The common Sevak Participation Rules govern the review cycle.

---

# 30. Event Rescheduling

A published/confirmed event may be rescheduled.

The same event identity shall be retained.

The system shall preserve:

* Original date
* Original time
* New date
* New time
* Rescheduling timestamp
* User performing the action
* Reason/remarks where applicable
* Scheduling history

The previous event identity shall not be deleted and recreated merely because the date changes.

---

# 31. Intention Reconfirmation After Rescheduling

When the event is rescheduled, members shall be asked to confirm their intention again for the new date.

The previous intention shall remain historical.

It shall not simply be overwritten.

Example:

```text
Original Event
    ↓
Member: I'LL ATTEND
    ↓
Event Rescheduled
    ↓
Member asked again
    ↓
New Intention
```

The new intention applies to the new date.

---

# 32. Probable Attendance After Rescheduling

Probable attendance shall be recalculated using the applicable current information for the new event date.

The system shall not blindly carry the previous probable attendance number forward.

Historical probable attendance information shall remain available for audit/history.

---

# 33. Cancellation

A published/confirmed event may be cancelled by an authorized user.

When cancelled:

```text
Status = CANCELLED
```

The event remains historically preserved.

Cancellation shall:

* Remove the event from applicable upcoming-event views.
* Prevent new attendance after the cancellation effective time.
* Preserve existing intention records.
* Preserve event history.
* Trigger applicable notifications.
* Be audited.

---

# 34. Post-Start Cancellation

Cancellation is permitted before or after the scheduled start time.

If cancellation occurs after the event has started:

```text
Attendance Already Recorded
        ↓
Preserved
```

Attendance already recorded shall not be deleted merely because the event is subsequently cancelled.

No attendance shall be accepted after the cancellation effective time.

---

# 35. Post-Start Rescheduling

Rescheduling may also occur after the scheduled start time where authorized.

The system shall preserve:

* Original event identity
* Original date/time
* Revised date/time
* Attendance already recorded
* Rescheduling history
* Audit trail

Attendance already recorded before the rescheduling action remains historical.

The revised event continues under the same event identity.

---

# 36. Event Completion

The event becomes eligible for completion after its scheduled end time.

It shall remain open for a configurable attendance reconciliation period.

The event shall not become immediately immutable merely because the scheduled end time has passed.

---

# 37. Attendance Reconciliation

During the reconciliation period, the authorized organizer may:

* Complete missing attendance.
* Add legitimate attendees.
* Correct attendance records through the permitted workflow.
* Reconcile probable and actual attendance.
* Review INACTIVE Sevak attendance.
* Ensure required reactivation-review flags are generated.

---

# 38. Manual Completion

An authorized organizer may mark the event:

```text
COMPLETED
```

once attendance reconciliation is complete.

The event shall then become the authoritative completed historical record.

---

# 39. Automatic Completion

The system may automatically complete the event after a configurable maximum post-event reconciliation period.

The maximum period shall be configurable.

It shall not be hard-coded as a universal number in this document.

---

# 40. Completed Event

Once `COMPLETED`:

* Event remains permanently available in history.
* Attendance remains preserved.
* Intention responses remain historical.
* Probable attendance remains available for comparison.
* Participant history remains preserved.
* Event statistics may be finalized.
* Normal editing is restricted.

Completion shall never delete:

* Event record
* Attendance
* Intentions
* Participant history
* Reactivation review history
* Host Sakha
* Location snapshot
* Scheduling history
* Notifications
* Audit trail

---

# 41. Post-Completion Correction

After completion, normal editing shall be locked.

Any correction must use the centralized ERP correction and approval workflow.

The correction record shall preserve:

* Original value
* Requested value
* Reason
* Requester
* Request timestamp
* Approver(s)
* Approval timestamp
* Final value
* Audit trail

The original value shall never disappear from history.

The requester shall not approve their own correction.

---

# 42. Correction Approval

The applicable approval framework is:

```text
Sakha Admin initiates
    ↓
Secretary + President approval
```

```text
Secretary initiates
    ↓
President approval
```

For:

```text
President initiates
```

the approval authority remains event-dependent until the centralized governance authority matrix is finalized.

The system shall therefore support approval based on:

* Event Type
* Organizational Level
* Requester Role
* Required Approver Role(s)
* Approval Sequence

---

# 43. Member-Facing Completed Event Results

After completion, the ERP may display generic event information to members.

This may include:

* Event Name
* Date
* Event Type
* Host Sakha
* Location
* Organizing Anchalika/Zilla
* General participation/attendance summary

Detailed individual attendance and result visibility is not frozen by this document.

Such visibility remains subject to:

* RBAC
* Privacy rules
* Reports standards
* Event standards
* Future finalized visibility rules

---

# 44. Administrative Authority

The event uses the existing NSS ERP RBAC and organizational scope.

No independent Sevak-specific permission architecture is created.

Typical organizational scope includes:

```text
Sakha-level
Anchalika-level
Zilla-level
Kendra-level
```

Specific permissions are governed centrally by the Administration/RBAC module.

No specific office-bearer title is hard-coded as the sole permission owner in this event document.

---

# 45. No Membership Transfer Through Attendance

Attendance at an Anchalika/Zilla Sevak Sangha Puja does not change:

* NSS Membership Sakha
* Membership status
* Anchalika affiliation
* Zilla affiliation
* Sevak Sakha association

For example:

```text
Sakha A
Anchalika A
      ↓
Attends Event hosted in
Sakha B / Anchalika B
      ↓
Affiliation remains unchanged
```

Membership Transfer remains the authoritative mechanism for changing organizational affiliation.

---

# 46. No Independent Sevak Transfer

There is no separate Sevak transfer workflow for event participation.

Cross-Anchalika/Zilla attendance is an event participation action only.

The person's existing:

```text
Person
Membership
Sangha Sevi ID
Sakha
Anchalika
Zilla
Sevak association
```

remain unchanged.

---

# 47. Relationship With Sakha-Level Sevak Sangha Session

This event is distinct from:

```text
SAKHA_SEVAK_SANGHA_SESSION
```

The two event types shall not be merged.

```text
SAKHA_SEVAK_SANGHA_SESSION
    ↓
Local Sakha activity

ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
    ↓
Larger periodic gathering
```

The Anchalika/Zilla event may include participants from multiple Sakhas and may permit cross-Anchalika/Zilla Sevak participation.

---

# 48. Relationship With Seva

Attendance at the Anchalika/Zilla Sevak Sangha Puja is not a Seva assignment.

```text
Event Attendance
      ≠
Seva Assignment
```

Seva is governed separately by:

```text
../seva/01_seva_business_rules.md
```

The male participation rule for Sevak Sangha events does not become a gender restriction on Seva.

---

# 49. Audit and History

The following must be auditable:

* Event creation
* Eligibility generation
* Publication
* Notifications
* Intention changes
* Probable attendance changes
* Cancellation
* Rescheduling
* Attendance
* Attendance corrections
* Completion
* Post-completion correction
* Approval workflow
* Reactivation review generated from INACTIVE Sevak attendance

Historical records shall not be physically deleted.

---

# 50. Frozen Principles

The following principles are approved for this document:

* Anchalika/Zilla Sevak Sangha Puja is a distinct event type.
* It is separate from the Sakha-Level Sevak Sangha Session.
* It is organized at Anchalika/Zilla level.
* It is typically conducted approximately once every six months.
* Frequency remains configurable.
* Events are manually created.
* No fixed recurring event generation is enforced.
* A registered Sakha is required as host.
* The host Sakha's registered location is used.
* Location is snapshotted for historical integrity.
* The organizing Anchalika/Zilla defines the primary eligibility scope.
* All eligible Sevaks of the organizing Anchalika/Zilla are automatically included in eligibility.
* Male NSS Members of the organizing Anchalika/Zilla are automatically included in eligibility.
* Host Sakha male NSS Members are automatically included for participation planning.
* A person appears only once per event.
* Eligibility does not equal attendance.
* Sevaks from another Anchalika/Zilla may attend.
* Cross-Anchalika/Zilla attendance does not change organizational affiliation.
* INACTIVE Sevaks may attend.
* INACTIVE attendance does not automatically reactivate the Sevak.
* INACTIVE attendance may generate a reactivation review.
* Published/confirmed events are visible through the applicable Member Dashboard.
* Respective Sanghas are notified after publication/confirmation.
* Intention is optional.
* Members may indicate `I'LL ATTEND` or `I WON'T BE ATTENDING`.
* No response is a valid state.
* Intention does not constitute attendance.
* Actual attendance is independent of probable attendance.
* Host sees both probable count and individual probable participant details.
* Probable attendance and actual attendance are separate.
* Total Eligible, Probable Attendance and Actual Attendance are separate numbers.
* Actual attendance is not restricted to the probable-attendance list.
* Events may be cancelled before or after start.
* Events may be rescheduled before or after start where authorized.
* Post-start cancellation preserves attendance already recorded.
* Rescheduling retains event identity.
* Rescheduling requires intention reconfirmation.
* Previous intentions remain historical.
* Probable attendance is recalculated using current information after rescheduling.
* Events remain open for a configurable reconciliation period.
* Completion may be manual or automatic.
* Completed events are locked for normal editing.
* Post-completion correction requires centralized approval and audit.
* Requester cannot approve their own correction.
* President-initiated correction authority remains event-dependent until governance authority is finalized.
* Generic completed-event information may be shown to members.
* Detailed individual attendance visibility remains subject to centralized RBAC/privacy/reporting rules.
* Historical records are never physically deleted.
* Event attendance does not constitute Membership or Sevak transfer.
* Seva assignment remains separate from event participation.
* Sevak Sangha participation is male-only under the applicable event eligibility rules.
* Seva itself is not gender-restricted by the Sevak Sangha participation rule.

---

# 51. Related Documents

```text
../../01_sevak_module_overview.md
../../03_sevak_lifecycle.md
../../04_sevak_participation_rules.md
../../05_sevak_business_rules.md
../../06_sevak_table_design.md

01_sakha_sevak_sangha_session_rules.md

../seva/01_seva_business_rules.md
../seva/02_upbs_seva_rules.md

../events/01_other_sevak_event_rules.md
```

---

# End of Document
