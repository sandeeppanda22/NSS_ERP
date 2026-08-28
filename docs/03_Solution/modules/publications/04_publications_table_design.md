# NSS ERP — Publications Table Design

**Document ID:** SOL-PUB-004  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Publications  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical table design for the NSS Publications
Module.

The Publications Module currently reuses the publication foundation already
frozen within Founder & Heritage.

The current publication foundation consists of:

    nss_publication
    publication_type_master
    publication_language_master

No duplicate publication master is introduced.

---

# 2. Current Table Scope

The current Publications Module introduces:

    0 new physical tables

It reuses:

    1. nss_publication
    2. publication_type_master
    3. publication_language_master

These three tables constitute the current publication data foundation.

---

# 3. Frozen Publication Table

The `nss_publication` table was frozen as version 1.1.

The frozen design includes:

- Publication identity
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
- Audit timestamps

The source explicitly records this table as **FROZEN v1.1**.

---

# 4. Table 1 — `nss_publication`

## Purpose

`nss_publication` is the authoritative publication entity.

It represents NSS publications such as:

- Books
- Magazines
- Journals
- Newsletters
- Annual Reports
- UPBS Souvenirs
- Research Publications
- Pamphlets
- Booklets
- Other publications

---

# 5. `nss_publication` — Logical Columns

| Column | Required | Key | Description |
|---|---:|---|---|
| `publication_pk` | Yes | PK | Internal publication identity |
| `publication_id` | Yes | UNIQUE | Human-readable publication business ID |
| `title` | Yes | — | Publication title |
| `publication_type_pk` | Yes | FK | Publication type |
| `publication_date` | No | — | Publication date |
| `edition_no` | No | — | Edition number |
| `language_pk` | Yes | FK | Publication language |
| `price` | No | — | Publication price |
| `currency_code` | No | — | Currency code |
| `page_count` | No | — | Number of pages |
| `isbn_number` | No | — | ISBN where applicable |
| `description` | No | — | Publication summary |
| `document_pk` | No | FK | Digital publication document |
| `cover_photo_document_pk` | No | FK | Cover image document |
| `is_digitized` | Yes | — | Digital version availability |
| `is_free_publication` | Yes | — | Free publication indicator |
| `created_at` | Yes | — | Creation timestamp |
| `updated_at` | Yes | — | Last update timestamp |

This column set follows the frozen v1.1 source definition.

---

# 6. `publication_pk`

Internal primary key of the publication.

The project database convention uses UUID for internal primary keys.

The value is used for relational references.

It is not intended to be the primary human-facing identifier.

---

# 7. `publication_id`

Human-readable business identifier for the publication.

It shall be unique.

The business identifier is used for:

- Search
- Reports
- UI
- Human communication
- Publication references

---

# 8. Publication Identity

The publication identity consists of:

    publication_pk
        +
    publication_id

The two serve different purposes:

```text
publication_pk
    =
internal relational identity

publication_id
    =
human-readable business identity
```

---

# 9. `title`

Stores the publication title.

The title is a catalogue attribute.

Changing a title through an approved correction does not automatically create
a new publication identity.

---

# 10. `publication_type_pk`

Foreign key to:

```
publication_type_master
```

This provides controlled publication classification.

---

# 11. Publication Type Master Relationship

The relationship is:

```text
publication_type_master
        1
        |
        | 0..N
        |
        ▼
nss_publication
```

One publication type can classify many publications.

Each publication has one publication type.

---

# 12. Publication Type Values

The currently established publication type values are:

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

These values are established by the frozen publication foundation.

---

# 13. `publication_date`

Stores the publication date where available.

Historical publications may retain their original recorded publication date.

---

# 14. `edition_no`

Stores the edition number where applicable.

The existing publication design supports multiple editions.

The current model does not introduce a separate:

```
publication_edition
```

table.

---

# 15. Edition Design Boundary

The current structure treats:

```
edition_no
```

as publication metadata.

A future requirement may introduce a dedicated edition entity if more
complex edition management becomes necessary.

Such a change requires separate design approval.

---

# 16. `language_pk`

Foreign key to:

```
publication_language_master
```

Language is mandatory for a publication.

This is explicitly frozen in the publication business rules.

---

# 17. Publication Language Master

The relationship is:

```text
publication_language_master
        1
        |
        | 0..N
        |
        ▼
nss_publication
```

One language may be associated with many publications.

---

# 18. Publication Language Values

The current language master values are:

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

These values are established by the frozen publication foundation.

---

# 19. `price`

Stores the publication price where applicable.

The current publication model supports:

```text
FREE
DONATION_BASED
FIXED_PRICE
```

Price is publication metadata.

It is not a financial transaction.

---

# 20. `currency_code`

Stores the currency associated with the publication price.

Current default:

```text
INR
```

The source specifically establishes INR as the default currency.

---

# 21. Price Precision

The earlier schema design recommends:

```text
NUMERIC(10,2)
```

for publication price.

This is a physical PostgreSQL datatype decision and shall be confirmed
during SQL implementation.

The logical design only requires a monetary value where applicable.

---

# 22. Free Publication

`is_free_publication` identifies a publication that is offered without a
fixed sale price.

Examples may include:

* Annual Reports
* Selected informational publications
* Free digital publications

The field is part of the frozen publication design.

---

# 23. Donation-Based Publication

A donation-based publication may have no fixed mandatory price.

The publication framework supports donation-based publications.

The donation itself is not stored as a publication financial transaction.

---

# 24. Finance Boundary

The following distinction is mandatory:

```text
Publication Price
        ≠
Financial Transaction
```

Actual income, receipts, payments, accounting, and financial reporting
belong to the Finance domain.

---

# 25. `page_count`

Stores the number of pages where applicable.

It is optional because some publication formats may not have a conventional
page count.

---

# 26. `isbn_number`

Stores ISBN where applicable.

ISBN is optional.

Not every NSS publication is required to have an ISBN.

---

# 27. ISBN and Publication ID

ISBN does not replace:

```text
publication_id
```

ISBN is an external publication identifier.

The NSS ERP publication identity remains:

```text
publication_pk
publication_id
```

---

# 28. `description`

Stores a summary or descriptive information about the publication.

It is intended for catalogue and presentation purposes.

---

# 29. `document_pk`

References the digital publication document where one exists.

Conceptually:

```text
nss_publication
      |
      | 0..1
      ▼
document_master
```

The document belongs to the common Document Management architecture.

---

# 30. Digital Publication

A publication may be:

```text
Physical only
```

or:

```text
Digital only
```

or:

```text
Physical + Digital
```

The frozen publication rules explicitly allow physical and digital copies to
coexist.

---

# 31. `cover_photo_document_pk`

References the document representing the publication cover image.

It is separate from:

```text
document_pk
```

which represents the main digital publication document.

---

# 32. Document Relationship

Conceptually:

```text
nss_publication
       │
       ├──────── document_pk
       │              │
       │              ▼
       │       Digital Publication
       │
       └──── cover_photo_document_pk
                      │
                      ▼
                 Cover Image
```

---

# 33. Document Storage Boundary

The Publications Module does not own physical file storage.

Document storage, retrieval, authorization, and lifecycle follow the common
Document Management architecture.

---

# 34. `is_digitized`

Indicates whether a digital version of the publication is available.

Possible logical states:

```text
TRUE
FALSE
```

The field is part of the frozen publication foundation.

---

# 35. Digitization Consistency

Where:

```text
is_digitized = TRUE
```

the publication should have an appropriate digital document reference.

The exact PostgreSQL constraint is an implementation decision.

---

# 36. `is_free_publication`

Indicates whether the publication is offered as a free publication.

It is distinct from:

```text
price
```

and:

```text
currency_code
```

---

# 37. Pricing Model

The current logical model supports:

```text
FREE
DONATION_BASED
FIXED_PRICE
```

The existing table structure uses:

```text
price
currency_code
is_free_publication
```

No separate pricing-model master is currently frozen.

---

# 38. Audit Columns

The frozen publication design contains:

```text
created_at
updated_at
```

These provide creation and update timestamps.

