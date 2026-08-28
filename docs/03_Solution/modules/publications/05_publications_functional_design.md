# NSS ERP — Publications Functional / Operational Design

**Document ID:** SOL-PUB-005  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Publications  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the functional and operational behavior of the
Publications Module.

The current Publications Module is built upon the publication foundation
already established under Founder & Heritage.

The module provides a dedicated functional experience for:

- Publication catalogue
- Publication discovery
- Publication classification
- Publication detail
- Digital Library
- Digital publication access
- Historical publication presentation

---

# 2. Functional Scope

The current functional scope is:

```text
Publications
│
├── Publication Catalogue
├── Publication Search
├── Publication Filtering
├── Publication Details
├── Publication Classification
├── Publication Language
├── Edition Information
├── Pricing Information
├── Digital Library
└── Digital Publication Access
```

---

# 3. Source Foundation

The Publications Module reuses the existing publication foundation:

```text
nss_publication
publication_type_master
publication_language_master
```

These tables already form part of the Founder & Heritage frozen scope.

The Publications Module does not duplicate them.

---

# 4. Functional Architecture

```text
Founder & Heritage
        │
        │ Existing Publication Foundation
        ▼
nss_publication
        │
        ├───────────────┐
        │               │
        ▼               ▼
Publication        Digital Library
Catalogue
        │
        ▼
Publication Detail
```

---

# 5. Publication Catalogue

The primary Publications experience is the Publication Catalogue.

The catalogue provides users with an organized view of NSS publications.

---

# 6. Catalogue Content

A publication catalogue entry may display:

* Publication title
* Publication type
* Language
* Publication date
* Edition
* Price
* ISBN
* Cover image
* Digital availability

---

# 7. Publication Types

The catalogue shall support the established publication types:

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

---

# 8. Publication Language

The catalogue shall support filtering and presentation by publication
language.

Current language values include:

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

Language is mandatory for a publication.

---

# 9. Catalogue Search

The Publications Module should provide publication search.

Search may include:

```text
Publication ID
Title
ISBN
```

Additional filtering may include:

```text
Publication Type
Language
Publication Date
Edition
Digital Availability
```

---

# 10. Publication Filtering

Users should be able to narrow the catalogue using controlled attributes.

Examples:

```text
Type = BOOK
Language = ODIA
Digitized = YES
```

or:

```text
Type = RESEARCH_PUBLICATION
Language = ENGLISH
```

---

# 11. Publication Detail

Selecting a publication shall open a detailed publication view.

The detail view may present:

```text
Title
Publication Type
Language
Publication Date
Edition
Price
Currency
Page Count
ISBN
Description
Cover
Digital Availability
```

---

# 12. Publication Identity

The detail page shall use the existing publication identity:

```text
publication_pk
publication_id
```

The UI shall not generate another identifier for the same publication.

---

# 13. Publication Cover

Where a cover document exists, the publication detail view may display it.

The cover is presentation information.

Changing the cover does not change publication identity.

---

# 14. Physical Publication

The catalogue shall support publications that exist physically without a
digital copy.

Example:

```text
Physical = YES
Digital = NO
```

Such a publication remains a valid catalogue record.

---

# 15. Digital Publication

A publication may have an associated digital document.

Example:

```text
Physical = YES
Digital = YES
```

The digital document is managed through the common Document Management
architecture.

---

# 16. Digital Library

The Digital Library is a functional component of the Publications Module.

It provides access to publications for which digital copies are available
and authorized for access.

---

# 17. Digital Library Selection

The Digital Library may identify publications using:

```text
is_digitized = TRUE
```

and the availability of an appropriate digital document.

---

# 18. Digital Library Display

A Digital Library listing may show:

* Cover
* Title
* Publication Type
* Language
* Publication Date
* Edition
* Digital availability

---

# 19. Digital Document Access

When a user selects an available digital publication, the system may provide
the associated document according to the applicable access policy.

Access shall follow:

* Authentication
* Authorization
* Document security
* Any applicable publication-access rules

---

# 20. Public Access Boundary

The current project source does not establish that every digitized
publication must be publicly downloadable.

Therefore:

```text
Digitized
    ≠
Automatically Public
```

The access policy remains subject to the common security and future
publication-access requirements.

---

# 21. Publication Pricing

The publication interface may display:

```text
FREE
DONATION BASED
FIXED PRICE
```

according to the publication's pricing information.

---

# 22. Free Publication

For a free publication, the UI may display:

```text
Free
```

rather than presenting a misleading zero-price sales transaction.

---

# 23. Donation-Based Publication

For donation-based publications, the UI may communicate that the
publication is available on a donation basis.

The Publications Module does not record the donation itself.

