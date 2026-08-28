# NSS ERP — Founder & Heritage Lifecycle

**Document ID:** SOL-HER-003  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Founder & Heritage  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle of content and records maintained by the Founder & Heritage Module.

Unlike Membership, Attendance, Sevak, Kumari, or Kishor, Founder & Heritage does not represent a participant lifecycle.

Its lifecycle concerns:

- Creation and preservation of heritage information
- Founder reference information
- Founder teachings
- NSS objectives
- Historical milestones
- Historical office bearers
- Publications
- Publication metadata
- Digital publication availability
- Historical preservation
- Administrative maintenance

---

# 2. Lifecycle Philosophy

Founder & Heritage follows the principle:

```text
Preserve
   ↓
Structure
   ↓
Review
   ↓
Publish / Present
   ↓
Maintain
   ↓
Preserve History
```

The purpose is preservation and controlled presentation of institutional heritage.

---

# 3. Lifecycle Scope

The lifecycle covers the current frozen Founder & Heritage entities:

```text
founder_master
founder_teaching
nss_objective_master
nss_historical_milestone
nss_publication
historical_office_bearer

publication_type_master
publication_language_master
```

The current frozen foundation contains six core tables plus two publication supporting masters.

---

# 4. Founder Lifecycle

The Founder has a special lifecycle.

It is not a normal active/inactive master record.

The Founder record is:

```text
Seeded
   ↓
Immutable Reference
   ↓
Preserved Permanently
```

---

# 5. Founder Initial Creation

The Founder reference is established as part of the NSS ERP foundation.

The Founder is:

```text
Swami Nigamananda Paramahansa Dev
```

The source specifies that only one Founder record exists.

---

# 6. Founder Record State

The Founder record is considered permanently valid.

There is no normal lifecycle such as:

```text
ACTIVE
INACTIVE
ARCHIVED
```

for the Founder reference.

---

# 7. Founder Immutability

The Founder record shall not be:

* Deactivated
* Replaced
* Archived
* Deleted

The source explicitly establishes the Founder as a single immutable seeded record.

---

# 8. Founder Content Maintenance

Founder information may require controlled correction or enhancement.

Examples:

```text
Biography correction
Historical information correction
Additional approved information
Photograph update
Reference update
```

Such maintenance shall preserve auditability.

---

# 9. Founder History

Changes to Founder content shall not result in loss of historical accountability.

Where the project-wide audit/versioning framework applies, previous values shall remain traceable.

---

# 10. Founder Teaching Lifecycle

Founder teachings have a separate content lifecycle.

Conceptually:

```text
Teaching Identified
       ↓
Teaching Recorded
       ↓
Content Reviewed
       ↓
Approved Heritage Content
       ↓
Published / Presented
       ↓
Maintained
```

The exact approval workflow is not separately frozen in the current Founder & Heritage source.

Therefore this document does not prescribe specific approval statuses.

---

# 11. Teaching Creation

A Founder teaching may be recorded as structured heritage content.

The `founder_teaching` domain covers:

* Teachings
* Philosophy
* Quotes
* Principles

as identified in the frozen foundation.

---

# 12. Teaching Review

Founder teaching content should be reviewed before being presented as official NSS heritage content.

The reviewing authority/workflow is not specifically frozen in the current source.

Therefore the ERP shall not hard-code a specific office bearer as the mandatory reviewer at this stage.

---

# 13. Teaching Publication

Once approved through the applicable content-governance process, teaching content may be presented through the Heritage Portal.

The public-facing Founder & Heritage Portal includes:

```text
Founder
Biography
Philosophy
Teachings
```

---

# 14. Teaching Correction

If an approved teaching record requires correction:

```text
Existing Record
      ↓
Controlled Correction
      ↓
Updated Record
```

The correction shall be auditable.

---

# 15. Teaching Historical Preservation

Corrections shall not erase the fact that an earlier version existed where project-wide history/versioning standards require preservation.

---

# 16. NSS Objective Lifecycle

Official NSS objectives are institutional reference content.

Their conceptual lifecycle is:

```text
Authoritative Source
       ↓
Objective Recorded
       ↓
Reviewed
       ↓
Official Reference
       ↓
Published / Presented
       ↓
Preserved
```

---

# 17. Objective Authority

The `nss_objective_master` records official NSS objectives.

The objectives shall originate from authoritative NSS sources.

The Heritage module shall not invent organizational objectives.

---

# 18. Objective Changes

If authoritative NSS objectives change through an approved organizational process, the ERP content shall be updated accordingly.

The historical record of the previous objective shall remain traceable where required by project history standards.

---

# 19. Objective Deactivation

The current source does not define a detailed objective status lifecycle.

