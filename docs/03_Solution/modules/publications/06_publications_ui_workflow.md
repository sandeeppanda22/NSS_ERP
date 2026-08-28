# NSS ERP — Publications UI & User Workflow Design

**Document ID:** SOL-PUB-006
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED + USER REQUIREMENTS
**Module:** Publications
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the user-facing screens, navigation, browsing,
discovery, digital-library, download, and notification workflows for the
NSS Publications Module.

The Publications Module shall provide members with a simple and accessible
way to discover NSS publications across years and categories.

---

# 2. Primary Member Requirement

Members shall be able to:

- Open Publications from the main application menu.
- See all available publications.
- Browse publications year-wise.
- Browse publications category-wise.
- Search publications.
- Open publication details.
- View available digital publications.
- Download digital publications where permitted.
- Discover newly launched books/publications.
- Receive notifications for new book launches.

---

# 3. Publications Menu

The main application navigation shall contain:

    Publications

This shall provide access to the Publications Module.

---

# 4. Publications Menu Structure

Recommended structure:

    Publications
    │
    ├── All Publications
    ├── Books
    ├── Magazines
    ├── Journals
    ├── Research Publications
    ├── UPBS Souvenirs
    ├── Newsletters
    ├── By Year
    ├── Digital Library
    └── New Publications

The exact menu presentation may be adjusted during UI implementation.

---

# 5. All Publications

The **All Publications** screen is the primary publication catalogue.

It shall display the complete list of publications available to the
member/user according to publication access rules.

---

# 6. Complete Publication List

Members shall be able to see the complete published publication list from:

    Publications → All Publications

This list shall not be restricted only to newly published books.

It shall include historical and previously published publications that are
available in the ERP catalogue.

---

# 7. Publication Categories

Members shall be able to browse publications by category.

The categories shall come from the existing:

    publication_type_master

Current categories include:

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

---

# 8. Category Navigation

Example:

    Publications
        ↓
    Books

The Books page shall display publications classified as:

    BOOK

Similarly:

    Publications
        ↓
    Research Publications

shall display:

    RESEARCH_PUBLICATION

---

# 9. Year-Wise Browsing

Members shall be able to browse publications by publication year.

Example:

    Publications
        ↓
    By Year
        ↓
    2026
        ↓
    Publications published in 2026

---

# 10. Year Selection

The By Year interface should present available publication years dynamically
from the publication records.

Example:

    2026
    2025
    2024
    2023
    2022
    ...
    
The system should not require manually maintained year values.

---

# 11. Year + Category Filtering

Members should be able to combine year and category filters.

Example:

    Year = 2026
    Category = BOOK

Result:

    Books published in 2026

Another example:

    Year = 2025
    Category = RESEARCH_PUBLICATION

Result:

    Research publications published in 2025

---

# 12. Language Filtering

Members may also filter by publication language.

Example:

    Language = ODIA

or:

    Language = ENGLISH

Language values come from:

    publication_language_master

---

# 13. Combined Filters

The catalogue should support combinations such as:

    Year
    +
    Category
    +
    Language
    +
    Digital Availability

Example:

    2026
    +
    Books
    +
    Odia
    +
    Digital Available

---

# 14. Search

The Publications catalogue shall provide search.

Search should support at minimum:

    Publication Title
    Publication ID
    ISBN

Where appropriate, search results may also expose:

    Type
    Language
    Year

---

# 15. Publication Cards

A publication catalogue card should provide concise information.

Recommended structure:

    ┌───────────────────────────────┐
    │          COVER IMAGE          │
    │                               │
    ├───────────────────────────────┤
    │ Publication Title             │
    │ Type                          │
    │ Language                      │
    │ Year                          │
    │ Edition                       │
    │                               │
    │ [View Details] [Read/Download]│
    └───────────────────────────────┘

---

# 16. Publication Detail Page

Selecting a publication shall open its detail page.

The detail page may display:

    Cover
    Title
    Publication Type
    Language
    Publication Date
    Edition
    Description
    Page Count
    ISBN
    Price
    Digital Availability

---

# 17. Digital Availability

The publication detail page shall clearly indicate whether a digital copy
is available.

Example:

    Digital Copy Available

or:

    Digital Copy Not Available

