"""
Sakha Asana == Sakha everywhere (owner decision 2026-10-31).

A SAKHA_ASANA is a Sakha Sangha without its own building: same
SAKHA_GOVERNING_BODY, President, members, attendance, correspondence and
Advisory Board representation. The ONE Python definition is
api/helpers.py::SAKHA_LIKE_ORG_TYPES (SQL: nss.fn_is_sakha_like_org_type(),
JS: NSS.SAKHA_LIKE_ORG_TYPES).

Two groups:
  * Static guards (no DB, no network): the stray-literal regression scan, the
    cross-layer constant consistency check, and the DDL/patch/build-script
    wiring checks.
  * Behaviour tests (real DB like the rest of tests/api, rolled back with the
    module SAVEPOINT) — written but NOT yet run against a database; do not
    claim they pass.
"""

import re
from pathlib import Path
from uuid import uuid4

import pytest

from api.helpers import (
    SAKHA_LIKE_ORG_TYPES,
    SAKHA_LIKE_ORG_TYPES_SQL,
    is_sakha_like,
)

REPO = Path(__file__).resolve().parents[2]


def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


# ═══════════════════════════════════════════════════════════════════════
# Static guard 1: no stray hard-coded 'SAKHA_SANGHA'-only filters
# ═══════════════════════════════════════════════════════════════════════

# Every non-comment line outside this allow-list that mentions a QUOTED
# SAKHA_SANGHA (or ``type_code=SAKHA_SANGHA``) fails the test: the gap that
# Sakha Asana fell through must not silently reappear. Each entry is a
# deliberately Sakha-Sangha-specific site (or a definition of the shared
# constant itself), with the reason. Substrings are matched against the
# whitespace-normalised line.
ALLOW_LIST: dict[str, list[str]] = {
    # ── the shared definitions themselves ──
    "api/helpers.py": ['SAKHA_LIKE_ORG_TYPES: tuple[str, ...] = ("SAKHA_SANGHA", "SAKHA_ASANA")'],
    "database/ddl/02_organization/10_sakha_like_org_type_function.sql":
        ["IN ('SAKHA_SANGHA', 'SAKHA_ASANA')"],
    "frontend/assets/js/nss-config.js": ['SAKHA_LIKE_ORG_TYPES: ["SAKHA_SANGHA", "SAKHA_ASANA"]'],
    # ── API docs strings only ──
    "api/routers/organization.py": ["Query(None, description="],
    "api/schemas/correspondence.py": ["e.g. 'SAKHA_SANGHA'"],
    # ── ORG-BR-096: Asana is never created through create_organization;
    #    id-sequence code generation is per stored type ──
    "api/routers/admin.py": [
        '"SAKHA_SANGHA": "SAKHA",',                                             # _TYPE_TO_SEQUENCE (code generation)
        '"ANCHALIKA_SANGHA", "ZILLA_SANGHA", "PATHA_CHAKRA", "SAKHA_SANGHA",',  # _STANDARD_CREATABLE_TYPES (ORG-BR-096)
    ],
    # ── ORG-BR-090: the Sakha's own allowed parents, keyed by stored type. The wing
    #    parents (Kumari/Sevak/local Mahila/Paribarik Asana) derive from
    #    SAKHA_LIKE_ORG_TYPES (GDR-008) and so are no longer literals ──
    "api/services/org_reparent_service.py": [
        '"SAKHA_SANGHA": {"ANCHALIKA_SANGHA", "ZILLA_SANGHA"},',
    ],
    # ── seed data keyed on the stored type ──
    "database/seed/01_foundation/02_master_data.sql": ["('SAKHA_SANGHA',"],
    "database/seed/02_organization/06_id_sequence_org_sync.sql": ["('SAKHA_SANGHA',"],
    "database/seed/02_organization/05_sakha_branches.sql": ["= 'SAKHA_SANGHA'"],       # the 175 real branches are SAKHA_SANGHA
    "database/seed/08_governance/03_body_master.sql": ["= 'SAKHA_SANGHA'"],            # Asana shells: 04_sakha_asana_*_patch.sql
    # ── frontend: dashboard "level" keys, creation form, wing parent map ──
    "frontend/assets/js/admin.js": [
        '{ typeCode: "SAKHA_SANGHA", label: "Sakha" },',          # DASHBOARD_LEVELS canonical Sakha level (NSS.orgLevelTypes widens it)
        '{ key: "SAKHA_SANGHA", label: "Sakha", typeCodes:',      # CORR_REGISTER_TAB_GROUPS tab key (typeCodes is the shared list)
        'orgTypeFilter: "SAKHA_SANGHA",',                         # default selection of a type dropdown
        'const standard = ["ANCHALIKA_SANGHA", "ZILLA_SANGHA", "PATHA_CHAKRA", "SAKHA_SANGHA"];',  # creatable types (ORG-BR-096)
        'organization_type_code === "SAKHA_SANGHA";',            # has_own_premises is a SAKHA_SANGHA attribute (ORG-BR-098)
        '|| "SAKHA_SANGHA" });',                                  # label fallback when the option carries no type
    ],
    "frontend/assets/js/dashboard.js": [
        '{ typeCode: "SAKHA_SANGHA", label: "Sakha" },',          # DASHBOARD_LEVELS canonical Sakha level
        'dashboardOrgsFor("SAKHA_SANGHA")',                       # the Sakha LEVEL (NSS.orgLevelTypes widens it)
        '|| "SAKHA_SANGHA",',                                     # default scope type when absent
        '? "SAKHA_SANGHA" : typeCode',
    ],
    "frontend/dashboard.html": ["orgCardIcon('SAKHA_SANGHA')", "orgIconSvg('SAKHA_SANGHA')"],  # the Sakha step icon
}

