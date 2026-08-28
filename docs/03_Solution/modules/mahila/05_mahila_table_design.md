# NSS ERP — Mahila Sangha Table Design

**Document ID:** SOL-MAH-005  
**Version:** 2.1.0  
**Status:** DRAFT — BYE-LAW ALIGNED  
**Module:** Mahila Sangha  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical table design for the Mahila Sangha module.

The design translates the approved:

- Mahila Sangha Bye-Law
- Mahila Business Rules
- Mahila Lifecycle
- Mahila ERD
- NSS Unified Governance Model
- Common NSS Membership Model
- Common Organization Model
- Common Event and Attendance Model
- Common Finance and Audit Model

into a logical data architecture.

This document is a Solution-layer document.

It does not create:

- SQL
- PostgreSQL DDL
- Django migrations
- database migration scripts
- implementation code

---

# 2. Design Philosophy

The Mahila module shall follow the NSS ERP principle:

```text
Common Capability
       |
       v
Reuse Common Module
       |
       v
Avoid Duplicate Tables
```

The Mahila module shall not create duplicate versions of common NSS entities when the common architecture already supports the required business rule.

The major common entities are:

```text
Person
Membership
Organization
Governance
Event
Attendance
Finance
Audit
Administration
```

---

# 3. Mahila Membership Architecture

The Mahila Sangha does not require a separate global membership architecture.

The verified Bye-Law defines Mahila Sangha membership and enrollment, while the NSS ERP project establishes that Mahila membership follows the common NSS membership framework.

Therefore:

```text
Person
   |
   v
NSS Membership
   |
   v
Sangha Sevi ID
   |
   v
Mahila Participation
```

No second global membership identity shall be created.

---

# 4. Person

## 4.1 Table

```text
person
```

**Owner:** Person Module

The Mahila module shall reuse the common Person table.

No:

```text
mahila_person
```

table shall be created.

---

## 4.2 Relationship

Conceptually:

```text
PERSON
   |
   v
MEMBERSHIP
```

Mahila-specific information must not duplicate the person's core identity.

---

# 5. Membership

## 5.1 Table

```text
membership
```

**Owner:** Membership Module

The Mahila module shall reuse the common Membership table.

The project source establishes:

```text
No separate Mahila membership process
No separate Mahila renewal process
Same NSS membership framework
```

The member therefore remains within the common NSS membership categories.

---

## 5.2 No Mahila Membership Table

The following table is not required:

```text
mahila_membership
```

Reason:

```text
Mahila Participation
       !=
Separate Global Membership
```

---

# 6. Sangha Sevi Identity

## 6.1 Common Identity

Mahila members who are NSS members continue to use the common Sangha Sevi identity.

Conceptually:

```text
Person
   |
   v
Membership
   |
   v
Sangha Sevi ID
```

The Mahila module shall not generate a second member identifier.

---

# 7. Organization

## 7.1 Common Organization

```text
organization
```

**Owner:** Organization Module

Mahila organizational entities shall use the common Organization architecture.

No:

```text
mahila_organization
```

table shall be created merely to represent Mahila organizational identity.

---

## 7.2 Organization Hierarchy

Mahila organizational relationships shall be represented through the common organization hierarchy.

Conceptually:

```text
NSS
 |
 +-- Mahila Sangha
       |
       +-- Kendra / Central Context
       |
       +-- Mahila Sakha Sanghas
```

The exact organizational hierarchy remains owned by the Organization module.

---

# 8. Mahila Sangha Organizational Identity

A Mahila Sangha organizational entity shall be identifiable through the common:

```text
organization
```

record.

Where required, the organization type/master data shall identify the organization as a Mahila Sangha.

No duplicate Mahila organization table is required.

---

# 9. General Body

## 9.1 General Body Membership

The verified Bye-Law states:

> All members of the Sangha including members of the Governing Body constitute the General Body of the Sangha.

Therefore General Body membership derives from the underlying Mahila Sangha membership.

No:

