# NSS ERP Organization Table Design

Version: 1.0

Status: DRAFT

---

# Purpose

This document defines the physical table structure for the Organization Module.

Business Rules and ERD must be approved before modifying this document.

---

# Table 1: organization_type_master

Purpose:

Stores NSS organization categories.

Columns:

organization_type_pk UUID PRIMARY KEY

organization_type_code VARCHAR(30) NOT NULL

organization_type_name VARCHAR(100) NOT NULL

display_order INTEGER NOT NULL

created_at TIMESTAMPTZ NOT NULL

is_active BOOLEAN NOT NULL DEFAULT TRUE

---

Unique Constraints

organization_type_code

organization_type_name

---

Seed Data

KENDRA

ANCHALIKA

ZILLA

SAKHA

PATHA_CHAKRA

---

# Table 2: organization_status_master

Purpose:

Stores organization lifecycle states.

Columns:

organization_status_pk UUID PRIMARY KEY

status_code VARCHAR(30) NOT NULL

status_name VARCHAR(100) NOT NULL

display_order INTEGER NOT NULL

created_at TIMESTAMPTZ NOT NULL

is_active BOOLEAN NOT NULL DEFAULT TRUE

---

Seed Data

ACTIVE

INACTIVE

UNDER_FORMATION

DISSOLVED

---

Unique Constraints

status_code

status_name

---

# Table 3: organization

Purpose:

Stores all NSS organizations.

Columns:

organization_pk UUID PRIMARY KEY

organization_id VARCHAR(20) NOT NULL

organization_name VARCHAR(200) NOT NULL

organization_type_pk UUID NOT NULL

parent_organization_pk UUID NULL

organization_status_pk UUID NOT NULL

established_date DATE NULL

remarks TEXT NULL

created_at TIMESTAMPTZ NOT NULL

created_by_sangha_sevi_pk UUID NULL

updated_at TIMESTAMPTZ NULL

updated_by_sangha_sevi_pk UUID NULL

deleted_at TIMESTAMPTZ NULL

deleted_by_sangha_sevi_pk UUID NULL

is_active BOOLEAN NOT NULL DEFAULT TRUE

---

Foreign Keys

organization_type_pk
→ organization_type_master

parent_organization_pk
→ organization

organization_status_pk
→ organization_status_master

---

Unique Constraints

organization_id

(parent_organization_pk, organization_name)

---

Indexes

organization_id

organization_name

organization_type_pk

parent_organization_pk

organization_status_pk

is_active

---

Business Validation Rules

KENDRA parent must be NULL

ANCHALIKA parent must be KENDRA

ZILLA parent must be KENDRA

SAKHA parent must be ANCHALIKA or ZILLA

PATHA_CHAKRA parent must be KENDRA

Only one active KENDRA allowed

---

Business ID Examples

KD0001

AN0001

ZL0001

SK0001

PC0001

Generated from id_sequence_master

---

# Table 4: organization_address

Purpose:

Stores organization address information.

Columns:

organization_address_pk UUID PRIMARY KEY

organization_pk UUID NOT NULL

address_line_1 VARCHAR(200) NOT NULL

address_line_2 VARCHAR(200) NULL

district_pk UUID NOT NULL

state_pk UUID NOT NULL

country_pk UUID NOT NULL

postal_code VARCHAR(20) NULL

created_at TIMESTAMPTZ NOT NULL

created_by_sangha_sevi_pk UUID NULL

updated_at TIMESTAMPTZ NULL

updated_by_sangha_sevi_pk UUID NULL

deleted_at TIMESTAMPTZ NULL

deleted_by_sangha_sevi_pk UUID NULL

is_active BOOLEAN NOT NULL DEFAULT TRUE

---

Foreign Keys

organization_pk
→ organization

district_pk
→ district_master

state_pk
→ state_master

country_pk
→ country_master

---

Indexes

organization_pk

district_pk

state_pk

country_pk

is_active

---

Future Tables

organization_contact

organization_document

organization_history

organization_asset

organization_office_bearer

These tables are outside Organization Module v1 scope.