Actual financial transactions belong to Finance.

---

# 24. Fixed-Price Publication

For fixed-price publications, the UI may display:

```text
Price
Currency
```

The price represents publication metadata.

It does not constitute a completed sale.

---

# 25. Edition Presentation

Where `edition_no` is recorded, the edition should be displayed in the
publication detail.

Example:

```text
Edition: 2
```

---

# 26. Multiple Editions

The current model supports multiple editions.

The Publications UI should make the edition information visible where
relevant.

The current design does not require a separate edition-management screen.

---

# 27. Historical Publications

Historical publications are part of the NSS heritage record.

The catalogue should therefore support historical publications even when
they are:

* Old
* Out of print
* No longer actively distributed
* Digitized
* No longer sold

---

# 28. Historical Publication Preservation

A publication should not disappear from the historical catalogue merely
because it is no longer operationally distributed.

Historical records remain valuable for:

* Heritage
* Research
* Reference
* Digital Library
* Reporting

---

# 29. UPBS Souvenirs

UPBS Souvenirs are represented through the existing publication type:

```text
UPBS_SOUVENIR
```

They may therefore appear in the Publications catalogue.

---

# 30. UPBS Boundary

The Publications Module does not manage the UPBS event itself.

The UPBS Module remains responsible for:

```text
Registration
Accommodation
Committee Management
Delegate Cards
Prasad Patra
Reports
```

The Publications Module only manages the publication record/catalogue
representation.

---

# 31. Founder & Heritage Integration

Founder & Heritage may present Publications as part of the historical NSS
experience.

The Publications Module provides a dedicated publication-oriented
experience.

Conceptually:

```text
Founder & Heritage
        │
        └── Publications
               │
               ▼
        Publications Module
```

---

# 32. Shared Publication Identity

The same publication must remain identifiable across:

```text
Founder & Heritage
Publications Catalogue
Digital Library
Reports
```

The system shall use the existing publication identity.

---

# 33. No Duplicate Records

The following pattern is prohibited:

```text
Heritage Publication
        +
Publications Publication
```

where both represent the same publication.

The system shall maintain one authoritative publication record.

---

# 34. Publication Search Workflow

```text
User opens Publications
        │
        ▼
Publication Catalogue
        │
        ├── Search
        ├── Filter
        └── Browse
        │
        ▼
Publication Result
        │
        ▼
Publication Detail
```

---

# 35. Digital Library Workflow

```text
User opens Digital Library
        │
        ▼
Digitized Publications
        │
        ▼
Select Publication
        │
        ▼
Publication Detail
        │
        ▼
Access Digital Document
```

Access is subject to authorization and document policy.

---

# 36. Publication Detail Workflow

```text
Catalogue
    │
    ▼
Publication
    │
    ├── Metadata
    ├── Cover
    ├── Edition
    ├── Price
    ├── ISBN
    └── Digital Copy
```

---

# 37. Publication Administration

Authorized users may manage publication metadata according to the common
ERP authorization model.

Potential metadata operations include:

```text
Create
View
Update
Search
Filter
```

Actual permission assignment is owned by the common RBAC/Administration
architecture.

---

# 38. Publication Creation

Where authorized publication creation is enabled:

```text
User
  ↓
Create Publication
  ↓
Enter Publication Metadata
  ↓
Select Publication Type
  ↓
Select Language
  ↓
Enter Optional Metadata
  ↓
Save
```

The system shall validate mandatory fields before saving.

---

# 39. Mandatory Publication Data

At minimum, publication creation requires:

```text
Title
Publication Type
Language
```

Language is explicitly mandatory in the frozen publication rules.

---

# 40. Optional Publication Data

Where applicable, the following may be recorded:

```text
Publication Date
Edition
Price
Currency
Page Count
ISBN
Description
Digital Document
Cover
```

---

# 41. Publication Type Validation

The selected publication type must exist in:

```text
publication_type_master
```

The UI should present controlled values rather than arbitrary text.

---

# 42. Language Validation

The selected publication language must exist in:

```text
publication_language_master
```

---

# 43. Publication Update

Authorized users may correct or update publication metadata.

Examples:

```text
Title correction
Description correction
Cover update
Digital document update
Price update
Edition metadata correction
```

Changes shall follow the common audit standards.

---

# 44. Historical Correction

Correcting metadata shall not silently create another publication identity.

The original publication identity remains unchanged.

---

# 45. Digital Document Update

Replacing a digital document does not create a new publication identity.

The document lifecycle follows the Document Management architecture.

---

# 46. Cover Update

Replacing a publication cover does not create another publication.

---

# 47. Price Update

Changing publication price does not automatically create another publication.

Where pricing is edition-specific, the current edition model must be
followed.

