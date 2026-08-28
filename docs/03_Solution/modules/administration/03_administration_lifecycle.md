# NSS ERP — Administration Lifecycle

**Document ID:** SOL-ADMIN-005  
**Version:** 0.1.0  
**Status:** DRAFT  
**Module:** Administration  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle states and transitions for the
Administration Module entities:

- `role_master`
- `permission_master`
- `role_permission`
- `user_role`
- `admin_scope`

The Administration lifecycle covers authorization management only.
The `user_account` lifecycle (account creation, locking, deactivation)
is owned by the Authentication & Security Module and defined there
(SOL-AUTH-005).

---

# 2. Source Authority

This lifecycle document is governed by:

- Administration Module Overview (SOL-ADMIN-001)
- Administration ERD (SOL-ADMIN-002)
- Administration Business Rules (SOL-ADMIN-003)
- Administration Table Design (SOL-ADMIN-004)
- Authentication & Security Lifecycle (SOL-AUTH-005)
- Common project audit/soft-delete standards

Where conflict exists, the source document with the later frozen date
prevails.

---

# 3. Role Master — Lifecycle States

```text
ACTIVE          Role is operationally current and assignable
INACTIVE        Role is deactivated; no new assignments permitted
```

---

# 4. Role Master State Definitions

## ACTIVE

The role is operationally current. It may be assigned to users through
`user_role` and may have permissions mapped through `role_permission`.

## INACTIVE

The role is deactivated. No new user-role assignments should reference
this role. The role record remains physically present for historical
accountability. Existing historical `user_role` and audit records
referencing this role remain interpretable (ADMIN-BR-049, ADMIN-BR-066,
ADMIN-BR-068).

---

# 5. Role Master State Transition Diagram

```text
              CREATED (Role Definition)
                     |
                     v
                  ACTIVE
                 /       \
    Normal ops  /         \  Deactivation
               v           v
           ACTIVE       INACTIVE
                           |
                      Reactivation (authorized)
                           |
                           v
                        ACTIVE
```

---

# 6. Transition: Role Creation -> ACTIVE

**Trigger:** New application role defined by authorized administrator

**Preconditions:**
- Authorized administrative user (ADMIN-BR-051)
- Role code/name is unique (Table Design Section 8.5)
- Role is a reusable authorization grouping, not a label for an
  individual person (ADMIN-BR-009)

**Effects:**
- `role_master_pk` assigned (UUID)
- Role state = ACTIVE
- `created_at` = current timestamp
- `created_by_sangha_sevi_pk` = creating authority

**Constraints:**
- Governance positions do not automatically become roles (ADMIN-BR-013)
- Membership statuses do not automatically become roles (ADMIN-BR-064)

**Audit:** Role creation is auditable (ADMIN-BR-051)

---

# 7. Transition: ACTIVE -> ACTIVE (Role Update)

**Trigger:** Role attributes updated (description, display name)

**Preconditions:**
- Role is ACTIVE
- Authorized administrative user
- Role code uniqueness maintained

**Effects:**
- Attribute(s) updated
- `updated_at` = current timestamp
- Role identity (`role_master_pk`) unchanged

**Constraints:**
- Update does not rewrite historical audit records (ADMIN-BR-066)

---

# 8. Transition: ACTIVE -> INACTIVE (Role Deactivation)

**Trigger:** Role deactivated by authorized administrator

**Preconditions:**
- Authorized administrative user
- Business justification exists

**Effects:**
- Role state = INACTIVE
- `updated_at` = current timestamp

**Constraints:**
- Does not physically delete the role record (ADMIN-BR-067, ADMIN-BR-068)
- Historical `user_role` assignments remain interpretable (ADMIN-BR-049)
- Historical `role_permission` mappings remain interpretable
- Historical audit records referencing this role remain unchanged (ADMIN-BR-066)
- Does not silently destroy `role_permission` rows (Table Design Section 10.5)

---

# 9. Transition: INACTIVE -> ACTIVE (Role Reactivation)

**Trigger:** Authorized reversal of role deactivation

**Preconditions:**
- Authorized administrative user
- Business justification exists

**Effects:**
- Role state = ACTIVE
- `updated_at` = current timestamp

---

# 10. Permission Master — Lifecycle States

```text
ACTIVE          Permission is operationally current and assignable
INACTIVE        Permission is deactivated; no new assignments permitted
```

---

# 11. Permission Master State Definitions

## ACTIVE

The permission is operationally current. It may be assigned to roles
through `role_permission`. Business modules may reference this permission
in authorization checks.

## INACTIVE

The permission is deactivated. No new `role_permission` mappings should
reference this permission. The permission record remains physically present
for historical accountability. Historical authorization evidence remains
interpretable (ADMIN-BR-068).

---

# 12. Permission Master State Transition Diagram