```text
mahila_general_body_member
```

table is required.

---

## 9.2 General Body History

Where meetings, resolutions or attendance of the General Body are recorded, the common:

```text
meeting
resolution
attendance
```

framework shall be reused where available.

---

# 10. Mahila Governing Body / Mahila Parichalana Mandali

## 10.1 One Body

The following are two names for the same Mahila governance body:

```text
Mahila Governing Body
        =
Mahila Parichalana Mandali
```

The database shall contain **one governance body record**, not two.

---

## 10.2 Common Governance Model

The body shall use the Unified Governance Model.

Conceptually:

```text
body_type_master
       |
       v
body_master
       |
       v
body_member_assignment
       |
       v
position_assignment
```

The exact physical table names remain controlled by the Governance module.

---

# 11. Mahila Governing Body Type

The common governance body type master shall support a value representing:

```text
MAHILA_GOVERNING_BODY
```

If the project standard uses the existing terminology:

```text
MAHILA_PARICHALANA_MANDALI
```

that value shall represent the same body.

Both labels shall not create two body records.

---

# 12. Governing Body Size

The verified Bye-Law establishes:

```text
9 Members
```

The body consists of:

```text
President
Vice-President
Parichalak
Secretary
Joint Secretary
Treasurer
3 Other Members
```

The common Governance model shall represent these nine assignments.

---

# 13. Governing Body Positions

The position master shall support:

```text
President
Vice-President
Parichalak
Secretary
Joint Secretary
Treasurer
Member
```

The three ordinary members are represented as three assignments to the `Member` position.

---

# 14. Joint Secretary

The Mahila Bye-Law explicitly uses:

```text
Joint Secretary
```

Therefore the position master shall use the Mahila-approved terminology.

It shall not be replaced by:

```text
Assistant Secretary
```

for the Mahila Governing Body.

Historical Mahila Governing Body records also use the designation Joint-Secretary.

---

# 15. Governing Body Membership

The common body-member assignment structure shall associate:

```text
Person / Membership
        |
        v
Mahila Governing Body
```

and the position assignment shall identify the person's office.

Conceptually:

```text
body_master
     |
     v
body_member_assignment
     |
     v
person / membership
     |
     v
position_assignment
```

---

# 16. Founder President

The Bye-Law provides a special Founder President arrangement.

This shall be represented using the common governance assignment model.

No:

```text
mahila_founder_president
```

table shall be created.

The special status is represented through the governance assignment and applicable tenure/status fields.

---

# 17. Permanent Vice-President

The Bye-Law provides a Permanent Vice-President arrangement for the specified original Sevika while she prefers to serve in that capacity.

This shall use the common governance assignment model.

No:

```text
mahila_permanent_vice_president
```

table shall be created.

---

# 18. Parichalak

The Parichalak is one of the positions in the Mahila Governing Body.

The common governance model shall represent:

```text
Body
+
Person
+
Position
+
Assignment
```

The Parichalak's additional powers are business rules, not a reason to create a separate Parichalak table.

---

# 19. Two-Year Governing Body Term

The verified Bye-Law states that the Governing Body holds office for:

```text
Two Years
```

from the date it assumes office.

It also continues after that period until a new Governing Body is constituted and takes over charge.

The governance assignment therefore needs to distinguish:

```text
term_start_date
scheduled_term_end_date
actual_end_date
```

---

# 20. Continuation After Term

The table design shall support:

```text
Scheduled Term End
        |
        v
Body Continues
        |
        v
Successor Constituted
        |
        v
Actual End
```

Therefore the scheduled term end must not automatically close the governance assignment.

---

# 21. Successor Governing Body

The Bye-Law provides a process whereby after expiry of the term:

```text
Parichalak
      |
      v
General Body consensus
      |
      v
List of members
      |
      v
President's consent
      |
      v
Office-bearers announced
```

The governance model shall preserve the resulting body as a new governance body instance.

The previous body remains historical.

---

# 22. Vacancy

