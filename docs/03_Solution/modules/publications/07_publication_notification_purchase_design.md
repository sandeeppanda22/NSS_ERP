# NSS ERP — Publication Notification & Future Purchase Design

**Document ID:** SOL-PUB-007
**Version:** 1.0.0
**Status:** DRAFT — USER REQUIREMENTS ALIGNED
**Module:** Publications
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines:

1. New publication/book launch notifications.
2. Member discovery of newly launched publications.
3. Publication price presentation.
4. Future Buy/Purchase capability.
5. The boundary between the current publication catalogue and future
   publication commerce.

The current publication foundation remains unchanged.

---

# 2. Current Publication Foundation

The Publications Module continues to use:

    nss_publication
    publication_type_master
    publication_language_master

No duplicate publication identity is introduced.

---

# 3. Member Publication Experience

Members shall be able to:

- Browse all publications.
- Browse by year.
- Browse by category.
- Browse by language.
- Search publications.
- View publication details.
- See publication price where applicable.
- View digital publications where permitted.
- Download digital publications where permitted.
- Discover new publications.
- Receive notifications for new book/publication launches.

---

# 4. Publication Menu

The main ERP navigation shall expose:

    Publications

Recommended menu:

    Publications
    │
    ├── All Publications
    ├── Books
    ├── Magazines
    ├── Journals
    ├── Research Publications
    ├── UPBS Souvenirs
    ├── By Year
    ├── Digital Library
    ├── New Publications
    └── Search

---

# 5. Complete Publication Catalogue

Members shall be able to see the complete publication list under:

    Publications → All Publications

The catalogue shall include historical and current publications available
in the publication foundation.

---

# 6. Year-Wise Publication Discovery

Members shall be able to select a publication year.

Example:

    Publications
        ↓
    By Year
        ↓
    2026

The system shall derive available years from:

    publication_date

No separate publication-year master is required.

---

# 7. Category-Wise Publication Discovery

Members shall be able to browse publications by category.

Categories are derived from:

    publication_type_master

Examples:

    Books
    Magazines
    Journals
    Research Publications
    UPBS Souvenirs
    Newsletters
    Annual Reports
    Pamphlets
    Booklets

---

# 8. Combined Discovery

The catalogue should allow combinations such as:

    Year + Category

    Year + Language

    Category + Language

    Year + Category + Language

    Year + Category + Digital Availability

Example:

    2026
    +
    Books
    +
    Odia

returns:

    Odia books published in 2026.

---

# 9. Publication Price

Members shall be able to see the publication price where applicable.

Example:

    Price: ₹150

The existing publication model supports:

    Free
    Donation Based
    Fixed Price

---

# 10. Free Publication

For a free publication, the UI shall communicate:

    Free

The system shall not represent a free publication as a completed
zero-value financial transaction.

---

# 11. Donation-Based Publication

For a donation-based publication, the UI may display:

    Donation Based

The donation itself belongs to the Finance domain.

The Publications Module shall not maintain a separate financial ledger.

---

# 12. Fixed-Price Publication

For a fixed-price publication, the UI shall display:

    Price
    Currency

Example:

    ₹250

The price is publication metadata.

It does not represent a completed sale.

---

# 13. Price Source

The publication price shall come from:

    nss_publication.price

and:

    nss_publication.currency_code

The Publications UI shall not maintain a second price source.

---

# 14. New Publication

The Publications Module shall provide a way for members to identify newly
published books and other publications.

Recommended location:

    Publications → New Publications

---

# 15. New Publication Listing

The New Publications screen may display:

- Cover
- Title
- Publication Type
- Language
- Publication Date
- Edition
- Price
- Digital Availability

---

# 16. New Book Launch

A new book launch shall be capable of being announced through the common
NSS ERP notification framework.

Example:

    New Book Published

    "Book Title"

    A new NSS publication is now available.

    [View Publication]

---

# 17. Notification Audience

The default audience for new publication/book notifications is:

    Eligible NSS Members

The common notification framework shall determine the exact audience and
delivery mechanism.

---

# 18. Notification Content