```text
              CREATED (Permission Definition)
                     |
                     v
                  ACTIVE
                 /       \
    Normal ops  /         \  Deactivation
               v           v
           ACTIVE       INACTIVE
                           |
                      Reactivation (authorized)
                           |
                           v
                        ACTIVE
```

---

# 13. Transition: Permission Creation -> ACTIVE

**Trigger:** New application permission defined by authorized administrator

**Preconditions:**
- Authorized administrative user (ADMIN-BR-051)
- Permission code/name is unique
- Permission is centrally defined (ADMIN-BR-003, ADMIN-BR-017)
- No module-specific permission table created (ADMIN-BR-002)

**Effects:**
- `permission_master_pk` assigned (UUID)
- Permission state = ACTIVE
- `created_at` = current timestamp
- `created_by_sangha_sevi_pk` = creating authority

**Audit:** Permission creation is auditable (ADMIN-BR-051)

---

# 14. Transition: ACTIVE -> ACTIVE (Permission Update)

**Trigger:** Permission attributes updated (description, module/domain label)

**Preconditions:**
- Permission is ACTIVE
- Authorized administrative user

**Effects:**
- Attribute(s) updated
- `updated_at` = current timestamp
- Permission identity (`permission_master_pk`) unchanged

**Constraints:**
- Update does not rewrite historical audit records (ADMIN-BR-066)

---

# 15. Transition: ACTIVE -> INACTIVE (Permission Deactivation)

**Trigger:** Permission deactivated by authorized administrator

**Preconditions:**
- Authorized administrative user
- Business justification exists

**Effects:**
- Permission state = INACTIVE
- `updated_at` = current timestamp

**Constraints:**
- Does not physically delete the permission record (ADMIN-BR-067, ADMIN-BR-068)
- Historical `role_permission` mappings remain interpretable
- Historical audit records referencing this permission remain unchanged (ADMIN-BR-066)

---

# 16. Transition: INACTIVE -> ACTIVE (Permission Reactivation)

**Trigger:** Authorized reversal of permission deactivation

**Preconditions:**
- Authorized administrative user
- Business justification exists

**Effects:**
- Permission state = ACTIVE
- `updated_at` = current timestamp

---

# 17. Role-Permission — Lifecycle

`role_permission` is a mapping table representing the assignment of
permissions to roles.

## States

```text
ASSIGNED        Mapping exists and is active
REVOKED         Mapping deactivated or removed
```

---

# 18. Transition: Role-Permission Assignment

**Trigger:** Permission assigned to a role

**Preconditions:**
- Role is ACTIVE
- Permission is ACTIVE
- No duplicate active mapping for same role + permission (Table Design Section 10.4)
- Authorized administrative user (ADMIN-BR-019)

**Effects:**
- `role_permission_pk` assigned (UUID)
- `role_master_pk` = target role
- `permission_master_pk` = target permission
- `created_at` = current timestamp
- `created_by_sangha_sevi_pk` = assigning authority

**Constraints:**
- Permissions are reusable across roles (ADMIN-BR-016)

**Audit:** Permission assignment is auditable (ADMIN-BR-051)

---

# 19. Transition: Role-Permission Revocation

**Trigger:** Permission removed from a role

**Preconditions:**
- Active mapping exists for this role + permission
- Authorized administrative user

**Effects:**
- Mapping deactivated (soft-delete or state change)
- `updated_at` = current timestamp

**Constraints:**
- Does not rewrite historical audit records (ADMIN-BR-020, ADMIN-BR-066)
- Historical authorization evidence preserved (ADMIN-BR-068)
- Revocation affects future effective access through this role
  (ADMIN-BR-020)

**Audit:** Permission revocation is auditable (ADMIN-BR-051)

---

# 20. User-Role — Lifecycle

`user_role` is a mapping table representing the assignment of roles
to user accounts.

## States

```text
ASSIGNED        Mapping exists and is active
REVOKED         Mapping deactivated or removed
```

Note: The source does not freeze a separate `role_history` table
(ADMIN-BR-070). If effective-dated assignment history is required,
it must be separately approved (Table Design Section 11.5).

---

# 21. Transition: User-Role Assignment

**Trigger:** Role assigned to a user account

**Preconditions:**
- User account exists (ADMIN-BR-004)
- Role is ACTIVE
- No duplicate active assignment for same user + role (Table Design Section 11.4)
- Authorized administrative user (ADMIN-BR-021)

**Effects:**
- `user_role_pk` assigned (UUID)
- `user_account_pk` = target user
- `role_master_pk` = target role
- `created_at` = current timestamp
- `created_by_sangha_sevi_pk` = assigning authority

**Constraints:**
- A user may hold multiple roles (ADMIN-BR-011)
- Role assignment does not create a new user identity (ADMIN-BR-022)
- Role assignment does not change Person or Membership status (ADMIN-BR-012)
- Governance position does not automatically become role assignment
  (ADMIN-BR-013, ADMIN-BR-065)

