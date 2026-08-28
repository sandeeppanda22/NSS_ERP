# NSS ERP — Publications Module Overview

**Document ID:** SOL-PUB-001  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Publications  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Publications Module provides the NSS ERP with a structured way to
catalogue, manage, discover, and present NSS publications.

The initial Publications scope is based on the publication capabilities
already established within the Founder & Heritage Module.

The Publications Module shall therefore build upon the existing publication
foundation rather than duplicate it.

---

# 2. Current Scope

The currently identified publication scope includes:

- Books
- Magazines
- Journals
- Research Publications
- Newsletters
- UPBS Souvenirs
- Pamphlets
- Booklets
- Other NSS publications
- Digital publications

---

# 3. Existing Heritage Publication Foundation

The Founder & Heritage Module already contains the frozen publication
foundation:

    nss_publication
    publication_type_master
    publication_language_master

These tables are part of the frozen Founder & Heritage scope.

Therefore the Publications Module shall not create duplicate versions of
these tables.

---

# 4. Heritage Boundary

The Founder & Heritage Module remains the authoritative owner of the
historical/heritage publication foundation.

Its publication records support the preservation and presentation of NSS
publication history.

The frozen `nss_publication` design already supports:

- Publication title
- Publication type
- Publication date
- Edition
- Language
- Price
- Currency
- Page count
- ISBN
- Description
- Digital copy
- Cover image
- Digitization status
- Free-publication status

---

# 5. Publications Module Relationship

The Publications Module is an operational/presentation layer around the
existing publication foundation.

Conceptually:

    Founder & Heritage
            │
            │ Publication Foundation
            ▼
      nss_publication
            │
            ▼
       Publications
          Module

The module shall reuse the established publication identity.

---

# 6. No Duplicate Publication Master

The Publications Module shall not create another:

    publication

table merely to duplicate:

    nss_publication

The existing publication identity shall remain authoritative unless an
approved future design explicitly changes module ownership.

---

# 7. Publication Type

Publication classification is controlled through:

    publication_type_master

The currently established publication types include:

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

These values originate from the existing Heritage publication design.

---

# 8. Publication Language

Publication language is controlled through:

    publication_language_master

The currently established language values include:

    ODIA
    ENGLISH
    HINDI
    BENGALI
    ASSAMESE
    TELUGU
    TAMIL
    OTHER

Language is mandatory for a publication.

---

# 9. Multilingual Publications

The existing publication design supports multilingual NSS publications.

The same publication concept may exist in different languages through
appropriate publication records/editions.

The exact future translation/version relationship is not separately frozen
by this document.

---

# 10. Publication Editions

The existing publication foundation supports multiple editions.

An edition may have:

- Edition number
- Publication date
- Language
- Price
- Other publication-specific metadata

The current source does not establish a separate operational edition table.

Therefore no new edition table is introduced here.

---

# 11. Publication Pricing

The existing publication design supports:

    Free
    Donation Based
    Fixed Price

The publication foundation includes pricing information and a
free-publication indicator.

---

# 12. Currency

The existing design includes:

    currency_code

with INR as the default currency.

The Publications Module shall reuse this established design.

---

# 13. Physical and Digital Publications

The publication foundation supports coexistence of:

    Physical Publication
    Digital Publication

A publication may have a digital copy while also having a physical edition.

---

# 14. Digitization

The publication foundation includes:

    is_digitized

This indicates whether a digital version is available.

The associated digital copy may be represented through the existing document
framework.

---

# 15. Cover Image

The existing publication design supports:

    cover_photo_document_pk

for the publication cover image.

The Publications Module shall reuse the established document architecture
rather than introducing another image-storage mechanism.

---

# 16. Digital Copy

The existing publication design supports:

    document_pk

for the digital publication copy.

The actual document storage mechanism belongs to the common Document
Management architecture.

---

# 17. ISBN

The publication foundation supports:

    isbn_number

where applicable.

ISBN is optional because not every NSS publication necessarily has an ISBN.

---

# 18. Page Count

The publication foundation supports:

    page_count

for publications where page count is applicable.

---

# 19. Publication Description

A publication may contain a descriptive summary.

The description is informational metadata and does not replace the
publication identity.

---

# 20. Publication Catalogue

The Publications Module shall provide a structured catalogue experience.

The catalogue may allow users to discover publications using attributes
such as:

- Title
- Type
- Language
- Publication date
- Edition
- ISBN
- Digitization availability

---

# 21. Search

Publication search should support appropriate publication metadata.

Possible search dimensions include:

    Title
    Publication ID
    Type
    Language
    ISBN
    Publication Date

Search behavior shall follow the common NSS ERP search and authorization
standards.

---

# 22. Digital Library

The existing project module division identifies:

    Digital Library

as part of the Publications scope.

The digital-library experience shall expose publications that have an
available digital copy, subject to authorization and document-access rules.

---

# 23. Digital Access

Digital publication access shall respect:

- Document security
- User authorization
- Publication availability
- Any future publication-access rules