Therefore no additional objective status values are frozen by this document.

---

# 20. Historical Milestone Lifecycle

Historical milestones follow:

```text
Historical Event Identified
          ↓
Historical Information Recorded
          ↓
Source / Evidence Recorded
          ↓
Reviewed
          ↓
Heritage Record
          ↓
Published / Presented
          ↓
Preserved
```

---

# 21. Milestone Creation

A historical milestone may be entered when an NSS historical event is identified and sufficiently documented.

Examples from the existing foundation include:

```text
1934 — Establishment of NSS
Formation of Advisory Board
Major Sammilani milestones
New Sakha formation
```

---

# 22. Milestone Source Reference

Where available, historical milestone records should retain their source/reference information.

The frozen logical design includes:

```text
source_reference
```

for historical milestones.

---

# 23. Milestone Review

Historical information should be reviewed before being presented as authoritative Heritage content.

The exact reviewing authority is not frozen in the current source.

---

# 24. Milestone Publication

Reviewed historical milestones may be presented through:

```text
NSS History
Milestones
```

on the Heritage Portal.

---

# 25. Milestone Correction

Historical records may be corrected when reliable evidence establishes that existing information is inaccurate.

Corrections shall be auditable.

---

# 26. Milestone Deletion

Historical milestones shall not be casually deleted.

The project principle is preservation of historical information.

If a record is found to be erroneous, correction or controlled retirement is preferable to destroying historical traceability.

---

# 27. Historical Office Bearer Lifecycle

Historical office-bearer records follow a preservation-oriented lifecycle:

```text
Historical Office Bearer Identified
            ↓
Historical Record Created
            ↓
Historical Information Reviewed
            ↓
Published / Preserved
            ↓
Historical Reference
```

---

# 28. Historical Office Bearer Record

The frozen design supports historical records containing information such as:

```text
Person Name
Position Name
Organization Name
From Date
To Date
Remarks
```

---

# 29. Historical Office Bearer Is Not Current Governance

The lifecycle of a historical office bearer shall not be confused with the lifecycle of a current office assignment.

```text
Historical Office Bearer
        ≠
Current Office Bearer
```

Current Governance remains controlled by the Governance module.

---

# 30. Historical Term Completion

When a historical office-bearer's term ends, the record becomes historical context.

The historical record remains preserved.

It is not deleted because the office bearer is no longer serving.

---

# 31. Historical Office Bearer Correction

Historical information may be corrected when reliable evidence requires correction.

Corrections must remain auditable.

---

# 32. Publication Lifecycle

Publications have the most structured lifecycle within Founder & Heritage.

Conceptually:

```text
Publication Identified
        ↓
Publication Record Created
        ↓
Metadata Recorded
        ↓
Classified
        ↓
Digital / Physical Information Recorded
        ↓
Publication Available
        ↓
Maintained
        ↓
Historical Record
```

The current source defines publication metadata and business rules but does not freeze a separate publication workflow-state enumeration.

---

# 33. Publication Identification

A publication record begins when an NSS publication is identified for inclusion in the Publication Library.

The record receives its publication identity.

---

# 34. Publication Metadata Creation

The publication record may contain:

```text
Title
Publication Type
Publication Date
Edition Number
Language
Price
Currency
Page Count
ISBN
Description
```

The frozen publication design includes these metadata fields.

---

# 35. Publication Classification

Every publication is classified using:

```text
publication_type_master
```

and:

```text
publication_language_master
```

Language is mandatory.

---

# 36. Publication Type Assignment

A publication may be classified as:

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

These are the frozen publication type classifications.

---

# 37. Publication Language Assignment

The frozen language classifications include:

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

# 38. Publication Physical Availability

A publication may exist as a physical publication.

Physical publication information remains part of the structured publication record.

---

# 39. Publication Digital Availability

A publication may have a digital copy.

The publication design supports:

```text
document_pk
```

for the digital copy.

---

# 40. Physical + Digital Coexistence

Physical and digital availability are independent.

Therefore:

```text
Physical + Digital
Physical Only
Digital Only
```

are conceptually possible depending on the actual publication record.

The frozen source explicitly states that digital and physical copies may coexist.

---

# 41. Digitization Lifecycle

A physical publication may later become digitized.

Conceptually:

```text
Physical Publication
        ↓
Digital Copy Prepared
        ↓
Document Associated
        ↓
is_digitized = TRUE
```

The original publication identity remains unchanged.

---

# 42. No New Publication Identity During Digitization

Digitizing a publication shall not create a second publication merely because a digital copy has been created.

```text
Same Publication
       +
Digital Copy
```

---

# 43. Cover Image

A publication may have a cover image document reference.