**Audit:** Role assignment is auditable (ADMIN-BR-051)

---

# 22. Transition: User-Role Revocation

**Trigger:** Role removed from a user account

**Preconditions:**
- Active assignment exists for this user + role
- Authorized administrative user

**Effects:**
- Assignment deactivated (soft-delete or state change)
- `updated_at` = current timestamp

**Constraints:**
- Does not change user identity (ADMIN-BR-022)
- Does not rewrite historical audit records (ADMIN-BR-023, ADMIN-BR-066)
- Historical actions performed under this role remain attributed
  (ADMIN-BR-048, ADMIN-BR-049)
- Does not cause uncontrolled destruction of historical records
  (Table Design Section 32)

**Audit:** Role revocation is auditable (ADMIN-BR-051)

---

# 23. Admin Scope — Lifecycle

`admin_scope` represents organizational authorization scope for a user.

## States

```text
ASSIGNED        Scope exists and is active
MODIFIED        Scope level or organizational unit changed
REVOKED         Scope deactivated or removed
```

Note: The source does not freeze a separate `scope_history` table
(ADMIN-BR-070). Historical scope state is preserved through audit
records (ADMIN-BR-050).

---

# 24. Transition: Scope Assignment

**Trigger:** Organizational scope assigned to a user

**Preconditions:**
- User account exists
- Scope level is valid (KENDRA / ANCHALIKA / ZILLA / SAKHA — ADMIN-BR-024)
- Organizational unit reference is valid (Organization module authority —
  ADMIN-BR-032, ADMIN-BR-033)
- Authorized administrative user (ADMIN-BR-025)

**Effects:**
- `admin_scope_pk` assigned (UUID)
- Scope level = authorized level
- Organization unit = authorized target
- `created_at` = current timestamp
- `created_by_sangha_sevi_pk` = assigning authority

**Constraints:**
- Does not create duplicate organizational entities (ADMIN-BR-034)
- Does not change Person or Membership identity (ADMIN-BR-026, ADMIN-BR-027)
- Scope cannot create invalid organizational relationships (ADMIN-BR-061)

**Audit:** Scope assignment is auditable (ADMIN-BR-051)

---

# 25. Transition: Scope Modification

**Trigger:** User's organizational scope changed (level or unit)

**Preconditions:**
- Active scope exists for this user
- New scope level/unit is valid
- Authorized administrative user

**Effects:**
- Scope level and/or organizational unit updated
- `updated_at` = current timestamp

**Constraints:**
- Does not retroactively alter historical activity (ADMIN-BR-050)
- Does not change user identity (ADMIN-BR-026)
- Organization hierarchy remains authoritative (ADMIN-BR-032)

**Audit:** Scope change is auditable (ADMIN-BR-051)

---

# 26. Transition: Scope Revocation

**Trigger:** Organizational scope removed from a user

**Preconditions:**
- Active scope exists for this user
- Authorized administrative user

**Effects:**
- Scope deactivated (soft-delete or state change)
- `updated_at` = current timestamp

**Constraints:**
- Does not invalidate historical authorization evidence (ADMIN-BR-068)
- Does not retroactively rewrite historical activity (ADMIN-BR-050)

**Audit:** Scope revocation is auditable (ADMIN-BR-051)

---

# 27. Cross-Module Lifecycle Events

## Events Administration Responds To

| Source Event | Source Module | Administration Response |
|---|---|---|
| Account Deactivated | Authentication | Active role assignments and scope become historically frozen |
| Person Death Recorded | Person | No automatic RBAC change; authorized administrator may act |
| Person Soft-Deleted | Person | Historical authorization records preserved |
| Governance Position Changed | Governance | No automatic role change (explicit mapping required) |
| Membership Terminated | Membership | No automatic role change (separate lifecycle) |

## Events Administration Generates

| Administration Event | Affected Modules | Expected Response |
|---|---|---|
| Role Created | Audit | Administrative event logged |
| Role Deactivated | Audit | Administrative event logged |
| Permission Created | Audit | Administrative event logged |
| Role-Permission Assigned | Audit | Administrative event logged |
| User-Role Assigned | Audit | Administrative event logged |
| Scope Assigned/Changed | Audit | Administrative event logged |

---

# 28. Account Deactivation and RBAC

When a user account is deactivated (Authentication lifecycle event):

- Active `user_role` assignments are not physically deleted
- Active `admin_scope` records are not physically deleted
- Active `role_permission` mappings are unaffected (role-level, not user-level)
- The user's effective authorization becomes denied through the
  Authentication layer (account state), not through RBAC deletion
- Historical authorization evidence remains interpretable
  (ADMIN-BR-048, ADMIN-BR-068)

