"""
Parity guard for the Assets & Property custodian rule (owner rule 2026-11-02,
GDR-010 §2C): property and assets are HELD only by physical organizations.

ONE definition per layer, kept in step here (same idea as
tests/api/test_sakha_asana_parity.py):
  Python  api/helpers.py::ASSET_CUSTODIAN_ORG_TYPES (built from SAKHA_LIKE_ORG_TYPES)
  SQL     nss.fn_is_asset_custodian_org_type()
          (database/ddl/11_assets_property/09_asset_custodian_org_type_function.sql)
  JS      NSS.ASSET_CUSTODIAN_ORG_TYPES (frontend/assets/js/nss-config.js)

File-parsing tests need no database; the last class checks the live function
and the live ORGANIZATION_TYPE catalogue (needs the bootstrapped DB).
"""

import re
from pathlib import Path

import pytest

from api.helpers import (
    ASSET_CUSTODIAN_NON_SAKHA_ORG_TYPES,
    ASSET_CUSTODIAN_ORG_TYPES,
    ASSET_CUSTODIAN_ORG_TYPES_SQL,
    SAKHA_LIKE_ORG_TYPES,
    is_asset_custodian_org_type,
)
from tests.assets_property_support import ELIGIBLE_CUSTODIAN_TYPES, INELIGIBLE_CUSTODIAN_TYPES

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
SQL_FILE = REPO / "database/ddl/11_assets_property/09_asset_custodian_org_type_function.sql"
EXPECTED = {"SAKHA_SANGHA", "SAKHA_ASANA", "PATHA_CHAKRA", "KENDRA", "NILACHALA_KUTIRA", "SMRUTI_MANDIRA"}


def _sql_other_types() -> tuple[str, ...]:
    text = SQL_FILE.read_text(encoding="utf-8")
    body = text[text.index("CREATE OR REPLACE FUNCTION nss.fn_is_asset_custodian_org_type"):]
    body = body[:body.index("$$;")]
    m = re.search(r"IN \(([^)]*)\)", body)
    assert m, "IN (...) list not found in the SQL function"
    return tuple(re.findall(r"'([A-Z_]+)'", m.group(1)))


class TestPython:
    def test_set_is_exactly_the_owner_rule(self):
        assert set(ASSET_CUSTODIAN_ORG_TYPES) == EXPECTED

    def test_built_from_the_sakha_like_definition(self):
        assert ASSET_CUSTODIAN_ORG_TYPES[:len(SAKHA_LIKE_ORG_TYPES)] == SAKHA_LIKE_ORG_TYPES
        assert ASSET_CUSTODIAN_ORG_TYPES == SAKHA_LIKE_ORG_TYPES + ASSET_CUSTODIAN_NON_SAKHA_ORG_TYPES

    def test_sql_fragment_is_generated_from_the_tuple(self):
        assert ASSET_CUSTODIAN_ORG_TYPES_SQL == "(" + ", ".join(f"'{t}'" for t in ASSET_CUSTODIAN_ORG_TYPES) + ")"

    @pytest.mark.parametrize("type_code", sorted(EXPECTED))
    def test_helper_accepts(self, type_code):
        assert is_asset_custodian_org_type(type_code)

    @pytest.mark.parametrize("type_code", INELIGIBLE_CUSTODIAN_TYPES + [None, ""])
    def test_helper_refuses(self, type_code):
        assert not is_asset_custodian_org_type(type_code)

    def test_test_support_lists_do_not_drift(self):
        assert set(ELIGIBLE_CUSTODIAN_TYPES) == EXPECTED
        assert not set(INELIGIBLE_CUSTODIAN_TYPES) & EXPECTED


class TestSqlFunctionFile:
    def test_sql_list_plus_sakha_function_equals_python(self):
        text = SQL_FILE.read_text(encoding="utf-8")
        assert "nss.fn_is_sakha_like_org_type(p_org_type_code)" in text   # the Sakha pair is not repeated
        assert _sql_other_types() == ASSET_CUSTODIAN_NON_SAKHA_ORG_TYPES

    def test_sql_does_not_repeat_the_sakha_pair(self):
        body = SQL_FILE.read_text(encoding="utf-8")
        body = body[body.index("CREATE OR REPLACE FUNCTION nss.fn_is_asset_custodian_org_type"):]
        assert "'SAKHA_" not in body[:body.index("$$;")]

    def test_trigger_is_insert_and_custodian_update_only_and_never_scans(self):
        text = SQL_FILE.read_text(encoding="utf-8")
        assert "BEFORE INSERT OR UPDATE OF custodian_organization_pk ON nss.custodianship" in text
        assert "FOR EACH ROW" in text and "ERRCODE = 'check_violation'" in text
        assert "ALTER TABLE" not in text   # no table rewrite / validation scan of existing rows


