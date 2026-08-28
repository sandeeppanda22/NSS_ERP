# NSS ERP — Kumari Sangha Module Overview

**Document ID:** SOL-KUM-001  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Kumari Sangha  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Kumari Sangha Module manages the NSS Kumari Sangha program as a distinct youth-development and value-education institution.

The module provides a structured way to manage:

- Kumari identity
- Kumari participation
- Kumari Sangha affiliation
- Activities
- Training
- Dina-Lipi
- Niyam Panchak
- Dasa Sheela
- Participation history
- Membership transition to NSS
- Family relationship
- Historical records

---

# 2. Institutional Position

Kumari Sangha is treated as a distinct NSS youth-development institution.

It is not:

- An NSS membership category
- An NSS membership type
- A Sangha Sevi category
- A replacement for NSS Membership
- A duplicate of Mahila Sangha

The project source characterizes Kumari Sangha as a continuous development program with its own identity and ongoing participation.

---

# 3. Core Purpose

The Kumari Sangha program focuses on development of young girls through:

- Character building
- Discipline
- Spiritual education
- Service orientation
- Value education
- Dina-Lipi practice
- Niyam Panchak
- Dasa Sheela
- Training
- Leadership development
- Preparation for future participation in Mahila Sangha

These objectives are part of the existing frozen Kumari baseline.

---

# 4. Target Participants

The current project baseline describes Kumari Sangha participants as:

```text
Young Girls
      |
      v
Primarily from NSS Families
      |
      v
Kumari Sangha Participation
```

The exact age boundary is **not currently frozen** in the available source material.

Therefore the ERP shall not hard-code a specific age range at this stage.

---

# 5. Kumari Identity

Every Kumari participant shall have a dedicated Kumari identity.

Example:

```text
KM000001
KM000002
KM000003
```

The Kumari ID is:

* Unique
* Permanent
* Never reused
* Valid within the Kumari Sangha context

The Kumari ID is separate from the NSS Sangha Sevi ID.

---

# 6. Kumari ID vs Sangha Sevi ID

The identity model is:

```text
Kumari Participant
        |
        v
KM000123
```

If the person later becomes an NSS member:

```text
KM000123
        |
        v
NSS Membership Approved
        |
        v
SS000456
```

The two identities remain linked.

```text
KM000123
    |
    +-- linked to --> SS000456
```

A Kumari participant does not automatically receive an NSS Sangha Sevi ID.

---

# 7. Person Foundation

Kumari participants use the common Person foundation.

The architectural relationship is:

```text
PERSON
   |
   +-- Family Relationship
   |
   +-- Kumari Participation
```

A person does not need to be an NSS member to exist in the Person foundation.

This preserves the project-wide principle:

```text
Person != Member
```

---

# 8. Family Relationship

Kumari participants may be connected to their NSS family through the common Family module.

Conceptually:

```text
NSS Family
     |
     +-- Daughter
            |
            v
       Kumari Participant
```

The Family module remains the owner of:

* Family
* Family relationship
* Family history

Kumari does not create a duplicate family architecture.

---

# 9. Kumari Sangha Participation

Kumari participation is separate from NSS membership.

The model is:

```text
Person
   |
   v
Kumari Participation
   |
   v
Kumari ID
```

rather than:

```text
Person
   |
   v
NSS Membership
```

for every Kumari participant.

This allows young participants to participate without prematurely creating NSS membership identities.

---

# 10. Membership Relationship

Kumari Sangha participation is not itself an NSS membership category.

Therefore:

```text
Kumari Participant
        !=
NSS Member
```

A participant may later apply for NSS membership.

---

# 11. Transition to NSS Membership

A Kumari participant may later apply for NSS Membership.

The transition is:

```text
Kumari Participant
        |
        v
Membership Application
        |
        v
Membership Review
        |
        v
Membership Approval
        |
        v
Sangha Sevi ID Generated
```

The original Kumari history remains preserved.

---

# 12. Long-Term Kumari Participants

The project baseline allows long-term active Kumari participants to be considered for direct Regular Membership where the applicable membership authority approves it.

Probationary Membership is therefore not automatically mandatory for every Kumari participant.

The assessment may consider:

* Years of Kumari participation
* Dina-Lipi participation
* Niyam Panchak knowledge
* Dasa Sheela knowledge
* Conduct and discipline
* Seva participation
* Recommendations

This rule is recorded in the existing frozen Kumari membership-transition baseline.

---

# 13. Kumari Membership Status

The Kumari record shall preserve its own participation status.

The current frozen model identifies statuses/reasons including:

```text
ACTIVE
MARRIED_OUT
BECAME_NSS_MEMBER
WITHDRAWN
DECEASED
```

These statuses belong to the Kumari lifecycle and must not be confused with NSS Membership status.

---

# 14. Marriage Transition

The current frozen project rule provides for a Kumari participant who marries to leave active Kumari participation.

Conceptually:

```text
Active Kumari
      |
      v
Marriage
      |
      v
MARRIED_OUT
```

The original Kumari history remains preserved.

---

# 15. Family History After Marriage

A former Kumari participant remains part of her birth-family history.

