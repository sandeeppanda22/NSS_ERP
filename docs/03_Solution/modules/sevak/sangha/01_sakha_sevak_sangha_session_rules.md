# NSS ERP — Sakha-Level Sevak Sangha Session Rules

**Document ID:** SOL-SEV-SANGHA-001  
**Version:** 1.0.0  
**Status:** DRAFT — CONSOLIDATION IN PROGRESS  
**Parent Module:** Sevak Sangha  
**Scope:** Sakha-Level Sevak Sangha Sessions

---

## 1. Purpose

This document defines the business rules for a **Sakha-Level Sevak Sangha Session**.

A Sakha-Level Sevak Sangha Session is a local activity conducted by a Sakha that has a Sevak Sangha.

These sessions are operationally distinct from:

- Anchalika/Zilla-level Sevak Sangha Puja
- Seva assignments
- UPBS Seva
- Other NSS events

---

## 2. Event Type

The ERP event type shall be:

```text
SAKHA_SEVAK_SANGHA_SESSION
```

This event type shall not be used for Anchalika/Zilla-level Sevak Sangha Puja.

---

## 3. Sakha-Level Sevak Sangha Availability

A Sakha may or may not have a Sevak Sangha.

```text
Sakha
├── Has Sevak Sangha
│   └── Sakha-Level Sessions may be conducted
│
└── Does not have Sevak Sangha
    └── No Sakha-Level Sevak Sangha Session
```

There is no requirement that every Sakha must have a Sevak Sangha.

---

## 4. Session Frequency

There is no fixed system-wide recurring schedule.

Sessions are conducted according to the requirements and practices of the individual Sakha.

In practice, a Sakha-Level Sevak Sangha Session is generally conducted after the Sunday Sangha Puja.

However:

* It is not necessarily conducted every Sunday.
* The actual frequency depends on the individual Sakha.
* The ERP shall not automatically generate recurring sessions.
* Authorized users create sessions when required.

---

## 5. Host Sakha

Every Sakha-Level Sevak Sangha Session must have a registered Sakha as its host.

The host Sakha is the Sakha conducting the local session.

The host Sakha's registered location shall be used as the event location.

---

## 6. Location

The registered location of the host Sakha shall automatically be associated with the session.

The system shall preserve a location snapshot at event creation for historical integrity.

Conceptually:

```text
Host Sakha
    ↓
Registered Sakha Location
    ↓
Session Location Snapshot
```

If the Sakha's registered location changes later, the historical event shall retain the location applicable when the event was created.

---

## 7. Participant Eligibility

Eligibility and actual attendance are separate concepts.

For a Sakha-Level Sevak Sangha Session, the eligible participant population shall be derived from authoritative Person, Membership and Sevak records.

The broad eligible population consists of:

1. Eligible Sevaks associated with that Sakha.
2. Male NSS Members of that Sakha.

The system shall not require separate manual entry of every eligible person.

---

## 8. Male Participation Rule

Sakha-Level Sevak Sangha participation is restricted to male participants.

This rule applies to participation in the Sevak Sangha session itself.

It does **not** restrict Seva assignments.

Therefore:

```text
Sakha-Level Sevak Sangha Session
    ↓
Male Participants
```

while:

```text
Seva Assignment
    ↓
Male or Female
```

Seva eligibility is governed separately by the Seva rules.

---

## 9. Sevak Eligibility

Eligible Sevaks associated with the host Sakha are included in the eligible participant population.

An `INACTIVE` Sevak is not automatically prohibited from attending.

Therefore, subject to the applicable event eligibility rules:

```text
ACTIVE Sevak
INACTIVE Sevak
```

may attend.

---

## 10. INACTIVE Sevak Attendance

An INACTIVE Sevak may attend a Sakha-Level Sevak Sangha Session.

Attendance does not automatically change the Sevak's status.

When an INACTIVE Sevak attends:

```text
Attendance Recorded
        ↓
Status remains INACTIVE
        ↓
Reactivation Review
```

The system shall flag the attendance for reactivation review.

An authorized user subsequently decides whether the Sevak:

* remains `INACTIVE`; or
* is reactivated to `ACTIVE`.

The system shall never perform:

```text
INACTIVE + ATTENDANCE = ACTIVE
```

automatically.

---

## 11. Reactivation Review

The reactivation review follows the common Sevak Participation Rules.

Rules:

1. Attendance by an INACTIVE Sevak creates or attaches to an open reactivation review cycle.
2. Only one open review cycle may exist for a Sevak at a time.
3. Additional attendance while the review cycle is open attaches to the existing cycle.
4. An authorized reviewer evaluates the cycle.
5. The reviewer may keep the Sevak INACTIVE or reactivate the Sevak.
6. Reactivation does not require a reason.
7. The review cycle is closed after review.
8. Closed review cycles remain permanently in history.

---

## 12. Unique Participant Rule

A person shall appear only once in the participant list for a session.

If a person qualifies through more than one eligibility condition, the person must still appear only once.

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

and not two participant entries.

---

## 13. Attendance Identity

Attendance shall be recorded against the Person and the applicable NSS/Sevak identity context according to the common Attendance module rules.

The session shall maintain one attendance record per person for the event.

Attendance represents actual participation.

Eligibility does not mean attendance.

---

## 14. Eligibility vs Attendance

The following concepts must remain separate:

```text
Eligibility
    ↓
Who may participate

Attendance
    ↓
Who actually participated
```

Therefore:

```text
Eligible ≠ Present
```

An eligible person may be absent.

---

## 15. Session Creation

Sessions are created manually by an authorized user.

The ERP shall not enforce a fixed recurring schedule.

The system shall not automatically create a weekly session merely because a Sakha has a Sevak Sangha.

---

## 16. Event Lifecycle

The Sakha-Level Sevak Sangha Session shall follow the common event lifecycle:

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
Event
```

---

## 17. Draft State

A session in `DRAFT` status:

* Is not visible as a published event to members.
* Does not trigger event notifications.
* May be prepared and edited by authorized users.

---

## 18. Published / Confirmed State

Only when the session is explicitly marked:

```text
PUBLISHED / CONFIRMED
```

does it become an active published event.

At this point:

* The event becomes visible according to applicable dashboard rules.
* Applicable notifications may be sent.
* Members may view the event.
* Attendance and intention functionality becomes available according to the common event rules.

---

## 19. Event Visibility

Published events may appear on the Member Dashboard according to the common NSS Event framework.

Visibility does not mean eligibility.

A member may see an event even when that member is not eligible to participate.

The system shall distinguish:

```text
Visibility
Eligibility
Intention
Attendance
```

---

## 20. Attendance Intention

Where the common event framework enables intention responses, a member may indicate:

```text
INTERESTED / WILL ATTEND
I WON'T BE ATTENDING
```

The response is optional.

No response does not mean:

```text
I WON'T BE ATTENDING
```

Intention is for organizational planning and does not constitute actual attendance.

---

## 21. Actual Attendance

Actual attendance is recorded independently of intention.

Therefore:

```text
I WILL ATTEND
    ≠
PRESENT
```

and:

```text
I WON'T BE ATTENDING
    ≠
Cannot attend
```

The actual attendance record is authoritative for attendance reporting.

---

## 22. Probable Attendance

Where probable attendance is enabled for the session, the host Sakha may view:

* Probable attendance count.
* Individual probable participant details.

Probable attendance is a planning figure and is not actual attendance.

The system shall not restrict actual attendance to the probable list.

---

## 23. Actual Attendee Not in Probable List

A person who actually attends may be recorded even if the person was not previously included in the probable-attendance list.

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
Attendance = PRESENT
```

This is valid.

---

## 24. Cancellation