This document does not establish public-vs-member access rules because the
current source does not freeze such a policy.

---

# 24. Publication Presentation

The Publications Module may provide:

- Publication catalogue
- Publication detail page
- Publication search
- Language filtering
- Type filtering
- Digital availability filtering
- Digital document access where permitted

---

# 25. Heritage Integration

The Publications Module should integrate naturally with Founder & Heritage.

For example:

    Founder & Heritage
          │
          ├── Founder
          ├── Teachings
          ├── Historical Milestones
          └── Publications
                    │
                    ▼
             Publications Module

The same publication identity should be reused.

---

# 26. Founder & Heritage Does Not Lose Publication Data

Moving publication functionality into a dedicated UI/module does not mean
moving or duplicating the underlying frozen Heritage publication data.

The existing publication foundation remains preserved.

---

# 27. Publication History

Historical NSS publications are important heritage records.

The Publications Module shall preserve their historical identity and
metadata.

Publication records shall not be casually deleted because they are no
longer actively distributed.

---

# 28. Publication Status

The current source does not establish a separate frozen publication-status
master.

Therefore this document does not introduce:

    publication_status_master

unless a later approved requirement establishes the need.

---

# 29. Inventory — Current Scope

The current project source does **not** establish a frozen publication
inventory/stock-management model.

Therefore the Publications Module does not currently define:

- Stock quantity
- Warehouse
- Store location
- Stock movement
- Purchase order
- Inventory adjustment

These remain outside the current frozen scope.

---

# 30. Distribution — Current Scope

The current source does not establish a frozen operational publication
distribution system.

Therefore no distribution tables are introduced at this stage.

Future distribution functionality may be added through an approved
requirement/design change.

---

# 31. Sales — Current Scope

The existing source establishes publication pricing and publication income
concepts, but does not establish a complete publication-sales workflow.

Therefore the current Publications Module does not freeze:

- Customer orders
- Sales invoices
- Payment collection
- Shipment
- Returns

as Publications tables.

---

# 32. Subscription — Current Scope

The current source does not establish a frozen publication subscription
system.

Therefore the module does not currently define:

    subscription

or:

    subscription_issue

tables.

---

# 33. Order Management — Current Scope

The current source does not establish publication order management.

Therefore the module does not currently define:

    publication_order
    publication_order_item

as frozen tables.

---

# 34. Distribution and Subscription Are Future Extensions

If NSS later requires operational publication management, the following may
be considered through formal solution design:

- Inventory
- Distribution
- Subscription
- Orders
- Sales
- Delivery
- Digital access management

None of these are frozen by this document.

---

# 35. Publication Income

The project source identifies proceeds from the sale of books, journals,
and other Kendra Sangha publications as a source of Kendra Sangha funds.

Publication income is therefore related to the Finance domain.

The Publications Module shall not independently create a parallel financial
ledger.

---

# 36. Finance Boundary

The distinction is:

    Publications
        =
    Publication Catalogue / Publication Operations

    Finance
        =
    Financial Transactions / Income

Publication price metadata does not constitute a financial transaction.

---

# 37. Document Management Boundary

The Publications Module may reference digital publication documents.

Document storage and document security remain under the common document
architecture.

---

# 38. Author Boundary

The current frozen publication foundation does not contain a publication
author table.

The earlier Heritage review identified:

    publication_author

as a possible future enhancement.

It is not introduced as a frozen Publications table by this document.

---

# 39. Publication Categories

Publication classification shall use the established:

    publication_type_master

rather than uncontrolled free-text categories.

---

# 40. Publication Languages

Publication language shall use:

    publication_language_master

rather than uncontrolled language text.

---

# 41. Publication Identity

Each publication record retains its established:

    publication_pk
    publication_id

The Publications Module shall use the existing business identity.

---

# 42. Publication ID

`publication_id` is the human-readable business identifier.

It shall remain stable and shall not be recreated merely because a
publication is presented through the Publications Module.

---

# 43. Person Relationship

The current source does not establish a frozen publication-to-person author
relationship.

Therefore the Publications Module does not currently create such a
relationship.

A future `publication_author` design may use the Person identity if formally
approved.

---

# 44. Organization Relationship

The current source does not establish a general publication-to-organization
ownership relationship.

Therefore no such relationship is frozen here.

---

# 45. UPBS Relationship

UPBS Souvenir is already represented as a publication type:

    UPBS_SOUVENIR

The Publications Module may therefore catalogue UPBS souvenirs using the
existing publication type.

The UPBS Module continues to own UPBS event/registration operations.

---

# 46. No UPBS Duplication

The Publications Module shall not duplicate:

- UPBS event
- UPBS registration
- Delegate
- Accommodation
- Prasad Patra

The publication catalogue only represents the publication itself.

---

# 47. Heritage Relationship

Founder & Heritage remains responsible for the historical context of
publications.

Publications provides the dedicated publication-oriented experience.

---

# 48. Reporting

The Publications Module should support publication-related reporting such
as:

- Publications by type
- Publications by language
- Publications by year
- Digitized publications
- Free publications
- Publications by edition

Any financial reporting remains owned by Finance.

---

# 49. Access Control

Publication administration shall use the common NSS ERP RBAC and
organizational-scope architecture.

The Publications Module shall not create an independent permission system.

---

# 50. Audit

Changes to publication metadata shall follow the common audit framework.

At minimum, publication creation and modification shall remain traceable.

---

# 51. Historical Preservation

Historical publication records shall remain available for:

- Heritage
- Research
- Reporting
- Digital library
- Historical reference

---

# 52. Module Boundary Summary

```text
FOUNDER & HERITAGE
        │
        └── Historical Publication Foundation
                │
                ▼
          nss_publication
                │
                ├── publication_type_master
                └── publication_language_master


PUBLICATIONS MODULE
        │
        ├── Catalogue
        ├── Search
        ├── Digital Library
        ├── Publication Presentation
        └── Future Operational Extensions
```

---

# 53. Current Data Ownership

| Capability                       | Current Owner                 |
| -------------------------------- | ----------------------------- |
| Publication identity             | Founder & Heritage foundation |
| Publication type                 | `publication_type_master`     |
| Publication language             | `publication_language_master` |
| Publication metadata             | `nss_publication`             |
| Historical publication context   | Founder & Heritage            |
| Publication catalogue experience | Publications                  |
| Digital publication presentation | Publications                  |
| Document storage                 | Common Document Management    |
| Publication income               | Finance                       |
| UPBS operations                  | UPBS                          |
| Inventory                        | Not yet frozen                |
| Subscription                     | Not yet frozen                |
| Orders                           | Not yet frozen                |
| Distribution                     | Not yet frozen                |

---

# 54. Current Table Ownership

The Publications Module currently introduces:

```text
0 new tables
```

It reuses the existing Heritage publication foundation.

Current publication-related tables remain:

```text
nss_publication
publication_type_master
publication_language_master
```

These are already part of the frozen Founder & Heritage scope.

---

# 55. Important Design Decision

The creation of a Publications Module does **not** imply creation of a
second publication database structure.

The principle is:

```
One Publication Identity
      ↓
Shared Publication Foundation
      ↓
Multiple Module Experiences
```

---

# 56. Future Operational Expansion

If NSS later requires a full publishing/distribution operation, a future
version may introduce separate operational entities.

Possible future areas include:

```
Inventory
Stock Movement
Distribution
Subscription
Orders
Order Items
Delivery
Digital Access
Publication Author
Publication Translation
```

These are possibilities only.

They are not frozen by PUB-01.

---

# 57. Avoiding Premature Schema Expansion

The Publications Module shall not expand the database merely because a
future capability might be useful.

A new table shall be introduced only when:

1. A business requirement exists.
2. The requirement is approved.
3. Ownership is defined.
4. Relationships are defined.
5. Business rules are documented.
6. ERD is updated.
7. Table design is approved.

---

# 58. Current Scope Statement

The current Publications Module is primarily:

```text
Publication Catalogue
+
Digital Library
+
Publication Discovery
+
Publication Presentation
```

built upon the already frozen Founder & Heritage publication foundation.

---

# 59. What Is Frozen by This Document

```text
✓ Publications is a distinct solution/module area

✓ Existing Heritage publication tables remain authoritative

✓ No duplicate publication master is created

✓ nss_publication is reused

✓ publication_type_master is reused

✓ publication_language_master is reused

✓ Books are supported

✓ Magazines are supported

✓ Journals are supported

✓ Research Publications are supported

✓ Newsletters are supported

✓ UPBS Souvenirs are supported

✓ Digital publications are supported

✓ Multilingual publications are supported

✓ Multiple editions are supported

✓ Free publications are supported

✓ Donation-based publications are supported

✓ Fixed-price publications are supported

✓ Digital and physical copies may coexist

✓ Digital library is part of the Publications scope

✓ Publication income belongs to Finance

✓ UPBS operations remain in UPBS

✓ Document storage belongs to common Document Management

✓ No inventory tables are currently frozen

✓ No subscription tables are currently frozen

✓ No order tables are currently frozen

✓ No distribution tables are currently frozen

✓ No author table is currently frozen
```

---

# 60. Explicitly Not Frozen

```text
Inventory Management
Stock Management
Distribution Management
Subscription Management
Order Management
Sales Workflow
Delivery Management
Publication Author Management
Translation Management
Digital Access Licensing
Publication Status Master
```

These require separate approved requirements before schema design.

---

# 61. Source Alignment

The existing project module division identifies Publications as covering:

```
Books
Magazines
Research Publications
UPBS Souvenirs
Digital Library
```

and allows it to remain under Heritage initially.

The Founder & Heritage publication design independently freezes:

```
nss_publication
publication_type_master
publication_language_master
```

Therefore this document treats the Publications Module as a dedicated
functional experience over the existing publication foundation rather than
creating duplicate database ownership.

---

# 62. Status

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
