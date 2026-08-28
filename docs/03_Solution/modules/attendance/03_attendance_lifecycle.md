# NSS ERP — Attendance Lifecycle

**Document ID:** SOL-ATT-006  
**Version:** 0.1.0  
**Status:** DRAFT  
**Module:** Attendance  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle states and transitions for the Attendance
Module entities:

- `weekly_sangha_puja`
- `weekly_sangha_puja_attendance`
- `attendance_exception`
- `attendance_review`

The Attendance lifecycle is independent of Membership lifecycle.
Attendance does not itself change Membership status (ATT-011, ATT-012).

---

# 2. Source Authority

This lifecycle document is governed by:

- Attendance Module Overview (SOL-ATT-001)
- Attendance Business Rules (SOL-ATT-003)
- Attendance Table Design (SOL-ATT-004)
- Attendance Review Workflow (SOL-ATT-005)
- Person Lifecycle (SOL-PER-005)
- Common project audit/soft-delete standards

Where conflict exists, the source document with the later frozen date
prevails.

---

# 3. Weekly Sangha Puja — Lifecycle States

```text
SCHEDULED       Record created, puja_date in future or current
CONDUCTED       puja_date has passed, attendance recording complete or in progress
```

---

# 4. Weekly Sangha Puja Transitions

## Transition: Creation -> SCHEDULED

**Trigger:** Weekly Sangha Puja event created for a Sakha

**Preconditions:**
- Valid `sakha_pk` reference (ATT-004)
- Valid `puja_date` (ATT-005)
- Authorized user

**Effects:**
- `weekly_sangha_puja_pk` assigned (UUID)
- `created_at` = current timestamp

## Transition: SCHEDULED -> CONDUCTED

**Trigger:** Puja date reached; attendance recording begins or completes

**Effects:**
- Attendance records may now be created against this event
- `updated_at` = current timestamp (if explicitly marked)

**Constraints:**
- Event record never physically deleted
- Historical puja records remain available for reporting

---

# 5. Weekly Sangha Puja Attendance — Lifecycle

Attendance records are event-based operational records.

## States

```text
PRESENT             attendance_status='PRESENT'
ABSENT              attendance_status='ABSENT'
EXCUSED_ABSENCE     attendance_status='EXCUSED_ABSENCE'
```

---

# 6. Attendance Record Transitions

## Transition: Recording -> PRESENT/ABSENT/EXCUSED_ABSENCE

**Trigger:** Attendance marked for a Member at a Weekly Sangha Puja

**Preconditions:**
- Valid `weekly_sangha_puja_pk` reference
- Valid `sangha_sevi_pk` reference (ATT-001)
- No duplicate record for same Member + same Puja event (Table Design Section 9)
- Valid `attendance_sakha_pk` (ATT-028)
- Authorized user

**Effects:**
- `attendance_pk` assigned (UUID)
- `attendance_status` = PRESENT / ABSENT / EXCUSED_ABSENCE
- `attendance_sakha_pk` = Sakha where attendance actually recorded
- `created_at` = current timestamp

**Rules:**
- Only ABSENT counts toward consecutive-absence monitoring (ATT-007)
- EXCUSED_ABSENCE does not increment consecutive-absence counter (ATT-008)

## Transition: Status Correction

**Trigger:** Authorized correction of attendance status (e.g., retroactive
exception approval changes ABSENT to EXCUSED_ABSENCE)

**Preconditions:**
- Authorized user (Secretary or President per authority matrix)
- Business justification exists

**Effects:**
- `attendance_status` updated
- `updated_at` = current timestamp

**Constraints:**
- Original attendance event not physically deleted (ATT-039)
- Correction is auditable (ATT-037)

---

# 7. Consecutive Absence Detection

The system monitors consecutive ABSENT records per Member:

```text
Week 1 — ABSENT
Week 2 — ABSENT
Week 3 — ABSENT
         |
         v
Attendance Review Created (ATT-010)
```

**Rules:**
- Only `attendance_status = 'ABSENT'` counts (ATT-007)
- EXCUSED_ABSENCE breaks the consecutive chain (ATT-008, ATT-025)
- PRESENT breaks the consecutive chain
- Detection is per Member across their attendance history

---

# 8. Attendance Exception — Lifecycle States

```text
ACTIVE          from_date <= current_date <= to_date (or to_date NULL)
EXPIRED         to_date < current_date
```

---

# 9. Attendance Exception Transitions

## Transition: Creation -> ACTIVE

**Trigger:** Approved attendance exception recorded

**Preconditions:**
- Valid `sangha_sevi_pk` reference
- Valid exception type (master data controlled — ATT-023)
- Approving authority identified (ATT-024)
- Authorized user (Secretary or President)