The Bye-Law defines vacancy handling.

For President or Vice-President vacancies, the specified General Body process is followed.

For other Governing Body vacancies, the Parichalak fills the vacancy from among Sangha members for the unexpired term.

The common Governance module shall represent these as assignment changes.

No:

```text
mahila_vacancy
```

table is required unless the common Governance module itself requires a dedicated vacancy entity.

---

# 23. Unexpired Term

A replacement member shall serve:

```text
Existing Body
     |
     v
Existing Term
     |
     v
Vacancy
     |
     v
Replacement
     |
     v
Unexpired Portion Only
```

The replacement shall not automatically receive a new two-year term.

---

# 24. Governance History

Historical governance assignments shall never be overwritten.

The system must be able to reconstruct:

```text
Who served
In which body
In which position
From when
Until when
Under what authority
```

---

# 25. Governance Table Reuse

The Mahila module shall reuse the common Governance structures.

Preferred logical structures:

```text
body_type_master
body_master
body_member_assignment
position_master
position_assignment
```

Exact physical names are controlled by the Governance module.

---

# 26. No Separate Mahila Governance Tables

The following are not required:

```text
mahila_governing_body
mahila_governing_body_member
mahila_parichalana_mandali
mahila_parichalana_mandali_member
mahila_position_assignment
```

The reason is:

```text
Mahila Governing Body
        =
Mahila Parichalana Mandali
        |
        v
Common Governance Model
```

---

# 27. Event Architecture

Mahila activities shall use the common Event architecture wherever the common framework supports the requirement.

Potential activities derived from the Bye-Law include:

```text
Regular Meetings
Discourses
Training
Seminars
Educational Activities
Seva Puja
```

The Bye-Law explicitly identifies these activities.

---

# 28. Event Table

```text
event
```

**Owner:** Event Module

Mahila activities shall be represented as events where appropriate.

No:

```text
mahila_event
```

table is required merely to identify the activity as Mahila.

---

# 29. Event Type

The common Event Type master may contain appropriate Mahila event categories.

Examples:

```text
MAHILA_MEETING
MAHILA_DISCOURSE
MAHILA_TRAINING
MAHILA_SEMINAR
MAHILA_EDUCATIONAL_ACTIVITY
SEVA_PUJA
```

The final master values belong to the Event module.

---

# 30. Event Participation

Participation shall use the common:

```text
event_participation
```

framework.

No:

```text
mahila_event_participant
```

table is required.

---

# 31. Attendance

Mahila event attendance shall use the common Attendance module.

No:

```text
mahila_attendance
```

table is currently required.

The Attendance module owns attendance identity and attendance rules.

---

# 32. Membership vs Participation

The table design must preserve:

```text
Membership
    !=
Event Participation
    !=
Attendance
```

A member attending a Mahila activity does not create a new membership record.

---

# 33. Seva Puja

The Bye-Law states that the Parichalak appoints Sevaks and Sevikas for day-to-day Seva Puja of Sri Sri Thakur.

The operational Seva/Seva Puja architecture shall use the appropriate common framework where available.

No:

```text
mahila_seva_puja
```

table is currently required.

---

# 34. Training Centres

The Bye-Law permits establishment of training centres.

Training activities shall use the common Event/Training framework where available.

No:

```text
mahila_training
```

table is currently required.

---

# 35. Seminars

Seminars are explicitly included among the Sangha's activities.

Seminars shall use the common Event framework.

---

# 36. Educational Institutions

Educational institutions attached to Nilachala Kutir are identified by the Bye-Law.

Institutional data should use the common Organization/Education framework where such a framework exists.

No duplicate Mahila institution table shall be created without an approved requirement.

---

# 37. Nilachala Kutir

Nilachala Kutir is the central institutional location identified in the Bye-Law.

The location shall use the common:

```text
organization
address
location
```

architecture.

No:

```text
mahila_location
```

table is required.

---

# 38. Finance

Mahila financial records shall use the common Finance module.