_FLAGGED = re.compile(r"""(['"])SAKHA_SANGHA\1|type_code=SAKHA_SANGHA\b|\bvalue_code\s*=\s*SAKHA_SANGHA\b""")
_COMMENT_PREFIXES = ("#", "--", "//", "*", "/*", "<!--")

_SCAN_GLOBS = [
    ("api", "*.py"),
    ("database/ddl", "*.sql"),
    ("database/seed", "*.sql"),
    ("frontend/assets/js", "*.js"),
    ("frontend", "*.html"),
]


def _scan_files():
    for root, pattern in _SCAN_GLOBS:
        base = REPO / root
        it = base.rglob(pattern) if root != "frontend" else base.glob(pattern)
        for path in sorted(it):
            rel = path.relative_to(REPO).as_posix()
            if "/demo/" in rel or "__pycache__" in rel or rel.endswith(".min.js"):
                continue
            yield rel, path


def _flagged_lines():
    for rel, path in _scan_files():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(_COMMENT_PREFIXES):
                continue
            if _FLAGGED.search(line):
                yield rel, n, _norm(line)


class TestNoStraySakhaOnlyLiterals:
    def test_every_hard_coded_sakha_sangha_is_allow_listed(self):
        stray = [
            f"{rel}:{n}: {text}"
            for rel, n, text in _flagged_lines()
            if not any(allowed in text for allowed in ALLOW_LIST.get(rel, ()))
        ]
        assert not stray, (
            "Hard-coded 'SAKHA_SANGHA' outside the allow-list — a Sakha Asana "
            "would silently be treated as a non-Sakha. Use SAKHA_LIKE_ORG_TYPES "
            "(api/helpers.py) / nss.fn_is_sakha_like_org_type() / "
            "NSS.SAKHA_LIKE_ORG_TYPES, or allow-list the site with a reason:\n  "
            + "\n  ".join(stray)
        )

    def test_allow_list_has_no_stale_entries(self):
        seen: dict[str, list[str]] = {}
        for rel, _n, text in _flagged_lines():
            seen.setdefault(rel, []).append(text)
        stale = [
            f"{rel}: {allowed}"
            for rel, allowed_list in ALLOW_LIST.items()
            for allowed in allowed_list
            if not any(allowed in text for text in seen.get(rel, ()))
        ]
        assert not stale, "Allow-list entries that no longer match any line (remove them):\n  " + "\n  ".join(stale)

    def test_scan_actually_finds_the_known_sites(self):
        """Guards the guard: a broken glob/regex would make the scan vacuous."""
        assert sum(1 for _ in _flagged_lines()) >= 20


# ═══════════════════════════════════════════════════════════════════════
# Static guard 2: one definition per layer, kept in step
# ═══════════════════════════════════════════════════════════════════════