The common project audit standard applies where additional audit attribution
is required.

---

# 39. Table 2 — `publication_type_master`

## Purpose

Provides controlled classification of NSS publications.

---

# 40. `publication_type_master` — Logical Columns

| Column                  | Required | Key    | Description              |
| ----------------------- | -------: | ------ | ------------------------ |
| `publication_type_pk`   |      Yes | PK     | Internal type identity   |
| `publication_type_code` |      Yes | UNIQUE | Machine-readable code    |
| `publication_type_name` |      Yes | —      | Display name             |
| `description`           |       No | —      | Type description         |
| `is_active`             |      Yes | —      | Operational master state |

The exact physical column set should follow the common Master Data standard.

The frozen publication source establishes the type master and its seed
values; it does not provide a separately frozen complete physical column
definition for this master.

---

# 41. Publication Type Codes

Current recommended/frozen seed values:

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

# 42. Type Master Principles

Publication types shall:

* Be centrally controlled
* Use stable codes
* Avoid uncontrolled duplicates
* Support reporting
* Support filtering
* Be reusable across publications

---

# 43. Table 3 — `publication_language_master`

## Purpose

Provides controlled language classification for publications.

---

# 44. `publication_language_master` — Logical Columns

| Column          | Required | Key    | Description                    |
| --------------- | -------: | ------ | ------------------------------ |
| `language_pk`   |      Yes | PK     | Internal language identity     |
| `language_code` |      Yes | UNIQUE | Machine-readable language code |
| `language_name` |      Yes | —      | Display language name          |
| `description`   |       No | —      | Language description           |
| `is_active`     |      Yes | —      | Operational master state       |

The exact physical column set follows the common Master Data standard.

---

# 45. Language Master Values

Current values:

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

# 46. Language Master Principles

Publication languages shall:

* Use controlled values
* Support filtering
* Support reporting
* Avoid inconsistent spelling
* Support future multilingual publication growth

---

# 47. Foreign Key Summary

| Child             | Column                    | Parent                        |
| ----------------- | ------------------------- | ----------------------------- |
| `nss_publication` | `publication_type_pk`     | `publication_type_master`     |
| `nss_publication` | `language_pk`             | `publication_language_master` |
| `nss_publication` | `document_pk`             | `document_master`             |
| `nss_publication` | `cover_photo_document_pk` | `document_master`             |

The exact document foreign-key implementation shall follow the final
Document Management design.

---

# 48. Logical Relationship

```text
publication_type_master
          │
          │ 1:N
          ▼
   nss_publication
          ▲
          │ N:1
          │
publication_language_master

   nss_publication
          │
          ├── 0..1 → document_master
          │
          └── 0..1 → document_master
```

The two document references represent different purposes:

```text
document_pk
    =
digital publication

cover_photo_document_pk
    =
cover image
```

---

# 49. Current Publication Table Count

```text
nss_publication                  1
publication_type_master         1
publication_language_master     1
──────────────────────────────────
Publication Foundation          3
```

These three tables already belong to the frozen Founder & Heritage
publication foundation.

---

# 50. New Tables Introduced by Publications Module

```text
New Tables = 0
```

This is intentional.

The Publications Module is currently a dedicated functional module over
the existing publication data foundation.

---

# 51. Tables Not Currently Introduced

The following are deliberately not introduced:

```text
publication_edition
publication_author
publication_translation
publication_inventory
publication_stock
publication_stock_movement
publication_distribution
publication_subscription
publication_order
publication_order_item
publication_delivery
publication_status_master
publication_access
```

These require separate approved requirements before physical schema design.

---

# 52. Publication Author

Earlier project discussion identified:

```text
publication_author
```

as a possible future enhancement.

It is not part of the current frozen table design.

If introduced later, it should consider the common Person identity rather
than creating a separate author-person master.

---

# 53. Publication Inventory

Inventory is not currently frozen.

No stock quantity or warehouse columns shall be added to `nss_publication`
merely to anticipate future inventory management.

---

# 54. Publication Subscription

Subscription is not currently frozen.

No subscription columns or tables are added.

---

# 55. Publication Order