---

# 18. View Digital Publication

Where a digital publication is available and viewing is permitted, the
member should have an action such as:

    [Read Online]

The actual reader implementation belongs to the Document Management/UI
architecture.

---

# 19. Download Digital Publication

Where downloading is permitted, the member should have:

    [Download]

The download action shall retrieve the authorized digital publication
document.

---

# 20. Download Permission

A publication being digitized does not automatically mean that every user
can download it.

The download action shall respect:

    Authentication
    Authorization
    Document Security
    Publication Access Policy

---

# 21. Member Download Workflow

```text
Member
  │
  ▼
Publications
  │
  ▼
Select Publication
  │
  ▼
Publication Detail
  │
  ▼
Digital Copy Available
  │
  ▼
[Download]
  │
  ▼
Authorization Check
  │
  ├── Allowed → Download
  │
  └── Not Allowed → Access Denied / View-only
```

---

# 22. Digital Library

The Digital Library shall provide a focused view of publications that have
digital copies.

Navigation:

```
Publications
    ↓
Digital Library
```

---

# 23. Digital Library Filters

The Digital Library should support:

```
Year
Category
Language
```

and optionally:

```
Search
```

---

# 24. New Publications

The Publications Module shall provide a way to identify newly published
books/publications.

Recommended navigation:

```
Publications
    ↓
New Publications
```

---

# 25. New Publication Identification

A publication may be considered new based on its publication date and/or
the ERP's publication announcement workflow.

The exact "new" duration is not frozen here.

For example, the UI may eventually show:

```
New
Recently Published
```

without requiring a separate publication master.

---

# 26. New Book Launch Notification

The ERP shall support notification for new book/publication launches.

Example:

```
New Book Published

"Title of the Book"

A new NSS publication is now available.

[View Publication]
```

---

# 27. Notification Audience

The default requirement is:

```
Members
```

New publication notifications should be available to eligible NSS members
through the common notification framework.

The final notification audience can be controlled through the standard
notification/authorization configuration.

---

# 28. Notification Content

A new-publication notification should contain:

```
Publication Title
Publication Type
Publication Date
Cover Image where available
Short Description where available
View Publication action
```

Where digital access is permitted, the notification may also provide a
direct action to the digital publication.

---

# 29. Notification Deep Link

Selecting the notification should take the user directly to:

```
Publications → Publication Detail
```

for that publication.

Example:

```
Notification
     ↓
New Book Launch
     ↓
Publication Detail
     ↓
Read / Download
```

---

# 30. Notification Does Not Duplicate Publication Data

The notification shall reference the existing publication identity.

It shall not create a duplicate publication record.

Conceptually:

```
Notification
     │
     ▼
publication_pk
     │
     ▼
nss_publication
```

---

# 31. Common Notification Framework

Publication launch notifications should use the common NSS ERP notification
architecture.

The Publications Module should not create an independent notification
engine.

---

# 32. New Book Launch Workflow

```text
Authorized Publication Administrator
          │
          ▼
Create / Update Publication
          │
          ▼
Publication Becomes Available
          │
          ▼
New Publication Announcement
          │
          ▼
Common Notification Service
          │
          ▼
Eligible Members
          │
          ▼
Notification
          │
          ▼
Publication Detail
```

---

# 33. Notification Trigger

The notification trigger should be associated with the approved
publication-launch/announcement event.

It should not be triggered simply because an administrator edits any
publication field.

---

# 34. Notification Deduplication

The same publication launch should not generate unlimited duplicate
notifications merely because the publication metadata is edited.

The common notification framework should control notification delivery and
deduplication.

---

# 35. Publication Launch

A publication launch represents the point at which NSS announces a new
publication.

The current publication table does not contain a dedicated:

```
publication_launch
```

entity.

Therefore the initial implementation should use the common notification
and publication workflow rather than introducing a new table without an
approved requirement.

---

# 36. New Publication vs Historical Publication

The catalogue contains:

```
Historical Publications
+
Current Publications
+
New Publications
```

"New Publications" is a discovery/presentation concept.

It does not mean that older publications are removed from the catalogue.

---

# 37. Historical Catalogue

Members should be able to browse historical publications by:

```
Year
Category
Language
```

