# NSS ERP — Founder & Heritage Business Rules

**Document ID:** SOL-HER-004  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Founder & Heritage  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing the Founder & Heritage Module.

The module preserves and manages:

- Founder information
- Founder teachings
- Official NSS objectives
- Historical milestones
- Historical office bearers
- NSS publications
- Publication classifications

The rules in this document are limited to the current frozen Founder & Heritage scope.

---

# 2. Scope

The current frozen scope consists of:

## Core Tables

1. `founder_master`
2. `founder_teaching`
3. `nss_objective_master`
4. `nss_historical_milestone`
5. `nss_publication`
6. `historical_office_bearer`

## Supporting Masters

7. `publication_type_master`
8. `publication_language_master`

This eight-table scope is explicitly identified in the frozen source.

---

# 3. HER-001 — Founder Identity

The Founder represented by the Founder & Heritage Module is:

**Swami Nigamananda Paramahansa Dev.**

The Founder record represents the institutional Founder reference for NSS.

---

# 4. HER-002 — Single Founder Record

The `founder_master` table shall contain exactly one Founder reference record.

Multiple Founder records shall not be created for NSS.

---

# 5. HER-003 — Founder Record Is Immutable

The Founder reference shall be treated as immutable institutional reference data.

The system shall not provide normal:

- activation
- deactivation
- replacement
- archival
- deletion

operations for the Founder record.

The frozen design explicitly removes `is_active` and `display_order` and specifies that the Founder record is never deleted.

---

# 6. HER-004 — Founder Record Is Seeded

The Founder record shall be established as part of the initial Heritage foundation.

It is not an ordinary user-created master record.

---

# 7. HER-005 — Founder Cannot Be Replaced

The system shall not provide a normal workflow to replace the Founder with another person.

---

# 8. HER-006 — Founder Cannot Be Deleted

The Founder record shall never be physically deleted.

Any correction to associated Founder information must preserve the institutional identity.

---

# 9. HER-007 — Founder Content Is Separate from Person

Founder heritage content shall not be treated as a normal NSS membership/person lifecycle.

The Founder reference is a Heritage-domain record.

---

# 10. HER-008 — Founder Teaching Ownership

Founder teachings shall belong to the Founder Heritage domain.

A teaching may represent:

- Teaching
- Philosophy
- Quote
- Principle

The frozen `founder_teaching` entity covers these concepts.

---

# 11. HER-009 — Founder Teaching Association

A Founder teaching shall be associated with the Founder reference.

Conceptually:

```text
Founder
   ↓
Founder Teaching
```

---

# 12. HER-010 — Teaching Content Integrity

Founder teaching content presented as official NSS Heritage content shall originate from an appropriate authoritative or approved source.

The system shall not present arbitrary user-generated material as an official Founder teaching.

---

# 13. HER-011 — Teaching Corrections

Authorized corrections to Founder teaching content shall be auditable.

Corrections shall not silently destroy required historical traceability.

---

# 14. HER-012 — No Separate Founder Quote Entity

A separate `founder_quote` entity is not part of the current frozen scope.

Quotes remain within the current Founder Teaching scope unless a future enhancement is separately approved.

---

# 15. HER-013 — NSS Objectives Are Official Reference Content

`nss_objective_master` shall contain official NSS objectives.

Objectives shall not be invented by application users.

---

# 16. HER-014 — Objective Authority

Objective content shall originate from approved NSS authoritative sources.

Where an authoritative source changes, the corresponding Heritage content shall be updated through the approved governance process.

---

# 17. HER-015 — Objective Preservation

Historical objective information shall remain traceable where changes occur.

An updated objective shall not automatically erase the historical existence of the previous wording where project-wide history requirements apply.

---

# 18. HER-016 — Historical Milestone Ownership

`nss_historical_milestone` shall contain important historical events and milestones of NSS.

---

# 19. HER-017 — Historical Milestone Source

Where available, a historical milestone shall retain its source reference.

The frozen milestone design includes `source_reference`.

---

# 20. HER-018 — Historical Milestone Accuracy

Historical milestones presented as official NSS history shall be based on reliable source material.