The marriage relationship is recorded through the common Family module.

The spouse may exist as a Person even if the spouse is not an NSS member.

This preserves:

* Family tree
* Marriage history
* Genealogy
* Future membership possibility

The Family module owns this information.

---

# 16. Dina-Lipi

Dina-Lipi is a core Kumari Sangha development activity.

The module shall support tracking of Dina-Lipi participation/progress.

The existing project source identifies Dina-Lipi tracking as a core Kumari capability.

---

# 17. Niyam Panchak

Niyam Panchak is part of the Kumari Sangha development program.

The module shall support its training/learning context.

Where detailed Niyam Panchak rules are not yet defined, the ERP shall not invent additional assessment rules.

---

# 18. Dasa Sheela

Dasa Sheela is part of the Kumari Sangha development program.

The module shall support its training/learning context.

Detailed assessment or certification rules remain dependent on approved operational requirements.

---

# 19. Training

Training is a core Kumari Sangha capability.

The module shall support:

* Training programs
* Training participation
* Training history
* Training completion where defined

The detailed training model shall be finalized in the dedicated business-rule and table-design documents.

---

# 20. Activities

Kumari Sangha supports ongoing activities rather than a single annual event model.

Activities may include:

* Regular Kumari activities
* Training activities
* Dina-Lipi-related activities
* Niyam Panchak activities
* Dasa Sheela activities
* Character-building activities
* Spiritual/value-education activities
* Service-oriented activities

The exact activity categories shall remain master-data driven.

---

# 21. Continuous Development Model

Kumari Sangha is a continuous development program.

Conceptually:

```text
Participant
    |
    v
Kumari Sangha
    |
    v
Ongoing Activities
    |
    v
Training
    |
    v
Dina-Lipi
    |
    v
Niyam Panchak
    |
    v
Dasa Sheela
    |
    v
Development
    |
    v
Future NSS / Mahila Participation
```

This distinguishes Kumari Sangha from the annual-event model used for Kishor Puja.

---

# 22. Relationship With Mahila Sangha

The current project baseline describes Kumari Sangha as a developmental pathway toward future Mahila Sangha participation.

Conceptually:

```text
Kumari Sangha
      |
      v
Development
      |
      v
Adulthood / Eligibility
      |
      v
Mahila Sangha
```

This is a developmental relationship, not an automatic membership conversion.

---

# 23. Governance

If Kumari Sangha requires office-bearers, coordinators or a committee, the common Unified Governance Model shall be used.

The project source specifically recommends reuse of:

```text
body_master
body_member_assignment
position_master
```

rather than separate governance tables.

---

# 24. Organization

Kumari Sangha shall use the common Organization framework.

Where an organization type is required, the project baseline identifies:

```text
KUMARI_SANGHA
```

as an organization type.

The exact organization hierarchy remains owned by the Organization module.

---

# 25. Core Logical Entities

The current frozen project baseline identifies the following Kumari logical tables:

```text
kumari_sangha
kumari_membership
kumari_activity
kumari_activity_participant
kumari_membership_transition
```

These are logical solution entities at this stage.

No SQL schema is being created in this documentation phase.

---

# 26. kumari_sangha

This entity represents the Kumari Sangha organizational context.

It provides the association between Kumari participants and the relevant Kumari Sangha organization.

---

# 27. kumari_membership

This entity represents a person's participation/membership within Kumari Sangha.

It is distinct from the common NSS Membership entity.

It shall support the Kumari lifecycle, including:

* Kumari ID
* Person
* Kumari Sangha
* Status
* Joining date
* Exit date
* Exit reason

The exact final column design belongs to K-05.

---

# 28. kumari_activity

This entity represents Kumari Sangha activities.

Activities remain distinct from NSS membership.

---

# 29. kumari_activity_participant

This entity represents participation of Kumari participants in Kumari activities.

Conceptually:

```text
Kumari Membership
        |
        v
Activity Participation
        |
        v
Kumari Activity
```

---

# 30. kumari_membership_transition

This entity preserves transition from Kumari participation to NSS Membership.

Conceptually:

```text
Kumari Membership
        |
        v
Transition
        |
        v
Sangha Sevi / NSS Membership
```

The transition record preserves the relationship between the two lifecycle stages.

---

# 31. Historical Preservation

The project-wide rule is:

```text
History Never Deleted
```

Therefore the Kumari module shall preserve:

* Kumari ID history
* Participation history
* Activity history
* Training history
* Dina-Lipi history
* Membership transition history
* Exit history

---

# 32. Visibility

The Kumari module participates in the project-wide family visibility model.

Family members may view authorized information concerning their own family's Kumari participants.

The project source specifically identifies family visibility for Kumari participants, including:

* Participant details
* Registration details
* Activity history
* Training history
* Participation status
* Guardian/family information where applicable
* Membership transition status

Family visibility remains restricted to the family's own records.

---

# 33. Kendra Visibility

Kendra-level authorized users may view Kumari participants across authorized Sakha/organizational scope.

The exact RBAC implementation belongs to the Administration/Security and Organization modules.

---

# 34. Sakha Visibility

Sakha-level authorized users shall only access Kumari information within their authorized organizational scope.