The frozen publication design supports:

```text
cover_photo_document_pk
```

The common Document framework remains responsible for the underlying document.

---

# 44. Publication Pricing

A publication may be:

```text
Free
Donation Based
Fixed Price
```

This classification is part of the frozen publication framework.

---

# 45. Free Publication

A free publication may be made available without a fixed sale price.

The publication record remains part of the Publication Library.

---

# 46. Donation-Based Publication

A publication may be available on a donation basis.

The publication record remains distinct from any future donation transaction.

---

# 47. Fixed-Price Publication

A publication may have a fixed recorded price and currency.

The current source uses INR as the default currency context.

---

# 48. Publication Edition Lifecycle

Multiple editions of the same publication are supported.

Conceptually:

```text
Publication
   ↓
Edition 1
   ↓
Edition 2
   ↓
Edition 3
```

Edition information is retained in the publication framework.

The source does not establish a separate publication-edition entity in the current frozen scope.

---

# 49. Publication Update

Publication metadata may be corrected or updated where authorized.

Examples:

```text
Incorrect page count
Incorrect ISBN
Corrected description
Corrected publication date
Updated digital copy
Updated cover image
```

Updates shall remain auditable.

---

# 50. Publication Historical Preservation

A publication record shall not be destroyed simply because:

* It is old
* It is out of print
* A newer edition exists
* A digital copy replaces physical access
* It is no longer actively distributed

Historical publication information remains part of NSS heritage.

---

# 51. Publication Edition Preservation

When a newer edition is recorded, earlier edition information shall remain historically traceable.

Example:

```text
Publication
 ├── Edition 1
 ├── Edition 2
 └── Edition 3
```

The earlier edition shall not be silently overwritten by the newer edition.

---

# 52. Publication Digital Replacement

Replacing a digital copy shall not delete the publication record.

Conceptually:

```text
Publication
   ↓
Old Digital Copy
   ↓
New Digital Copy
```

Where project-wide document history supports versioning, document history shall be preserved there.

---

# 53. Publication Availability Changes

Publication availability may change over time.

Examples:

```text
Physical Available
Physical Unavailable
Digital Available
Digital Unavailable
```

The source does not define a formal availability-state master.

Therefore this document does not invent one.

---

# 54. Public Heritage Presentation Lifecycle

Approved Heritage content follows:

```text
Heritage Record
      ↓
Authorized for Presentation
      ↓
Public Heritage Portal
      ↓
Maintained
```

The Portal includes:

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

# 55. Public Content Removal

Removing content from a public presentation does not necessarily mean deleting the underlying historical record.

The system should distinguish:

```text
Record Preservation
        from
Public Presentation
```

---

# 56. Administrative Lifecycle

Authorized administrators may maintain Heritage records according to common RBAC.

Administrative actions may include:

```text
Create
Review
Correct
Update
Associate Document
Classify
Publish / Present
```

Exact permissions belong to the common Administration/RBAC module.

---

# 57. RBAC Boundary

Founder & Heritage shall not create a separate authentication or authorization system.

It uses common:

```text
Authentication
RBAC
Organizational Scope
Audit
```

---

# 58. Audit Lifecycle

Important Heritage changes shall remain auditable.

Examples:

```text
Founder content correction
Teaching update
Objective update
Milestone correction
Publication update
Publication digitization
Historical office-bearer correction
```

---

# 59. Historical Preservation Rule

The core lifecycle principle is:

```text
Never destroy historical context merely because current information has changed.
```

This applies particularly to:

```text
Historical Milestones
Historical Office Bearers
Publications
Founder Content
```

---

# 60. No Membership-Style Lifecycle

Founder & Heritage does not use:

```text
ACTIVE
INACTIVE
PROBATIONARY
REGULAR
SUSPENDED
RENEWAL
TRANSFER
```

as a generic module lifecycle.

Those are operational concepts belonging to other NSS modules.

---

# 61. No Participant Lifecycle

Founder & Heritage does not have:

```text
Applicant
Probationary
Active
Inactive
Transferred
Exited
```

participant states.

The module is primarily a heritage/content repository.

---

# 62. No Automatic Lifecycle Transitions

The current source does not define automatic transitions for Heritage content.

Therefore the system shall not invent scheduled automatic publication, archival, or deactivation rules.

---

# 63. No Automatic Expiry

Founder teachings, objectives, historical milestones, historical office-bearers, and historical publications do not automatically expire.

---

# 64. Founder Final State

The Founder reference ultimately remains:

```text
IMMUTABLE
```

It does not enter an inactive or archived state.

---

# 65. Founder Teaching Final State

A Founder teaching remains a historical/knowledge record.