The system shall not treat unverified user assertions as authoritative historical facts.

---

# 21. HER-019 — Historical Milestone Preservation

Historical milestones shall be preserved.

A milestone shall not be deleted merely because it is old or no longer operationally relevant.

---

# 22. HER-020 — Historical Milestone Correction

If reliable evidence establishes that a historical milestone contains incorrect information, the record may be corrected through an authorized process.

The correction shall remain auditable.

---

# 23. HER-021 — Historical Office Bearer Ownership

`historical_office_bearer` shall preserve historical leadership information.

The frozen scope specifically includes historical:

* Presidents
* Parichalaks
* Secretaries
* Other relevant office bearers.

---

# 24. HER-022 — Historical Office Bearer Is Historical

A historical office-bearer record represents a past organizational role.

It shall not be treated as a current Governance assignment.

---

# 25. HER-023 — Current Governance Separation

Current office-bearer information shall remain owned by the Governance module.

The Heritage module shall not replace current Governance records.

```text
Historical Office Bearer
        ≠
Current Office Bearer
```

---

# 26. HER-024 — Historical Term Preservation

When an office-bearer's term ends, the historical record shall remain preserved.

Ending a term shall not delete the historical record.

---

# 27. HER-025 — Historical Office Bearer Dates

Where known, the historical record shall preserve:

* From date
* To date

These dates describe historical service.

---

# 28. HER-026 — Historical Office Bearer Correction

Historical office-bearer information may be corrected when authoritative evidence requires correction.

Corrections shall be auditable.

---

# 29. HER-027 — Publication Identity

Every NSS publication shall have its own publication identity.

The publication identity shall remain distinguishable from its digital document.

---

# 30. HER-028 — Publication Title

A publication shall have a recorded title.

The title is part of the publication's structured metadata.

---

# 31. HER-029 — Publication Type Mandatory

Every publication shall be classified using the approved publication type master.

The publication shall not rely solely on free-text type classification.

---

# 32. HER-030 — Publication Type Master

The current approved publication type values are:

```text
BOOK
MAGAZINE
JOURNAL
NEWSLETTER
ANNUAL_REPORT
UPBS_SOUVENIR
RESEARCH_PUBLICATION
PAMPHLET
BOOKLET
OTHER
```

These values are from the frozen publication framework.

---

# 33. HER-031 — Publication Language Mandatory

Every publication shall have a language classification.

Language is mandatory in the frozen publication design.

---

# 34. HER-032 — Publication Language Master

The current approved language values are:

```text
ODIA
ENGLISH
HINDI
BENGALI
ASSAMESE
TELUGU
TAMIL
OTHER
```

---

# 35. HER-033 — Publication Language Is Not Free Text

Publication language shall use the approved language master rather than unrestricted free-text values.

This supports consistent reporting and searching.

---

# 36. HER-034 — Publication Date

Where applicable, the publication date shall be recorded.

The date represents the publication's recorded publication date, not necessarily the date on which its digital copy was uploaded.

---

# 37. HER-035 — Publication Edition

The publication framework supports multiple editions of the same publication.

Edition information shall therefore be retained.

---

# 38. HER-036 — Multiple Editions

The system shall permit multiple editions of a publication.

Example:

```text
Publication
 ├── Edition 1
 ├── Edition 2
 └── Edition 3
```

Multiple editions are explicitly supported by the frozen publication rules.

---

# 39. HER-037 — Edition Does Not Destroy Previous Edition History

A new edition shall not silently overwrite historical information belonging to an earlier edition.

Historical edition information shall remain traceable.

---

# 40. HER-038 — Publication Price

A publication may have a recorded price.

Price information shall be maintained as structured publication metadata.

---

# 41. HER-039 — Publication Pricing Models

The publication framework supports:

```text
Free
Donation Based
Fixed Price
```

These are distinct commercial/availability concepts.

---

# 42. HER-040 — Free Publication

A publication may be designated as free.

A free publication does not require a fixed sale price.

---

# 43. HER-041 — Donation-Based Publication

A publication may be offered on a donation basis.