The Bye-Law identifies funds including:

* Pranamis
* Voluntary donations
* Specific-purpose donations
* Government grants
* Semi-Government grants
* Non-official body grants including Kendra Sangha
* Miscellaneous contributions
* Earnings from landed properties and other sources
* Landed properties held in the name of the President.

---

# 39. Finance Tables

The Mahila module shall reuse the common Finance tables.

It shall not create:

```text
mahila_finance
mahila_receipt
mahila_donation
mahila_expenditure
mahila_ledger
```

unless a future approved requirement establishes a genuinely Mahila-specific financial entity.

---

# 40. Specific-Purpose Donation

The Bye-Law requires donations received for a specific purpose to be used only for that purpose.

The common Finance model must therefore be capable of preserving:

```text
Donation
   |
   v
Purpose
   |
   v
Utilization
```

This is a Finance-module responsibility.

---

# 41. Bank Operation

The Bye-Law specifies that Sangha funds are kept in a Postal Savings Bank or State Bank of India, or both, operated jointly by Treasurer and Secretary.

This is represented through the common Finance and authorization architecture.

No Mahila-specific bank table is required.

---

# 42. Expenditure Resolution

The Bye-Law requires expenditure to be supported by a relevant Governing Body resolution.

Conceptually:

```text
Mahila Governing Body
        |
        v
Resolution
        |
        v
Expenditure
```

The common Governance/Resolution and Finance modules own these entities.

---

# 43. Audit

The Bye-Law requires annual audit by a qualified auditor.

The audit report must first receive final approval from the Governing Body and then be placed before the General Body for approval.

The common Audit architecture shall represent this workflow.

---

# 44. Audit Tables

No:

```text
mahila_audit
```

table is required.

The common:

```text
audit
audit_report
audit_approval
```

architecture, or the final equivalent defined by the Audit module, shall be reused.

---

# 45. Representation

The Bye-Law provides that the Secretary or Joint Secretary may represent the Sangha before government offices, local bodies and other authorities and receive donations and grants on behalf of the Sangha.

This is represented through:

```text
Governance Assignment
+
Role/Permission
+
Organization Scope
```

rather than a separate representation table.

---

# 46. Dispute Records

The Bye-Law provides a dispute-resolution authority through the Parichalak of Nilachala Saraswata Sangha.

Where the common Governance/Administration framework supports dispute records, it shall be reused.

No:

```text
mahila_dispute
```

table is currently frozen.

---

# 47. Amendment Records

The Bye-Law permits the Governing Body to amend provisions by resolution, subject to prior consultation with the President of Nilachala Saraswata Sangha and placement before the next General Body meeting for information.

The common:

```text
resolution
document
governance
```

architecture should be used.

No:

```text
mahila_amendment
```

table is currently required.

---

# 48. Dissolution

The Bye-Law contains provisions concerning dissolution and vesting of remaining property in Kendra Sangha.

The dissolution state shall be represented through the common Organization/Governance lifecycle.

No:

```text
mahila_dissolution
```

table is required.

---

# 49. Master Data

Mahila shall reuse common master-data structures.

Potential relevant master data includes:

```text
Organization Type
Governance Body Type
Governance Position
Event Type
Event Category
Membership Type
Status
```

---

# 50. Governance Body Type

The governance body type shall distinguish the Mahila Governing Body from other governance bodies.

Recommended logical value:

```text
MAHILA_GOVERNING_BODY
```

The project may retain the business terminology:

```text
MAHILA_PARICHALANA_MANDALI
```

as an alternate display label.

These must resolve to the same body type.

---

# 51. No Duplicate Body Types

The following must not become two independent body types:

```text
MAHILA_GOVERNING_BODY
MAHILA_PARICHALANA_MANDALI
```

Instead:

```text
Internal Identity:
MAHILA_GOVERNING_BODY

Display / Alternate Name:
Mahila Parichalana Mandali
```

or the reverse, depending on the finalized Governance master-data convention.

