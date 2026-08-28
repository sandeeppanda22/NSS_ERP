# NSS ERP — Mahila Sangha Module Overview

**Document ID:** SOL-MAH-001  
**Version:** 2.1.0  
**Status:** DRAFT — BYE-LAW ALIGNED  
**Module:** Mahila Sangha  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the scope, purpose, boundaries, ownership and architectural position of the Mahila Sangha Module within NSS ERP.

The module represents Mahila Sangha-related institutional, membership, governance, lifecycle, activity and administrative information within the ERP.

The module is derived from:

1. The verified and approved **Bye-Law of Nilachala Saraswata Mahila Sangha**.
2. Applicable NSS Bye-Law.
3. Approved NSS governance standards.
4. Approved NSS Membership and Person frameworks.
5. Existing approved NSS ERP governance decisions.
6. Mahila-specific ERP business rules derived from the above sources.

Where a Mahila-specific rule is explicitly established by the approved Mahila Bye-Law, that Bye-Law is authoritative for the rule.

---

# 2. Authoritative Mahila Institution

The authoritative source identifies the institution as:

**Nilachala Saraswata Mahila Sangha**

The registered office is:

**Nilachala Kutir, Swargadwar, Puri.**

The Bye-Law records registration under the Societies Registration Act, 1860, with Registration No. **7726/79 of 1974-75**.

The Memorandum describes the institution as an organization of female devotees of Sri Sri Paramahansa Paribrajakacharya Srimat Swamy Nigamananda Saraswati Dev, functioning under the auspices of Nilachala Saraswata Sangha (Kendra Sangha).

---

# 3. Institutional Purpose

The Mahila Sangha exists to pursue the objectives stated in its approved Memorandum and Bye-Law.

The documented objectives include:

- Preservation and maintenance of the Asan of Sri Sri Thakur at Nilachala Kutir.
- Regular spiritual meetings.
- Discourses on the life and teachings of Sri Sri Thakur.
- Training centres and seminars.
- Educational institutions attached to Nilachala Kutir.
- Theoretical and practical training intended to develop ideal Sevikas.
- Activities for women and girls, including those requiring support.
- Seva Puja at Nilachala Kutir.
- Other activities performed according to established practices and conventions approved and directed by Kendra Sangha.

The ERP module shall therefore support the management and traceability of these institutional functions without attempting to redefine their spiritual or statutory meaning.

---

# 4. Relationship With Kendra Sangha

The Mahila Sangha functions under the auspices of Nilachala Saraswata Sangha (Kendra Sangha).

The Bye-Law states that Mahila Sangha functions and activities, including Seva Puja at Nilachala Kutir and establishment of training or educational centres, are to be performed according to established practices and conventions approved and directions issued by Kendra Sangha.

Therefore:

```text
Kendra Sangha
      │
      │ auspices / guidance / direction
      ▼
Nilachala Saraswata Mahila Sangha
```

The ERP must preserve this organizational relationship.

---

# 5. Mahila Sangha Membership

The Mahila Bye-Law defines membership of the Mahila Sangha.

The minimum qualifications include:

* Good moral character.
* Unshakable faith in the eternal existence of Sri Sri Thakur.
* Acceptance of Sri Sri Thakur as sole and supreme Guru and Ishta.
* Desire to regulate one's life for Guru Seva.
* Duly enrolled membership of a Mahila Sangha affiliated to Nilachala Saraswata Sangha.

The Parichalak is responsible for enrolling members from among female devotees who satisfy the stated qualifications.

---

# 6. ERP Membership Identity Boundary

The Mahila module shall not create a second global NSS identity.

The common NSS identity model remains authoritative:

```text
Person
   ↓
NSS Membership
   ↓
Sangha Sevi ID
```

Mahila-specific participation or affiliation shall be represented as a relationship to the authoritative Person/Membership identity.

Therefore:

```text
Mahila participation
        ≠
new NSS identity
```

and:

```text
Mahila participation
        ≠
duplicate Person
```

This follows the project-wide `Person ≠ Member` and `Membership ID = Sangha Sevi ID` principles.

---

# 7. Membership Cessation

The approved Mahila Bye-Law specifies that membership:

* Automatically ceases after death.
* Automatically ceases after resignation.
* May be ordered to cease by the Parichalak for violation of the Sangha's rules and regulations following a report by the Secretary.

The ERP shall preserve the reason and history of membership cessation.

The module shall not silently convert these distinct causes into a single generic inactive state without retaining the underlying reason.

---

# 8. General Body

The Bye-Law establishes a General Body consisting of:

```text
All members of the Mahila Sangha
+
Members of the Governing Body
```

Governing Body members are therefore also members of the General Body.

The ERP shall represent General Body participation through the common Governance framework wherever applicable.

---

# 9. Governing Body

The Mahila Sangha has a Governing Body consisting of **9 members**:

1. President
2. Vice-President
3. Parichalak
4. Secretary
5. Joint Secretary
6. Treasurer
7. Other Member
8. Other Member
9. Other Member

The Bye-Law explicitly defines this composition.

The ERP shall preserve these Mahila-specific office titles.

In particular:

```text
Joint Secretary
```

shall be used for the Mahila Sangha Governing Body.

It shall not be silently renamed to `Assistant Secretary`, because the verified Mahila Bye-Law uses `Joint Secretary`.

---

# 10. Governing Body Term

The approved Bye-Law specifies a two-year term for the Governing Body from the date it assumes office.

The body continues after expiry of the prescribed period until a new Governing Body is constituted and takes over charge.

This Mahila-specific rule takes precedence over any generic ERP governance assumption where the two conflict.

---

# 11. Founder President and Permanent Vice-President

The Bye-Law contains specific provisions for the two original Sevikas identified in the founding constitution.

It provides for:

* Founder President
* Permanent Vice-President

while they prefer to continue serving in those capacities.

The ERP governance model must therefore support historical/special office tenure without incorrectly treating these positions as ordinary fixed-term assignments.

---

# 12. Parichalak

The Mahila Bye-Law gives the Parichalak significant authority.

Among other provisions, the Parichalak:

* Enrols members.
* May order cessation of membership for rule violations following the prescribed process.
* Has overall charge of the Sangha's activities.
* Has responsibilities concerning Sangha property.
* Appoints Sevaks/Sevikas for day-to-day Seva Puja where provided by the Bye-Law.
* Has responsibilities concerning Satsikshya.

The ERP must therefore model Parichalak authority through workflow and centralized RBAC rather than treating the role as a display-only title.

---

# 13. President

The President has defined authority within the Governing Body.

The Bye-Law gives the President, among other responsibilities, authority relating to important policy decisions concerning implementation of Sri Sri Thakur's wishes and participation in constitution of the Governing Body.

The ERP shall represent these authorities through governance workflows.

---

# 14. Other Office Bearers

The Mahila Bye-Law defines responsibilities for:

```text
Vice-President
Secretary
Joint Secretary
Treasurer
```

The ERP shall preserve these titles and responsibilities.

Their detailed permissions shall be mapped to the centralized Governance and RBAC frameworks rather than creating a separate authorization system inside the Mahila module.

---

# 15. Mahila Governance Architecture

The ERP uses the common Unified Body Governance Model.

Conceptually:

```text
Common Governance Framework
             │
             ├── Mahila Sangha Governing Body
             │
             └── Mahila General Body
```

The Mahila module provides the Mahila-specific governance rules.

It does not create a completely independent governance engine.

---

# 16. Mahila Parichalana Mandali — Source Classification

Existing NSS ERP project material identifies a:

```text
Mahila Parichalana Mandali
```

This is the Odia/organizational terminology for the same Mahila Governing Body defined in the verified Bye-Law.

```text
Mahila Governing Body = Mahila Parichalana Mandali
```

The verified Bye-Law uses "Governing Body" (English).

The NSS project documentation uses "Mahila Parichalana Mandali" (Odia organizational term).

Both refer to the same 9-member body with a 2-year term and identical composition (President, Vice-President, Parichalak, Secretary, Joint Secretary, Treasurer, 3 Members).

The ERP shall represent this as **one governance body** through the Unified Body Governance Model.

Its rules (term, composition, positions, constitution process) are established by the verified Mahila Bye-Law.

---

# 17. Seva Puja