Donation handling itself is outside the current Heritage publication table and belongs to the applicable Finance/Donation functionality.

---

# 44. HER-042 — Fixed-Price Publication

A publication may have a fixed price.

The publication record shall preserve the applicable currency information.

---

# 45. HER-043 — Currency

The frozen publication design includes `currency_code`.

The default currency context is INR.

---

# 46. HER-044 — Page Count

Where known, publication page count may be recorded.

It is publication metadata and does not represent digital document size.

---

# 47. HER-045 — ISBN

Where applicable, an ISBN may be recorded.

ISBN is optional in the frozen design.

---

# 48. HER-046 — Publication Description

A publication may have a structured description or summary.

The description shall not be used as a replacement for the publication title or classification.

---

# 49. HER-047 — Digital Copy

A publication may have a digital copy.

The frozen design provides:

```text
document_pk
```

for the digital copy reference.

---

# 50. HER-048 — Physical and Digital Copies May Coexist

A publication may have both:

```text
Physical Copy
+
Digital Copy
```

The existence of a digital copy does not replace the physical publication record.

This is explicitly frozen.

---

# 51. HER-049 — Digitization

The publication framework includes:

```text
is_digitized
```

to indicate availability of a digital version.

---

# 52. HER-050 — Digitization Does Not Create New Publication Identity

Digitizing a physical publication shall not create a second publication identity.

The same publication record may be associated with its digital copy.

---

# 53. HER-051 — Cover Image

A publication may have a cover image through:

```text
cover_photo_document_pk
```

The underlying document/image is managed through the common Document framework.

---

# 54. HER-052 — No Heritage File Storage

Founder & Heritage shall not create a separate file-storage architecture.

Digital publication and image references shall use the common Document Management framework.

---

# 55. HER-053 — Publication Metadata vs Document

The publication record and the digital document are separate concepts.

```text
Publication Metadata
        ≠
Digital File
```

---

# 56. HER-054 — Publication Preservation

A publication record shall remain historically available even when the publication is no longer actively distributed.

Examples:

```text
Old Publication
Out of Print
Old Edition
Digital Copy Unavailable
Physical Copy Unavailable
```

These conditions do not justify destruction of the historical publication record.

---

# 57. HER-055 — Publication Correction

Authorized users may correct publication metadata where reliable information requires correction.

Examples:

* Incorrect title
* Incorrect publication date
* Incorrect edition
* Incorrect ISBN
* Incorrect page count
* Incorrect description
* Incorrect classification

Corrections shall be auditable.

---

# 58. HER-056 — Publication Type Master Integrity

Publication type master values shall be centrally managed.

Individual publications shall not create arbitrary new type values.

---

# 59. HER-057 — Publication Language Master Integrity

Publication language master values shall be centrally managed.

Individual publications shall not create arbitrary new language values.

---

# 60. HER-058 — Master Data Changes

Changes to publication type or language masters shall follow the common master-data governance process.

Historical publication records shall remain interpretable after master-data maintenance.

---

# 61. HER-059 — Founder Heritage Does Not Own Membership

The Heritage module shall not manage:

* Membership approval
* Membership renewal
* Membership transfer
* Sangha Sevi lifecycle

Those belong to the Membership module.

---

# 62. HER-060 — Founder Heritage Does Not Own Attendance

The Heritage module shall not manage attendance.

Attendance remains owned by the Attendance module.

---

# 63. HER-061 — Founder Heritage Does Not Own Current Governance

The Heritage module shall not manage:

* Current governing bodies
* Current position assignments
* Elections
* Current office-bearer appointments

These remain within Governance.

---

# 64. HER-062 — Founder Heritage Does Not Own Organization Master

The Heritage module shall not create duplicate organization master data.

The common Organization module remains authoritative.

---

# 65. HER-063 — Founder Heritage Does Not Own Person Master

The Heritage module shall not create a duplicate general-purpose Person master.

Where historical or document relationships require Person integration, the common Person module remains authoritative.

---

# 66. HER-064 — Historical Data Is Not Operational Data

Historical records shall not be interpreted as current operational state.

Examples:

```text
Historical President
        ≠
Current President

Historical Sakha
        ≠
Current Sakha

Historical Publication
        ≠
Current Operational Activity
```

---

# 67. HER-065 — Historical Information Must Remain Traceable

Where a historical record is corrected, its historical context shall remain traceable through the common audit/history standards.

---

# 68. HER-066 — Public Presentation Does Not Equal Record Deletion

Removing a record from public presentation does not necessarily mean deleting the underlying Heritage record.

The system shall distinguish:

```text
Record Preservation
        from
Public Visibility
```

---

# 69. HER-067 — Public Heritage Content

The Heritage Portal may present approved information covering:

```text
Founder
Biography
Philosophy
Teachings
Milestones
Publications
Historical Office Bearers
```

This is the documented public Heritage structure.

---

# 70. HER-068 — Public Content Must Be Controlled

Content presented as official NSS Heritage information shall be controlled through authorized administrative processes.

---

# 71. HER-069 — Administrative Authority

Founder & Heritage administration shall use the common NSS ERP RBAC framework.

No separate Heritage authentication or permission framework shall be created.

---

# 72. HER-070 — Auditability

The following actions shall be auditable:

```text
Founder content correction
Teaching creation/update
Objective creation/update
Milestone creation/update
Historical office-bearer creation/update
Publication creation/update
Publication classification
Digital document association
Publication correction
```

---

# 73. HER-071 — Physical Deletion Restriction

Historical Heritage records shall not be physically deleted merely because they are old or no longer current.

---

# 74. HER-072 — No Automatic Expiry

Founder teachings, objectives, historical milestones, historical office-bearer records, and publications shall not automatically expire.

---

# 75. HER-073 — No Automatic Archival Workflow

The current frozen source does not establish an automatic archival lifecycle for Heritage records.

Therefore no automatic archival rule shall be introduced without separate approval.

---

# 76. HER-074 — No Unsupported Approval States

The current source does not freeze a universal Heritage content status model.

Therefore the module shall not invent mandatory statuses such as:

```text
DRAFT
SUBMITTED
APPROVED
PUBLISHED
ARCHIVED
```

as universal database business states.

Where workflow is later required, it must be separately approved.

---

# 77. HER-075 — Source Authority

Where authoritative NSS source material exists, it takes precedence over:

* User-entered assumptions
* Generic historical information
* Unverified third-party information

---

# 78. HER-076 — No Statutory Reinterpretation

Founder & Heritage shall preserve and present authoritative content.

It shall not reinterpret statutory or bye-law provisions as new statutory rules.

---

# 79. HER-077 — Future Enhancement Boundary

The following are not current frozen business entities:

```text
founder_quote
heritage_document
heritage_photo_gallery
publication_author
historical_event_participant
```

They remain future enhancements.

---

# 80. HER-078 — Future Enhancements Require Approval

A future Heritage entity shall not be introduced into the frozen design without:

```text
Business Requirement
        ↓
Solution Design
        ↓
Approval
        ↓
Documentation Update
```

---

# 81. HER-079 — No SQL in Business Rules

This document defines business rules only.

It does not define:

* PostgreSQL DDL
* SQL constraints
* SQL indexes
* Triggers
* Django migrations

---

# 82. HER-080 — Common Audit Standard

All Heritage entities shall follow the project-wide audit standards.

The Heritage module shall not create a separate audit architecture.

---

# 83. HER-081 — Common Document Standard

All digital Heritage documents shall follow the common Document Management standards.

---

# 84. HER-082 — Common Master Data Standard

Publication type and language shall follow the common Master Data governance standards.

---

# 85. HER-083 — Historical Office Bearer and Governance Traceability

Where historical office-bearer information corresponds to a person or organization represented elsewhere in the ERP, relationships shall preserve historical context without replacing current records.

---

# 86. HER-084 — Publication Searchability

Publication metadata shall support structured searching and filtering using available fields such as:

```text
Title
Type
Language
Publication Date
Edition
ISBN
```

---

# 87. HER-085 — Publication Reporting

The Publication Library shall support reporting by:

```text
Publication Type
Language
Year
Edition
Digital Availability
```

where the corresponding information exists.