---

# 48. Publication Deactivation

The current source does not establish a dedicated publication-status
workflow.

Therefore the Publications Module does not define a new publication-status
lifecycle here.

Historical publication preservation remains the priority.

---

# 49. Publication Removal From Catalogue

Removing a publication from a user-facing catalogue view must not imply
physical database deletion.

Historical publication records must remain preserved where required.

---

# 50. Document Security

Digital publication files may contain protected content.

Document access shall use the common authorization/security framework.

---

# 51. Role-Based Access

The Publications Module uses existing NSS ERP RBAC.

It does not create an independent publication permission architecture.

---

# 52. Organizational Scope

Publication administration shall respect the applicable organizational
scope of the logged-in user.

The detailed permission matrix belongs to Administration/RBAC.

---

# 53. Audit

The following activities should be auditable:

```text
Publication creation
Publication modification
Digital document association
Cover association
Metadata correction
```

---

# 54. Reporting

The Publications Module should support catalogue-oriented reporting such as:

```text
Publications by Type
Publications by Language
Publications by Year
Digitized Publications
Free Publications
Publications by Edition
```

Financial publication reports belong to Finance.

---

# 55. Publication Dashboard

A future Publications dashboard may display:

```text
Total Publications
Books
Magazines
Journals
Research Publications
UPBS Souvenirs
Digitized Publications
Languages
```

This is a functional/UI proposal, not a frozen database requirement.

---

# 56. Catalogue Statistics

Catalogue statistics should be derived from the authoritative publication
records.

No duplicate reporting tables should be created solely for catalogue
counts.

---

# 57. Search Performance

Publication search should use the existing publication data foundation.

Search optimization through indexes is a physical implementation concern
and is not defined in this document.

---

# 58. Mobile Experience

The Publications catalogue should be usable on mobile devices.

The project UI philosophy emphasizes simple, accessible, mobile-friendly
interfaces.

---

# 59. Accessibility

Publication browsing should be accessible to users with varying technical
abilities.

Avoid unnecessary technical terminology in member-facing screens.

---

# 60. User Experience

The Publications experience should feel more like a:

```text
Digital Library / Heritage Portal
```

than an:

```text
ERP Transaction Screen
```

This follows the project's existing distinction between heritage/public
presentation and administrative ERP screens.

---

# 61. Catalogue Navigation

Recommended navigation:

```text
Publications
│
├── All Publications
├── Books
├── Magazines
├── Journals
├── Research Publications
├── UPBS Souvenirs
├── Newsletters
├── Digital Library
└── Search
```

The exact navigation remains a UI implementation decision.

---

# 62. Publication Card

A catalogue card may display:

```text
[Cover]

Title
Type
Language
Edition

Digital Available
Price / Free
```

---

# 63. Publication Detail Page

Suggested structure:

```text
Cover
────────────────────────────

Title
Publication Type
Language
Publication Date
Edition

Description

ISBN
Page Count

Price / Pricing Model

[Read Digital Copy]
```

The actual UI belongs to the UI solution layer.

---

# 64. Digital Library Card

A Digital Library card may emphasize:

```text
Cover
Title
Language
Type
Edition

[Read]
```

---

# 65. Search Result

A search result should provide enough information to distinguish similar
publications:

```text
Title
Type
Language
Edition
Publication Date
```

---

# 66. Same Title, Different Language

Where publications have the same title but different language records, the
catalogue shall distinguish them through language information.

---

# 67. Same Title, Different Edition

Where multiple editions are represented, edition information should be
displayed so users can distinguish them.

---

# 68. Same Publication, Physical and Digital

The catalogue should present physical/digital availability as attributes of
the same publication.

It should not display them as unrelated publications.

---

# 69. Publication Lifecycle Boundary

The current Publications functional design does not define a complete
operational lifecycle such as:

```text
Draft
Published
Out of Print
Archived
```

because the current source does not freeze such a status model.

---

# 70. Inventory Boundary

Inventory functionality is not currently frozen.

The current module therefore does not define:

```text
Stock
Warehouse
Stock Movement
Inventory Adjustment
```

---

# 71. Distribution Boundary

Distribution functionality is not currently frozen.

The current module does not define:

```text
Distribution Order
Shipment
Delivery
Dispatch
```

---

# 72. Subscription Boundary

Subscription functionality is not currently frozen.

The current module does not define:

```text
Subscription
Subscription Issue
Subscriber
Renewal
```

---

# 73. Sales Boundary

The publication price is supported.

A complete publication sales workflow is not currently frozen.

Therefore this document does not define:

```text
Sales Order
Invoice
Payment
Return
Refund
```

---

# 74. Finance Integration Boundary