Seva Puja is explicitly included within the Mahila Sangha's activities.

The Bye-Law specifically refers to Seva Puja at Nilachala Kutir and states that it is to be performed according to established practices and conventions approved and directed by Kendra Sangha.

Detailed Seva Puja operational rules shall be maintained in the appropriate operational module/documentation.

The Mahila module records the institutional relationship but does not redefine the common Seva-Puja framework.

---

# 18. Training and Educational Activities

The Bye-Law permits:

* Training centres.
* Seminars.
* Educational institutions.
* Theoretical training.
* Practical training.
* Activities aimed at development of ideal Sevikas.

These capabilities are therefore within the institutional scope of Mahila Sangha.

The ERP shall not assume that every such activity requires a permanent Mahila-specific database entity.

The final representation shall follow the approved common Event, Training or Education framework when those operational modules are defined.

---

# 19. Nilachala Kutir

Nilachala Kutir is central to the stated institutional objectives.

The Bye-Law refers to:

* Maintenance of the Asan of Sri Sri Thakur.
* Regular meetings at Nilachala Kutir.
* Seva Puja.
* Training and educational institutions attached to Nilachala Kutir.

The ERP shall preserve Nilachala Kutir as the authoritative location/institutional context where applicable.

---

# 20. Activities

Mahila activities shall be categorized according to their actual institutional purpose.

Potential categories derived from the Bye-Law include:

```text
SPIRITUAL_MEETING
DISCOURSE
SEVA_PUJA
TRAINING
SEMINAR
EDUCATIONAL_ACTIVITY
NILACHALA_KUTIR_ACTIVITY
OTHER_APPROVED_ACTIVITY
```

These values are conceptual at this stage.

They shall not be treated as a frozen master-data list until the corresponding business rules are approved.

---

# 21. Common Event Framework

The Mahila module should use the common NSS Event framework for activities that require:

* Event scheduling.
* Participant registration.
* Attendance.
* Notifications.
* Event history.

The old draft proposal for Mahila-specific activity tables shall therefore be reviewed against the common Event architecture during the ERD and Table Design steps.

No duplicate event framework is frozen by this overview.

---

# 22. Finance

The Mahila Bye-Law contains specific provisions for:

* Pranamis.
* Voluntary donations.
* Specific-purpose donations.
* Grants.
* Kendra Sangha grants.
* Other contributions.
* Property/other earnings.
* Banking.
* Expenditure.
* Audit.

The finance implementation shall use the common NSS Finance framework wherever available.

The Mahila module shall define the Mahila-specific rules and relationships.

---

# 23. Specific-Purpose Donations

The Bye-Law states that donations received for a specific purpose shall be spent and utilized for that purpose alone.

The ERP finance model must therefore preserve the purpose associated with such receipts and support traceability between:

```text
Receipt
   ↓
Specified Purpose
   ↓
Utilization
```

---

# 24. Banking

The Mahila Bye-Law contains specific banking and fund-operation provisions.

These shall be represented through the common Finance module rather than a separate Mahila banking system.

Mahila-specific authorization shall follow the Bye-Law and applicable Finance rules.

---

# 25. Audit

The Bye-Law requires annual audit by a qualified auditor.

The audit report is placed before the Governing Body for final approval and subsequently before the General Body for approval.

The ERP shall preserve this sequence.

Conceptually:

```text
Annual Accounts
      ↓
Qualified Auditor
      ↓
Audit Report
      ↓
Governing Body Approval
      ↓
General Body Approval
```

---

# 26. Dispute Resolution

The Bye-Law provides a specific dispute mechanism.

Controversies concerning the affairs of Nilachala Kutir and the Sangha are referred to the Parichalak, Nilachala Saraswata Sangha, whose decision is stated in the Bye-Law to be binding.

The ERP may provide a dispute/complaint workflow, but must preserve the authority defined by the governing document.

---

# 27. Amendment

The Bye-Law permits the Governing Body to amend, substitute or delete provisions where necessary to achieve the stated aims, subject to the specified process.

Prior consultation with the President of Nilachala Saraswata Sangha is a pre-condition, and the amendment is to be placed before the next General Body meeting for information.

The ERP shall preserve:

```text
Proposal
    ↓
Governing Body Resolution
    ↓
Required Kendra President Consultation
    ↓
General Body Information
```

---

# 28. Dissolution

The Bye-Law provides that if the Sangha is dissolved, remaining property after satisfaction of debts and liabilities shall vest in Kendra Sangha, which will undertake to fulfil the stated aims and objects.

The ERP must preserve this as an institutional lifecycle rule.

---

# 29. Relationship With Common NSS Modules

The Mahila module depends on several common ERP domains.

```text
Person
   │
   ▼
Membership
   │
   ▼
Mahila Participation
```

and:

```text
Organization
   │
   ▼
Mahila Organizational Context
```

and:

```text
Governance
   │
   ▼
Mahila Governing Body
   │
   ▼
General Body
```

and:

```text
Event
   │
   ▼
Mahila Activities
   │
   ▼
Attendance
```

and:

```text
Finance
   │
   ▼
Mahila Funds / Accounts / Audit
```

---

# 30. Module Ownership Boundary

The Mahila module owns:

* Mahila-specific business rules.
* Mahila participation/affiliation.
* Mahila institutional lifecycle.
* Mahila governance-specific rules.
* Mahila activity requirements.
* Mahila-specific finance rules.
* Mahila-specific reporting requirements.

The following remain owned by common modules:

* Person identity.
* NSS Membership identity.
* Sangha Sevi ID.
* Organization master.
* Governance engine.
* RBAC.
* Event engine.
* Attendance engine.
* Finance engine.
* Audit engine.

---

# 31. Identity Principle

The Mahila module shall never create a competing global identity.

The authoritative identity chain remains:

```text
Person
   ↓
NSS Membership
   ↓
Sangha Sevi ID
```

Mahila participation is attached to this identity.

This is consistent with the project's frozen identity architecture.

---

# 32. History Preservation

Mahila historical information shall be preserved.

This includes:

* Membership enrollment.
* Membership cessation.
* Governing Body terms.
* Office-bearer assignments.
* General Body participation.
* Activities.
* Financial records.
* Audit records.
* Amendments.
* Institutional lifecycle.

Historical records shall not be silently overwritten.

This follows the project-wide `History Never Deleted` principle.

---

# 33. Authorization

Mahila operations use centralized NSS RBAC.

No separate:

```text
mahila_role
mahila_permission
```

authorization architecture shall be created.

Authorization is based on:

```text
User
+
Role
+
Governance Position
+
Organizational Scope
+
Permission
```

---

# 34. Reporting Scope

The Mahila module shall support reporting such as:

* Mahila Sangha membership/participation.
* Governing Body composition.
* Office-bearer history.
* General Body information.
* Activities.
* Seva Puja activity.
* Training/educational activity.
* Financial summaries.
* Audit status.
* Historical institutional information.

Detailed report specifications will be defined later.

---

# 35. Module Dashboard Scope

A future Mahila dashboard may provide:

```text
Mahila Members
Active Participation
Governing Body
Current Office Bearers
Upcoming Activities
Seva Puja
Training / Education
Finance Summary
Audit Status
Reports
```

The exact dashboard will be defined during UI documentation.

---

# 36. Security and Privacy

Mahila data shall follow common NSS security standards.

Sensitive information shall be exposed only according to:

```text
Role
+
Organizational Scope
+
Business Need
```

The module shall not expose private member information simply because the user has access to the Mahila module.

---

# 37. Configuration Principle

The system shall prefer configuration and master data over hardcoded values.

Examples include:

```text
Activity Type
Organization
Governance Body Type
Position
Fund Type
Donation Purpose
Approval Type
```

However, values explicitly fixed by the Bye-Law, such as the nine-member Governing Body composition, shall be enforced by the business rules rather than treated as arbitrary configuration.

---

# 38. Bye-Law vs ERP Decision Classification

Mahila documentation shall classify rules as:

### BYE-LAW

Directly supported by the verified Mahila Bye-Law.

### NSS GOVERNANCE

Supported by an approved common NSS governance framework.

### ERP DESIGN

An implementation decision required to represent an approved rule.

### PENDING

Insufficient authoritative source exists.

This classification prevents implementation assumptions from being presented as statutory facts.

