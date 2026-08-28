# NSS ERP — Founder & Heritage Module Overview

**Document ID:** SOL-HER-001  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Founder & Heritage  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Founder & Heritage Module preserves, organizes, and presents the institutional, spiritual, historical, and documentary heritage of Nilachala Saraswata Sangha.

The module provides a structured repository for:

- Founder information
- Founder philosophy and teachings
- Official NSS objectives
- Historical milestones
- NSS publications
- Historical office bearers

The module serves both ERP users and the public-facing Heritage Portal.

---

# 2. Module Position

Founder & Heritage is a core NSS ERP module.

It is primarily a:

```text
Knowledge
+
Heritage
+
Historical Reference
+
Publication
```

domain rather than an operational membership module.

---

# 3. Core Heritage Scope

The currently frozen Founder & Heritage foundation contains six core domain tables:

```text
founder_master
founder_teaching
nss_objective_master
nss_historical_milestone
nss_publication
historical_office_bearer
```

The current frozen foundation identifies these six tables as the core Heritage scope.

---

# 4. Supporting Publication Masters

The publication framework additionally contains two supporting masters:

```text
publication_type_master
publication_language_master
```

Therefore the current documented scope is:

```text
Core Heritage Tables       = 6
Supporting Masters         = 2
Total Current Scope       = 8
```

The publication framework is frozen at this scope.

---

# 5. Founder

The Founder section preserves the authoritative reference information about:

```text
Swami Nigamananda Paramahansa Dev
```

The Founder is represented through the dedicated `founder_master` reference record.

---

# 6. Founder Master

`founder_master` is a special reference table.

The frozen design specifies:

```text
Exactly one founder record
Immutable reference
No is_active field
No display_order field
Never deleted
```

The source identifies the Founder as Swami Nigamananda Paramahansa Dev.

---

# 7. Founder Biography

The Heritage Portal shall provide a dedicated Founder Biography section.

The biography is treated as heritage/reference content rather than as an operational Person record.

The Founder Master therefore does not replace the common Person module.

---

# 8. Founder Philosophy

The module shall preserve the Founder-related philosophical material required for the Heritage Portal.

This content forms part of the institutional knowledge base.

---

# 9. Founder Teachings

Founder teachings are represented through:

```text
founder_teaching
```

The table is intended to contain:

* Teachings
* Philosophy
* Quotes
* Principles

as identified in the frozen foundation.

---

# 10. NSS Objectives

Official NSS objectives are represented through:

```text
nss_objective_master
```

The module preserves the official organizational objectives as authoritative reference content.

---

# 11. Historical Milestones

Institutional history is represented through:

```text
nss_historical_milestone
```

The table records important NSS historical events and milestones.

---

# 12. Historical Office Bearers

Historical leadership information is represented through:

```text
historical_office_bearer
```

This preserves historical office bearers such as:

* Presidents
* Parichalaks
* Secretaries
* Other historically relevant office bearers

The frozen foundation explicitly includes this table.

---

# 13. Publications

The module provides the central NSS publication repository through:

```text
nss_publication
```

The publication framework covers:

* Books
* Magazines
* Journals
* Newsletters
* Annual Reports
* UPBS Souvenirs
* Research Publications
* Pamphlets
* Booklets
* Other approved publication types

The current publication type master includes these classifications.

---

# 14. Publication Languages

The publication framework supports language classification.

The frozen master includes:

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

# 15. Publication Metadata

The frozen publication design supports metadata including:

* Title
* Publication type
* Publication date
* Edition number
* Language
* Price
* Currency
* Page count
* ISBN
* Description
* Digital copy
* Cover image
* Digitization status
* Free-publication status

The publication framework is frozen at this level.

---

# 16. Digital Publications

A publication may have a digital copy.

The frozen publication model supports:

```text
document_pk
```

for the digital document reference.

Digital and physical publications may coexist.

---

# 17. Physical Publications

The system shall support publication records representing physical editions.

Physical and digital availability are independent concepts.

---

# 18. Free and Paid Publications

The publication framework supports:

```text
Free
Donation Based
Fixed Price
```

publication models.

The publication pricing rules are part of the frozen publication framework.

---

# 19. Multiple Editions

Multiple editions of the same publication are supported.

Edition information is therefore retained as part of the publication record.

---

# 20. Heritage Portal

The Founder & Heritage module provides the content for the public-facing Heritage Portal.

The frozen portal structure includes:

```text
Founder

Biography

Philosophy

Teachings

Milestones

Publications

Historical Office Bearers
```

---

# 21. Founder Portal

The Founder section shall provide access to:

```text
Founder Identity
Biography
Philosophy
Teachings
Historical Context
```

The Founder Portal is primarily informational and heritage-oriented.

---

# 22. Teachings Portal

The Teachings section shall present structured Founder teachings from the `founder_teaching` domain.

