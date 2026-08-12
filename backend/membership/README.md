# backend/membership/

Membership/Sangha Sevi ID models. In `INSTALLED_APPS`, admin-registered, but has **no
`urls.py`** — unreachable over HTTP except via `/admin/`.

## Models (`models.py`)

- `MembershipType`, `MembershipStatus` — lookup tables (`code`, `name`, `description`,
  `is_active`).
- `SanghaSevi` — `sangha_sevi_id` (unique), `person` (OneToOne → `foundation.Person`,
  PROTECT), `organization` FK (PROTECT) → `foundation.Organization`, `membership_type` /
  `membership_status` FKs (PROTECT), `joining_date` (required), `renewal_due_date`, `remarks`.

Note: `sangha_sevi_id` here is a Django model field name, not evidence of a project-wide `_id`
business-identifier convention — the SQL DDL convention is `_code` (see
`docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas).

## Open work

- No views/URLs — membership data is only reachable via Django admin today.
