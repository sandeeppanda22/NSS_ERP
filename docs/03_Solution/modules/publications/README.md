# NSS ERP Publications Module

Status: DRAFT — SOURCE ALIGNED + USER REQUIREMENTS, v1.0.0. Full Solution design complete (7
files) — the most extensive doc set of any module added this pass; there is no
`backend/publications/` Django app.

---

## Documents

01_publications_module_overview.md (`SOL-PUB-001`) — Version 1.0.0
Purpose: Structured catalogue/discovery/presentation of NSS publications (Books, Magazines,
Journals), built on the existing Founder & Heritage publication foundation.

02_publications_erd.md — Version 1.0.0
Purpose: Entity relationship design — reuses Heritage's publication entities rather than
duplicating them.

03_publications_business_rules.md — Version 1.0.0, PUB-BR-001–PUB-BR-093
Purpose: Business rules for catalogue browsing, Digital Library, and price display.

04_publications_table_design.md — Version 1.0.0
Purpose: Physical table design — **zero new tables**; see Key facts.

05_publications_functional_design.md — Version 1.0.0
Purpose: Functional design for the member-facing catalogue.

06_publications_ui_workflow.md — Version 1.0.0, PUB-FR-001–PUB-FR-023
Purpose: UI/workflow spec — year/category/language browsing, Digital Library.

07_publication_notification_purchase_design.md — Version 1.0.0, PUB-BUY-001–PUB-BUY-015
Purpose: New-book-launch notifications via the common notification framework, and a future
Buy/Purchase workflow — explicitly deferred, not frozen.

---

## Key facts

- **Zero new tables.** Publications reuses the Founder & Heritage tables
  (`nss_publication`, `publication_type_master`, `publication_language_master` — see
  `docs/03_Solution/modules/heritage/`) rather than inventing its own.
- Member-facing catalogue: browse by year/category/language, Digital Library, price display
  (free/donation/fixed-price, matching Heritage's v1.1 publication model).
- Future Buy/Purchase workflow is explicitly deferred/not frozen (PUB-BUY series).

---

## Current Status

Design Complete · ERD Complete · Business Rules Drafted (SOURCE ALIGNED + USER REQUIREMENTS) ·
Table Design Drafted (zero new tables) · Functional/UI/Notification design drafted · SQL
Implementation Not Started (rides on Heritage's tables, which are themselves not implemented
beyond `founder_master`) · `backend/publications/` Django app does not exist yet