The Administration Module does not independently deactivate accounts —
it responds to Authentication lifecycle state.

---

# 29. Person Death and Administration

When a Person's death is recorded (Person Module event):

- No automatic RBAC changes occur
- An authorized administrator may choose to:
  - Request account deactivation (Authentication action)
  - Revoke role assignments
  - Revoke scope assignments
- Historical authorization records remain fully preserved
- Historical actions attributed to this user remain unchanged

The Administration Module does not independently record death — it may
respond through authorized administrative action.

---

# 30. Governance Position and Application Role

Governance positions and application roles are separate concepts
(ADMIN-BR-013, ADMIN-BR-065):

```text
Governance Position (Governance Module)
    President, Secretary, Parichalak

Application Role (Administration Module)
    role_master records
```

- Holding a governance position does not automatically grant application
  permissions (ADMIN-BR-065)
- Position-to-role mapping, where required, must be explicitly defined
  (ADMIN-BR-014)
- Permissions are not hard-coded from office-bearer titles (ADMIN-BR-018)

---

# 31. Prohibited Lifecycle Patterns

The following are explicitly prohibited:

```text
- Physical deletion of role_master records (ADMIN-BR-067, ADMIN-BR-068)
- Physical deletion of permission_master records (ADMIN-BR-067, ADMIN-BR-068)
- Physical deletion of historical authorization evidence (ADMIN-BR-068)
- Role change rewriting historical audit records (ADMIN-BR-049, ADMIN-BR-066)
- Scope change retroactively altering historical activity (ADMIN-BR-050)
- Permission revocation rewriting historical audit (ADMIN-BR-020)
- Creating module-specific RBAC/permission tables (ADMIN-BR-002)
- Creating duplicate organizational hierarchy (ADMIN-BR-034)
- Creating duplicate authentication mechanism (ADMIN-BR-008)
- Governance position automatically becoming role assignment (ADMIN-BR-013)
- Membership status automatically becoming role assignment (ADMIN-BR-064)
- Hard-coded office-bearer authorization (ADMIN-BR-018)
- Deactivated user's historical actions becoming unattributable (ADMIN-BR-048)
```

---

# 32. Lifecycle and Audit Integration

| Transition | Audit Fields |
|---|---|
| Role Creation | created_at, created_by_sangha_sevi_pk |
| Role Update | updated_at, updated_by_sangha_sevi_pk |
| Role Deactivation | updated_at |
| Permission Creation | created_at, created_by_sangha_sevi_pk |
| Permission Update | updated_at, updated_by_sangha_sevi_pk |
| Permission Deactivation | updated_at |
| Role-Permission Assignment | created_at, created_by_sangha_sevi_pk |
| Role-Permission Revocation | updated_at |
| User-Role Assignment | created_at, created_by_sangha_sevi_pk |
| User-Role Revocation | updated_at |
| Scope Assignment | created_at, created_by_sangha_sevi_pk |
| Scope Modification | updated_at |
| Scope Revocation | updated_at |

All administrative transitions are auditable through the central Audit
framework (ADMIN-BR-051, ADMIN-BR-052).

---

# 33. Lifecycle State Query Patterns

| Query Intent | Filter |
|---|---|
| Active roles | `role_master.is_active = TRUE` |
| Deactivated roles | `role_master.is_active = FALSE` |
| Active permissions | `permission_master.is_active = TRUE` |
| Permissions for a role | `role_permission.role_master_pk = ? AND is_active = TRUE` |
| Roles for a user | `user_role.user_account_pk = ? AND is_active = TRUE` |
| Active scope for user | `admin_scope.user_account_pk = ? AND is_active = TRUE` |
| Users with Sakha scope | `admin_scope.scope_level = 'SAKHA' AND is_active = TRUE` |
| Historical role assignments | `user_role.user_account_pk = ?` (no is_active filter) |
| Effective authorization | User + user_role + role_master + role_permission + permission_master + admin_scope |

---

# 34. Explicitly Not Frozen Here

The following lifecycle details are left to implementation:

```text
Exact role catalogue (ADMIN-BR-045)
Exact permission catalogue (ADMIN-BR-045)
Exact role inheritance hierarchy (ADMIN-BR-044)
Exact role_history table (ADMIN-BR-070)
Exact scope_history table (ADMIN-BR-070)
Exact high-risk segregation-of-duty rules (ADMIN-BR-042)
Exact self-escalation prevention rules (ADMIN-BR-057)
Exact RBAC change approval workflow (ADMIN-BR-058)
Exact super-administrator privileges (ADMIN-BR-043)
Exact position-to-role mapping mechanism
Exact effective-dated authorization model
Exact admin_scope FK to Organization tables
Exact scope inheritance across organizational hierarchy
```

---

# 35. Status

```text
DOCUMENT STATUS:
DRAFT

VERSION:
0.1.0
```