class TestJs:
    def test_constant_matches_python(self):
        js = (REPO / "frontend/assets/js/nss-config.js").read_text(encoding="utf-8")
        m = re.search(r"NSS\.ASSET_CUSTODIAN_ORG_TYPES\s*=\s*\[([^\]]*)\]", js)
        assert m, "NSS.ASSET_CUSTODIAN_ORG_TYPES not found"
        entries = [e.strip() for e in m.group(1).split(",") if e.strip()]
        assert entries[0] == "...NSS.SAKHA_LIKE_ORG_TYPES"                  # Sakha pair spread, not repeated
        assert tuple(e.strip('"') for e in entries[1:]) == ASSET_CUSTODIAN_NON_SAKHA_ORG_TYPES

    def test_helper_exists(self):
        js = (REPO / "frontend/assets/js/nss-config.js").read_text(encoding="utf-8")
        assert "NSS.isAssetCustodianOrgType" in js


class TestBuildWiring:
    FILE = "09_asset_custodian_org_type_function.sql"

    @pytest.mark.parametrize("script", ["database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh"])
    def test_script_runs_the_patch_after_the_guards_and_before_the_reference_patch(self, script):
        text = (REPO / script).read_text(encoding="utf-8")
        guards = text.index("08_assets_property_guards.sql\"")
        fn = text.index(self.FILE + '"')
        ref = text.index("01_assets_property_reference_data_patch.sql\"")
        assert guards < fn < ref
        assert re.search(r'(run_sql|Invoke-Sql) "asset_custodian_org_type_function"', text)

    @pytest.mark.parametrize("script", ["database/scripts/03_validate.sh", "database/scripts/03_validate.ps1"])
    def test_validate_checks_function_trigger_and_warns_on_legacy_rows(self, script):
        text = (REPO / script).read_text(encoding="utf-8")
        assert "fn_is_asset_custodian_org_type" in text
        assert "trg_custodianship_custodian_guard" in text
        assert re.search(r"(check_warn_count|Check-WarnCount) \"Assets & Property: existing custodianships held by a NON-eligible", text)

    def test_sh_and_ps1_validate_use_the_same_sql(self):
        sh = (REPO / "database/scripts/03_validate.sh").read_text(encoding="utf-8")
        ps = (REPO / "database/scripts/03_validate.ps1").read_text(encoding="utf-8")
        for needle in ("NOT nss.fn_is_asset_custodian_org_type(md.value_code)", "tgname = 'trg_custodianship_custodian_guard'"):
            assert needle in sh and needle in ps


