# NSS ERP — Publications Business Rules

**Document ID:** SOL-PUB-003
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Publications
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing NSS Publications.

The current Publications Module is based on the publication foundation
already frozen within Founder & Heritage.

The module provides:

- Publication catalogue
- Publication classification
- Language management
- Edition information
- Pricing information
- Digital publication support
- Digital library presentation
- Historical publication preservation

---

# 2. Scope Principle

The Publications Module shall reuse the existing publication foundation.

The following existing tables remain authoritative:

    nss_publication
    publication_type_master
    publication_language_master

The Publications Module shall not duplicate these entities.

---

# 3. Rule Identification

Publication business rules use:

    PUB-BR-001
    PUB-BR-002
    PUB-BR-003
    ...

---

# 4. Publication Identity

## PUB-BR-001 — One Publication Identity

Each publication shall have one authoritative publication identity.

The existing:

    nss_publication

table remains the publication identity source.

---

## PUB-BR-002 — No Duplicate Publication Master

The Publications Module shall not create another publication master for the
same publication identity.

---

## PUB-BR-003 — Publication ID

Each publication shall have a unique business identifier:

    publication_id

The internal database identity is:

    publication_pk

---

## PUB-BR-004 — Publication Identity Is Stable

Presentation of a publication through the Publications Module does not create
a new publication identity.

---

# 5. Publication Classification

## PUB-BR-005 — Controlled Publication Type

Every publication shall have a publication type.

Publication type shall be maintained through:

    publication_type_master

---

## PUB-BR-006 — Publication Type Vocabulary

The currently established publication types are:

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

No uncontrolled duplicate classification system shall be created.

---

## PUB-BR-007 — Type Is Not Free Text

The publication type shall reference the controlled publication type master.

The publication record shall not depend on arbitrary free-text type values.

---

# 6. Publication Language

## PUB-BR-008 — Language Is Mandatory

Every publication shall have a recorded language.

This is a frozen publication business rule.

---

## PUB-BR-009 — Controlled Language

Publication language shall be maintained through:

    publication_language_master

---

## PUB-BR-010 — Established Language Values

The current language master supports:

    ODIA
    ENGLISH
    HINDI
    BENGALI
    ASSAMESE
    TELUGU
    TAMIL
    OTHER

---

## PUB-BR-011 — No Uncontrolled Language Text

Publication language shall not be maintained as arbitrary free text when a
corresponding controlled language value exists.

---

# 7. Multilingual Publications

## PUB-BR-012 — Multilingual Publication Support

The publication framework shall support NSS publications in multiple
languages.

---

## PUB-BR-013 — Language Is Publication Metadata

Language identifies the language associated with the publication record.

It does not independently define publication identity.

---

## PUB-BR-014 — Translation Future Extension

The current model does not freeze a separate publication-translation entity.

Translation management shall require a separate approved design if needed.

---

# 8. Publication Date

## PUB-BR-015 — Publication Date

A publication may contain a publication date representing the date associated
with the publication record.

---

## PUB-BR-016 — Historical Publication Dates

Historical NSS publications shall retain their recorded publication dates.

---

# 9. Editions

## PUB-BR-017 — Multiple Editions Supported

Multiple editions of the same publication are supported.

This is a frozen publication business rule.

---

## PUB-BR-018 — Edition Number

The current publication model records:

    edition_no

for the publication record.

---

## PUB-BR-019 — Edition Is Not a Separate Frozen Entity

The current source does not establish a separate:

    publication_edition

table.

Therefore no separate edition entity is required by the current design.

---

## PUB-BR-020 — Edition Changes

An edition change shall not be interpreted automatically as creation of an
entirely unrelated publication.

The exact grouping/version semantics remain subject to future publication
design if required.

---

# 10. Pricing

## PUB-BR-021 — Publication Pricing Models

An NSS publication may be:

    FREE
    DONATION_BASED
    FIXED_PRICE

These are the currently established pricing modes.

---

## PUB-BR-022 — Free Publication

A publication may be made available without a fixed sale price.

The existing publication model supports:

    is_free_publication

---

## PUB-BR-023 — Donation-Based Publication

A publication may be offered on a donation basis.

Donation-based availability shall not automatically create a financial
transaction.

---

## PUB-BR-024 — Fixed-Price Publication

A publication may have a fixed publication price.

The price is publication metadata.

---