Order management is not currently frozen.

No order columns or tables are added.

---

# 56. Publication Distribution

Distribution is not currently frozen.

No distribution columns or tables are added.

---

# 57. Publication Translation

The current model supports language classification.

It does not freeze a translation relationship.

No translation table is added.

---

# 58. Publication Status

A separate publication-status master is not currently frozen.

No:

```text
publication_status_master
```

is introduced.

---

# 59. Physical Schema Boundary

This document does not define final PostgreSQL DDL.

The following remain implementation concerns:

```text
CREATE TABLE
ALTER TABLE
CHECK constraints
INDEX definitions
UNIQUE index implementation
Foreign-key actions
Triggers
Generated values
PostgreSQL-specific datatype tuning
```

---

# 60. Expected PostgreSQL Considerations

When the physical schema is eventually implemented, particular attention
should be given to:

```text
publication_id uniqueness
publication_type_fk validity
language_fk validity
NULL-aware price handling
currency validation
document references
cover document references
digitization consistency
free-publication consistency
```

These are implementation considerations derived from the frozen logical
model.

---

# 61. Audit and History

Publication records are historical/heritage information as well as catalogue
information.

The physical implementation shall preserve historical records according to
the common lifecycle and audit standards.

---

# 62. No Physical Deletion by Normal Catalogue Operation

Removing a publication from a catalogue view must not automatically mean
physical database deletion.

Historical publication preservation remains important.

---

# 63. Publication and Heritage

The underlying tables remain part of the Founder & Heritage foundation.

The Publications Module does not change their ownership simply by providing
a separate functional area.

---

# 64. Publication and Digital Library

The Digital Library uses the same:

```text
nss_publication
```

identity.

It does not create a second digital publication table.

---

# 65. Publication and UPBS

UPBS souvenirs use:

```text
publication_type_master
    =
UPBS_SOUVENIR
```

No UPBS operational table is duplicated in Publications.

---

# 66. Publication and Finance

Price metadata remains in:

```text
nss_publication
```

Financial transactions remain outside this module.

---

# 67. Publication Table Design Summary

```text
                         nss_publication
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
     publication_type      language          documents
          master            master
             │                 │                 │
             │                 │          ┌──────┴──────┐
             │                 │          │             │
             │                 │          ▼             ▼
             │                 │       Digital       Cover
             │                 │       Document      Document
             │                 │
             └─────────────────┴───────────────────────
```

---

# 68. Final Logical Column Set — `nss_publication`

```text
publication_pk
publication_id
title
publication_type_pk
publication_date
edition_no
language_pk
price
currency_code
page_count
isbn_number
description
document_pk
cover_photo_document_pk
is_digitized
is_free_publication
created_at
updated_at
```

This is the frozen v1.1 publication column set.

---

# 69. Final Publication Type Master

```text
publication_type_pk
publication_type_code
publication_type_name
description
is_active
```

Seed values:

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

# 70. Final Publication Language Master

```text
language_pk
language_code
language_name
description
is_active
```

Seed values:

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

# 71. Frozen Publication Foundation

```text
                PUBLICATION FOUNDATION
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
 nss_publication    type_master    language_master
          │
          │
          ├── Digital Document
          │
          └── Cover Document
```

---

# 72. Current Design Decision

The Publications Module does not require a separate database schema at this
stage.

The architecture is:

```text
Existing Frozen Data Foundation
             ↓
     Publications Module
             ↓
Catalogue / Search / Digital Library
```

---

# 73. Future Schema Expansion Rule

A future publication table may only be added when:

1. The business requirement is established.
2. Ownership is defined.
3. Business rules are documented.
4. ERD is updated.
5. Table design is approved.
6. Physical SQL is separately prepared.

---

# 74. Source Alignment

The publication source explicitly freezes:

```text
nss_publication v1.1
```

with the publication identity, type, date, edition, language, price,
currency, page count, ISBN, description, digital document, cover document,
digitization, free-publication flag, and audit timestamps.

The supporting masters are:

```text
publication_type_master
publication_language_master
```

with the established publication-type and language values.

---

# 75. Status

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