---

# 52. Status

Governance assignments should use the common status model.

Possible statuses include:

```text
ACTIVE
ENDED
VACATED
SUSPENDED
```

Only approved common Governance status values should be used.

---

# 53. Audit Fields

Any Mahila-specific table introduced in the future shall comply with the project-wide audit standards.

Conceptually:

```text
created_at
created_by
updated_at
updated_by
```

Where applicable:

```text
deleted_at
deleted_by
```

---

# 54. History Preservation

The NSS ERP principle is:

```text
History Never Deleted
```

Therefore the following must remain historically reconstructable:

```text
Membership
Membership Status
Governing Bodies
Office-Bearer Assignments
Vacancies
Events
Participation
Attendance
Finance
Audit
Resolutions
```

---

# 55. Foreign-Key Ownership

Cross-module relationships shall reference the owning module's authoritative entity.

Examples:

```text
membership_id
organization_id
governance_body_id
body_member_assignment_id
position_id
event_id
attendance_id
finance_transaction_id
```

Exact physical names are controlled by the common database standards.

---

# 56. No Duplicate Master Data

The Mahila module shall not create duplicate:

```text
Country
State
District
City
Organization
Membership Type
Governance Position
Event Type
Status
```

masters.

Existing project master data shall be reused.

---

# 57. Conditional Mahila Activity Table

An earlier design considered:

```text
mahila_activity
```

This remains:

```text
PENDING
```

It shall only be introduced if the common Event architecture cannot represent a genuine Mahila-specific requirement.

Until that requirement is demonstrated:

```text
event
```

is the preferred table.

---

# 58. Dedicated Mahila Tables — Current Decision

Current mandatory Mahila-specific physical tables:

```text
NONE
```

This is an intentional architecture decision.

Mahila is primarily a domain/business module operating over common NSS ERP foundations.

---

# 59. Tables Explicitly Not Required

The following are not part of the current Mahila table design:

```text
mahila_person
mahila_membership
mahila_membership_renewal

mahila_organization

mahila_general_body_member

mahila_governing_body
mahila_governing_body_member

mahila_parichalana_mandali
mahila_parichalana_mandali_member

mahila_position_assignment

mahila_event
mahila_event_participant

mahila_attendance

mahila_seva_puja
mahila_training

mahila_finance
mahila_donation
mahila_expenditure
mahila_audit

mahila_amendment
mahila_dispute
mahila_dissolution
```

These are avoided because the common NSS architecture already provides the required conceptual capabilities.

---

# 60. Final Logical Architecture

The Mahila data model is:

```text
                         PERSON
                           |
                           v
                      MEMBERSHIP
                           |
                           v
                     SANGHA SEVI
                           |
             +-------------+-------------+
             |                           |
             v                           v
       ORGANIZATION                 GOVERNANCE
             |                           |
             |                           v
             |              MAHILA GOVERNING BODY
             |              (MAHILA PARICHALANA
             |                   MANDALI)
             |                           |
             |                    +------+------+
             |                    |             |
             |                 MEMBERS       POSITIONS
             |
             v
           EVENT
             |
       +-----+-----+
       v           v
PARTICIPATION   ATTENDANCE

             FINANCE
                |
                v
              AUDIT
```

---

# 61. Mahila Governance Relationship

The final governance relationship is:

```text
                     MAHILA SANGHA
                           |
                           v
             MAHILA GOVERNING BODY
                           |
                           |
              also known as
                           |
                           v
          MAHILA PARICHALANA MANDALI
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
      President      Vice-President    Parichalak
          |
      Secretary
          |
    Joint Secretary
          |
      Treasurer
          |
    3 Other Members
```

This is **one body and one governance record**.

---

# 62. Governance Lifecycle

The logical lifecycle is:

```text
Governing Body Constituted
          |
          v
Assignments Created
          |
          v
Two-Year Term
          |
          v
Possible Vacancy
          |
          v
Replacement for Unexpired Term
          |
          v
Term Expiry
          |
          v
Successor Body Constituted
          |
          v
Outgoing Body Becomes Historical
```