This makes the Publications Module useful as an NSS publication archive as
well as a current-publication catalogue.

---

# 38. Publication Archive

The publication catalogue should preserve access to historical records.

Example:

```
Publications
    ↓
By Year
    ↓
1995
    ↓
Historical Publications
```

---

# 39. Year Navigation Example

```text
Publications
│
├── 2026
│   ├── Books
│   ├── Magazines
│   └── Research Publications
│
├── 2025
│   ├── Books
│   ├── Magazines
│   └── Research Publications
│
├── 2024
│   └── ...
│
└── Earlier Years
```

The actual years shall be dynamically derived.

---

# 40. Category Navigation Example

```text
Publications
│
├── Books
├── Magazines
├── Journals
├── Research Publications
├── Newsletters
├── Annual Reports
├── UPBS Souvenirs
├── Pamphlets
└── Booklets
```

---

# 41. Category + Year Example

```text
Books
   │
   ├── 2026
   ├── 2025
   ├── 2024
   └── Earlier
```

The UI may alternatively provide year filters instead of nested navigation.

---

# 42. Publication List View

The module should support a list/table view in addition to card/grid view
where appropriate.

Example columns:

```
Title
Type
Language
Publication Date
Edition
Digital
Action
```

---

# 43. Responsive Design

The Publications interface shall support:

```
Desktop
Tablet
Mobile
```

Members may access Publications from the ERP web application on different
screen sizes.

---

# 44. Member Experience

The member experience should be simple.

The member should not need to understand database concepts such as:

```
publication_pk
document_pk
publication_type_pk
```

These are system-level concepts.

---

# 45. Member Navigation Summary

```text
Member
  │
  ▼
Publications
  │
  ├── All Publications
  ├── By Year
  ├── By Category
  ├── Digital Library
  ├── New Publications
  └── Search
```

---

# 46. Publication Discovery Flow

```text
Publications
      │
      ├── Browse All
      │
      ├── Browse by Year
      │
      ├── Browse by Category
      │
      ├── Search
      │
      └── New Publications
              │
              ▼
       Publication Detail
              │
       ┌──────┴──────┐
       │             │
       ▼             ▼
    Read Online   Download
```

---

# 47. Notification Discovery Flow

```text
New Publication
      │
      ▼
Launch Announcement
      │
      ▼
Member Notification
      │
      ▼
View Publication
      │
      ▼
Publication Detail
      │
      ├── Read
      └── Download
```

---

# 48. Publication Access

The Publications Module distinguishes:

```
Catalogue Access
    =
Ability to see publication metadata
```

from:

```
Digital Access
    =
Ability to view/download the digital document
```

A member may be able to see a publication even where the digital file is
not available or downloadable.

---

# 49. Download Availability

The UI should only show:

```
[Download]
```

when a downloadable digital copy exists and the current user is authorized.

Otherwise it may show:

```
[View Details]
```

or:

```
[Read Online]
```

depending on access policy.

---

# 50. Publication Without Digital Copy

A publication without a digital copy shall still appear in:

```
All Publications
By Year
By Category
Search
```

It shall simply indicate:

```
Digital Copy Not Available
```

---

# 51. Publication With Digital Copy

A publication with an available digital copy may show:

```
[Read Online]
[Download]
```

subject to authorization.

---

# 52. Publication With Cover Only

A publication may have a cover image without a digital copy.

The catalogue should still display the cover.

The user should not assume that the cover implies a downloadable book.

---

# 53. Publication Detail Information Hierarchy

Recommended presentation order:

```text
1. Cover
2. Title
3. Publication Type
4. Language
5. Publication Date
6. Edition
7. Description
8. ISBN
9. Page Count
10. Price
11. Digital Availability
12. Read / Download
```

---

# 54. New Book Highlight

A newly launched book may be highlighted in:

```
Publications → New Publications
```

and optionally on:

```
Member Dashboard
```

through the common notification/dashboard framework.

---

# 55. Member Dashboard Notification

Where supported by the common dashboard framework, a new book notification
may appear as:

```
New Publication

[Book Title]

Published on [Date]

[View]
```

The Publications Module provides the publication target; the dashboard
framework controls presentation.

---

# 56. Notification Center

The notification may also remain available in the common:

```
Notification Center
```

