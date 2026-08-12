# NSS ERP Organization Module Design

Version: 1.0

Status: DRAFT

---

# Purpose

The Organization Module represents the NSS organizational hierarchy.

All members, governance bodies, attendance records, and activities belong to an organizational unit.

---

# Organization Hierarchy

KENDRA
↓
ANCHALIKA
↓
ZILLA
↓
SAKHA

---

# Design Decision

Use a single organization table.

Do NOT create separate tables:

anchalika

zilla

sakha

kendra

---

# Why Single Table?

Benefits:

* No duplicated structure
* Easier reporting
* Simpler APIs
* Flexible future expansion
* Cleaner hierarchy management

---

# Core Tables

organization_type_master

organization_status_master

organization

organization_address

---

# organization_type_master

Purpose:

Defines organization categories.

Examples:

KENDRA

ANCHALIKA

ZILLA

SAKHA

PATHA_CHAKRA

---

# organization_status_master

Purpose:

Defines organization lifecycle status.

Examples:

ACTIVE

INACTIVE

UNDER_FORMATION

DISSOLVED

---

# organization

Purpose:

Stores all NSS organizational units.

Key Fields:

organization_pk

organization_id

organization_name

organization_type_pk

parent_organization_pk

organization_status_pk

---

# Hierarchy Rule

parent_organization_pk references organization.organization_pk

Examples:

Kendra
→ parent = NULL

Anchalika
→ parent = Kendra

Zilla
→ parent = Anchalika

Sakha
→ parent = Zilla

---

# Organization Business ID

Examples:

KD0001

AN0001

ZL0001

SK0001

Generated from:

id_sequence_master

---

# Organization Address

Each organization may have an address.

Address is stored separately.

Purpose:

Normalization

Future multiple address support

---

# Future Extensions

Possible future additions:

Organization Contact

Organization Office Bearers

Organization History

Organization Assets

Organization Buildings

---

# Design Principles

Single Organization Table

Self-Referencing Hierarchy

UUID Primary Keys

Business IDs for Users

Master Data Driven

Audit Enabled

Soft Delete Enabled