A publication notification may contain:

    Publication Title
    Publication Type
    Publication Date
    Cover Image
    Short Description
    Price where applicable
    Digital Availability
    View Publication action

---

# 19. Notification Deep Link

Selecting a publication notification shall open:

    Publications
        ↓
    Publication Detail

The notification shall reference the existing publication identity.

---

# 20. Notification Identity

The notification shall point to:

    publication_pk

It shall not create a duplicate publication record.

---

# 21. Notification Workflow

```text
Publication Ready
       │
       ▼
Publication Announcement
       │
       ▼
Common Notification Framework
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

# 22. Notification Trigger

A new-publication notification shall be triggered by an approved
publication-launch/announcement action.

A normal metadata edit shall not automatically generate another launch
notification.

---

# 23. Notification Deduplication

The same publication launch shall not repeatedly notify members simply
because publication metadata is subsequently edited.

Notification deduplication belongs to the common notification framework.

---

# 24. Notification Channels

Publication notifications may use the common notification channels supported
by the ERP, such as:

```
In-App
Email
Push
```

Any additional channel requires common notification-framework support.

The Publications Module shall not implement independent notification
channels.

---

# 25. Notification Center

Publication notifications shall appear in the common ERP Notification
Center where supported.

The Publications Module provides the publication target.

---

# 26. Member Dashboard

Where dashboard notifications are supported, a new book/publication may
appear as:

```
New Publication

[Publication Title]

Published on [Date]

[View]
```

The Dashboard remains part of the common UI framework.

---

# 27. Digital Publication From Notification

Where a digital copy is available and the member has permission:

```
Notification
    ↓
Publication Detail
    ↓
Read / Download
```

The notification itself does not bypass document authorization.

---

# 28. Download From Publication Detail

Where an authorized digital document exists, the publication detail page
may provide:

```
[Download]
```

The download uses the common Document Management architecture.

---

# 29. Price + Digital Copy

A publication may simultaneously have:

```
Price = ₹150
Digital Copy = Available
```

This does not automatically mean that downloading the digital copy requires
payment.

Digital-access policy and purchase policy are separate concerns.

---

# 30. Current Catalogue vs Future Purchase

The current Publications Module supports:

```
Publication Catalogue
+
Price Display
```

A complete purchase workflow is a future capability.

---

# 31. Future Buy Option

The publication detail page shall be designed to accommodate:

```
[Buy]
```

or:

```
[Purchase]
```

for publications that are made available for sale.

This action is explicitly:

```
FUTURE
```

and is not part of the current implemented purchase workflow.

---

# 32. Future Buy Button

The future UI may display:

```
Price: ₹250

[Buy]
```

The Buy action shall only be enabled when the future purchase capability
is implemented and the publication is purchasable.

---

# 33. Future Purchase Workflow

The conceptual future workflow is:

```text
Publication Detail
       │
       ▼
     [Buy]
       │
       ▼
     Cart
       │
       ▼
    Checkout
       │
       ▼
     Payment
       │
       ▼
     Order
       │
       ▼
 Fulfilment / Delivery
```

This workflow is conceptual only.

---

# 34. Future Purchase Is Not Current Scope

The following are NOT frozen by PUB-007:

```
Cart
Checkout
Payment
Order
Shipment
Delivery
Return
Refund
Inventory
```

They require separate approved requirements and design.

---

# 35. Future Order Management

If purchasing is introduced, the system may eventually require:

```
publication_order
publication_order_item
```

These tables are not introduced by this document.

---

# 36. Future Inventory

Physical book sales may eventually require:

```
Stock
Inventory
Warehouse
Stock Movement
```

No inventory schema is introduced currently.

---

# 37. Future Delivery

Physical book purchase may require:

```
Address
Delivery
Shipment
Tracking
```

The current Publications Module does not define these.

Existing address/foundation architecture should be reused where appropriate.

---

# 38. Future Payment

A future purchase workflow may integrate with an approved payment system.

Payment transactions shall belong to the Finance/payment architecture.

The Publications Module shall not implement a parallel financial ledger.

---

# 39. Future Sales Integration

The conceptual future architecture is:

```text
Publications
      │
      ▼