A published/confirmed session may be cancelled by an authorized user.

When cancelled:

```text
Status = CANCELLED
```

The event remains historically preserved.

The cancelled session:

* is removed from applicable upcoming-event views;
* does not accept new attendance after the cancellation effective time;
* preserves existing intention records;
* preserves audit information;
* generates applicable notifications.

---

## 25. Post-Start Cancellation

A session may be cancelled even after the scheduled start time.

If attendance has already been recorded:

```text
Recorded Attendance
        ↓
Permanently Preserved
```

Attendance already recorded shall never be deleted merely because the event was subsequently cancelled.

No attendance shall be accepted after the cancellation effective time.

---

## 26. Rescheduling

A published/confirmed session may be rescheduled.

The same event identity shall be retained.

The system shall preserve:

* Original date/time
* New date/time
* Rescheduling timestamp
* User who performed the action
* Reason/remarks where applicable
* Complete scheduling history

After rescheduling, member intention shall be reconfirmed for the new date.

Previous intentions remain historical and are not overwritten.

---

## 27. Attendance Reconciliation

After the scheduled session ends, the event enters an attendance reconciliation period.

The organizer may:

* complete missing attendance;
* add legitimate attendees;
* correct attendance records within the permitted reconciliation workflow;
* reconcile probable and actual attendance;
* ensure INACTIVE Sevak attendance creates the appropriate reactivation review.

The session does not become immediately immutable merely because its scheduled end time has passed.

---

## 28. Completion

An authorized organizer may mark the session:

```text
COMPLETED
```

once attendance reconciliation is finished.

The system may automatically mark the event `COMPLETED` after the configured maximum post-event reconciliation period if the organizer has not completed it manually.

The maximum period is configurable and shall not be hard-coded in this document.

---

## 29. Completed Session

Once completed:

* The event remains permanently available in historical records.
* Attendance remains preserved.
* Intention history remains preserved.
* Participant history remains preserved.
* Probable attendance remains available for comparison.
* Event statistics may be finalized.
* Normal editing is restricted.

Completion shall never delete:

* Event record
* Attendance
* Intention responses
* Participant history
* Reactivation review history
* Host Sakha
* Location snapshot
* Scheduling history
* Notifications
* Audit history

---

## 30. Post-Completion Correction

A completed session is locked for normal editing.

Any correction after completion must use the centralized ERP correction and approval workflow.

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

The requester cannot approve their own correction.

The exact approval authority for a President-initiated correction remains event-dependent and is governed by the centralized organizational authority framework.

---

## 31. Administrative Authority

The session uses the existing NSS ERP RBAC and organizational scope.

No separate Sevak-specific permission architecture is created here.

Typical scope:

```text
Sakha-level user
    ↓
Sakha-level Sevak operations
```

Authorized actions may include:

* Create session
* Publish/confirm session
* Cancel session
* Reschedule session
* Manage attendance
* Reconcile attendance
* Complete session
* Initiate permitted corrections

Detailed office-bearer permissions are governed centrally by the Administration/RBAC module.

---

## 32. No Cross-Sakha Local Participation

A Sakha-Level Sevak Sangha Session is a local Sakha activity.

A member of another Sakha shall not be treated as a participant in the host Sakha's Sevak Sangha merely because the person is physically present there.

The ERP shall not create an independent cross-Sakha Sevak association from attendance.

NSS Membership Transfer remains the authoritative mechanism for changing the member's current Sakha.

---

## 33. No Independent Sevak Transfer

There is no separate Sevak transfer workflow.

When NSS Membership is transferred:

```text
NSS Membership Transfer
        ↓
Current Sakha Changes
        ↓
Sevak association follows Membership
```

If the new Sakha has a Sevak Sangha, the applicable new Sevak association may be created according to the core Sevak lifecycle rules.

If the new Sakha does not have a Sevak Sangha:

```text
No Current Sakha Sevak Sangha Association
```