---

# 39. Current Authoritative Mahila Facts

The following are directly supported by the verified Bye-Law:

```text
✓ Nilachala Saraswata Mahila Sangha
✓ Registered institution
✓ Registered office at Nilachala Kutir, Puri
✓ Functions under the auspices of Kendra Sangha
✓ Female devotee-oriented institution
✓ Defined membership qualifications
✓ Parichalak enrollment authority
✓ Membership cessation provisions
✓ General Body
✓ 9-member Governing Body
✓ President
✓ Vice-President
✓ Parichalak
✓ Secretary
✓ Joint Secretary
✓ Treasurer
✓ Three other members
✓ Two-year Governing Body term
✓ Founder President provision
✓ Permanent Vice-President provision
✓ Seva Puja
✓ Training / educational activities
✓ Finance provisions
✓ Audit
✓ Dispute resolution
✓ Amendment provisions
✓ Dissolution provisions
```

These are grounded in the supplied Bye-Law.

---

# 40. Current Pending Items

The following must not be presented as established by the verified Mahila Bye-Law without another authoritative source:

```text
Exact Sakha-level Mahila Sangha operational structure
Detailed Mahila event/attendance rules
Detailed Mahila membership status model within ERP
```

These may already exist in other approved NSS project sources, but they require explicit traceability before being represented as authoritative Mahila rules.

---

# 41. Terminology Equivalence

The verified Mahila Bye-Law uses "Governing Body" (English) for the same body that NSS project documentation calls "Mahila Parichalana Mandali" (Odia organizational term).

This has been resolved:

```text
Mahila Governing Body = Mahila Parichalana Mandali
```

One body. One governance record. The Bye-Law is authoritative for its composition, term and position titles.

---

# 42. Architectural Position

The Mahila module sits within the NSS ERP architecture as:

```text
                 NSS ERP
                    │
        ┌───────────┴───────────┐
        │                       │
     Common NSS             Mahila Module
     Foundations                 │
        │                       │
        ├── Person              ├── Mahila Participation
        ├── Membership          ├── Mahila Governance Rules
        ├── Organization        ├── Mahila Activities
        ├── Governance          ├── Mahila Finance Rules
        ├── Event              └── Mahila Reporting
        ├── Attendance
        ├── Finance
        ├── RBAC
        └── Audit
```

---

# 43. Documentation Sequence

The Mahila documentation set is:

```text
01_mahila_module_overview.md
02_mahila_erd.md
03_mahila_lifecycle.md
04_mahila_business_rules.md
05_mahila_table_design.md
```

The sequence is:

```text
Overview
   ↓
ERD
   ↓
Lifecycle
   ↓
Business Rules
   ↓
Table Design
```

The Table Design document shall be completed last.

---

# 44. Documentation-Only Phase

At this stage:

```text
No SQL schema is being generated.
No migrations are being generated.
No Django models are being generated.
No PostgreSQL DDL is being generated.
```

The purpose of this documentation phase is to establish the approved functional and solution model for all NSS ERP modules before implementation.

---

# 45. Related Documents

```text
NSS Bye-Law

NSS_Mahila_Sangha_Bye_Law.docx

NSS Governance Rules

NSS Membership Rules

NSS Organization Documentation

NSS Governance Documentation

NSS Event Documentation

NSS Attendance Documentation

NSS Finance Documentation
```

---

# 46. Next Documents

After this overview:

```text
02_mahila_erd.md
```

will define the conceptual relationships.

Then:

```text
03_mahila_lifecycle.md
```

will define membership and governance lifecycle behavior.

Then:

```text
04_mahila_business_rules.md
```

will consolidate the detailed MAH-* rules and Bye-Law-derived rules.

Finally:

```text
05_mahila_table_design.md
```

will describe the intended physical data model without generating SQL.

---

# 47. Status

This document is:

```text
DRAFT — BYE-LAW RECONCILIATION
```

It becomes eligible for freeze only after:

1. Existing Mahila documents are reconciled.
2. Mahila ERD is completed.
3. Lifecycle rules are completed.
4. Business rules are consolidated.
5. Cross-module dependencies are reviewed.
6. Authoritative-source traceability is verified.

---

# End of Document
