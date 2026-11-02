# database/seed/01_foundation/

Foundation Module seed data — initial reference values required before
any downstream module can operate.

Authority: SOL-FND-004 §29–§31, SOL-ARCH-010 §8

## Seed Execution Order

Execute AFTER all DDL in `database/ddl/01_foundation/` has completed.
Files must be run in numeric order (each may depend on data from earlier files).

| # | File | Seeds Into | Depends On |
|--:|------|-----------|-----------|
| 01 | `01_master_category.sql` | `master_category` | DDL complete |
| 02 | `02_master_data.sql` | `master_data` | `01_master_category.sql` |
| 03 | `03_id_sequence_master.sql` | `id_sequence_master` | DDL complete |
| 04 | `04_country.sql` | `country` | DDL complete |
| 05 | `05_state.sql` | `state` | `04_country.sql` |
| 06 | `06_district.sql` | `district` | `05_state.sql` |
| 07 | `07_system_setting.sql` | `system_setting` | DDL complete |
| 08 | `08_postal_code.sql` | `postal_code` | `05_state.sql` |
| 08b | `08b_postal_code_bulk.sql` | `postal_code` (all-India, ~17.9k PINs) | `05_state.sql` |
| 08c | `08c_post_office_bulk.sql` | `post_office` (all post offices per PIN) | `08b_postal_code_bulk.sql` |
| 09 | `09_sakha_postal_codes.sql` | `postal_code` | `05_state.sql` — runs in Phase 4 |
| 10 | `10_festival_calendar.sql` | `festival_master`, `festival_calendar_date` | DDL complete |
| 11 | `11_city_village.sql` | `city_village` (~673k locality rows) | `06_district.sql`, `08b_postal_code_bulk.sql` |
| 11b | `11b_city_village_urban_recovery.sql` | `city_village` (additive urban-PIN recovery) | `11_city_village.sql` |

`02_build.sh`/`.ps1` run every file except `09` in Phase 2, in the order of the `FOUNDATION_SEED`
array (`...08`, `08b`, `08c`, `10`, `11`, `11b`); **`09_sakha_postal_codes.sql` runs later, in
Phase 4**, right before `seed/02_organization/05_sakha_branches.sql` (which consumes its PINs).

## Execution Command

```bash
# As nss_db_owner against the nss_erp database:
for f in database/seed/01_foundation/0*.sql database/seed/01_foundation/1*.sql; do
    psql -U nss_db_owner -d nss_erp -f "$f"
done
```

(The glob is a convenience for a manual run; `02_build.sh` is authoritative — it runs `09_sakha_postal_codes.sql` in Phase 4,
not here.)

---

## Seed File Descriptions

### 01_master_category.sql

Seeds 13 lookup categories into `master_category`. These are the top-level
classification buckets; each category's individual values are seeded in
`02_master_data.sql`.

| # | `category_code` | Purpose |
|--:|-----------------|---------|
| 1 | `GENDER` | Gender classification for persons |
| 2 | `RELATIONSHIP_TYPE` | Family relationship types (used by Family module) |
| 3 | `MEMBERSHIP_TYPE` | Types of NSS membership (per Bye-Law) |
| 4 | `STATUS` | Unified lifecycle status for all ERP entities (organizations, memberships, governance, etc.) — replaces the earlier per-module `MEMBERSHIP_STATUS`/`ORGANIZATION_STATUS` |
| 5 | `LOGIN_ROLE` | Application login role classification |
| 6 | `STATUS_REASON` | Reason codes for status changes |
| 7 | `WORKFLOW_STATUS` | Generic workflow state values |
| 8 | `DOCUMENT_TYPE` | Classification of stored documents |
| 9 | `APPLICATION_TYPE` | Types of member applications |
| 10 | `MARITAL_STATUS` | Marital status for persons |
| 11 | `ADDRESS_TYPE` | Types of addresses (permanent, current, official) |
| 12 | `ORGANIZATION_TYPE` | Types of organizations in the NSS hierarchy (added for Organization module) |
| 13 | `BLOOD_GROUP` | Blood group classification for persons (added for Person module) |

