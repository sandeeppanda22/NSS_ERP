# api/routers/

One FastAPI `APIRouter` per module, all included by `api/main.py`. **15 routers, 201 endpoints**
(decorator-counted; `governance.py`, `membership_change_request.py` and `correspondence.py` are Tier 6, uncommitted on `feature/tier6-governance`). Raw parameterized psycopg2 SQL, no ORM; response models live in
`api/schemas/`. See `api/README.md` for the per-endpoint tables.

| File | Prefix | Endpoints | Auth |
|------|--------|-----------|------|
| `bootstrap.py` | `/api/v1/bootstrap` | 4 | none |
| `foundation.py` | `/api/v1/foundation` | 33 (21 reads, 8 admin writes, 4 member `propose` POSTs) | `FOUNDATION_VIEW` / `FOUNDATION_MANAGE` (festival-calendar writes: `FOUNDATION_CALENDAR_MANAGE`); `propose` endpoints: login only, active Sangha Sevi |
| `organization.py` | `/api/v1/organization` | 11 | `ORGANIZATION_VIEW`; `/organizations/selectable` needs login only |
| `person.py` | `/api/v1/person` | 5 | `PERSON_VIEW` (list, search); login only (`/search-selectable`); self-or-`PERSON_VIEW` (detail, addresses) |
| `family.py` | `/api/v1/family` | 16 | `get_current_user` + ownership checks; `FAMILY_VIEW`/`FAMILY_MANAGE` override |
| `membership.py` | `/api/v1/membership` | 8 | `MEMBERSHIP_VIEW` (list, search, darshak-summary); self-or-`MEMBERSHIP_VIEW` (per-member) |
| `auth.py` | `/api/v1/auth` | 10 | none for login/refresh/forgot/reset; JWT for the rest |
| `admin.py` | `/api/v1/admin` | 32 (incl. 4 `/credentials/members*` endpoints: list, timeline, issue, promote Darshak→Regular) | `require_any_permission(...)` per endpoint, plus scope checks |
| `registration.py` | `/api/v1/register` | 12 | none (public) |
| `claim_approval.py` | `/api/v1/admin/claims` | 5 | `MEMBERSHIP_APPROVE` or `ADMIN_USER_MANAGE`, scope-filtered |
| `audit.py` | `/api/v1/audit` | 1 | `AUDIT_VIEW` |
| `geo_approval.py` | `/api/v1/admin/geo-entries` | 4 | `FOUNDATION_MANAGE`, scope-filtered |
| `governance.py` | `/api/v1/governance` | 46 (bodies, body types, positions, assignments, acting assignments, elections, nominations, votes, results) | reads `GOVERNANCE_VIEW`/`GOVERNANCE_MANAGE`; writes `GOVERNANCE_MANAGE` + org scope; `/public/*`, `/elections/open-for-voting`, `/votes/self` need login only |
| `correspondence.py` | `/api/v1/correspondence` | 9 | `CORRESPONDENCE_VIEW` (reads) / `CORRESPONDENCE_MANAGE` (writes) + admin scope on `register_organization_pk` (`actor_scope_org_pks`/`require_org_in_scope`); status transitions per §6.2, reopen needs remarks; reference number from `next_correspondence_reference_number()` (needs the register org's `short_code`, else 422) |
| `membership_change_request.py` | `/api/v1/membership/change-requests` | 5 | `get_current_user`; Sakha Transfer / Apply for Darshak two-step release→accept workflow (MBR-048/049), scope-checked per Sakha |

## Non-obvious wiring

- **Read vs write pool.** `get_connection` (`nss_db_backend`, SELECT-only) for reads;
  `get_write_connection` (`nss_db_writer`, commit on success / rollback on exception) for any
  mutation and for `POST /auth/login`. Pure `GET`s under `admin`/`claim_approval`/`audit`/
  `register` use the read pool.
- **Two auth styles.** Blanket `require_permission(...)` (Foundation, Organization, list/search
  endpoints) versus ownership (`family.py`'s `_require_family_view/_manage/_head`; `person.py`/
  `membership.py` via `helpers.require_self_or_permission()`). Do not collapse them: ordinary
  members hold no role/permission and reach their own data only through the ownership path.
- **Cross-router reuse.** `registration.py` imports `fetch_countries`/`fetch_states`/
  `fetch_districts`/`fetch_postal_codes`/`fetch_master_data` from `foundation.py` and
  `fetch_organizations` from `organization.py`, so the public and permission-gated endpoints
  share one query.
- **Shared SQL** lives in `api/helpers.py` (`FAMILY_MAJORITY_CTE_SQL`,
  `ORGANIZATION_ADDRESS_JOINS_SQL`, `PERSON_MASTER_DATA_JOINS_SQL`, `MEMBER_JOINS_SQL`,
  `USER_ACCOUNT_MEMBERSHIP_JOINS_SQL`) — splice these, do not copy them.
- **Scope vs permission (`admin.py`).** Holding `ORGANIZATION_MANAGE`/`ADMIN_USER_MANAGE` does not
  grant global reach; only `UserContext.is_super_admin()` (`NSS_ERP_ADMIN`) does. Everyone else is
  checked against their `admin_scope` subtree (`rbac_service.require_org_in_scope()` etc.).
- **Every write calls `helpers.log_audit()`** (writes `nss.system_event_log`) after the business
  SQL; the DB `fn_audit_trigger()` independently writes a second, generic row.
- Several module docstrings here are stale — see "Known gaps" in `api/README.md`.
