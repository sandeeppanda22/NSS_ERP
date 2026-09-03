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
| 08 | `08_postal_code.sql` | `postal_code` | `04_country.sql`, `05_state.sql` |

## Execution Command

```bash
# As NSS_ADMIN against the nss_erp database:
for f in database/seed/01_foundation/0*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done
```

---

## Seed File Descriptions

### 01_master_category.sql

Seeds 11 lookup categories into `master_category`. These are the top-level
classification buckets; each category's individual values are seeded in
`02_master_data.sql`.

| # | `category_code` | Purpose |
|--:|-----------------|---------|
| 1 | `GENDER` | Gender classification for persons |
| 2 | `RELATIONSHIP_TYPE` | Family relationship types (used by Family module) |
| 3 | `MEMBERSHIP_TYPE` | Types of NSS membership (per Bye-Law) |
| 4 | `MEMBERSHIP_STATUS` | Lifecycle status of membership |
| 5 | `LOGIN_ROLE` | Application login role classification |
| 6 | `STATUS_REASON` | Reason codes for status changes |
| 7 | `WORKFLOW_STATUS` | Generic workflow state values |
| 8 | `DOCUMENT_TYPE` | Classification of stored documents |
| 9 | `APPLICATION_TYPE` | Types of member applications |
| 10 | `MARITAL_STATUS` | Marital status for persons |
| 11 | `ADDRESS_TYPE` | Types of addresses (permanent, current, official) |

---

### 02_master_data.sql

Seeds individual values into `master_data` for each category created above.
Uses `CROSS JOIN ... VALUES` with a subquery to resolve `master_category_pk`
by `category_code` — no hardcoded UUIDs.

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

**MEMBERSHIP_STATUS** (7 values): ACTIVE, INACTIVE, SUSPENDED, TRANSFERRED,
RESIGNED, EXPELLED, DECEASED

**RELATIONSHIP_TYPE** (29 values, comprehensive for Indian family structure):
- Immediate family: SPOUSE, FATHER, MOTHER, SON, DAUGHTER, BROTHER, SISTER
- In-laws: FATHER_IN_LAW, MOTHER_IN_LAW, SON_IN_LAW, DAUGHTER_IN_LAW,
  BROTHER_IN_LAW, SISTER_IN_LAW
- Grandparents/grandchildren: GRANDFATHER, GRANDMOTHER, GRANDSON, GRANDDAUGHTER
- Uncle/aunt/nephew/niece: UNCLE, AUNT, NEPHEW, NIECE
- Cousins: COUSIN
- Step relations: STEP_FATHER, STEP_MOTHER, STEP_SON, STEP_DAUGHTER
- Guardian/ward: GUARDIAN, WARD
- Other: OTHER

---

### 03_id_sequence_master.sql

Seeds 9 ID sequences into `id_sequence_master`. Each sequence defines a
prefix and counter for generating human-readable business IDs.

| # | `sequence_code` | Prefix | Generated ID example | Purpose |
|--:|-----------------|--------|---------------------|---------|
| 1 | `PERSON` | `P` | P00000001 | Person identity |
| 2 | `SANGHA_SEVI` | `SS` | SS00000001 | Membership identity |
| 3 | `ANCHALIKA` | `ANC` | ANC00000001 | Anchalika organization (multiple) |
| 4 | `ZILLA` | `ZL` | ZL00000001 | Zilla organization (multiple) |
| 5 | `SAKHA` | `SKH` | SKH00000001 | Sakha organization (multiple) |
| 6 | `SAKHA_ASANA` | `SA` | SA00000001 | Sakha Asana organization (multiple) |
| 7 | `PATHA_CHAKRA` | `PC` | PC00000001 | Patha Chakra organization (multiple) |
| 8 | `FAMILY` | `F` | F00000001 | Family group |
| 9 | `DOCUMENT` | `DOC` | DOC00000001 | Document tracking |

All sequences start at `current_value = 0` with `padding_length = 8`.

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

Seeds ~770 districts into `district` for all Indian states and Union
Territories. Uses subquery to resolve `state_pk` by `state_code` within
India. Non-India countries do not have pre-seeded districts — those are
populated at runtime as needed.

| State | Districts | State | Districts |
|-------|----------:|-------|----------:|
| Andhra Pradesh | 26 | Maharashtra | 36 |
| Arunachal Pradesh | 26 | Manipur | 16 |
| Assam | 35 | Meghalaya | 12 |
| Bihar | 38 | Mizoram | 11 |
| Chhattisgarh | 33 | Nagaland | 16 |
| Goa | 2 | Odisha | 30 |
| Gujarat | 33 | Punjab | 23 |
| Haryana | 22 | Rajasthan | 50 |
| Himachal Pradesh | 12 | Sikkim | 6 |
| Jharkhand | 24 | Tamil Nadu | 38 |
| Karnataka | 31 | Telangana | 33 |
| Kerala | 14 | Tripura | 8 |
| Madhya Pradesh | 55 | Uttar Pradesh | 75 |
| | | Uttarakhand | 13 |
| | | West Bengal | 23 |

**Union Territories:**

| UT | Districts |
|----|----------:|
| Delhi | 11 |
| Jammu & Kashmir | 20 |
| Ladakh | 2 |
| Chandigarh | 1 |
| Puducherry | 4 |
| Andaman & Nicobar | 3 |
| Dadra & Nagar Haveli and Daman & Diu | 3 |
| Lakshadweep | 1 |

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
| 5 | `PRESIDENT_APPROVAL_REQUIRED` | `true` | BOOLEAN | Whether President approval is needed for membership actions |

---

### 08_postal_code.sql

Seeds 2 postal codes into `postal_code` — the minimal bootstrap set required
by Organization seed data (FK references from `organization.postal_code_pk`).
Uses JOIN to resolve `country_pk` and `state_pk` from existing seed data.

| # | Postal Code | Post Office | Used By |
|--:|-------------|-------------|---------|
| 1 | `751022` | Unit 9 SO, Bhubaneswar | Kendra Sangha (Satsikshya Mandir) |
| 2 | `752001` | Puri HO | Nilachala Kutira, Smruti Mandira |

Full postal code data (India Post PIN codes) is loaded during deployment
or data migration — this file only seeds what the Organization bootstrap needs.

---

## Notes

- Seed data uses `CROSS JOIN ... VALUES` with subqueries to resolve parent PKs
  by code — no hardcoded UUIDs.
- Additional categories and values will be added by downstream module seeds
  (e.g., Organization adds organization-type values to `master_data`).
- Cities/villages are not seeded — populated during deployment or data migration.
- Postal codes: a minimal bootstrap set (751022 Bhubaneswar, 752001 Puri) is
  seeded to satisfy Organization seed FK references. Full postal code data
  (India Post PIN codes) is populated during deployment or data migration.