---

### 02_master_data.sql

Seeds individual values into `master_data` for each category created above (89 values total:
3 + 5 + 3 + 7 + 4 + 16 + 30 + 13 + 8 — counted from the seed file; it has changed more than
once, so re-verify after editing). Uses `CROSS JOIN ... VALUES` with a subquery to resolve `master_category_pk`
by `category_code` — no hardcoded UUIDs. `LOGIN_ROLE`, `STATUS_REASON`, `WORKFLOW_STATUS`, and
`APPLICATION_TYPE` are seeded as categories only (0 values) — reserved for later use.

**GENDER** (3 values): MALE, FEMALE, OTHER

**MARITAL_STATUS** (5 values): UNMARRIED, MARRIED, WIDOWED, DIVORCED, SEPARATED

**ADDRESS_TYPE** (3 values): PERMANENT, CURRENT, OFFICIAL

**DOCUMENT_TYPE** (7 values): PHOTO, ID_PROOF, ADDRESS_PROOF, CERTIFICATE,
CORRESPONDENCE, PROPERTY_DOCUMENT, MEETING_MINUTES

**MEMBERSHIP_TYPE** (4 values):
- `PROBATIONARY` — Probationary Member (initial membership stage, per Bye-Law §B)
- `REGULAR` — Regular Member (full membership, per Bye-Law §B)
- `ASSOCIATE` — Associate Member (per Bye-Law §B)
- `HONORARY` — Honorary Member (ERP-FROZEN; not in current Bye-Law — added as an operational category by project decision)

**STATUS** (16 values, unified ERP-wide lifecycle status — replaces the earlier per-module
`MEMBERSHIP_STATUS`). Each value tagged with `applicable_modules` array:
- Organization: PROPOSED, APPROVED, ACTIVE, INACTIVE, SUSPENDED, DISSOLVED, ARCHIVED (7)
- Membership: ACTIVE, INACTIVE, SUSPENDED, LAPSED, TRANSFERRED, RESIGNED, EXPELLED, ARCHIVED, EXPIRED, RENEWAL_PENDING, ON_HOLD, DISCIPLINARY_REVIEW (12)
- Person: ACTIVE, INACTIVE, DECEASED, ARCHIVED (4)

EXPIRED is tagged `{MEMBERSHIP}` (a Parichaya Patra/Anumati Patra lapsing from non-renewal is a
membership-lifecycle event) — note `parichaya_patra.status`/`anumati_patra.status` are each
their own inline `VARCHAR` + `CHECK` column, not FKs into `master_data`, so this row is a
reference/lookup value rather than what those two tables actually store.

**RELATIONSHIP_TYPE** (30 values, comprehensive for Indian family structure — grew from 29 to 30
in Tier 5, with the addition of `SELF`):
- Immediate family: SPOUSE, FATHER, MOTHER, SON, DAUGHTER, BROTHER, SISTER
- In-laws: FATHER_IN_LAW, MOTHER_IN_LAW, SON_IN_LAW, DAUGHTER_IN_LAW,
  BROTHER_IN_LAW, SISTER_IN_LAW
- Grandparents/grandchildren: GRANDFATHER, GRANDMOTHER, GRANDSON, GRANDDAUGHTER
- Uncle/aunt/nephew/niece: UNCLE, AUNT, NEPHEW, NIECE
- Cousins: COUSIN
- Step relations: STEP_FATHER, STEP_MOTHER, STEP_SON, STEP_DAUGHTER
- Guardian/ward: GUARDIAN, WARD
- Self: `SELF` (Tier 5 — a family founder/head with no relational context to record
  against; `display_order = 0`, sorts before every other value)
- Other: OTHER

