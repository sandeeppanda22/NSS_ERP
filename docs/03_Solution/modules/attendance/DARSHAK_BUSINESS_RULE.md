# NSS ERP — Darshak Business Rule

**Document Type:** ERP Implementation Decision (not derived from Bye-Laws)
**Version:** 1.1
**Date:** 2026-08-16
**Status:** Approved
**Source:** Project Owner clarification — corrects earlier project Rule Book usage

---

## Terminology Correction

An earlier project Rule Book used "Darshak → Full Member" as a simplified membership model. After reviewing the actual NSS Bye-Law (REF-002), the official categories are:

| Project Rule Book term | Official Bye-Law term | Bye-Law Reference |
|------------------------|----------------------|-------------------|
| Darshak | **Probationary Member** | REF-002-002 |
| Full Member | **Regular Member** | REF-002-003 |
| Associate Member | **Associate Member** | REF-002-004 |

**"Darshak" is not an official NSS Bye-Law membership category.** It must not be used as an authoritative database membership type.

The database `membership_type_master` will use the official Bye-Law terms: PROBATIONARY, REGULAR, ASSOCIATE.

---

## Operational Usage of "Darshak"

In day-to-day Sangha operations, "Darshak" is used informally to refer to attendees at a Weekly Sangha Puja who are not Regular Members of that specific Sakha:

| Who is called Darshak operationally | Official status |
|-------------------------------------|-----------------|
| Probationary Member (holds Anumati Patra, not yet Parichaya Patra) | Statutoryly: Probationary Member per REF-002-002 |
| Member from another Sakha attending without transferring Parichaya Patra | Statutoryly: Regular Member of their home Sakha |

---

## ERP Treatment

- **Database membership_type_master:** Uses official terms only (PROBATIONARY, REGULAR, ASSOCIATE)
- **UI label:** "Darshak" may appear as a display label in dashboards and attendance screens for operational familiarity
- **Attendance tracking:** Darshak attendance is tracked separately from Regular Member attendance of that Sakha

---

## Dashboard Display

| Dashboard | What is shown |
|-----------|---------------|
| Sakha Dashboard | Total registered Darshak for this Sakha (Probationary + Other Sakha members), weekly Puja attendance |
| Kendra Dashboard | Aggregate Darshak across all Sakhas (total registered, monthly Puja attendance) |
| Attendance Marking | Separate section listing Darshak present (with type: Probationary vs Other Sakha) |

---

## Statutory Basis

### Probationary Member (REF-002-002)

Enrolled after meeting prescribed qualifications. Issued **Anumati Patra**. Must continue for at least one year and undergo prescribed training before becoming Regular Member.

### Regular Member (REF-002-003)

After probation + training, enrolled as full-fledged member. Issued **Parichaya Patra** (Identity Card).

Exception: The Parichalak can directly enroll a devotee as a Regular Member and subsequently direct that person to become a member of a Sakha Sangha.

### Associate Member (REF-002-004)

Enrolled by the Parichalak (suo motu or on Sakha recommendation) considering active participation and sympathetic attitude. Can attend all functions but cannot vote or hold elected posts.

---

## Key Rule

> "Darshak" is an operational/UI label only. The authoritative database model uses the official Bye-Law membership categories. No database table or column should use "Darshak" as a membership type value.

---

# End of Document