Purchase / Order
      │
      ▼
Payment
      │
      ▼
Finance
      │
      ▼
Fulfilment
```

Exact ownership shall be determined during future purchase-system design.

---

# 40. Future Digital Purchase

If NSS later decides to sell digital publications, the purchase and digital
access models shall be designed separately.

The following concepts must not be assumed to be identical:

```
Digital Copy Available
Digital Copy Downloadable
Digital Copy Purchasable
```

---

# 41. Future Physical Purchase

If NSS later sells physical publications through the ERP, the workflow may
require:

```
Publication
    ↓
Order
    ↓
Payment
    ↓
Inventory
    ↓
Delivery
```

This is future scope.

---

# 42. Future Purchase Eligibility

The future purchase design shall determine whether purchasing is available
to:

```
Members
Non-members
Both
```

The current Publications Module does not freeze this rule.

---

# 43. Future Purchase Pricing

The existing:

```
price
currency_code
```

provide the current publication price foundation.

A future sales system may require additional concepts such as:

```
Effective Price
Discount
Tax
Shipping Charge
Promotional Price
```

None are currently frozen.

---

# 44. Future Price History

The current publication table contains the current publication price.

A historical price-management system is not currently frozen.

If required, price history shall be separately designed.

---

# 45. Publication Price Does Not Mean Purchasable

The presence of:

```
price
```

does NOT automatically mean:

```
purchasable = TRUE
```

Current price represents publication metadata.

Future purchase availability requires a separate approved business rule.

---

# 46. Publication Catalogue and Commerce

The Publications Module therefore has two conceptual layers:

```text
CURRENT

Publication Information
Catalogue
Digital Library
Price Display
Notifications


FUTURE

Buy
Cart
Order
Payment
Inventory
Delivery
```

---

# 47. Future Purchase State

A future implementation may require a publication to be classified as:

```
Not For Sale
Available For Sale
Temporarily Unavailable
```

These statuses are NOT currently frozen.

---

# 48. Future Purchase Button Visibility

The future Buy button should only appear when:

1. The purchase feature is enabled.
2. The publication is approved for sale.
3. The publication has a valid price where required.
4. The required stock/availability conditions are satisfied.
5. The user is eligible to purchase.

The exact rules require future design.

---

# 49. Member Experience — Current

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
          │
          ▼
  Publication Detail
          │
          ├── Price
          ├── Read
          └── Download
```

---

# 50. Member Experience — Future Purchase

```text
Member
  │
  ▼
Publication Detail
  │
  ├── Price
  │
  ├── Read
  │
  ├── Download
  │
  └── Buy
         │
         ▼
       Cart
         │
         ▼
      Checkout
         │
         ▼
      Payment
         │
         ▼
       Order
```

The Buy branch is future.

---

# 51. New Book Experience

```text
New Book Launch
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
      ├── Price
      ├── Read / Download
      └── Buy*
      
* Future
```

---

# 52. No Duplicate Notification Publication

The notification system shall reference:

```
nss_publication
```

It shall not maintain another publication catalogue.

---

# 53. No Year Master

Year-wise browsing shall derive the year from:

```
publication_date
```

No:

```
publication_year_master
```

is required.

---

# 54. No Category Duplication

Category-wise browsing shall use:

```
publication_type_master
```

No separate publication-category master shall be introduced unless a future
requirement establishes a distinction between publication type and
publication category.

---

# 55. No Digital Publication Duplicate

Digital Library shall use:

```
nss_publication
document_pk
is_digitized
```

No separate:

```
digital_publication
```

table is required.

---

# 56. No Notification Table

Publication notifications shall use the common notification framework.

No:

```
publication_notification
```

table is introduced by this design.

---

# 57. No Purchase Tables Yet

The following are explicitly NOT introduced:

```
publication_order
publication_order_item
cart
payment
shipment
inventory
stock_movement
```

They belong to future purchase/commerce design.

---

# 58. Finance Boundary

Publication price belongs to:

```
Publications
```

Actual money movement belongs to:

```
Finance
```

This distinction remains mandatory.

