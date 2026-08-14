# backend/heritage/

Founder & Heritage module. Currently has one real model, no views/URLs yet.

## Models (`models.py`)

- `Founder` — singleton model (`db_table="founder_master"`). `founder_pk` (UUID PK),
  `founder_code` (unique), `founder_name`, `spiritual_name`, `birth_name`, `father_name`,
  `mother_name`, `birth_date`, `mahasamadhi_date`, `birth_place`, `biography`,
  `founder_message`, `website_url`, `created_at`/`updated_at`. `save()` raises
  `ValidationError` if a record already exists (only one Founder record allowed); `delete()`
  always raises `ValidationError` (the record can never be deleted).

In `INSTALLED_APPS` (`backend/config/settings.py`). No `urls.py`/views yet — reachable only via
Django admin (`admin.py` registers `Founder`).

Reserved design scope beyond this model: Biography, Philosophy, Teachings, Publications (see
root `README.md` § Module Structure and `docs/03_Solution/modules/heritage/README.md`).