If corrected, its history shall remain traceable according to project-wide audit/version standards.

---

# 66. Objective Final State

An official NSS objective remains an institutional reference record.

Changes must originate from authoritative organizational decisions.

---

# 67. Historical Milestone Final State

A historical milestone remains part of the institutional historical record.

It does not expire.

---

# 68. Historical Office Bearer Final State

A historical office-bearer record remains preserved after the person's term ends.

The end of the term does not delete the historical record.

---

# 69. Publication Final State

A publication remains part of the Publication Library even when:

```text
Out of Print
Old Edition
Physical Copy Unavailable
Digital Copy Unavailable
```

where applicable.

---

# 70. Lifecycle Diagram

```text
                  FOUNDER & HERITAGE
                         |
        ┌────────────────┼─────────────────┐
        |                |                 |
        ▼                ▼                 ▼
     FOUNDER          CONTENT          PUBLICATION
        |                |                 |
        |                ├── Teachings     ├── Metadata
        |                ├── Objectives    ├── Classification
        |                └── Milestones    ├── Digital Copy
        |                                  └── Editions
        |                                      |
        ▼                                      ▼
   IMMUTABLE                              PRESERVED
        |                                      |
        └──────────────────┬───────────────────┘
                           ▼
                  HERITAGE PORTAL
```

---

# 71. Content Lifecycle Diagram

```text
Authoritative Source
        ↓
Record Created
        ↓
Content Reviewed
        ↓
Approved / Accepted
        ↓
Heritage Presentation
        ↓
Maintenance
        ↓
Historical Preservation
```

Where the current source does not define a formal approval state, these stages describe the conceptual lifecycle rather than mandatory database status values.

---

# 72. Publication Lifecycle Diagram

```text
Publication Identified
        ↓
Metadata Recorded
        ↓
Type + Language Assigned
        ↓
Physical / Digital Information Recorded
        ↓
Publication Library
        ↓
Digital Copy Added / Updated
        ↓
Edition Updates
        ↓
Historical Preservation
```

---

# 73. Historical Lifecycle Diagram

```text
Historical Information
        ↓
Source Identified
        ↓
Historical Record Created
        ↓
Reviewed
        ↓
Heritage Reference
        ↓
Public Presentation
        ↓
Permanent Historical Preservation
```

---

# 74. Document Integration Lifecycle

For digital Heritage artifacts:

```text
Heritage Record
      ↓
Document Identified
      ↓
Document Associated
      ↓
Available Through Authorized Interface
      ↓
Document Maintained Through Common Document Framework
```

The Heritage module does not create an independent document-management lifecycle.

---

# 75. Future Enhancement Boundary

The following are not part of the current frozen lifecycle:

```text
founder_quote
heritage_document
heritage_photo_gallery
publication_author
historical_event_participant
```

They have been identified as future enhancements rather than current frozen entities.

---

# 76. Future Lifecycle Rule

If future Heritage entities are approved, each shall receive its own documented lifecycle before implementation.

No future entity shall be silently introduced into the current lifecycle.

---

# 77. Cross-Module Lifecycle Dependencies

Founder & Heritage may interact with:

```text
Document Management
Organization
Person
Governance
Master Data
Authentication
RBAC
Audit
```

Each dependency remains owned by its respective module.

---

# 78. Governance Boundary

Historical office-bearer records preserve history.

Current governance records remain authoritative for current positions.

Therefore:

```text
Heritage
   ↓
Historical Reference

Governance
   ↓
Current Authority
```

---

# 79. Publication Boundary

Founder & Heritage owns the structured NSS publication catalogue.

Document Management owns digital file handling.

Therefore:

```text
Publication Metadata
        ↓
Founder & Heritage

Digital File
        ↓
Document Management
```

---

# 80. Lifecycle Integrity

The Founder & Heritage lifecycle shall preserve:

```text
Identity
Authenticity
Historical Context
Source Traceability
Auditability
Publication Metadata
Digital Association
```

---

# 81. Final Lifecycle Principles

The module shall follow these principles:

```text
1. Founder is immutable.

2. Founder content is preserved.

3. Official objectives originate from authoritative sources.

4. Historical milestones are preserved.

5. Historical office-bearers remain historical records after their terms end.

6. Publications remain historically traceable.

7. Multiple publication editions are supported.

8. Physical and digital publication copies may coexist.

9. Publication language is mandatory.

10. Publication type is master-data driven.

11. Digital documents use common Document Management.

12. Public presentation is separate from record preservation.

13. Administrative changes are auditable.

14. No unsupported lifecycle states are introduced.

15. Future Heritage entities require separate approval.
```

---

# 82. Lifecycle Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

---

# End of Document