---

# 59. Existing Finance Relationship

The project source already recognizes proceeds from the sale of books,
journals, and other publications as Kendra Sangha income.

Therefore a future purchase system must integrate with Finance rather than
creating an independent Publications financial ledger.

---

# 60. Business Requirements

```text
PUB-BUY-001
Publication price shall be visible to members where applicable.

PUB-BUY-002
Free publications shall be clearly identified as Free.

PUB-BUY-003
Donation-based publications shall be clearly identified as Donation Based.

PUB-BUY-004
Fixed-price publications shall display price and currency.

PUB-BUY-005
Publication price shall be sourced from the authoritative publication
record.

PUB-BUY-006
The Publications UI shall accommodate a future Buy/Purchase action.

PUB-BUY-007
Buy/Purchase shall not be considered implemented until a separate purchase
workflow is approved.

PUB-BUY-008
The future purchase workflow shall integrate with Finance for actual
financial transactions.

PUB-BUY-009
The future purchase workflow shall define inventory requirements separately.

PUB-BUY-010
The future purchase workflow shall define physical delivery requirements
separately.

PUB-BUY-011
Publication price alone shall not imply that the publication is
purchasable.

PUB-BUY-012
New book/publication launches shall be capable of generating member
notifications through the common notification framework.

PUB-BUY-013
Publication notifications shall deep-link to the relevant publication
detail page.

PUB-BUY-014
Notification generation shall not duplicate publication records.

PUB-BUY-015
Historical publications shall remain discoverable even when not currently
available for purchase.
```

---

# 61. Current vs Future Scope

| Capability                            | Status                     |
| ------------------------------------- | -------------------------- |
| All Publications                      | CURRENT                    |
| Browse by Year                        | CURRENT                    |
| Browse by Category                    | CURRENT                    |
| Browse by Language                    | CURRENT                    |
| Search                                | CURRENT                    |
| Publication Detail                    | CURRENT                    |
| Price Display                         | CURRENT                    |
| Free / Donation / Fixed Price display | CURRENT                    |
| Digital Library                       | CURRENT                    |
| Digital View                          | CURRENT, subject to access |
| Digital Download                      | CURRENT, subject to access |
| New Publications                      | CURRENT                    |
| New Book Notifications                | CURRENT REQUIREMENT        |
| Buy Button                            | FUTURE                     |
| Cart                                  | FUTURE                     |
| Checkout                              | FUTURE                     |
| Payment                               | FUTURE                     |
| Orders                                | FUTURE                     |
| Inventory                             | FUTURE                     |
| Delivery                              | FUTURE                     |
| Returns / Refunds                     | FUTURE                     |

---

# 62. Schema Impact

Current requirements require:

```text
Existing:
    nss_publication
    publication_type_master
    publication_language_master

Common:
    Notification Framework
    Document Management
    Finance
```

New Publications tables:

```
0
```

Future purchase tables:

```
NOT YET DESIGNED
```

---

# 63. Final Architecture

```text
                         PUBLICATIONS
                              │
              ┌───────────────┼────────────────┐
              │               │                │
              ▼               ▼                ▼
          Catalogue      Digital Library   Notifications
              │               │                │
              └───────────────┼────────────────┘
                              ▼
                     Publication Detail
                              │
                    ┌─────────┼─────────┐
                    │         │         │
                    ▼         ▼         ▼
                  Price      Read    Download
                             
                             
                         FUTURE
                            │
                           Buy
                            │
                           Cart
                            │
                        Checkout
                            │
                         Payment
                            │
                          Order
                            │
                    Inventory / Delivery
```

---

# 64. Design Principle

The Publications Module shall follow:

```
One Publication Identity
    ↓
One Publication Foundation
    ↓
Catalogue + Digital Library
    ↓
Member Discovery
    ↓
Notifications
    ↓
Future Purchase Capability
```

Future commerce functionality shall be added without duplicating the
publication identity.

---

# 65. Status

DOCUMENT STATUS:

```
DRAFT — USER REQUIREMENTS ALIGNED
```

VERSION:

```
1.0.0
```

---

# End of Document
