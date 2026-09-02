# NSS ERP — Bootstrap Architecture

**Document ID:** SOL-ARCH-011
**Version:** 1.0.0
**Status:** FROZEN
**Date:** 2026-09-02
**Parent Documents:**
- SOL-ARCH-010 — DDL Creation Order
- SOL-ARCH-008 — Implementation Dependency Order
- SOL-ADMIN-004 — Administration Table Design (§8.7–8.10)
- SOL-AUTH-004 — Authentication & Security Table Design

**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the ERP database bootstrap architecture — the
sequence in which the initial database is built, RBAC definitions are
established, and the first administrator account is created.

The bootstrap architecture resolves a circular dependency: audited
operations require an accountable actor, but that actor's identity
requires tables that don't yet exist during initial database creation.

---

# 2. Core Principle

`NSS_ADMIN` is the **system-wide ERP administrator role**. It is an
RBAC role defined in `role_master` and is not itself a person, Sangha
Sevi, or user account. The role is assigned through `user_role` to an
authorized Sangha Sevi's ERP user account.

```text
Sangha Sevi (real person)
  ↓
user_account
  ↓
user_role → NSS_ADMIN role
  ↓
admin_scope → NSS-wide
  ↓
ALL ERP PERMISSIONS
```

There is no fake, system, or placeholder actor. The initial
administrator is a real Sangha Sevi who has been assigned the
`NSS_ADMIN` role. The audit trail identifies the specific Sangha
Sevi, not the role itself.

If multiple administrators need all-access:

```text
Sangha Sevi A → user_account A → NSS_ADMIN
Sangha Sevi B → user_account B → NSS_ADMIN
```

Both have all ERP permissions, but the audit trail remains
distinguishable:

```text
Change #1001  created_by_sangha_sevi_pk = A
Change #1002  created_by_sangha_sevi_pk = B
```

---

# 3. NSS_ADMIN Permission Model

`NSS_ADMIN` receives all **ERP application permissions** through the
**normalized RBAC model**, not through a hard-coded application bypass.

`NSS_ADMIN` does not automatically confer unrestricted PostgreSQL
database access. The PostgreSQL `nss_admin` role remains a separate
technical security boundary (see §7.2).

```text
NSS_ADMIN role
    ↓
role_permission (all approved permissions)
    ↓
permission_master
```

If a new permission is introduced later, the Administration model
explicitly assigns it to `NSS_ADMIN` through `role_permission`.
Application code shall not contain:

```text
if role == NSS_ADMIN then bypass_all_checks
```

This keeps the authorization model auditable and consistent.

---

# 4. Bootstrap Sequence

## Phase 0 — Bootstrap RBAC Definitions

Create the three RBAC definition tables and seed their data.

