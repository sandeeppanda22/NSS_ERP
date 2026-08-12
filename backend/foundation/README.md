# backend/foundation/

Core Person/Organization Django models and the only browsable (non-admin) data views besides
login/dashboard. In `INSTALLED_APPS` and wired into the root URLconf.

## Models (`models.py`)

- `OrganizationType` — `code` (unique), `name`, `description`, `is_active`.
- `Organization` — `organization_type` FK (PROTECT), `code` (unique), `name`, `short_name`.
- `Address` — `address_line_1/2`, `city`, `district`, `state`, `postal_code`,
  `country` (default `"India"`).
- `Person` — `first_name`, `middle_name`, `last_name`, `gender` (plain CharField, no choices),
  `date_of_birth`, `mobile_number`, `email`, `address` FK (SET_NULL).

**These are simpler, separate models from the SQL schema in `database/ddl/03_person/` and
`database/ddl/02_organization/`** (auto-increment PK vs UUID `_pk`, plain `gender` field vs a
`gender_master` FK, no `person_code`/business ID). The two are not reconciled yet — see
`docs/PROJECT_DOCUMENTATION.md` → Architecture/Gotchas before extending either.

## Views / URLs

- `person_list` / `person_detail` (`views.py`, both `@login_required`) — list active persons
  ordered by first name, and a single-person detail view (404 if not found).
- `urls.py` — `/persons/`, `/persons/<int:pk>/`.