---

# 88. HER-086 — Heritage Reporting

The module shall support structured reporting for:

```text
Founder Teachings
NSS Objectives
Historical Milestones
Historical Office Bearers
Publications
```

---

# 89. HER-087 — Family / Member Visibility

Where Heritage content is exposed to authenticated members, visibility shall follow the common application security and authorization framework.

Heritage content does not create a separate member access model.

---

# 90. HER-088 — Public Read Access

Public Heritage content may be made available without requiring ERP authentication where approved.

Administrative modification remains restricted.

---

# 91. HER-089 — Founder Biography

The Founder Biography shall be treated as Heritage content associated with the immutable Founder reference.

It shall not create a duplicate Founder identity.

---

# 92. HER-090 — Founder Philosophy

Founder Philosophy shall be represented as Heritage content associated with the Founder domain.

---

# 93. HER-091 — Founder Teaching Search

Founder teachings should be discoverable through structured Heritage interfaces.

Search functionality shall not alter the underlying teaching record.

---

# 94. HER-092 — Historical Milestone Ordering

Historical milestones should support chronological presentation.

The underlying milestone date remains the authoritative chronological field where available.

---

# 95. HER-093 — Historical Office Bearer Ordering

Historical office-bearer information should support chronological historical presentation using the recorded service dates where available.

---

# 96. HER-094 — Publication Digital Availability

Where a digital document exists, the publication may expose the authorized digital access mechanism.

The underlying file remains owned by Document Management.

---

# 97. HER-095 — Publication Cover

A publication may have a cover image associated through the common document system.

A cover image is supplementary publication metadata and does not constitute a separate publication.

---

# 98. HER-096 — Publication Identity Across Editions

The publication design supports multiple editions.

Edition information shall remain distinguishable so that historical publication information is not lost.

---

# 99. HER-097 — No Duplicate Heritage Entities

The module shall not create duplicate entities for concepts already owned by common modules.

Examples:

```text
Person
Organization
Document
Membership
Governance
Attendance
Audit
```

---

# 100. HER-098 — Current Frozen Heritage Foundation

The final frozen current foundation is:

```text
Founder
├── founder_master
└── founder_teaching

NSS Heritage
├── nss_objective_master
└── nss_historical_milestone

Publications
├── nss_publication
├── publication_type_master
└── publication_language_master

History
└── historical_office_bearer
```

---

# 101. HER-099 — Future Scope Is Not Current Scope

Recommended future tables shall not be treated as current business requirements.

The distinction is:

```text
FROZEN
    ↓
Current Business Rules

RECOMMENDED
    ↓
Future Candidate

NOT APPROVED
    ↓
Not Implemented
```

---

# 102. HER-100 — Final Business Rule

Founder & Heritage shall preserve NSS's institutional heritage without conflating historical/reference information with current operational ERP state.

The module shall maintain:

```text
Founder Identity
Founder Teachings
Official Objectives
Historical Milestones
Historical Leadership
Publication Heritage
```

while relying on common NSS ERP modules for:

```text
Person
Organization
Membership
Governance
Documents
Authentication
RBAC
Audit
```

---

# 103. Final Frozen Rules Summary

```text
✓ One immutable Founder record

✓ Founder record is never deleted

✓ Founder identity is Swami Nigamananda Paramahansa Dev

✓ Founder teachings belong to the Founder domain

✓ Official NSS objectives are authoritative reference content

✓ Historical milestones are preserved

✓ Historical office bearers are separate from current Governance

✓ Publications are structured Heritage records

✓ Publication type is master-data driven

✓ Publication language is mandatory

✓ Publication language uses a master

✓ Free publications are supported

✓ Donation-based publications are supported

✓ Fixed-price publications are supported

✓ Physical and digital publication copies may coexist

✓ Digital copies use the common Document framework

✓ Multiple editions are supported

✓ Historical publication information is preserved

✓ Heritage records are auditable

✓ No unsupported universal Heritage status workflow is introduced

✓ Future Heritage entities remain outside the frozen scope

✓ No SQL schema is defined in this document
```

---

# 104. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

---

# End of Document