These tables have **zero FK dependencies** on Foundation, Organization,
or Person (SOL-ARCH-010: `role_master` Depth 0 #13, `permission_master`
Depth 0 #14, `role_permission` Depth 1 #20).

```text
DDL:
  role_master              (Depth 0)
  permission_master        (Depth 0)
  role_permission          (Depth 1)

Seed:
  permission catalogue
  7 frozen roles
  role-permission mappings
```

No user accounts, no user-role assignments, no scopes at this phase.

## Phase 1 — Extensions + Foundation DDL

```text
DDL:
  PostgreSQL extensions (pgcrypto, pg_trgm, btree_gin)
  12 Foundation tables (Depths 0–4)

Seed:
  Foundation reference data
```

Already implemented.

## Phase 2 — Organization DDL

```text
DDL:
  3 Organization tables (Depths 0–3)

Seed:
  8 organization types
  6 organization statuses
  3 unique root organizations (KEN, NKT, SMR)
```

Already implemented.

## Phase 3 — Person + Sangha Sevi

```text
DDL:
  person                   (Depth 2)
  sangha_sevi              (Depth 4)

Seed:
  Bootstrap administrator's Person record
  Bootstrap administrator's Sangha Sevi identity
```

Person module design is pending (person_id vs person_code, address
model, Aadhaar/photo model not yet frozen).

## Phase 4 — Remaining Auth/Admin Tables

```text
DDL:
  user_account             (Depth 3, FK → person)
  password_history         (Depth 4, FK → user_account)
  user_role                (Depth 4, FK → user_account + role_master)
  admin_scope              (Depth 4, FK → user_account + role_master + organization)
```

These tables cannot be created earlier because of their FK
dependencies on Person and Organization.

## Phase 5 — Bootstrap NSS_ADMIN Role Assignment

```text
Seed:
  user_account record for designated administrator
  user_role assignment → NSS_ADMIN role
  admin_scope → NSS-wide / all-access scope
  Initial password (Argon2 hash, securely supplied — never in Git)
```

After this phase, the ERP has an accountable administrator — a real
Sangha Sevi assigned the `NSS_ADMIN` role.

## Phase 6 — Pass 2 Audit-Actor FK Constraints

```text
ALTER TABLE:
  Add *_by_sangha_sevi_pk FK constraints to all tables
  (SOL-ARCH-010 §5)
```

Precondition: `sangha_sevi` contains at least one record (the
bootstrap administrator).

## Phase 7+ — Remaining Modules

```text
Membership
Heritage
Family
Attendance
Governance
...
```

All subsequent ERP operations are attributable to the authenticated
ERP user and corresponding Sangha Sevi identity. Controlled deployment
and seed operations remain database-installation activities and shall
not be represented as fictitious Sangha Sevi actions.

---

# 5. Directory Structure

```text
database/
├── ddl/
│   ├── 00_bootstrap/            RBAC definition tables
│   │   ├── 01_role_master.sql
│   │   ├── 02_permission_master.sql
│   │   └── 03_role_permission.sql
│   │
│   ├── 01_foundation/           Foundation tables (IMPLEMENTED)
│   ├── 02_organization/         Organization tables (IMPLEMENTED)
│   └── ...
│
└── seed/
    ├── 00_bootstrap/            RBAC seed data
    │   ├── 01_permission_master.sql
    │   ├── 02_role_master.sql
    │   └── 03_role_permission.sql
    │
    ├── 01_foundation/           Foundation seed (IMPLEMENTED)
    ├── 02_organization/         Organization seed (IMPLEMENTED)
    └── ...
```

---

# 6. Two-Pass DDL Strategy Integration

The existing two-pass strategy (SOL-ARCH-010 §5) remains unchanged:

```text
Pass 1:
  CREATE TABLE statements — audit-actor columns exist but
  *_by_sangha_sevi_pk FK constraints are NOT enforced

Pass 2:
  After NSS_ADMIN Sangha Sevi exists →
  ALTER TABLE ADD CONSTRAINT for all *_by_sangha_sevi_pk FKs
```

The bootstrap architecture determines WHEN the Sangha Sevi actor
becomes available (Phase 3/5). The two-pass strategy determines
HOW the audit FKs are deferred until that point.

---

# 7. Credential Security

**No credentials shall be stored in Git.**

The bootstrap seed scripts create the `user_account` row structure
but the initial password hash is supplied through a secure mechanism
at deployment time:

```text
Option A: Environment variable at deployment
Option B: Secure parameter store
Option C: Interactive prompt during bootstrap script
```

The exact mechanism is an operational decision, not a schema decision.

The seed scripts in Git shall contain:

```sql
-- Password hash supplied at deployment time
-- DO NOT commit actual password hashes to version control
```

---

## 7.1 NSS_ADMIN Account Bootstrap Procedure

The initial `NSS_ADMIN` role assignment shall be created only after the
designated administrator has a valid Person and Sangha Sevi identity.

`NSS_ADMIN` is not a PostgreSQL database login and is not a synthetic
system actor. It is an ERP RBAC role assigned to a real Sangha Sevi's
user account through `user_role`.

The bootstrap process is:

```text
1. Establish Person
       ↓
2. Establish Sangha Sevi identity
       ↓
3. Create user_account
       ↓
4. Assign NSS_ADMIN through user_role
       ↓
5. Establish NSS-wide administrative scope
       ↓
6. Establish initial credential securely
       ↓
7. Authenticate as NSS_ADMIN
       ↓
8. Perform subsequent ERP administration and transactions
```

**Step 1 — Create the bootstrap administrator's Person.** Create the
Person record for the individual designated to operate the initial ERP
administration. The Person record must be a normal ERP Person record.
It must not be marked as a special system or bootstrap person. The
exact Person schema is governed by the Person module design.

**Step 2 — Create the Sangha Sevi identity.** Create the corresponding
Sangha Sevi identity using the normal Membership/Sangha Sevi identity
model. The resulting `sangha_sevi_pk` becomes the authoritative ERP
identity of the administrator. No artificial Sangha Sevi identity shall
be created for database bootstrap purposes.

**Step 3 — Create the ERP user account.** Create a `user_account`
record referencing the administrator's Person identity. The account is
an ERP authentication identity, distinct from the PostgreSQL `nss_admin`
database role. The account shall not contain embedded role or permission
information.

**Step 4 — Assign the NSS_ADMIN role.** Create the `user_role`
assignment linking the user account to the `NSS_ADMIN` role. The role
obtains its authorization through the normalized `role_permission` model.
No application-level bypass shall be used.

**Step 5 — Establish NSS-wide administrative scope.** Create the
`admin_scope` record for the bootstrap administrator. The scope
represents NSS-wide/system-level administration. `NSS_ADMIN` is not
restricted to an individual Sakha, Zilla, Anchalika, or other
organizational scope.

**Step 6 — Establish the initial credential.** The initial credential
shall be supplied through the secure deployment mechanism defined by
the credential-security policy. The credential or password hash shall
never be committed to Git.

**Step 7 — Authenticate as NSS_ADMIN.** The administrator authenticates
through the normal ERP authentication mechanism. The authenticated ERP
session establishes the current Sangha Sevi actor:

```text
Authenticated User → user_account → Person → Sangha Sevi → sangha_sevi_pk
```

**Step 8 — Perform subsequent ERP transactions.** All subsequent
administrative operations are executed under the authenticated
`NSS_ADMIN` identity.

---

## 7.2 Database Installation vs ERP Transactions

The following identities are deliberately distinct:

| Identity | Purpose |
|----------|---------|
| PostgreSQL `nss_admin` | Executes DDL, schema installation and controlled database seed scripts |
| ERP `NSS_ADMIN` | Real Sangha Sevi and all-access ERP administrator |
| ERP `user_account` | Authentication identity used by the ERP |
| Sangha Sevi identity | Authoritative business/person identity used for audit attribution |

```text
PostgreSQL nss_admin  ≠  ERP NSS_ADMIN
```

The PostgreSQL account establishes the database environment. The ERP
`NSS_ADMIN` account performs authenticated business operations.

Where initialization SQL must establish records before the
administrator's Sangha Sevi identity exists, those records are part of
the controlled bootstrap process and are not represented as having
been performed by a fictitious Sangha Sevi.

---

## 7.3 Initialization and Audit Transition

```text
Phase 0–2: No Sangha Sevi exists
           Audit-actor columns exist but FKs not enforced
           Records created by PostgreSQL nss_admin (schema installation)

Phase 3:   NSS_ADMIN Sangha Sevi identity becomes available

Phase 5:   NSS_ADMIN user account + role + scope established

Phase 6:   Pass 2 audit-actor FKs enforced
           Precondition: sangha_sevi contains at least one record

Phase 7+:  Normal authenticated ERP operations
           All audit-actor columns populated by application
```

The two-pass strategy does not require earlier bootstrap records to
invent an actor identity that did not yet exist.

---

## 7.4 Creating Additional ERP Users

Once authenticated as `NSS_ADMIN`, the administrator creates
subsequent ERP users through Administration functionality:

```text
NSS_ADMIN
   ↓
Create/identify Person → Sangha Sevi
   ↓
Create user_account
   ↓
Assign appropriate role(s)
   ↓
Assign admin_scope where required
   ↓
User authenticates → authorized ERP operations
```

Every subsequent user receives only the roles and organizational
scopes authorized for that user. Ordinary users shall not receive
all permissions merely because they are Sangha Sevies.

---

## 7.5 Audit Attribution of ERP Operations

For an authenticated ERP transaction:

```text
ERP Session → user_account → Sangha Sevi → Audit Actor
```

The authenticated Sangha Sevi identity is the business actor recorded
in audit metadata:

```text
created_by_sangha_sevi_pk = <authenticated actor>
updated_by_sangha_sevi_pk = <authenticated actor>
deleted_by_sangha_sevi_pk = <authenticated actor>
```

The centralized `field_change_log` likewise records the applicable
change actor according to its final physical design.

The audit trail answers: **WHO** (which Sangha Sevi), **WHAT** (which
record/field changed), **WHEN** (timestamp).

The PostgreSQL database login used to establish the schema is not a
substitute for the ERP business actor.

---

## 7.6 Seed Data vs ERP Transactions

Controlled deployment seed scripts and normal ERP transactions are
different execution contexts:

| Context | Actor | Purpose |
|---------|-------|---------|
| Controlled deployment | PostgreSQL `nss_admin` | DDL, reference-data seed |
| Normal ERP operation | Authenticated ERP user | Business transactions with audit attribution |

Seed scripts shall not assume a real ERP user exists before the
bootstrap identity has been created. After the bootstrap administrator
exists, administrative and operational data changes performed through
the ERP shall be executed through the authenticated application
identity and recorded against the corresponding Sangha Sevi actor.

---

## 7.7 Transition from Database Bootstrap to Authenticated Operations

The PostgreSQL `nss_admin` account is used **only** for controlled
schema installation and bootstrap operations. Once the real Sangha
Sevi identity and ERP `NSS_ADMIN` account have been established,
subsequent business/master-data creation and operational transactions
shall be performed through the authenticated ERP application as
`NSS_ADMIN`, so that the resulting audit trail identifies the
responsible Sangha Sevi.

The transition point is:

```text
Phase 0–4:  PostgreSQL nss_admin
            Controlled schema + seed operations
            No ERP user exists yet
            Audit-actor columns NULL or unpopulated

            ─── TRANSITION POINT ───

Phase 5:    NSS_ADMIN ERP account created
            Authenticated ERP session available

Phase 6+:   ERP NSS_ADMIN
            All subsequent data operations through application
            Audit-actor columns populated by application
            created_by_sangha_sevi_pk = NSS_ADMIN Sangha Sevi
```

After the transition:

- Module setup and configuration → through ERP as `NSS_ADMIN`
- Master data creation/maintenance → through ERP as `NSS_ADMIN`
- Organizational data operations → through ERP as `NSS_ADMIN`
- User creation and role assignment → through ERP as `NSS_ADMIN`
- All operational transactions → through authenticated ERP user

The PostgreSQL `nss_admin` login remains available for future schema
migrations (DDL changes, new module tables, index additions), but
shall not be used for business data operations once the ERP
application layer is operational.

---

# 8. Frozen Decisions

| Decision | Status | Source |
|----------|--------|--------|
| NSS_ADMIN is an RBAC role, not an identity | FROZEN | SOL-ARCH-011 §2 |
| NSS_ADMIN = all ERP application permissions (not DB access) | FROZEN | SOL-ARCH-011 §3 |
| Phase 0 bootstrap (3 RBAC tables before Foundation) | FROZEN | SOL-ARCH-011 §4 |
| Directory: `00_bootstrap/` | FROZEN | SOL-ARCH-011 §5 |
| No credentials in Git | FROZEN | SOL-ARCH-011 §7 |
| PostgreSQL nss_admin ≠ ERP NSS_ADMIN | FROZEN | SOL-ARCH-011 §7.2 |
| Seed data ≠ ERP transactions (distinct audit contexts) | FROZEN | SOL-ARCH-011 §7.6 |
| Post-bootstrap operations via authenticated NSS_ADMIN | FROZEN | SOL-ARCH-011 §7.7 |
| 7 frozen roles (SOL-ADMIN-004 §8.7) | FROZEN | SOL-ADMIN-004 |
| SELF_SERVICE_MEMBER excluded | FROZEN | SOL-ADMIN-004 §8.10 |
| Permission catalogue | PENDING | Not yet frozen |
| Person schema | PENDING | Not yet frozen |
| Bootstrap administrator identity | PENDING | Real Sangha Sevi to receive NSS_ADMIN TBD |
| Privileged DB access via ERP (MFA-controlled) | FUTURE | SOL-ARCH-012 (not yet created) |

---

# 9. What This Document Does NOT Do

- Does not define column-level schema for any table
- Does not create the permission catalogue
- Does not identify the specific person who will be the initial NSS_ADMIN
- Does not generate PostgreSQL DDL
- Does not override SOL-ARCH-010 table depth/sequence assignments
- Does not change the two-pass audit FK strategy
- Does not define MFA-controlled privileged database access
  (deferred to future SOL-ARCH-012)

---

# 10. Status

```text
DOCUMENT STATUS:
FROZEN

DOCUMENT ID:
SOL-ARCH-011

VERSION:
1.0.0

BOOTSTRAP PHASES:
8 (Phase 0 through Phase 7+)

PHASE 0 TABLES:
3 (role_master, permission_master, role_permission)

CREDENTIAL POLICY:
No credentials in Git

NEXT:
Freeze column-level design for Phase 0 tables
```