**ORGANIZATION_TYPE** (14 values: 13 per NSS Bye-Law hierarchy + preamble, plus the singleton `ADVISORY_BOARD` added 2026-10-30 — its organization row is created by `02_organization/07_advisory_board_organization_patch.sql`): KENDRA,
NILACHALA_KUTIRA, SMRUTI_MANDIRA, ANCHALIKA_SANGHA, ZILLA_SANGHA, SAKHA_SANGHA, SAKHA_ASANA,
PARIBARIK_ASANA, PARIBARIK_SANGHA, PATHA_CHAKRA, KUMARI_SANGHA, SEVAK_SANGHA, MAHILA_SANGHA,
ADVISORY_BOARD

**BLOOD_GROUP** (8 values, added for the Person module): A_POSITIVE, A_NEGATIVE, B_POSITIVE,
B_NEGATIVE, AB_POSITIVE, AB_NEGATIVE, O_POSITIVE, O_NEGATIVE

---

### 03_id_sequence_master.sql

Seeds 14 ID sequences into `id_sequence_master`. Each sequence defines a
prefix and counter for generating human-readable business IDs.

| # | `sequence_code` | Prefix | `padding_length` | Generated ID example | Purpose |
|--:|-----------------|--------|:---:|---------------------|---------|
| 1 | `PERSON` | `P` | 10 | P0000000001 | Person identity |
| 2 | `SANGHA_SEVI` | `SS` | 8 | SS00000001 | Membership identity |
| 3 | `ANCHALIKA` | `ANC` | 8 | ANC00000001 | Anchalika organization (multiple) |
| 4 | `ZILLA` | `ZL` | 8 | ZL00000001 | Zilla organization (multiple) |
| 5 | `SAKHA` | `SKH` | 0 (was 8 — changed in Tier 5) | SKH1 | Sakha organization (multiple) |
| 6 | `SAKHA_ASANA` | `SA` | 8 | SA00000001 | Sakha Asana organization (multiple) |
| 7 | `PATHA_CHAKRA` | `PC` | 8 | PC00000001 | Patha Chakra organization (multiple) |
| 8 | `PARIBARIK_ASANA` | `PA` | 5 | PA00001 | Paribarik Asana organization (multiple) |
| 9 | `PARIBARIK_SANGHA` | `PS` | 3 | PS001 | Paribarik Sangha organization (multiple) |
| 10 | `FAMILY` | `F` | 8 | F00000001 | Family group |
| 11 | `DOCUMENT` | `DOC` | 8 | DOC00000001 | Document tracking |
| 12 | `KUMARI_SANGHA` | `KS` | 5 | KS00001 | Reserved for a future module (not yet consumed by any API) |
| 13 | `SEVAK_SANGHA` | `SEV` | 5 | SEV00001 | Reserved for a future module (not yet consumed by any API) |
| 14 | `MAHILA_SANGHA` | `MS` | 5 | MS00001 | Reserved for a future module (not yet consumed by any API) |

All sequences start at `current_value = 0`. `padding_length` varies per sequence (see table
above). **`SAKHA`'s `padding_length` was changed from `8` to `0` in Tier 5**
— it is no longer true that "no existing sequence's `padding_length` has been
changed to 0"; `SAKHA` is now the first real example, matching the unpadded `SKH1`-`SKH175`
codes seeded by `database/seed/02_organization/05_sakha_branches.sql` (Tier 5). Every
other sequence's `padding_length` is unchanged from the zero-padded values in the table above.
The `chk_id_sequence_padding` CHECK constraint on `id_sequence_master` was loosened from
`BETWEEN 2 AND 12` to `BETWEEN 0 AND 12` to allow this.

**Note:** Unique organizations (KENDRA/`KEN`, NILACHALA_KUTIRA/`NKT`,
SMRUTI_MANDIRA/`SMR`) do not have sequences — they receive fixed codes
directly from the Organization module's seed data.

---

### 04_country.sql

Seeds 5 countries into `country`. India is seeded first (`display_order = 1`)
as the primary operating country.