according to normal notification retention rules.

---

# 57. Read / Unread Notification

Publication launch notifications should follow the common notification
framework's read/unread behavior.

The Publications Module does not create separate notification-state logic.

---

# 58. Notification Preferences

If the common notification framework supports preferences, members may
eventually control publication-related notifications.

This does not require a Publications-specific preference table.

---

# 59. Notification Channels

The actual channels:

```
In-App
Email
Push
SMS
```

shall follow the common notification framework and approved communication
configuration.

The Publications Module does not independently implement these channels.

---

# 60. Search Result Deep Link

Every publication search result should open the same publication detail
page.

This ensures consistent navigation:

```text
Search
  ↓
Result
  ↓
Publication Detail
```

---

# 61. Category Result Deep Link

Similarly:

```text
Category
  ↓
Publication
  ↓
Publication Detail
```

---

# 62. Year Result Deep Link

And:

```text
Year
  ↓
Publication
  ↓
Publication Detail
```

---

# 63. Digital Library Deep Link

And:

```text
Digital Library
  ↓
Publication
  ↓
Publication Detail
  ↓
Read / Download
```

---

# 64. No Duplicate Publication Screens

The system should not create separate publication-detail implementations
for:

```
Search
Category
Year
Digital Library
Notifications
```

All should resolve to the same Publication Detail experience.

---

# 65. Publication Detail as Single Source of Presentation

```text
Search ──────────────┐
Category ────────────┤
Year ────────────────┤
Digital Library ─────┤
Notification ────────┤
New Publications ────┘
          │
          ▼
Publication Detail
```

---

# 66. Administrative vs Member Experience

The Publications Module shall provide two conceptual experiences:

```text
Member
    =
Discover / View / Read / Download

Authorized Administrator
    =
Create / Maintain / Manage
```

---

# 67. Member Permissions

Members shall be able to access publication information according to the
publication visibility rules.

The default requirement is that members can browse the publication
catalogue.

---

# 68. Administrative Permissions

Publication administration shall follow common NSS ERP RBAC.

The Publications Module shall not create a separate authorization system.

---

# 69. Audit

Administrative changes to publication records shall be auditable according
to the common audit framework.

---

# 70. Notification Audit

Notification generation and delivery shall be handled by the common
notification framework.

The publication itself remains the authoritative content source.

---

# 71. No New Publication Table for Notifications

The notification requirement does not justify creating:

```
publication_notification
```

as a Publications table.

The common notification framework shall be reused.

---

# 72. No New Publication Table for Year

Year-wise browsing does not require:

```
publication_year_master
```

The year is derived from:

```
publication_date
```

---

# 73. No New Publication Table for Category

Category-wise browsing does not require a separate category table.

It uses:

```
publication_type_master
```

---

# 74. No New Publication Table for Digital Library

The Digital Library does not require:

```
digital_publication
```

as a duplicate publication entity.

It uses:

```
nss_publication
+
document_pk
+
is_digitized
```

---

# 75. Current Functional Requirements

```text
PUB-FR-001
Members shall access Publications from the main ERP menu.

PUB-FR-002
Members shall see all available publications.

PUB-FR-003
Members shall browse publications by year.

PUB-FR-004
Members shall browse publications by category.

PUB-FR-005
Members shall filter publications by language.

PUB-FR-006
Members shall search publications.

PUB-FR-007
Members shall view publication details.

PUB-FR-008
Members shall identify digital availability.

PUB-FR-009
Members shall read digital publications where permitted.

PUB-FR-010
Members shall download digital publications where permitted.

PUB-FR-011
Members shall discover newly published books/publications.

PUB-FR-012
Eligible members shall receive notifications for new book/publication
launches.

PUB-FR-013
Notification selection shall open the corresponding publication detail.

PUB-FR-014
Publication notifications shall use the common notification framework.

PUB-FR-015
Year-wise browsing shall derive years from publication dates.

PUB-FR-016
Category-wise browsing shall use publication type master.

PUB-FR-017
Digital Library shall use the existing publication identity.

PUB-FR-018
Historical publications shall remain discoverable.

PUB-FR-019
A publication without a digital copy shall remain visible in the
catalogue.

PUB-FR-020
Publication search/category/year/digital-library entries shall resolve to
the same publication detail experience.

PUB-FR-021
Members shall be able to see the publication price where applicable.

PUB-FR-022
The publication detail experience shall accommodate a future Buy/Purchase
action.

PUB-FR-023
The Buy/Purchase workflow shall not be considered implemented until a
separate approved purchase/order design is completed.
```