class TestSharedDefinitionsAgree:
    def test_python_constant(self):
        assert SAKHA_LIKE_ORG_TYPES == ("SAKHA_SANGHA", "SAKHA_ASANA")
        assert is_sakha_like("SAKHA_ASANA") and is_sakha_like("SAKHA_SANGHA")
        assert not is_sakha_like("ANCHALIKA_SANGHA") and not is_sakha_like(None)

    def test_sql_in_list_is_generated_from_the_constant(self):
        assert SAKHA_LIKE_ORG_TYPES_SQL == "('SAKHA_SANGHA', 'SAKHA_ASANA')"

    def test_sql_function_matches_python(self):
        sql = (REPO / "database/ddl/02_organization/10_sakha_like_org_type_function.sql").read_text()
        body = sql.split("AS $$", 1)[1]
        assert tuple(re.findall(r"'([A-Z_]+)'", body)) == SAKHA_LIKE_ORG_TYPES

    def test_js_constant_matches_python(self):
        js = (REPO / "frontend/assets/js/nss-config.js").read_text()
        m = re.search(r"SAKHA_LIKE_ORG_TYPES:\s*\[([^\]]*)\]", js)
        assert m, "NSS.SAKHA_LIKE_ORG_TYPES not found"
        assert tuple(re.findall(r'"([A-Z_]+)"', m.group(1))) == SAKHA_LIKE_ORG_TYPES

    def test_membership_and_advisory_triggers_use_the_sql_function(self):
        for rel in (
            "database/ddl/05_membership/14_sakha_only_membership_trigger.sql",
            "database/ddl/08_governance/12_governance_seat_limits.sql",
        ):
            text = (REPO / rel).read_text()
            assert "nss.fn_is_sakha_like_org_type" in text, rel

    def test_sakha_dashboard_level_and_icons_widen_to_asana(self):
        from_js = (REPO / "frontend/assets/js/nss-config.js").read_text()
        assert "orgLevelTypes(typeCode)" in from_js and "appendSakhaLikeTypeCodes(params)" in from_js


# ═══════════════════════════════════════════════════════════════════════
# Static guard 3: DDL / patch / build-script wiring (.sh == .ps1 == render)
# ═══════════════════════════════════════════════════════════════════════

_BUILD_SCRIPTS = ["database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh"]


class TestPatchWiring:
    @pytest.mark.parametrize("script", _BUILD_SCRIPTS)
    def test_sakha_like_function_is_wired_before_its_callers(self, script):
        text = (REPO / script).read_text()
        fn = text.index("10_sakha_like_org_type_function.sql")
        membership = re.search(r"14_sakha_only_membership_trigger\.sql", text).start()
        governance = re.search(r"12_governance_seat_limits\.sql\"", text).start()
        assert fn < membership and fn < governance

    @pytest.mark.parametrize("script", _BUILD_SCRIPTS)
    def test_step_role_patch_is_wired_after_the_step_table(self, script):
        text = (REPO / script).read_text()
        ddl = text.index("07_organization_reparent_step.sql")
        patch = text.index("09_organization_reparent_step_source_role_patch.sql")
        assert patch > ddl

    def test_step_ddl_and_patch_allow_the_new_role_and_four_steps(self):
        for rel in (
            "database/ddl/02_organization/07_organization_reparent_step.sql",
            "database/ddl/02_organization/09_organization_reparent_step_source_role_patch.sql",
        ):
            text = (REPO / rel).read_text()
            assert "'SOURCE_PARENT_PRESIDENT'" in text, rel
            assert "BETWEEN 1 AND 4" in text, rel

    def test_service_roles_are_all_in_the_ddl_check(self):
        from api.services import org_reparent_service as svc

        ddl = (REPO / "database/ddl/02_organization/07_organization_reparent_step.sql").read_text()
        for role in (svc.ROLE_SAKHA_PRESIDENT, svc.ROLE_SOURCE_PARENT_PRESIDENT,
                     svc.ROLE_DEST_PARENT_PRESIDENT, svc.ROLE_KENDRA_PRESIDENT):
            assert f"'{role}'" in ddl
        labels = (REPO / "frontend/assets/js/nss-config.js").read_text()
        assert "SOURCE_PARENT_PRESIDENT:" in labels