| # | Code | Country | Display Order |
|--:|------|---------|:------------:|
| 1 | `IN` | India | 1 |
| 2 | `US` | United States | 2 |
| 3 | `GB` | United Kingdom | 3 |
| 4 | `AU` | Australia | 4 |
| 5 | `CA` | Canada | 5 |

---

### 05_state.sql

Seeds 112 state-level entries into `state`. Uses subquery to resolve
`country_pk` by `country_code`.

| Country | Count | Details |
|---------|------:|---------|
| India (`IN`) | 36 | All 28 states + 8 Union Territories |
| United States (`US`) | 51 | All 50 states + District of Columbia |
| United Kingdom (`GB`) | 4 | England, Scotland, Wales, Northern Ireland |
| Australia (`AU`) | 8 | 6 states + 2 territories |
| Canada (`CA`) | 13 | 10 provinces + 3 territories |
| **Total** | **112** | |

---

### 06_district.sql

Seeds 785 districts into `district` across all 36 Indian states and Union Territories, keyed on the
numeric LGD district code (`district_code` is globally unique so `11_city_village.sql` resolves
`district_pk` by code rather than by name). Uses subquery to resolve `state_pk` by `state_code` within
India. Non-India countries do not have pre-seeded districts — those are populated at runtime as
needed. Per-state counts (state code: districts):

| State | Districts | State | Districts |
|-------|----------:|-------|----------:|
| Andhra Pradesh (AP) | 28 | Maharashtra (MH) | 36 |
| Arunachal Pradesh (AR) | 27 | Manipur (MN) | 16 |
| Assam (AS) | 35 | Meghalaya (ML) | 12 |
| Bihar (BR) | 38 | Mizoram (MZ) | 11 |
| Chhattisgarh (CG) | 33 | Nagaland (NL) | 17 |
| Goa (GA) | 3 | Odisha (OD) | 30 |
| Gujarat (GJ) | 34 | Punjab (PB) | 23 |
| Haryana (HR) | 23 | Rajasthan (RJ) | 41 |
| Himachal Pradesh (HP) | 12 | Sikkim (SK) | 6 |
| Jharkhand (JH) | 24 | Tamil Nadu (TN) | 38 |
| Karnataka (KA) | 31 | Telangana (TS) | 33 |
| Kerala (KL) | 14 | Tripura (TR) | 8 |
| Madhya Pradesh (MP) | 55 | Uttar Pradesh (UP) | 75 |
| | | Uttarakhand (UK) | 13 |
| | | West Bengal (WB) | 23 |

**Union Territories:**

| UT | Districts |
|----|----------:|
| Delhi (DL) | 14 |
| Jammu & Kashmir (JK) | 20 |
| Ladakh (LA) | 2 |
| Chandigarh (CH) | 1 |
| Puducherry (PY) | 2 |
| Andaman & Nicobar (AN) | 3 |
| Dadra & Nagar Haveli and Daman & Diu (DN) | 3 |
| Lakshadweep (LD) | 1 |

---

### 07_system_setting.sql

Seeds 5 initial system settings into `system_setting`. Values are illustrative
defaults; actual production values are configured during deployment.

| # | `setting_key` | Value | Type | Purpose |
|--:|---------------|-------|------|---------|
| 1 | `CURRENT_MEMBERSHIP_YEAR` | `2026-2027` | STRING | Active membership year (financial year format, Apr–Mar) |
| 2 | `DEFAULT_COUNTRY` | `IN` | STRING | Default country code for new records |
| 3 | `PASSWORD_EXPIRY_DAYS` | `90` | INTEGER | Days before password must be changed |
| 4 | `MAX_LOGIN_ATTEMPTS` | `5` | INTEGER | Failed logins before account lockout |
| 5 | `MEMBERSHIP_DARSHAK_LOCAL_ID_MARKER` | `D` | STRING | Namespace marker inserted between a Sakha short code and the local number for Darshak/Probationary local Sakha IDs (MBR-030C, e.g. `ESSD000045` vs Regular `ESS000123`); configurable so it is never hardcoded |