The content may be organized for:

* Reading
* Search
* Reference
* Educational use

The exact presentation hierarchy shall be defined in the UI documentation.

---

# 23. Objectives Portal

The official NSS objectives may be presented as institutional reference content.

The ERP shall distinguish official objectives from general explanatory content.

---

# 24. Historical Milestones Portal

Historical milestones shall be presented chronologically or through another approved historical navigation mechanism.

The underlying source of truth remains:

```text
nss_historical_milestone
```

---

# 25. Historical Office Bearers Portal

The Heritage Portal shall provide access to historical office-bearer information.

This provides institutional continuity and preserves leadership history.

---

# 26. Publication Library

The Publication Library provides searchable access to NSS publications.

The portal may organize publications by:

```text
Type
Language
Year
Edition
Availability
```

The publication type and language masters provide the primary classification framework.

---

# 27. Publication Search

The publication repository should support searching by relevant publication metadata.

Potential search dimensions include:

```text
Title
Publication Type
Language
Publication Date
Edition
ISBN
```

Exact search behavior belongs to the later UI/API documentation.

---

# 28. Publication Download

Where a digital copy exists and access is permitted, users may access the digital publication through the document reference.

Access control remains governed by the common security framework.

---

# 29. Heritage and Person Boundary

The Founder & Heritage module shall not duplicate the common Person module.

Founder heritage information is historical/reference content.

The common Person module remains authoritative for ordinary person identity.

---

# 30. Heritage and Membership Boundary

Historical office-bearer records do not replace current Governance or Membership records.

The distinction is:

```text
Historical Office Bearer
        ≠
Current Office Bearer
```

Current governance remains governed by the Governance module.

---

# 31. Heritage and Governance Boundary

The Heritage module preserves historical office-bearer information.

The Governance module remains authoritative for:

* Current governing bodies
* Current positions
* Current assignments
* Elections
* Terms
* Vacancies

---

# 32. Heritage and Publications Boundary

The Founder & Heritage module owns the NSS heritage publication catalogue.

Publication-specific operational processes, where applicable, shall use the appropriate common document and administration infrastructure.

---

# 33. Common Document Integration

Digital publication files and related documents shall use the common Document Management framework.

The Heritage module stores the appropriate reference rather than creating a separate document-storage architecture.

---

# 34. Audit

Heritage and publication records shall follow the common audit standards.

Important administrative changes shall remain traceable.

---

# 35. Historical Preservation

Historical records shall be preserved.

The module follows the project-wide principle:

```text
History Never Deleted
```

Historical information shall not be physically removed merely because it is no longer current.

---

# 36. Immutable Founder Reference

The Founder Master is a special immutable reference.

The frozen design specifies:

```text
One Founder
No deletion
No active/inactive lifecycle
No display ordering
```

---

# 37. Master-Data Driven Design

The module uses master-data-driven classification where appropriate.

Current examples:

```text
publication_type_master
publication_language_master
```

This avoids hard-coding publication classifications throughout the application.

---

# 38. Current Scope

The current Founder & Heritage module scope is:

```text
Founder
├── Founder Master
└── Founder Teachings

NSS Heritage
├── NSS Objectives
└── Historical Milestones

Publications
├── NSS Publications
├── Publication Type Master
└── Publication Language Master

History
└── Historical Office Bearers
```

---

# 39. Core Table Summary

```text
1. founder_master
2. founder_teaching
3. nss_objective_master
4. nss_historical_milestone
5. nss_publication
6. historical_office_bearer
```

---

# 40. Supporting Master Summary

```text
1. publication_type_master
2. publication_language_master
```

---

# 41. Current Module Count

```text
Core Tables             = 6
Supporting Masters      = 2
Current Scope           = 8
```

This is the current frozen Founder & Heritage foundation.

---

# 42. Future Expansion Boundary

The source material identifies additional Heritage capabilities as recommendations/future enhancements rather than part of the current frozen foundation.

Examples include:

```text
founder_quote
heritage_document
heritage_photo_gallery
publication_author
historical_event_participant
```

These shall not be treated as current frozen tables.

---

# 43. No Premature Expansion

The current implementation shall not add future Heritage tables merely because they have been recommended.

Each future capability requires its own approved business/design decision before becoming part of the frozen solution.

---

# 44. Public vs Administrative Content

The module serves two broad audiences:

```text
Public / Members
        ↓
Heritage Portal

Authorized Administrators
        ↓
Heritage Management
```

Public presentation and administrative editing are separate concerns.

---

# 45. Administrative Management

Authorized users may manage:

* Founder teaching content
* NSS objectives
* Historical milestones
* Publications
* Historical office-bearer records

subject to RBAC and audit.

The exact permission matrix belongs to the common Administration/RBAC module.

---

# 46. Founder Content Governance