## PUB-BR-025 — Publication Price

Where applicable, publication price shall be stored with the publication
record.

---

## PUB-BR-026 — Currency

The publication record supports:

    currency_code

with INR as the current default currency.

---

## PUB-BR-027 — Price Is Not a Financial Transaction

The presence of a publication price does not constitute a financial
transaction.

Actual receipts, payments, sales income, and accounting belong to the
Finance domain.

---

# 11. Physical and Digital Publications

## PUB-BR-028 — Physical and Digital Coexistence

A publication may have both:

    Physical Copy

and:

    Digital Copy

This is explicitly supported by the frozen publication design.

---

## PUB-BR-029 — Physical-Only Publication

A publication may exist without a digital copy.

---

## PUB-BR-030 — Digital Publication

A publication may have a digital copy associated through the common document
framework.

---

## PUB-BR-031 — Digital Does Not Replace Physical Identity

Creating a digital copy does not create a separate publication identity.

---

# 12. Digitization

## PUB-BR-032 — Digitization Flag

The publication model supports:

    is_digitized

to indicate availability of a digital version.

---

## PUB-BR-033 — Digitized Publication

A digitized publication should have an appropriate digital document
reference.

The exact database consistency constraint belongs to physical schema
implementation.

---

## PUB-BR-034 — Digitization Does Not Alter Historical Identity

Digitizing an historical publication does not create a new publication
identity.

---

# 13. Digital Library

## PUB-BR-035 — Digital Library

The Publications Module shall support a Digital Library experience for
publications that have available digital copies.

---

## PUB-BR-036 — Digital Library Uses Existing Publications

The Digital Library shall use:

    nss_publication

as the publication source.

It shall not create a separate digital-publication master.

---

## PUB-BR-037 — Digital Document Access

Access to digital documents shall follow the common document and security
architecture.

---

## PUB-BR-038 — Digital Access Is Not Automatically Public

The current source does not establish a universal rule that all digitized
publications must be publicly downloadable.

Access policy shall be determined by the applicable authorization/publishing
rules.

---

# 14. Cover Image

## PUB-BR-039 — Publication Cover

The publication foundation supports a cover document reference:

    cover_photo_document_pk

---

## PUB-BR-040 — Cover Is Supporting Metadata

The cover image does not define publication identity.

Replacing a cover image does not create a new publication.

---

# 15. ISBN

## PUB-BR-041 — ISBN Optional

ISBN is optional.

Not every NSS publication is required to have an ISBN.

---

## PUB-BR-042 — ISBN Does Not Replace Publication ID

ISBN is an external publication identifier where applicable.

It does not replace:

    publication_id

---

# 16. Page Count

## PUB-BR-043 — Page Count

Page count may be recorded where applicable.

It is publication metadata and does not define publication identity.

---

# 17. Description

## PUB-BR-044 — Publication Description

A publication may contain a descriptive summary.

Description does not constitute a separate publication entity.

---

# 18. Historical Preservation

## PUB-BR-045 — Historical Publication Preservation

Historical NSS publications shall remain represented in the ERP where
required for heritage, research, reporting, or digital-library purposes.

---

## PUB-BR-046 — No Deletion Merely Because Publication Is Old

A publication shall not be removed merely because it is:

- Old
- Out of print
- No longer actively distributed
- Digitized
- Superseded by a later edition

---

## PUB-BR-047 — Historical Identity Preservation

Historical publication identity and metadata shall remain traceable.

---

# 19. Founder & Heritage Boundary

## PUB-BR-048 — Heritage Publication Foundation

The existing Founder & Heritage publication tables remain authoritative.

---

## PUB-BR-049 — Publications Functional Boundary

The Publications Module provides the dedicated publication-oriented
experience over that foundation.

---

## PUB-BR-050 — No Data Duplication

Moving publication presentation into a dedicated module shall not duplicate
the underlying publication records.

---

# 20. UPBS Souvenirs

## PUB-BR-051 — UPBS Souvenir Classification

UPBS Souvenir is a supported publication type:

    UPBS_SOUVENIR

---

## PUB-BR-052 — UPBS Operational Boundary

The Publications Module manages the publication record/catalogue.

The UPBS Module remains responsible for UPBS event operations.

---

## PUB-BR-053 — No UPBS Data Duplication

The Publications Module shall not duplicate:

- UPBS Event
- Registration
- Delegate
- Accommodation
- Prasad
- Committee
- Volunteer operations

---

# 21. Finance Boundary

## PUB-BR-054 — Finance Owns Transactions

Actual publication financial transactions belong to Finance.

---

## PUB-BR-055 — Publication Income

Publication sales may generate publication income.

The Publications Module shall not maintain a parallel financial ledger.

---

## PUB-BR-056 — Price and Income Are Different

The following are distinct:

    Publication Price
        =
    Publication Metadata

    Publication Income
        =
    Financial Transaction

---

# 22. Inventory Boundary

## PUB-BR-057 — Inventory Not Currently Frozen

The current publication source does not establish a frozen inventory model.

Therefore the Publications Module does not currently maintain:

- Stock quantity
- Warehouse
- Store
- Stock movement
- Inventory adjustment

---

## PUB-BR-058 — Future Inventory

If publication inventory becomes an approved requirement, it shall be
designed separately.

It shall not be introduced implicitly into the current publication tables.

---

# 23. Distribution Boundary

## PUB-BR-059 — Distribution Not Currently Frozen

The current source does not establish a frozen publication distribution
workflow.

No distribution entity is introduced by the current design.

---

## PUB-BR-060 — Future Distribution

Distribution may be introduced through a future approved design.

---

# 24. Subscription Boundary

## PUB-BR-061 — Subscription Not Currently Frozen

The current source does not establish a frozen publication subscription
system.

No subscription entity is introduced by the current design.

---

## PUB-BR-062 — Future Subscription

If subscriptions become an approved requirement, they shall be designed as
a separate operational capability.

---

# 25. Order Boundary

## PUB-BR-063 — Order Management Not Currently Frozen

The current Publications design does not establish:

    publication_order
    publication_order_item

entities.

---

## PUB-BR-064 — Future Orders

Publication ordering may be introduced later through approved requirements.

---

# 26. Author Boundary

## PUB-BR-065 — Author Management Not Currently Frozen

The current source does not freeze:

    publication_author

as a current publication table.

---

## PUB-BR-066 — Future Author Management

If author management becomes necessary, the future design should consider
reuse of the common Person identity where applicable.

---

# 27. Translation Boundary

## PUB-BR-067 — Translation Management Not Currently Frozen

The current model supports multilingual publications through language
classification.

It does not currently establish a separate translation relationship.

---

# 28. Publication Search

## PUB-BR-068 — Publication Search

The Publications Module should support search using available publication
metadata.

Potential search attributes include:

- Publication ID
- Title
- Type
- Language
- Publication Date
- Edition
- ISBN
- Digital Availability

---

## PUB-BR-069 — Controlled Filtering

Type and language filtering shall use the corresponding master tables.

---

# 29. Publication Catalogue

## PUB-BR-070 — Catalogue

The Publications Module shall provide a catalogue representation of
available publication records.

The catalogue uses the existing publication foundation.

---

# 30. Publication Detail

## PUB-BR-071 — Publication Detail

A publication detail view may present:

- Title
- Type
- Language
- Publication Date
- Edition
- Price
- ISBN
- Page Count
- Description
- Digital availability
- Cover

---

# 31. Access Control

## PUB-BR-072 — Common Authorization

Publication administration shall use the common NSS ERP authorization and
RBAC framework.

---

## PUB-BR-073 — No Independent Publication Permission Framework

The Publications Module shall not create a separate permission system.

---

# 32. Audit

## PUB-BR-074 — Publication Changes Auditable

Publication creation and material changes shall follow the common audit
framework.

---

## PUB-BR-075 — Digital Document Changes Auditable

Changes affecting publication digital documents shall follow the common
document/audit framework.

---

# 33. Data Integrity

## PUB-BR-076 — Valid Publication Type

Every publication shall reference a valid publication type.

---

## PUB-BR-077 — Valid Publication Language

Every publication shall reference a valid publication language.

---

## PUB-BR-078 — Language Mandatory

A publication without a valid language is invalid.

---

## PUB-BR-079 — Valid Document References

Where digital or cover documents are supplied, references shall point to
valid document records.

---

# 34. Publication Identity Invariants

## PUB-BR-080 — Publication Identity Invariant

The following shall remain true:

    One Publication
        ↓
    One publication_pk
        +
    One publication_id

---

## PUB-BR-081 — Digital Copy Does Not Create Publication

Adding a digital copy shall not create another publication.