---

### 08_postal_code.sql

Seeds 3 postal codes into `postal_code` — the minimal bootstrap set required
by Organization seed data (FK references from `organization.postal_code_pk`).
Resolves `state_pk` from existing seed data (`postal_code` no longer carries `country_pk` or
`post_office_name`). These PINs are also in `08b`; this file is a safety net so `08b` is not a
hard prerequisite.

| # | Postal Code | Used By |
|--:|-------------|---------|
| 1 | `751022` | Kendra Sangha (Satsikshya Mandir) |
| 2 | `752001` | Nilachala Kutira, Smruti Mandira |
| 3 | `753001` | Originally the second Tier 4 verification Sakha location; retained as a plain reference PIN |

---

### 08b_postal_code_bulk.sql / 08c_post_office_bulk.sql

`08b`: all-India PIN load (file header: 17,869 distinct PINs, one row per PIN, dominant state),
sourced from 4 government LGD files (Simplified Geography Model, 2026-10-02). `08c`: every post
office per PIN into `post_office` (source: India Post 2025 directory), joined to its parent PIN at
load time (offices whose PIN has no parent row are skipped); rows are `entry_status='APPROVED'`,
idempotent via `uq_post_office_pin_name_approved`.

---

### 09_sakha_postal_codes.sql (Tier 5)

Seeds 56 additional unique postal codes into `postal_code`, extracted from the official NSS
Sakha branch directory addresses — the minimal bootstrap set needed by
`database/seed/02_organization/05_sakha_branches.sql` (175 real Sakha branches; 63 carry a PIN
directly in the source directory, a further 58 are resolved through the India Post `post_office`
data, and 54 get `postal_code_pk = NULL`). Run AFTER `04_country.sql`/
`05_state.sql` (resolves `state_pk` by code, `ON CONFLICT (postal_code)` — the approved-only partial unique index) and BEFORE `database/seed/02_organization/05_sakha_branches.sql`.

---

### 10_festival_calendar.sql

Seeds `festival_master` (one row: `DOLA_PURNIMA`, the ERP reference date for Probationary-to-Regular
conversion, transfers and Patra validity, SOL-ARCH-013) and `festival_calendar_date` rows for
calendar years 2024–2028 (entered data, never computed; years outside that range are intentionally
not seeded). Upserts `festival_master` on `festival_code`.

### 11_city_village.sql / 11b_city_village_urban_recovery.sql

`11`: ~673k locality rows (file header: 672,619 village rows + 789 urban-only rows), `district_pk`
resolved directly by LGD district code for villages (NULL when an urban-only locality's ULB is
ambiguous). `11b`: additive, idempotent recovery of one representative locality per otherwise
orphan urban PIN, district resolved from the India Post directory. Both are very large files —
expect a slow Phase 2.

---

## Notes

- Seed data uses `CROSS JOIN ... VALUES` with subqueries to resolve parent PKs
  by code — no hardcoded UUIDs.
- Additional categories and values are added by downstream module seeds directly into this
  folder's files (e.g., Organization added `STATUS` + `ORGANIZATION_TYPE` to
  `01_master_category.sql`/`02_master_data.sql`; Person added `BLOOD_GROUP`). Downstream
  modules do not carry their own `master_data` seed — Foundation stays the single owner.
- Cities/villages ARE seeded all-India (`11`/`11b`); members can propose missing geographic values at runtime (see `ddl/01_foundation/README.md` → Member-Assisted Geographic Entry).
- Postal codes: `08_postal_code.sql` seeds the 3 PINs Organization needs (751022, 752001, 753001),
  `08b` loads all-India PINs, and `09_sakha_postal_codes.sql` adds the 56 Sakha-branch PINs
  (already present if `08b` ran).