If publication sales are later implemented:

```text
Publications
      │
      ▼
Sales / Order Process
      │
      ▼
Finance
```

The Publications Module shall not create a parallel financial ledger.

---

# 75. Author Boundary

Author management is not currently frozen.

The current functional design does not define:

```text
Author Registration
Author Profile
Author Assignment
```

A future author relationship should consider reuse of the Person identity.

---

# 76. Translation Boundary

The current system supports publication language.

A full translation-management workflow is not currently frozen.

---

# 77. Operational Expansion Rule

Any expansion into:

```text
Inventory
Distribution
Subscription
Sales
Orders
Delivery
Authors
Translation
Digital Licensing
```

shall require separate requirements and solution design.

---

# 78. Functional Role Summary

| Function                            | Current Status                     |
| ----------------------------------- | ---------------------------------- |
| Publication Catalogue               | IN SCOPE                           |
| Search                              | IN SCOPE                           |
| Filtering                           | IN SCOPE                           |
| Publication Detail                  | IN SCOPE                           |
| Type Classification                 | IN SCOPE                           |
| Language Classification             | IN SCOPE                           |
| Edition Information                 | IN SCOPE                           |
| Pricing Information                 | IN SCOPE                           |
| Digital Library                     | IN SCOPE                           |
| Digital Document Access             | IN SCOPE, subject to authorization |
| Historical Publication Presentation | IN SCOPE                           |
| Inventory                           | NOT FROZEN                         |
| Distribution                        | NOT FROZEN                         |
| Subscription                        | NOT FROZEN                         |
| Orders                              | NOT FROZEN                         |
| Sales Workflow                      | NOT FROZEN                         |
| Delivery                            | NOT FROZEN                         |
| Author Management                   | NOT FROZEN                         |
| Translation Management              | NOT FROZEN                         |

---

# 79. Functional Data Flow

```text
                    nss_publication
                           │
             ┌─────────────┼──────────────┐
             │             │              │
             ▼             ▼              ▼
         Catalogue      Search        Digital Library
             │             │              │
             └─────────────┼──────────────┘
                           ▼
                   Publication Detail
                           │
                  ┌────────┴────────┐
                  │                 │
                  ▼                 ▼
               Metadata        Digital Copy
```

---

# 80. Administrative Data Flow

```text
Authorized User
      │
      ▼
Publication Administration
      │
      ├── Create
      ├── Update
      ├── Document Association
      └── Cover Association
      │
      ▼
nss_publication
```

---

# 81. Member/User Data Flow

```text
User
 │
 ▼
Publications
 │
 ├── Browse
 ├── Search
 ├── Filter
 └── Digital Library
 │
 ▼
Publication Detail
 │
 ▼
Authorized Digital Access
```

---

# 82. Publication Module Boundary

The current module is best understood as:

```text
Publication Information
+
Catalogue
+
Digital Library
```

rather than a complete commercial publishing platform.

---

# 83. Current Table Impact

This functional design introduces:

```text
New Tables = 0
```

The functionality operates over:

```text
nss_publication
publication_type_master
publication_language_master
```

---

# 84. Current Frozen Foundation

```text
                 PUBLICATIONS
                       │
                       ▼
              Existing Foundation
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   nss_publication   Type        Language
                     Master       Master
          │
          ├── Digital Document
          └── Cover Document
```

---

# 85. Future Evolution

If NSS later requires a broader Publications operation, the module may
evolve toward:

```text
Publication
     │
     ├── Catalogue
     ├── Digital Library
     ├── Inventory
     ├── Distribution
     ├── Subscription
     ├── Orders
     ├── Sales
     └── Delivery
```

Each future capability requires its own approved design.

---

# 86. Design Principle

The current Publications Module follows:

```text
Reuse Frozen Foundation
        ↓
Provide Dedicated Publication Experience
        ↓
Avoid Duplicate Identity
        ↓
Add Operational Capabilities Only When Approved
```

---

# 87. Source Traceability

This functional design is based on the project source establishing:

* Publications as a distinct module area
* Books
* Magazines
* Research Publications
* UPBS Souvenirs
* Digital Library
* Existing Heritage publication foundation

The project source specifically allows Publications to remain under Heritage
initially.

The publication foundation itself establishes:

* Publication type
* Publication language
* Publication date
* Edition
* Price
* Currency
* Page count
* ISBN
* Description
* Digital document
* Cover image
* Digitization
* Free-publication flag

and the rules for mandatory language, pricing modes, physical/digital
coexistence, and multiple editions.

---

# 88. Status

DOCUMENT STATUS:

```
DRAFT — SOURCE ALIGNED
```

VERSION:

```
1.0.0
```

---

# End of Document