# ═══════════════════════════════════════════════════════════════════════
# Behaviour: an Asana behaves like a Sakha (real DB, rolled back)
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def asana_world(client, write_conn):
    from tests.reparent_support import (
        _create_admin_with_scope, _create_person_with_login, _login_headers, _with_sevi_pk,
        create_org, create_test_organization, kendra_pks, location_pks,
    )

    kendra_pk, _ = kendra_pks(write_conn)
    admin = _with_sevi_pk(write_conn, _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE", organization_pk=None))
    admin_h = _login_headers(client, admin["sangha_sevi_id"], admin["password"])
    loc = location_pks(write_conn)
    parent = create_org(client, admin_h, loc, "ANCHALIKA_SANGHA", kendra_pk, "AsnParent")
    asana = create_test_organization(
        write_conn, name_prefix="AsnParity", type_code="SAKHA_ASANA", parent_pk=parent,
        short_code="AP" + uuid4().hex[:3].upper(),
    )
    member = _create_person_with_login(write_conn, "AsanaMember", organization_pk=asana)
    return {"admin_h": admin_h, "parent": parent, "asana": asana, "member": member,
            "kendra_pk": kendra_pk}


@pytest.mark.integration
class TestAsanaIsASakha:
    def test_require_sakha_organization_accepts_asana_and_rejects_non_sakha(self, write_conn, asana_world):
        from fastapi import HTTPException
        from api.helpers import require_sakha_organization

        cur = write_conn.cursor()
        require_sakha_organization(cur, asana_world["asana"])
        with pytest.raises(HTTPException) as exc:
            require_sakha_organization(cur, asana_world["parent"])
        assert exc.value.status_code == 422

    def test_db_trigger_allows_a_member_at_an_asana_but_not_at_an_anchalika(self, write_conn, asana_world):
        """MBR-038A trigger (fn_is_sakha_like_org_type): the fixture already
        inserted a sangha_sevi at the Asana; moving it under an Anchalika must fail."""
        import psycopg2

        cur = write_conn.cursor()
        cur.execute("SELECT organization_pk FROM nss.sangha_sevi WHERE sangha_sevi_pk = %s",
                    (asana_world["member"]["sangha_sevi_pk"],))
        assert str(cur.fetchone()[0]) == asana_world["asana"]
        cur.execute("SAVEPOINT asana_trigger_probe")
        with pytest.raises(psycopg2.Error):
            cur.execute("UPDATE nss.sangha_sevi SET organization_pk = %s WHERE sangha_sevi_pk = %s",
                        (asana_world["parent"], asana_world["member"]["sangha_sevi_pk"]))
        cur.execute("ROLLBACK TO SAVEPOINT asana_trigger_probe")

    def test_sql_function_truth_table(self, write_conn):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT nss.fn_is_sakha_like_org_type('SAKHA_SANGHA'), nss.fn_is_sakha_like_org_type('SAKHA_ASANA'),
                   nss.fn_is_sakha_like_org_type('ANCHALIKA_SANGHA'), nss.fn_is_sakha_like_org_type(NULL)
        """)
        assert cur.fetchone() == (True, True, False, False)

    def test_home_sakha_resolves_an_asana(self, write_conn, asana_world):
        from api.routers.governance import _home_sakha

        pk, _name = _home_sakha(write_conn.cursor(), asana_world["member"]["person_pk"])
        assert str(pk) == asana_world["asana"]

    def test_advisory_board_unrepresented_list_includes_an_asana(self, write_conn, asana_world):
        from api.routers.governance import _advisory_board_unrepresented_sakhas

        cur = write_conn.cursor()
        cur.execute("""
            SELECT bm.body_master_pk FROM nss.body_master bm
            JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
            WHERE bt.body_type_code = 'ADVISORY_BOARD' AND bm.is_active = TRUE LIMIT 1
        """)
        row = cur.fetchone()
        if row is None:
            pytest.skip("No ADVISORY_BOARD body shell seeded.")
        rows = _advisory_board_unrepresented_sakhas(cur, str(row[0]))
        assert asana_world["asana"] in {str(r["organization_pk"]) for r in rows}

    def test_org_list_or_matches_both_sakha_like_types(self, client, asana_world):
        r = client.get(
            "/api/v1/organization/organizations?type_code=SAKHA_SANGHA&type_code=SAKHA_ASANA&limit=500",
            headers=asana_world["admin_h"],
        )
        assert r.status_code == 200, r.text
        assert asana_world["asana"] in {o["organization_pk"] for o in r.json()}

    def test_org_stats_sakha_count_includes_an_asana(self, client, asana_world):
        r = client.get(f"/api/v1/organization/organizations/{asana_world['parent']}/stats",
                       headers=asana_world["admin_h"])
        assert r.status_code == 200, r.text
        assert r.json()["sakha_sanghas"] == 1, "the parent's only Sakha-like descendant is the Asana"

    def test_public_registration_sakha_list_includes_an_asana(self, client, asana_world):
        r = client.get("/api/v1/register/reference-data")
        assert r.status_code == 200, r.text
        assert asana_world["asana"] in {s["organization_pk"] for s in r.json()["sakhas"]}

    def test_member_attach_and_kumari_sevak_sakha_options_include_an_asana(self, client, asana_world):
        h = asana_world["admin_h"]
        r = client.get("/api/v1/admin/sakha-scope-options", headers=h)
        assert r.status_code == 200, r.text
        assert asana_world["asana"] in {s["organization_pk"] for s in r.json()["sakhas"]}
        # Wing parents are Sakha-like too (GDR-008, amends ORG-BR-092).
        w = client.get("/api/v1/admin/organizations/kumari-sevak-sakha-options?type_code=SEVAK_SANGHA", headers=h)
        assert w.status_code == 200, w.text
        assert asana_world["asana"] in {s["organization_pk"] for s in w.json()["sakhas"]}


# ═══════════════════════════════════════════════════════════════════════
# GDR-008: a Sakha Asana hosts every wing a Sakha Sangha can
# ═══════════════════════════════════════════════════════════════════════

_WING_TYPES = ("KUMARI_SANGHA", "SEVAK_SANGHA", "MAHILA_SANGHA", "PARIBARIK_ASANA")


class TestWingParentMatrixStatic:
    """No DB: the matrix is derived from the one shared Sakha-like set."""

    @pytest.mark.parametrize("wing", _WING_TYPES)
    def test_wing_parents_include_every_sakha_like_type(self, wing):
        from api.services.org_reparent_service import ALLOWED_PARENT_TYPES

        assert set(SAKHA_LIKE_ORG_TYPES) <= ALLOWED_PARENT_TYPES[wing]

    def test_exact_wing_parent_sets(self):
        from api.services.org_reparent_service import ALLOWED_PARENT_TYPES

        sakha_like = set(SAKHA_LIKE_ORG_TYPES)
        assert ALLOWED_PARENT_TYPES["KUMARI_SANGHA"] == sakha_like
        assert ALLOWED_PARENT_TYPES["SEVAK_SANGHA"] == sakha_like
        assert ALLOWED_PARENT_TYPES["PARIBARIK_ASANA"] == sakha_like
        # The Kendra tier of Mahila Sangha (the singleton) is kept as is.
        assert ALLOWED_PARENT_TYPES["MAHILA_SANGHA"] == {"KENDRA"} | sakha_like

    def test_admin_router_reexports_the_same_matrix(self):
        from api.routers import admin
        from api.services.org_reparent_service import ALLOWED_PARENT_TYPES

        assert admin._ALLOWED_PARENT_TYPES is ALLOWED_PARENT_TYPES

    def test_js_parent_map_is_derived_from_the_shared_js_constant(self):
        js = (REPO / "frontend/assets/js/admin.js").read_text()
        for line in ("KUMARI_SANGHA: sakhaLike,", "SEVAK_SANGHA: sakhaLike,",
                     'MAHILA_SANGHA: ["KENDRA", ...sakhaLike],', "PARIBARIK_ASANA: sakhaLike,"):
            assert line in js, line
        assert "const sakhaLike = NSS.SAKHA_LIKE_ORG_TYPES;" in js

    def test_kumari_sevak_uniqueness_trigger_keys_on_parent_pk_not_parent_type(self):
        sql = (REPO / "database/ddl/02_organization/05_organization_kumari_sevak_uniqueness_trigger.sql").read_text()
        body = sql.split("AS $$", 1)[1]
        assert "SAKHA_SANGHA" not in body and "SAKHA_ASANA" not in body


@pytest.fixture(scope="module")
def asana_wing_world(client, write_conn, asana_world):
    from tests.reparent_support import create_test_organization

    def wing(type_code, parent):
        return create_test_organization(
            write_conn, name_prefix=f"Wing{type_code[:4]}", type_code=type_code,
            parent_pk=parent, short_code=None,
        )

    from tests.reparent_support import create_org, location_pks

    # A separate Anchalika so these tests never disturb the stats assertions above.
    wparent = create_org(client, asana_world["admin_h"], location_pks(write_conn),
                         "ANCHALIKA_SANGHA", asana_world["kendra_pk"], "AsnWingParent")
    return {**asana_world, "wing": wing, "wparent": wparent}


@pytest.mark.integration
class TestAsanaHostsWings:
    @pytest.mark.parametrize("wing_type", ["KUMARI_SANGHA", "SEVAK_SANGHA"])
    def test_nss_admin_creates_kumari_sevak_under_an_asana(self, client, write_conn, asana_wing_world, wing_type):
        w = asana_wing_world
        r = client.post("/api/v1/admin/organizations", headers=w["admin_h"], json={
            "organization_name": f"AsnWing {wing_type} {uuid4().hex[:6]}",
            "organization_type_code": wing_type,
            "parent_organization_pk": w["asana"],
        })
        assert r.status_code == 201, r.text
        assert r.json()["organization_code"] is None  # wings carry no code (ORG-BR-104)
        cur = write_conn.cursor()
        cur.execute("SELECT parent_organization_pk FROM nss.organization WHERE organization_pk = %s",
                    (r.json()["organization_pk"],))
        assert str(cur.fetchone()[0]) == w["asana"]

    @pytest.mark.parametrize("wing_type", ["KUMARI_SANGHA", "SEVAK_SANGHA"])
    def test_second_active_kumari_sevak_per_asana_is_refused(self, client, asana_wing_world, wing_type):
        """ORG-BR-102 applies per Sakha-like parent: one active of each type per Asana."""
        w = asana_wing_world
        own_asana = w["wing"]("SAKHA_ASANA", w["wparent"])
        payload = {"organization_type_code": wing_type, "parent_organization_pk": own_asana}
        first = client.post("/api/v1/admin/organizations", headers=w["admin_h"],
                            json={**payload, "organization_name": f"AsnDup1 {uuid4().hex[:6]}"})
        assert first.status_code == 201, first.text
        second = client.post("/api/v1/admin/organizations", headers=w["admin_h"],
                             json={**payload, "organization_name": f"AsnDup2 {uuid4().hex[:6]}"})
        assert second.status_code in (409, 422), second.text

    def test_uniqueness_is_independent_between_an_asana_and_a_sangha_sakha(self, client, write_conn, asana_wing_world):
        from tests.reparent_support import create_org, location_pks

        w = asana_wing_world
        sakha = create_org(client, w["admin_h"], location_pks(write_conn), "SAKHA_SANGHA", w["wparent"], "AsnIndep")
        own_asana = w["wing"]("SAKHA_ASANA", w["wparent"])
        for pk in (sakha, own_asana):
            r = client.post("/api/v1/admin/organizations", headers=w["admin_h"], json={
                "organization_name": f"Indep {uuid4().hex[:6]}",
                "organization_type_code": "SEVAK_SANGHA", "parent_organization_pk": pk,
            })
            assert r.status_code == 201, r.text

    def test_db_accepts_local_mahila_and_paribarik_asana_under_an_asana(self, asana_wing_world):
        w = asana_wing_world
        assert w["wing"]("MAHILA_SANGHA", w["asana"])
        assert w["wing"]("PARIBARIK_ASANA", w["asana"])

    def test_local_mahila_under_an_asana_is_not_a_singleton(self, write_conn, asana_wing_world):
        """Only the Kendra-parented Mahila Sangha is unique; two under Asanas (or one
        under the same Asana twice) are legal, and the API mirror agrees."""
        from api.helpers import find_active_singleton_org_pk

        w = asana_wing_world
        w["wing"]("MAHILA_SANGHA", w["asana"])
        assert find_active_singleton_org_pk(write_conn.cursor(), "MAHILA_SANGHA", w["asana"]) is None
        w["wing"]("MAHILA_SANGHA", w["asana"])  # a second one does not trip the DB singleton trigger

    def test_wing_can_be_reparented_from_a_sangha_sakha_to_an_asana(self, client, write_conn, asana_wing_world):
        from tests.reparent_support import create_org, location_pks, parent_of, patch_parent

        w = asana_wing_world
        sakha = create_org(client, w["admin_h"], location_pks(write_conn), "SAKHA_SANGHA", w["wparent"], "AsnMove")
        made = client.post("/api/v1/admin/organizations", headers=w["admin_h"], json={
            "organization_name": f"MoveKumari {uuid4().hex[:6]}",
            "organization_type_code": "KUMARI_SANGHA", "parent_organization_pk": sakha,
        })
        assert made.status_code == 201, made.text
        fresh_asana = w["wing"]("SAKHA_ASANA", w["wparent"])
        r = patch_parent(client, w["admin_h"], made.json()["organization_pk"], fresh_asana)
        assert r.status_code == 200, r.text
        assert parent_of(write_conn, made.json()["organization_pk"]) == fresh_asana

    def test_wing_under_a_non_sakha_parent_is_still_refused(self, client, asana_wing_world):
        w = asana_wing_world
        r = client.post("/api/v1/admin/organizations", headers=w["admin_h"], json={
            "organization_name": f"BadParent {uuid4().hex[:6]}",
            "organization_type_code": "KUMARI_SANGHA", "parent_organization_pk": w["wparent"],
        })
        assert r.status_code == 422, r.text
        assert "SAKHA_ASANA" in r.json()["detail"] and "SAKHA_SANGHA" in r.json()["detail"]

    def test_sakha_admin_scoped_to_an_asana_gets_a_locked_picker_and_can_create(self, client, write_conn, asana_wing_world):
        from tests.reparent_support import _create_admin_with_scope, _login_headers, _with_sevi_pk

        w = asana_wing_world
        fresh_asana = w["wing"]("SAKHA_ASANA", w["wparent"])
        sa = _with_sevi_pk(write_conn, _create_admin_with_scope(
            write_conn, role_code="NSS_ERP_SAKHA_ADMIN", scope_level="SAKHA", organization_pk=fresh_asana))
        h = _login_headers(client, sa["sangha_sevi_id"], sa["password"])
        opts = client.get("/api/v1/admin/organizations/kumari-sevak-sakha-options?type_code=KUMARI_SANGHA", headers=h)
        assert opts.status_code == 200, opts.text
        assert opts.json()["mode"] == "locked" and opts.json()["auto_select_pk"] == fresh_asana
        r = client.post("/api/v1/admin/organizations", headers=h, json={
            "organization_name": f"SakhaAdminKumari {uuid4().hex[:6]}",
            "organization_type_code": "KUMARI_SANGHA",  # parent auto-resolved from scope (ORG-BR-102)
        })
        assert r.status_code == 201, r.text
        cur = write_conn.cursor()
        cur.execute("SELECT parent_organization_pk FROM nss.organization WHERE organization_pk = %s",
                    (r.json()["organization_pk"],))
        assert str(cur.fetchone()[0]) == fresh_asana

    @pytest.mark.parametrize("wing_type", ["KUMARI_SANGHA", "SEVAK_SANGHA", "MAHILA_SANGHA"])
    def test_org_stats_and_wings_of_an_asana_count_its_wings(self, client, asana_wing_world, wing_type):
        w = asana_wing_world
        fresh_asana = w["wing"]("SAKHA_ASANA", w["wparent"])
        w["wing"](wing_type, fresh_asana)
        r = client.get(f"/api/v1/organization/organizations/{fresh_asana}/wings", headers=w["admin_h"])
        assert r.status_code == 200, r.text
        counts = {x["wing_type_code"]: x["organization_count"] for x in r.json()["wings"]}
        assert counts[wing_type] == 1, counts
        # The Anchalika parent rolls the Asana's wing up through the same subtree CTE.
        up = client.get(f"/api/v1/organization/organizations/{w['parent']}/wings", headers=w["admin_h"])
        assert up.status_code == 200, up.text
        assert {x["wing_type_code"]: x["organization_count"] for x in up.json()["wings"]}[wing_type] >= 1

    def test_org_stats_total_counts_wing_under_asana(self, client, asana_wing_world):
        w = asana_wing_world
        fresh_asana = w["wing"]("SAKHA_ASANA", w["wparent"])
        w["wing"]("KUMARI_SANGHA", fresh_asana)
        r = client.get(f"/api/v1/organization/organizations/{fresh_asana}/stats", headers=w["admin_h"])
        assert r.status_code == 200, r.text
        assert r.json()["sakha_sanghas"] == 1
        assert r.json()["kumari_sanghas"] == 1
