# api/schemas/

Pydantic models, one module per router (`bootstrap`, `foundation`, `organization`, `person`,
`family`, `membership`, `auth`, `admin`, `audit`, `geo_approval`, and Tier 6 `governance`,
`membership_change_request`, `correspondence`). `registration.py` and `claim_approval.py` have no
schema module — their request/response models are defined inline in the routers, as are
`admin.py`'s organization create/update and admin-person request bodies.

`admin.py` also carries `AutoGrantedScopeResponse` (Tier 6, read-only §63 composite auto-grants on user detail).

Conventions:

- Response models never include audit columns, with one deliberate exception:
  `audit.py::FieldChangeLogResponse` exists to expose the change-log actor columns.
- `person.py` models never include `aadhaar_encrypted`/`aadhaar_hash`, only `aadhaar_last4`
  (PER-BR-081).
- `foundation.py::SequenceResponse` omits `current_value`.
- `*ListResponse` models (`PersonListResponse`, `MemberListResponse`, `UserListResponse`, ...)
  wrap paginated results with a total; cursor rows are converted by
  `api/helpers.py::rows_to_models`/`row_to_model`.
- No ORM: models are built from raw psycopg2 cursor rows.