class TestOwnerDecisionPatchesWiring:
    """Static (DB-free) checks of the 2026-11-02 owner decisions: grant withdrawal and 'belongs to' (GDR-010 §2B.2/§2D)."""

    SCRIPTS = ["database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh"]
    WITHDRAWN = [
        ("NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN", "ASSET_VIEW"), ("NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN", "ASSET_MANAGE"),
        ("NSS_ERP_ANCHALIKA_ADMIN", "ASSET_MANAGE"), ("NSS_ERP_ZILLA_ADMIN", "ASSET_MANAGE"),
    ]

    @pytest.mark.parametrize("script", SCRIPTS)
    def test_revoke_patch_runs_right_after_the_grant_patch(self, script):
        text = (REPO / script).read_text(encoding="utf-8")
        grant = text.index('05_assets_property_permissions_patch.sql"')
        revoke = text.index('06_assets_property_permissions_revoke_patch.sql"')
        assert grant < revoke
        assert re.search(r'(run_sql|Invoke-Sql) "assets_property permissions revoke patch"', text)

    @pytest.mark.parametrize("script", SCRIPTS)
    def test_belongs_to_patch_runs_after_the_tables_and_guards(self, script):
        text = (REPO / script).read_text(encoding="utf-8")
        fn = text.index('09_asset_custodian_org_type_function.sql"')
        bt = text.index('10_assets_property_belongs_to_patch.sql"')
        ref = text.index('01_assets_property_reference_data_patch.sql"')
        assert fn < bt < ref
        assert re.search(r'(run_sql|Invoke-Sql) "assets_property_belongs_to_patch"', text)

    def test_grant_patch_no_longer_inserts_the_withdrawn_pairs(self):
        sql = (REPO / "database/seed/00_bootstrap/05_assets_property_permissions_patch.sql").read_text(encoding="utf-8")
        body = sql[sql.index("WITH mappings"):]
        for role, perm in self.WITHDRAWN:
            assert f"('{role}', '{perm}')" not in body
        assert len(re.findall(r"\('NSS_ERP_\w+', 'ASSET_(?:VIEW|MANAGE)'\)", body)) == 12

    def test_revoke_patch_soft_deletes_exactly_the_four_pairs(self):
        sql = (REPO / "database/seed/00_bootstrap/06_assets_property_permissions_revoke_patch.sql").read_text(encoding="utf-8")
        code = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
        assert sorted(re.findall(r"\('(NSS_ERP_\w+)',\s*'(ASSET_\w+)'\)", code)) == sorted(self.WITHDRAWN)
        assert not re.search(r"\bDELETE\s+FROM\b", code, re.IGNORECASE)
        assert "is_active  = FALSE" in code and "deleted_at = NOW()" in code
        assert "rp.is_active           = TRUE" in code            # idempotent: only still-active rows

    def test_belongs_to_is_in_both_the_table_ddl_and_the_patch(self):
        for table, ddl in (("property", "01_property.sql"), ("asset", "02_asset.sql")):
            text = (REPO / "database/ddl/11_assets_property" / ddl).read_text(encoding="utf-8")
            assert "belongs_to_organization_pk UUID NULL" in text
            assert f"fk_{table}_belongs_to_org" in text and f"idx_{table}_belongs_to_org" in text
        patch = (REPO / "database/ddl/11_assets_property/10_assets_property_belongs_to_patch.sql").read_text(encoding="utf-8")
        assert patch.count("ADD COLUMN IF NOT EXISTS belongs_to_organization_pk UUID NULL") == 2
        assert patch.count("CREATE INDEX IF NOT EXISTS") == 2
        assert "REFERENCES nss.organization (organization_pk)" in patch

    def test_validate_sh_and_ps1_carry_the_same_new_checks(self):
        sh = (REPO / "database/scripts/03_validate.sh").read_text(encoding="utf-8")
        ps = (REPO / "database/scripts/03_validate.ps1").read_text(encoding="utf-8")
        for needle in (
            "the 4 withdrawn grants are NOT active",
            "property -> organization (belongs-to)", "asset -> organization (belongs-to)",
            "ASSET_MANAGE actively granted to >= 4 roles", "ASSET_VIEW actively granted to >= 8 roles",
            "belongs_to_organization_pk",
        ):
            assert needle in sh and needle in ps, needle
        assert '"role_permission" 178' in sh and '"role_permission" 178' in ps