---

## PUB-BR-082 — Cover Change Does Not Create Publication

Changing a cover image shall not create another publication.

---

## PUB-BR-083 — Price Change Does Not Create Publication

Changing the price does not automatically create another publication.

Where an edition-specific price is required, edition rules apply.

---

## PUB-BR-084 — Metadata Correction Does Not Create Publication

Correcting title, description, language, or other metadata does not
automatically create another publication.

---

# 35. Publication Edition Invariants

## PUB-BR-085 — Editions Are Supported

Multiple editions may exist.

---

## PUB-BR-086 — Edition Does Not Automatically Mean New Publication

An edition represents a version/edition of a publication concept under the
current model.

The precise grouping mechanism is not separately frozen.

---

# 36. Future Extension Governance

## PUB-BR-087 — New Publication Entity Requires Approval

A new publication-related table shall not be added merely because a
potential feature is desirable.

---

## PUB-BR-088 — Future Operational Capability

Any future:

- Inventory
- Distribution
- Subscription
- Order
- Delivery
- Author
- Translation
- Digital licensing

capability shall undergo separate requirements and solution design.

---

# 37. Prohibited Patterns

## PUB-BR-089 — No Duplicate Publication Master

Do not create a second publication master representing the same identity.

---

## PUB-BR-090 — No Free-Text Type Duplication

Do not create a second uncontrolled publication-type classification.

---

## PUB-BR-091 — No Free-Text Language Duplication

Do not bypass the publication language master with arbitrary language values.

---

## PUB-BR-092 — No Finance Duplication

Do not create publication financial transactions inside the Publications
Module.

---

## PUB-BR-093 — No UPBS Duplication

Do not duplicate UPBS operational records in Publications.

---

# 38. Current Frozen Rules Summary

The following publication rules are directly supported by the existing frozen
publication foundation:

```text
✓ Language is mandatory

✓ Publication type is controlled

✓ Publication language is controlled

✓ Multiple publication languages are supported

✓ Publications may be FREE

✓ Publications may be DONATION_BASED

✓ Publications may have FIXED_PRICE

✓ Currency is recorded

✓ INR is the default currency

✓ Physical and digital copies may coexist

✓ Digital copies may be associated with publications

✓ Cover images may be associated

✓ Multiple editions are supported

✓ ISBN is optional

✓ Page count is supported

✓ Publication description is supported

✓ Digitization status is supported

✓ Free-publication status is supported

✓ UPBS Souvenir is a publication type

✓ Historical publications are preserved

✓ Publication identity is not duplicated

✓ Publications reuse the Heritage publication foundation
```

---

# 39. Current Non-Frozen Areas

The following are deliberately not treated as frozen business rules:

```text
Inventory Management
Stock Movement
Warehouse Management
Distribution Workflow
Subscription Workflow
Order Management
Delivery Workflow
Author Management
Translation Management
Digital Licensing
Publication Status Lifecycle
```

---

# 40. Current Table Impact

These business rules do not introduce new tables.

Current publication foundation remains:

```
nss_publication
publication_type_master
publication_language_master
```

New Publications tables:

```
0
```

---

# 41. Traceability

| Rule Area            | Governing Source                                   |
| -------------------- | -------------------------------------------------- |
| Publication identity | Existing Founder & Heritage publication foundation |
| Publication type     | `publication_type_master`                          |
| Publication language | `publication_language_master`                      |
| Mandatory language   | Frozen publication business rules                  |
| Pricing models       | Frozen publication business rules                  |
| Digital + physical   | Frozen publication business rules                  |
| Multiple editions    | Frozen publication business rules                  |
| Digital copy         | Existing `nss_publication` design                  |
| Cover image          | Existing `nss_publication` design                  |
| UPBS Souvenir        | Existing publication type framework                |
| Finance boundary     | Common Finance architecture                        |
| Document boundary    | Common Document Management architecture            |

---

# 42. Final Publication Model

The current business model is:

```
PUBLICATION
      │
      ├── TYPE
      ├── LANGUAGE
      ├── DATE
      ├── EDITION
      ├── PRICE
      ├── ISBN
      ├── DESCRIPTION
      ├── DIGITAL COPY
      └── COVER
```

with:

```
Physical + Digital
    = Supported
```

and:

```
Free + Donation + Fixed Price
    = Supported
```

---

# 43. Status

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
