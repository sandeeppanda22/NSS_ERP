# backend/family/

Family grouping models. In `INSTALLED_APPS` but has **no `urls.py`** — unreachable over HTTP,
and not registered in Django admin either (the only real-model app that isn't).

## Models (`models.py`)

- `FamilyGroup` — `family_id` (unique), `family_name`, `is_active`, `remarks`.
- `FamilyMembership` — `family` FK (CASCADE) ↔ `foundation.Person` FK (PROTECT),
  `relationship` (choices: HEAD/SPOUSE/CHILD/PARENT/SIBLING/OTHER), `is_primary`,
  `start_date`/`end_date`, `remarks`.

## Open work

- No views/URLs exist — data is only reachable by adding admin registration or building views.
- Not registered in `admin.py` (stub file).