class TestAcquisitionAndTerminalCustodyWiring:
    """Static (DB-free) checks of the 2026-11-03 owner decisions: acquisition method (GDR-010 §2E) and
    disposal / retirement closing custody (GDR-010 §2F)."""

    SCRIPTS = ["database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh"]
    DDL = REPO / "database/ddl/11_assets_property"
    ACQ = "11_assets_property_acquisition_method_patch.sql"
    TERMINAL = "12_assets_property_terminal_custody_patch.sql"

    @pytest.mark.parametrize("script", SCRIPTS)
    def test_acquisition_patch_runs_after_belongs_to_and_before_the_reference_patch(self, script):
        text = (REPO / script).read_text(encoding="utf-8")
        bt = text.index('10_assets_property_belongs_to_patch.sql"')
        acq = text.index(self.ACQ + '"')
        ref = text.index('01_assets_property_reference_data_patch.sql"')
        assert bt < acq < ref
        assert re.search(r'(run_sql|Invoke-Sql) "assets_property_acquisition_method_patch"', text)

    @pytest.mark.parametrize("script", SCRIPTS)
    def test_terminal_custody_patch_runs_after_the_reference_patch_that_seeds_its_end_reasons(self, script):
        text = (REPO / script).read_text(encoding="utf-8")
        ref = text.index('01_assets_property_reference_data_patch.sql"')
        term = text.index(self.TERMINAL + '"')
        assert ref < term
        assert re.search(r'(run_sql|Invoke-Sql) "assets_property_terminal_custody_patch"', text)

    @pytest.mark.parametrize("script", SCRIPTS[:2])
    def test_build_header_lists_both_patches(self, script):
        text = (REPO / script).read_text(encoding="utf-8")
        assert f"ddl/11_assets_property/{self.ACQ}" in text and f"ddl/11_assets_property/{self.TERMINAL}" in text

    def test_acquisition_column_is_in_both_table_ddl_and_the_patch(self):
        for table, ddl in (("property", "01_property.sql"), ("asset", "02_asset.sql")):
            text = (self.DDL / ddl).read_text(encoding="utf-8")
            assert "acquisition_method_master_data_pk UUID NULL" in text
            assert f"fk_{table}_acquisition_method" in text and f"idx_{table}_acquisition_method" in text
        patch = (self.DDL / self.ACQ).read_text(encoding="utf-8")
        assert patch.count("ADD COLUMN IF NOT EXISTS acquisition_method_master_data_pk UUID NULL") == 2
        assert patch.count("CREATE INDEX IF NOT EXISTS") == 2
        assert "REFERENCES nss.master_data (master_data_pk)" in patch

    def test_reference_patch_seeds_the_category_and_the_two_terminal_end_reasons(self):
        sql = (REPO / "database/seed/11_assets_property/01_assets_property_reference_data_patch.sql").read_text(encoding="utf-8")
        assert "('ACQUISITION_METHOD', 'Acquisition Method'" in sql
        for code in ("PURCHASE", "DONATION", "GIFT", "BEQUEST", "TRANSFER_IN", "CONSTRUCTION", "OTHER"):
            assert f"('ACQUISITION_METHOD', '{code}'" in sql
        assert "('CUSTODIANSHIP_END_REASON', 'DISPOSED'" in sql and "('CUSTODIANSHIP_END_REASON', 'RETIRED'" in sql
        assert "ON CONFLICT (master_category_pk, value_code) DO NOTHING" in sql      # never overwrites an admin's edit

    def test_terminal_custody_patch_is_dml_only_and_only_touches_active_rows_of_terminal_records(self):
        sql = (self.DDL / self.TERMINAL).read_text(encoding="utf-8")
        code = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
        assert not re.search(r"\b(DELETE|DROP|TRUNCATE|ALTER|CREATE)\b", code, re.IGNORECASE)
        assert code.count("UPDATE nss.custodianship") == 2
        assert "p.status = 'DISPOSED'" in code and "a.status = 'RETIRED'" in code
        assert code.count("c.status = 'ACTIVE'") == 2                      # idempotent: ENDED rows never match again

    def test_guards_file_adds_the_terminal_insert_guard_and_keeps_the_rest(self):
        sql = (self.DDL / "08_assets_property_guards.sql").read_text(encoding="utf-8")
        for needle in ("fn_custodianship_terminal_guard", "trg_custodianship_terminal_guard", "BEFORE INSERT ON nss.custodianship",
                       "trg_custodianship_guard", "AP-018 violation: an ENDED custodianship is history"):
            assert needle in sql, needle

    def test_validate_sh_and_ps1_carry_the_same_new_checks(self):
        sh = (REPO / "database/scripts/03_validate.sh").read_text(encoding="utf-8")
        ps = (REPO / "database/scripts/03_validate.ps1").read_text(encoding="utf-8")
        for needle in (
            "property -> master_data (acquisition method)", "asset -> master_data (acquisition method)",
            "ACQUISITION_METHOD master category seeded with values", "CUSTODIANSHIP_END_REASON has DISPOSED + RETIRED",
            "no ACTIVE custodianship on a DISPOSED property / RETIRED asset",
            "terminal-record custodianship insert guard present", "acquisition_method_master_data_pk",
            "SELECT 7 - COUNT(DISTINCT mc.category_code)", "'ACQUISITION_METHOD');",
        ):
            assert needle in sh and needle in ps, needle


class TestLiveDatabase:
    @pytest.mark.parametrize("type_code", sorted(EXPECTED | set(INELIGIBLE_CUSTODIAN_TYPES)))
    def test_sql_function_agrees_with_python(self, write_conn, type_code):
        with write_conn.cursor() as cur:
            cur.execute("SELECT nss.fn_is_asset_custodian_org_type(%s)", (type_code,))
            assert cur.fetchone()[0] is is_asset_custodian_org_type(type_code)

    def test_every_organization_type_is_classified(self, write_conn):
        """A newly added ORGANIZATION_TYPE must be consciously classified (custodian or not)."""
        with write_conn.cursor() as cur:
            cur.execute(
                """
                SELECT md.value_code FROM nss.master_data md
                JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
                WHERE mc.category_code = 'ORGANIZATION_TYPE' AND md.is_active = TRUE
                """
            )
            live = {r[0] for r in cur.fetchall()}
        unclassified = live - EXPECTED - set(INELIGIBLE_CUSTODIAN_TYPES)
        assert not unclassified, f"Classify new organization type(s) for custodianship: {sorted(unclassified)}"
