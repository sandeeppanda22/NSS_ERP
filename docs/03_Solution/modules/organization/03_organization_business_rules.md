# NSS ERP Organization Business Rules

Version: 1.0

Status: DRAFT

---

# 1. Purpose

This document defines the business rules governing NSS organizational entities.

These rules take precedence over database implementation.

---

# 2. Organization Types

Supported organization types:

KENDRA

ANCHALIKA

ZILLA

SAKHA

PATHA_CHAKRA

---

# 3. Hierarchy Structure

Official hierarchy:

KENDRA
   ├── ANCHALIKA
   │      └── SAKHA
   │
   ├── ZILLA
   │      └── SAKHA
   │
   └── PATHA_CHAKRA

---

# 4. Root Organization Rule

There shall be only one active KENDRA organization.

KENDRA has:

parent_organization_pk = NULL

No other organization type may have a NULL parent.

---

# 5. Anchalika Rule

Every ANCHALIKA must belong to one KENDRA.

An ANCHALIKA cannot exist without a KENDRA.

---

# 6. Zilla Rule

Every ZILLA must belong to one ANCHALIKA.

A ZILLA cannot exist without an ANCHALIKA.

---

# 7. Sakha Rule

Every SAKHA must belong to one ZILLA.

A SAKHA cannot exist without a ZILLA.

---

# 8. Patha Chakra Rule

A PATHA_CHAKRA must belong to a SAKHA.

A PATHA_CHAKRA cannot exist independently.

---

# 9. Active Status Rule

Organizations may be:

ACTIVE

INACTIVE

UNDER_FORMATION

DISSOLVED

Only ACTIVE organizations may conduct operations.

---

# 10. Deactivation Rule

Organizations shall not be deleted.

Organizations may be marked:

INACTIVE

or

DISSOLVED

Historical records must remain intact.

---

# 11. Hierarchy Change Rule

Parent organization changes shall be permitted only through an approved transfer process.

Direct updates are prohibited.

All hierarchy changes must be auditable.

---

# 12. Organization Creation Rule

Organization creation authority:

KENDRA Authorized Administrators

or

Authorized Governance Officials

depending on future governance rules.

---

# 13. Organization Code Rule

Every organization must have:

organization_id

Examples:

KD0001

AN0001

ZL0001

SK0001

PC0001

Generated through:

id_sequence_master

---

# 14. Duplicate Name Rule

Organization names should be unique within the same parent organization.

Example:

Two Sakhas under the same Zilla should not share the same name.

---

# 15. Address Rule

Organizations may have an address.

Address information shall be maintained separately.

---

# 16. Historical Integrity Rule

Organization history must never be deleted.

Deactivated organizations remain available in historical reports.

---

# 17. Audit Rule

All organization changes must capture:

Created By

Updated By

Deleted By

Timestamp

Reason

---

# 18. Future Expansion Rule

Future organization types may be added without redesigning the hierarchy model.

---

# 19. Organization Principles

Single Organization Table

Hierarchy Driven

History Preserved

No Physical Delete

Audit Enabled

Master Data Driven

By-Law Governed