The previous association remains historical.

---

## 34. Sakha With No Sevak Sangha

If a Sakha does not have a Sevak Sangha:

* No Sakha-Level Sevak Sangha Session can be created for that Sakha.
* No current Sakha Sevak Sangha association exists.
* Historical Sevak associations remain preserved.
* Members do not use another Sakha's Sevak Sangha as their current local association.

---

## 35. Relationship With Anchalika/Zilla Sevak Sangha Puja

The Sakha-Level Session and Anchalika/Zilla-level Sevak Sangha Puja are separate event types.

```text
SAKHA_SEVAK_SANGHA_SESSION
        ≠
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

The two event types have separate:

* Eligibility
* Participation scope
* Scheduling
* Notifications
* Attendance context
* Reporting
* Dashboard treatment

Rules for Anchalika/Zilla-level Puja are maintained separately in:

```text
sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md
```

---

## 36. Relationship With Seva

Attendance at a Sakha-Level Sevak Sangha Session is not itself a Seva assignment.

```text
Attendance
    ≠
Seva Assignment
```

Seva assignment is governed by:

```text
../seva/01_seva_business_rules.md
```

A Sevak may have multiple Seva assignments.

Seva eligibility is not restricted by the male-only participation rule of the Sevak Sangha session.

---

## 37. Audit and History

All session lifecycle actions shall be auditable.

The system shall preserve historical records for:

* Session creation
* Publication
* Cancellation
* Rescheduling
* Attendance
* Attendance corrections
* Completion
* Post-completion corrections
* Notifications
* Reactivation review generated from attendance

Physical deletion of historical session or attendance records is prohibited.

---

## 38. Frozen Principles

The following principles are approved for this document:

* A Sakha may or may not have a Sevak Sangha.
* Sakha-Level Sevak Sangha Sessions are local Sakha activities.
* Sessions are not necessarily weekly.
* Sessions generally occur after Sunday Sangha Puja where the Sakha follows that practice.
* No fixed recurring schedule is enforced.
* Sessions are manually created by authorized users.
* Every session has a registered Sakha as host.
* Host Sakha registered location is used.
* Location history is preserved.
* Event type is `SAKHA_SEVAK_SANGHA_SESSION`.
* Participation is male-only.
* Eligible Sevaks and male NSS Members form the broad eligible population.
* One person appears only once per session.
* Eligibility does not equal attendance.
* INACTIVE Sevaks may attend.
* INACTIVE attendance does not automatically reactivate a Sevak.
* INACTIVE attendance generates or feeds a reactivation review.
* No attendance-based automatic inactivity exists.
* Published/confirmed events become visible according to the common event framework.
* Intention and attendance are separate.
* Actual attendance is not restricted to probable attendance.
* Cancellation preserves historical information.
* Post-start cancellation preserves attendance already recorded.
* Rescheduling preserves the same event identity.
* Rescheduling requires intention reconfirmation.
* Attendance reconciliation occurs before final completion.
* Completion may be manual or automatic after a configurable maximum period.
* Completed events are locked for normal editing.
* Post-completion corrections require the centralized correction workflow.
* No independent Sevak transfer is created.
* NSS Membership Transfer remains authoritative for Sakha association.
* Sakha-Level Session rules are separate from Anchalika/Zilla Puja rules.
* Sakha-Level Session participation is separate from Seva assignment.
* Seva may be performed by eligible male or female persons under separate Seva rules.
* Historical records are permanently preserved.

---

## 39. Related Documents

```text
../01_sevak_module_overview.md
../03_sevak_lifecycle.md
../04_sevak_participation_rules.md
../05_sevak_business_rules.md
../06_sevak_table_design.md

02_anchalika_zilla_sevak_sangha_puja_rules.md

../seva/01_seva_business_rules.md
../seva/02_upbs_seva_rules.md

../events/01_other_sevak_event_rules.md
```

---

# End of Document