Founder-related content is authoritative heritage content.

Changes to such content should be subject to appropriate administrative control and audit.

The module shall not treat Founder content like ordinary user-generated content.

---

# 47. Historical Content Governance

Historical milestones and office-bearer records should be managed as institutional historical records.

Corrections must preserve auditability and historical integrity.

---

# 48. Publication Governance

Publication metadata shall be maintained as structured information rather than relying solely on uploaded files.

A digital document is an associated artifact, not the complete publication record.

---

# 49. Publication Language Rule

Language is mandatory for a publication record.

This is explicitly frozen in the publication framework.

---

# 50. Publication Availability Rule

A publication may simultaneously have:

```text
Physical Copy
+
Digital Copy
```

The existence of a digital copy does not imply that a physical edition does not exist.

---

# 51. Publication Pricing Rule

A publication may be:

```text
Free
Donation Based
Fixed Price
```

The publication framework supports all three.

---

# 52. Publication Edition Rule

Multiple editions of the same publication shall be supported.

Edition information must therefore not be treated as a single immutable publication identity.

---

# 53. Heritage Search

The future Heritage Portal should support discovery across:

```text
Founder
Teachings
Objectives
Milestones
Publications
Historical Office Bearers
```

The exact search architecture will be defined separately.

---

# 54. Heritage Reporting

Authorized users should be able to retrieve structured information for:

```text
Historical Milestones
Historical Office Bearers
Publications
Founder Teachings
NSS Objectives
```

---

# 55. No Operational Membership Logic

Founder & Heritage shall not implement:

```text
Membership Approval
Membership Renewal
Membership Transfer
Attendance Enforcement
```

Those belong to their respective modules.

---

# 56. No Operational Governance Logic

Historical office-bearer records do not implement current governance workflows.

Current Governance remains separate.

---

# 57. No Duplicate Publication Storage

The Heritage module shall not create an independent file-storage system.

Digital documents shall use the common Document Management framework.

---

# 58. No Duplicate Location Master

If historical events or publications require location information, the common Location framework shall be used where applicable.

---

# 59. UI Position

The Founder & Heritage Portal is intended to feel more like a heritage/public-information portal than a conventional ERP administration screen.

The existing UI source explicitly describes the Heritage Portal as a modern website rather than a standard admin page.

---

# 60. UI Sections

The initial Heritage UI sections are:

```text
Founder
Biography
Philosophy
Teachings
Milestones
Publications
Historical Office Bearers
```

---

# 61. Mobile Accessibility

The broader NSS UI philosophy requires:

```text
Simple
Traditional
Spiritual
Mobile Friendly
Accessible to Elder Members
Minimal Training Required
```

The Heritage Portal should follow the same overall philosophy.

---

# 62. Security

Heritage administrative functions shall use the common:

```text
Authentication
RBAC
Organizational Scope
Audit
```

framework.

Public heritage content may have a different read-access policy from administrative editing.

---

# 63. Documentation Hierarchy

The Founder & Heritage documentation set will follow:

```text
01 Module Overview
02 ERD
03 Lifecycle
04 Business Rules
05 Table Design
```

Each document has a distinct purpose.

---

# 64. Database-First Alignment

The logical documentation sequence remains:

```text
Source
   ↓
Business Rules
   ↓
Module Overview
   ↓
ERD
   ↓
Lifecycle
   ↓
Table Design
   ↓
Physical Database
```

No SQL schema is produced as part of this documentation stage.

---

# 65. Source Authority

The Founder & Heritage module follows the project's source hierarchy.

Where authoritative NSS source material exists, it takes precedence over generic assumptions.

Where the current source does not define a rule, the documentation shall identify the gap rather than inventing a rule.

---

# 66. Current Frozen Foundation

The current Founder & Heritage foundation is considered sufficiently defined for Solution documentation.

The frozen scope is:

```text
Founder
Teachings
NSS Objectives
Historical Milestones
Publications
Historical Office Bearers
Publication Types
Publication Languages
```

---

# 67. Module Objective

The ultimate objective is to ensure that NSS institutional heritage is:

```text
Preserved
Structured
Searchable
Auditable
Accessible
Historically Traceable
```

while maintaining the distinction between historical/reference information and current operational ERP data.

---

# 68. Final Module Architecture

```text
                    FOUNDER & HERITAGE
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
       FOUNDER          NSS HERITAGE    PUBLICATIONS
          │                │                │
          ├── Master       ├── Objectives  ├── Publication
          └── Teachings    └── Milestones  ├── Type Master
                                            └── Language Master
          │
          ▼
   HISTORICAL OFFICE
       BEARERS
```

---

# 69. Final Scope Boundary

Current:

```text
6 Core Tables
+
2 Supporting Masters
```

Future enhancements are not part of the current frozen scope.

---

# 70. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

---

# End of Document