The exact permission matrix remains owned by the common RBAC framework.

---

# 35. Reports

The Kumari module shall support reporting for:

* Kumari participant count
* Active Kumaris
* Activity participation
* Training participation
* Dina-Lipi tracking
* Development history
* Membership transition
* Organizational/Sakha distribution

The exact reporting implementation belongs to Reports and Analytics.

---

# 36. Dashboard

The project UI baseline identifies a Kumari Sangha portal containing:

```text
Total Participants
Active Kumaris
Upcoming Activities
Participant List
Training
Dina-Lipi
Niyam Panchak
Dasa Sheela
```

---

# 37. Common Module Integration

The Kumari module integrates with:

```text
Person
Family
Organization
Membership
Governance
Event/Activity
Attendance
Reports
Administration/RBAC
Audit
```

Kumari-specific functionality should not duplicate common foundation capabilities.

---

# 38. Membership Boundary

The following distinction is mandatory:

```text
Kumari Sangha Participation
        !=
NSS Membership
```

A participant can exist in Kumari Sangha without an NSS Sangha Sevi ID.

---

# 39. Identity Boundary

The following distinction is mandatory:

```text
Kumari ID
   !=
Sangha Sevi ID
```

Example:

```text
KM000123
   |
   v
later
   |
   v
SS000456
```

The relationship is preserved historically.

---

# 40. Kishor Puja Boundary

Kumari Sangha and Kishor Puja shall remain separate business modules.

Kumari Sangha:

```text
Continuous Development Program
```

Kishor Puja:

```text
Annual Event-Based Participation
```

The project source explicitly distinguishes these models.

---

# 41. Mahila Boundary

Kumari Sangha is not a Mahila Sangha membership category.

The relationship is developmental:

```text
Kumari
   |
   v
Future
   |
   v
Mahila
```

Actual Mahila membership remains governed by Mahila/NSS membership rules.

---

# 42. Security

The module shall use the common NSS RBAC framework.

Authorization shall consider:

```text
User
+
Role
+
Organization Scope
+
Permission
```

No separate Kumari authorization engine shall be created.

---

# 43. Audit

Kumari administrative actions shall use the common Audit framework.

Auditable actions include:

* Participant creation
* Status changes
* Activity creation
* Participation changes
* Training records
* Membership transition
* Administrative corrections

---

# 44. Master Data

The Kumari module shall use master data where appropriate.

Potential master-data areas include:

```text
Kumari Status
Activity Type
Training Type
Organization Type
Transition Type
Exit Reason
```

The final master-data catalog remains controlled by the Master Data module.

---

# 45. Age Rule

The exact age boundary for Kumari Sangha is currently not frozen in the available project source.

Therefore:

```text
Exact age limit = PENDING
```

The system shall not hard-code an age cutoff until an authoritative operational rule is documented.

---

# 46. Eligibility Rule

The current working baseline identifies:

```text
Young Girls
Daughters of NSS Families
Adolescent Age Group
```

as the intended participant population.

Because the exact age rule is not frozen, this remains a documented working eligibility model rather than a hard-coded statutory requirement.

---

# 47. Future Membership

Kumari participation can contribute to a future NSS Membership application.

The transition is not automatic.

Membership approval remains subject to the common NSS Membership authority and rules.

---

# 48. Future Mahila Participation

Kumari Sangha may serve as a developmental pathway toward Mahila Sangha.

However:

```text
Kumari Participation
        !=
Automatic Mahila Membership
```

The future transition must follow the applicable Mahila/NSS rules.

---

# 49. Architectural Principles

The Kumari module follows these project principles:

```text
Person != Member

Kumari ID != Sangha Sevi ID

Participation != Membership

Family First

History Never Deleted

Unified Governance Model

Master Data Driven

Documentation First

Source Supremacy
```

---

# 50. Out of Scope for This Overview

This document does not freeze detailed rules for:

* Exact age eligibility
* Detailed Dina-Lipi assessment
* Detailed Niyam Panchak assessment
* Detailed Dasa Sheela assessment
* Training certification
* Detailed Kumari governance
* Detailed activity approval
* Detailed attendance rules
* Detailed transition approval workflow

Those belong in the appropriate downstream documents once authoritative requirements are available.

---

# 51. Related Documents

The planned Kumari Solution documentation set is:

```text
docs/03_Solution/modules/kumari/

+-- 01_kumari_module_overview.md
+-- 02_kumari_erd.md
+-- 03_kumari_lifecycle.md
+-- 04_kumari_business_rules.md
+-- 05_kumari_table_design.md
```

---

# 52. Source Traceability

This overview is based on the existing NSS ERP project-source decisions concerning:

* Kumari Sangha definition
* Kumari identity
* Kumari membership
* Activities
* Training
* Dina-Lipi
* Niyam Panchak
* Dasa Sheela
* Membership transition
* Family integration
* Governance integration

The project governance framework requires downstream Solution documentation to remain traceable to its governing sources.

---

# 53. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

The module is considered structurally defined at the Solution Overview level.

Detailed business rules, lifecycle, ERD and table design shall be documented in subsequent Kumari documents.

---

# End of Document