**Effects:**
- `exception_pk` assigned (UUID)
- `from_date` = exception start
- `to_date` = exception end (or NULL for open-ended)
- `approved_by` = approving authority
- `approved_date` = approval date
- `created_at` = current timestamp

**Rules:**
- Exception covers Weekly Sangha Puja dates within the period (ATT-025)
- Absences within the exception period treated as EXCUSED_ABSENCE

## Transition: ACTIVE -> EXPIRED

**Trigger:** Exception `to_date` passes

**Effects:**
- No field update required (state derived from date comparison)
- Exception record remains for historical reference

**Constraints:**
- Exception records never physically deleted
- Historical exceptions remain available for review

---

# 10. Attendance Review — Lifecycle States

```text
OPEN                    review_status='OPEN'
DEFERRED                review_status='DEFERRED'
CLOSED                  review_status='CLOSED'
ESCALATED_TO_PRESIDENT  review_status='ESCALATED_TO_PRESIDENT'
ESCALATED_TO_PARICHALAK review_status='ESCALATED_TO_PARICHALAK'
```

---

# 11. Attendance Review State Transition Diagram

```text
    3 Consecutive Absences
              |
              v
            OPEN
           /  |  \
          /   |   \
         v    v    v
     CLOSED  DEFERRED  ESCALATED_TO_PRESIDENT
                |              |
           (revisit)     President Review
                |           /    |    \
                v          v     v     v
              OPEN    CLOSED  REOPEN  ESCALATED_TO_PARICHALAK
                                |
                                v
                              OPEN
```

---

# 12. Transition: Trigger -> OPEN

**Trigger:** Three consecutive Weekly Sangha Puja absences detected (ATT-010, ATT-014)

**Preconditions:**
- Consecutive absence count = 3 (only ABSENT, not EXCUSED_ABSENCE)
- Valid `sangha_sevi_pk`

**Effects:**
- `review_pk` assigned (UUID)
- `review_status` = OPEN
- `trigger_date` = date of third consecutive absence
- `consecutive_absences` = 3 (or actual count)
- `assigned_to_role` = SECRETARY
- `created_at` = current timestamp

**Constraints:**
- Review creation does not change Membership status (ATT-011, ATT-012)
- No automatic suspension, cancellation, or revocation (ATT-013)

---

# 13. Transition: OPEN -> CLOSED

**Trigger:** Secretary or President closes the review after examination

**Preconditions:**
- Review is in OPEN state (or ESCALATED state for President)
- Authorized user (Secretary or President per authority matrix)
- Examination completed

**Effects:**
- `review_status` = CLOSED
- `closed_by_sangha_sevi_pk` = closing authority
- `updated_at` = current timestamp
- Remarks preserved

**Audit:** Closure action recorded (ATT-038)

---

# 14. Transition: OPEN -> DEFERRED

**Trigger:** Secretary defers the review for later action

**Preconditions:**
- Review is in OPEN state
- Authorized user (Secretary or President)
- Reason documented

**Effects:**
- `review_status` = DEFERRED
- `deferred_by_sangha_sevi_pk` = deferring authority
- `updated_at` = current timestamp
- Remarks preserved

**Constraints:**
- Deferred review remains available for revisit
- May return to OPEN when revisited

---

# 15. Transition: OPEN -> ESCALATED_TO_PRESIDENT

**Trigger:** Secretary escalates to President

**Preconditions:**
- Review is in OPEN state
- Secretary determines matter requires President-level authority
- Authorized user (Secretary)

**Effects:**
- `review_status` = ESCALATED_TO_PRESIDENT
- `escalated_by_sangha_sevi_pk` = escalating Secretary
- `updated_at` = current timestamp

---

# 16. Transition: ESCALATED_TO_PRESIDENT -> ESCALATED_TO_PARICHALAK

**Trigger:** President escalates to Parichalak

**Preconditions:**
- Review is in ESCALATED_TO_PRESIDENT state
- President determines higher authority required
- Authorized user (President)

**Effects:**
- `review_status` = ESCALATED_TO_PARICHALAK
- `updated_at` = current timestamp

---

# 17. Transition: CLOSED -> OPEN (Reopen)

**Trigger:** President reopens a closed review

**Preconditions:**
- Review is in CLOSED state
- Authorized user (President only — Secretary cannot reopen)

**Effects:**
- `review_status` = OPEN
- `updated_at` = current timestamp

**Audit:** Reopen action recorded with President identity and reason

**Constraints:**
- Original closure action remains historically traceable
- Secretary's original decision preserved in audit trail