The Bye-Law explicitly provides continuation after the two-year period until a successor takes over.

---

# 63. Data Ownership Matrix

| Data                   | Owning Module           | Mahila Action            |
| ---------------------- | ----------------------- | ------------------------ |
| Person                 | Person                  | Reuse                    |
| Membership             | Membership              | Reuse                    |
| Sangha Sevi ID         | Membership              | Reuse                    |
| Organization           | Organization            | Reuse                    |
| Organization hierarchy | Organization            | Reuse                    |
| Governing Body         | Governance              | Reuse                    |
| Governance Member      | Governance              | Reuse                    |
| Governance Position    | Governance              | Reuse                    |
| Position Assignment    | Governance              | Reuse                    |
| Event                  | Event                   | Reuse                    |
| Participation          | Event                   | Reuse                    |
| Attendance             | Attendance              | Reuse                    |
| Finance                | Finance                 | Reuse                    |
| Audit                  | Audit                   | Reuse                    |
| RBAC                   | Administration/Security | Reuse                    |
| Mahila-specific table  | Mahila                  | None currently confirmed |

---

# 64. Database Impact Summary

Current design:

```text
Person                    -> REUSE
Membership                -> REUSE
Sangha Sevi               -> REUSE
Organization              -> REUSE
Governance                -> REUSE
Event                     -> REUSE
Event Participation       -> REUSE
Attendance                -> REUSE
Finance                   -> REUSE
Audit                     -> REUSE
RBAC                      -> REUSE

Mahila-specific tables    -> NONE CONFIRMED
```

---

# 65. Important Architectural Rule

The following distinction is mandatory:

```text
Different Business Rules
        !=
Different Physical Tables
```

The Mahila Governing Body has Mahila-specific business rules.

That does not require a separate governance database architecture.

---

# 66. Mahila Governance Identity Rule

The system shall never create two governance bodies merely because both names are used:

```text
Mahila Governing Body
Mahila Parichalana Mandali
```

They resolve to:

```text
ONE BODY
```

---

# 67. Terminology Rule

All Mahila Solution documents shall consistently use:

```text
Mahila Governing Body (Mahila Parichalana Mandali)
```

on first reference.

Subsequent references may use:

```text
Mahila Governing Body
```

or:

```text
Mahila Parichalana Mandali
```

provided the context remains clear that both refer to the same body.

---

# 68. Source Alignment

The table design is derived from:

```text
NSS Mahila Sangha Bye-Law
Mahila Module Business Rules
Mahila Module Lifecycle
Mahila Module ERD
NSS Unified Governance Model
NSS Membership Model
NSS Organization Model
NSS Event Model
NSS Attendance Model
NSS Finance Model
NSS Audit Model
```

The Bye-Law remains authoritative for Mahila statutory requirements.

---

# 69. No SQL in This Phase

This document does not contain:

```text
CREATE TABLE
ALTER TABLE
CREATE INDEX
FOREIGN KEY DDL
CHECK CONSTRAINT DDL
PostgreSQL migrations
```

Those belong to a later implementation phase after the Solution documentation is approved.

---

# 70. Final Decision

The Mahila Sangha module shall use a **shared-architecture model**.

The core design is:

```text
Common NSS Foundation
        +
Mahila Business Rules
        |
        v
Mahila Module
```

The Mahila Governing Body / Mahila Parichalana Mandali is represented through the common Unified Governance Model.

No duplicate Mahila membership, governance, event, attendance, finance or audit architecture is introduced.

---

# 71. Status

```text
DOCUMENT STATUS:
DRAFT — BYE-LAW ALIGNED
VERSION:
2.1.0
```

The current table design is aligned with the corrected Mahila business-rule interpretation:

```text
Mahila Governing Body
        =
Mahila Parichalana Mandali

9 Members
2-Year Term
Joint Secretary
```

---

# End of Document