---

# 76. UI Navigation Summary

```text
MAIN MENU
│
└── Publications
    │
    ├── All Publications
    │
    ├── By Year
    │   ├── 2026
    │   ├── 2025
    │   ├── 2024
    │   └── ...
    │
    ├── By Category
    │   ├── Books
    │   ├── Magazines
    │   ├── Journals
    │   ├── Research Publications
    │   ├── UPBS Souvenirs
    │   └── ...
    │
    ├── Digital Library
    │
    ├── New Publications
    │
    └── Search
```

---

# 77. Final Member Experience

The intended member experience is:

```text
Open ERP
   ↓
Publications
   ↓
See all NSS publications
   ↓
Browse by Year / Category
   ↓
Select Publication
   ↓
View Details
   ↓
Read / Download digital copy
```

And for new books:

```text
New Book Published
       ↓
Member Notification
       ↓
Open Notification
       ↓
Publication Detail
       ↓
Read / Download
```

---

# 78. Data Architecture

The functional UI uses:

```text
                    nss_publication
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
        Type            Language         Document
        Master           Master
          │                │                │
          └────────────────┼────────────────┘
                           │
                           ▼
                  Publications UI
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
     Catalogue          Digital Library    Notifications
```

---

# 79. Schema Impact

The requirements in this document do not require new publication tables.

Specifically:

```text
Year browsing
    → publication_date

Category browsing
    → publication_type_master

Language filtering
    → publication_language_master

Digital Library
    → is_digitized + document_pk

New publication notification
    → common notification framework
```

---

# 80. Future Extension Boundary

The following remain outside the current frozen implementation:

```text
Inventory
Subscription
Orders
Sales Workflow
Distribution
Delivery
Author Management
Translation Management
Digital Licensing
```

If required later, they shall be separately designed.

---

# 81. Publication Price Display

Members shall be able to see the price of a publication where a price
is applicable.

The publication detail page may display:

    Price: ₹XXX

The price comes from the existing:

    nss_publication.price
    nss_publication.currency_code

This applies to all publication types — books, magazines, journals,
research publications, UPBS souvenirs, etc.

---

# 82. Free Publications

Where a publication is free, the UI shall display:

    Free

rather than presenting a misleading purchase price.

The free status comes from the existing:

    nss_publication.is_free_publication

---

# 83. Donation-Based Publications

Where a publication follows a donation-based model, the UI may display:

    Donation Based

The actual donation transaction is outside the current Publications scope.

---

# 84. Future Buy Option

The Publications Module shall be designed to accommodate a future:

    [Buy]

or:

    [Purchase]

action for publications/books that are available for sale.

The purchase workflow is NOT part of the current frozen implementation.

---

# 85. Future Purchase Workflow

The future purchase workflow may be:

```text
Publication Detail
      │
      ▼
   [Buy]
      │
      ▼
Order / Cart
      │
      ▼
Payment
      │
      ▼
Fulfilment / Delivery
```

The exact workflow, payment integration, inventory, delivery, order
management, cancellation, refund, and return rules require separate
requirements and design.

---

# 86. Purchase Workflow Boundary

The following are NOT frozen by the current Publications implementation:

```text
Order Table
Order Item Table
Cart
Payment Gateway Integration
Invoice Generation
Shipment / Delivery
Return / Refund
Inventory Deduction
```

These require separately approved requirements and solution design.

---

# 87. Price Terminology

The price field applies to all publication types:

```text
Books
Magazines
Journals
Research Publications
UPBS Souvenirs
Newsletters
Pamphlets
Booklets
Annual Reports
```

The existing `nss_publication.price` and `currency_code` remain the
authoritative price representation.

No separate "book price" column is needed.

---

# 88. Status

DOCUMENT STATUS:

```
DRAFT — SOURCE ALIGNED + USER REQUIREMENTS
```

VERSION:

```
1.0.0
```

---

# End of Document