---

# 18. Transition: DEFERRED -> OPEN (Revisit)

**Trigger:** Deferred review revisited for further action

**Preconditions:**
- Review is in DEFERRED state
- Authorized user (Secretary or President)

**Effects:**
- `review_status` = OPEN
- `updated_at` = current timestamp

---

# 19. Review and Membership Action

If an Attendance Review results in a Membership concern:

```text
Attendance Review
       |
Authorized Decision (Secretary/President/Parichalak)
       |
Membership Workflow Triggered (owned by Membership Module)
       |
Membership Action (if approved)
```

**Constraints:**
- Attendance Module does not directly perform Membership lifecycle changes (ATT-036)
- Membership status owned by Membership Module (ATT-036)
- Human review required before any Membership action (ATT-035)

---

# 20. Cross-Module Lifecycle Events

## Events Attendance Responds To

| Source Event | Source Module | Attendance Response |
|---|---|---|
| Person Death Recorded | Person | No new attendance recorded; open reviews may be closed |
| Person Soft-Deleted | Person | Historical attendance preserved as references |
| Membership Terminated | Membership | No new attendance recorded for terminated member |
| Membership Transferred | Membership | Home Sakha context updates; historical attendance unchanged |

## Events Attendance Generates

| Attendance Event | Affected Modules | Expected Response |
|---|---|---|
| Attendance Review Created | Notification (if applicable) | Alert to Secretary |
| Review Escalated | Notification (if applicable) | Alert to President/Parichalak |
| Consecutive Absence Threshold | Reports | Dashboard/watch-list updates |

---

# 21. Person Death and Attendance

When a Person's death is recorded (Person Module event):

- No further attendance records created for the deceased
- Open Attendance Reviews for the deceased may be closed
  (death resolves the attendance question)
- Historical attendance records fully preserved
- Historical review records fully preserved

The Attendance Module does not independently record death — it responds
to the Person lifecycle event.

---

# 22. Prohibited Lifecycle Patterns

The following are explicitly prohibited:

```text
- Physical deletion of attendance records (ATT-039)
- Physical deletion of attendance review records (ATT-040)
- Physical deletion of attendance exceptions
- Automatic Membership suspension on 3 absences (ATT-011)
- Automatic Membership cancellation on 3 absences (ATT-012)
- Automatic Parichaya Patra revocation (ATT-013)
- Secretary reopening a closed review (authority matrix)
- Attendance directly updating Membership status (ATT-036)
- Creating duplicate Membership identity (ATT-002)
- Erasing original attendance on exception approval
```

---

# 23. Lifecycle and Audit Integration

| Transition | Audit Fields |
|---|---|
| Puja Event Creation | created_at |
| Attendance Recording | created_at, created_by |
| Attendance Correction | updated_at, updated_by |
| Exception Creation | created_at, approved_by, approved_date |
| Review Creation | created_at, trigger_date |
| Review Closure | closed_by_sangha_sevi_pk, updated_at |
| Review Deferral | deferred_by_sangha_sevi_pk, updated_at |
| Review Escalation | escalated_by_sangha_sevi_pk, updated_at |
| Review Reopen | updated_at (President identity preserved) |

---

# 24. Lifecycle State Query Patterns

| Query Intent | Filter |
|---|---|
| Upcoming puja events | `weekly_sangha_puja.puja_date >= current_date` |
| Attendance for a Member | `weekly_sangha_puja_attendance.sangha_sevi_pk = ?` |
| Consecutive absences | `attendance_status = 'ABSENT'` ordered by puja_date DESC |
| Active exceptions | `attendance_exception.from_date <= ? AND (to_date IS NULL OR to_date >= ?)` |
| Open reviews | `attendance_review.review_status = 'OPEN'` |
| Escalated reviews | `review_status IN ('ESCALATED_TO_PRESIDENT', 'ESCALATED_TO_PARICHALAK')` |
| Cross-Sakha attendance | `attendance_sakha_pk != Member's home sakha_pk` |
| Watch list | Members with consecutive_absences >= 2 |

---

# 25. Explicitly Not Frozen Here

The following lifecycle details are left to implementation:

```text
Exact consecutive-absence detection mechanism (trigger vs scheduled job vs query)
Exact notification mechanism for review creation/escalation
Exact review reassignment workflow if Secretary changes
Exact exception approval UI/workflow
Exact cross-Sakha attendance recording UI
Exact Membership workflow integration mechanism
Exact Parichalak escalation handling workflow
Exact watch-list threshold (2 vs configurable)
```

---

# 26. Status

```text
DOCUMENT STATUS:
DRAFT

VERSION:
0.1.0
```
