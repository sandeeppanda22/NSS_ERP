"""
DB-free checks of the build summary's table report (owner request 2026-11-20): how many tables the run CREATED, how many were ALREADY THERE
(DDL skipped) and how many it ALTERED. The comparison is database/scripts/schema_report.sh; the snapshot is schema_snapshot.sql; both build
scripts that print a summary use them, and 02_build.ps1 carries the PowerShell twin.
"""
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "database/scripts/schema_report.sh"
bash = shutil.which("bash")


def _report(before: str, after: str, tmp_path, limit: int = 40) -> str:
    b, a = tmp_path / "before", tmp_path / "after"
    b.write_text(textwrap.dedent(before).strip() + "\n"), a.write_text(textwrap.dedent(after).strip() + "\n")
    out = subprocess.run([bash, "-c", f'. "{REPORT}"; schema_report "{b}" "{a}" {limit}'], capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    return out.stdout


@pytest.mark.skipif(bash is None, reason="bash not available")
def test_created_existing_and_altered_tables_are_counted_and_named(tmp_path):
    out = _report(
        """
        person|20|5|3|1
        organization|18|4|2|1
        finance_head|30|9|4|1
        """,
        """
        person|20|5|3|1
        organization|19|5|2|1
        finance_head|30|9|4|1
        finance_fund_new|8|2|1|0
        funds_two|5|1|1|1
        """, tmp_path)
    assert "Tables in schema nss: 5 (before this run: 3)" in out
    assert "Tables created now:   2" in out and "+ finance_fund_new" in out and "+ funds_two" in out
    assert "Tables already there: 3" in out
    assert "Tables altered:       1" in out and "~ organization  (+1 column, +1 constraint)" in out
    assert "~ person" not in out and "~ finance_head" not in out         # a patch that found everything in place changes nothing


@pytest.mark.skipif(bash is None, reason="bash not available")
def test_a_rerun_that_changes_nothing_reports_zero_created_and_zero_altered(tmp_path):
    same = "person|20|5|3|1\norganization|18|4|2|1"
    out = _report(same, same, tmp_path)
    assert "Tables created now:   0" in out and "Tables altered:       0" in out and "Tables already there: 2" in out


@pytest.mark.skipif(bash is None, reason="bash not available")
def test_plural_wording_and_the_list_limit(tmp_path):
    out = _report("t|1|1|1|1", "t|3|2|4|1", tmp_path)
    assert "~ t  (+2 columns, +1 constraint, +3 indexes)" in out
    many_after = "\n".join(f"n{i:02d}|1|1|1|0" for i in range(5))
    out = _report("x|1|1|1|0", "x|1|1|1|0\n" + many_after, tmp_path, limit=3)
    assert "Tables created now:   5" in out and "... and 2 more" in out


def test_the_snapshot_is_read_only_and_covers_what_the_report_compares():
    sql = (ROOT / "database/scripts/schema_snapshot.sql").read_text(encoding="utf-8")
    assert re.search(r"^\s*SELECT\b", sql, re.M) and not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)\b", re.sub(r"--.*", "", sql), re.I)
    for catalog in ("pg_attribute", "pg_constraint", "pg_index", "pg_trigger"):
        assert catalog in sql


@pytest.mark.parametrize("rel,snapshot_calls", [("database/scripts/02_build.sh", 2), ("render_build.sh", 2)])
def test_the_shell_builds_take_a_snapshot_before_and_after_and_print_the_report(rel, snapshot_calls):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert "schema_report.sh" in text and text.count("schema_snapshot_to ") == snapshot_calls and "schema_report \"${SCHEMA_BEFORE}\" \"${SCHEMA_AFTER}\"" in text
    assert text.index('schema_snapshot_to "${SCHEMA_BEFORE}"') < text.index("run_sql ") or text.index('schema_snapshot_to "${SCHEMA_BEFORE}"') < text.index("run_ddl ")
    assert text.rindex('schema_snapshot_to "${SCHEMA_AFTER}"') > text.index('schema_snapshot_to "${SCHEMA_BEFORE}"')


def test_the_powershell_build_has_the_twin():
    text = (ROOT / "database/scripts/02_build.ps1").read_text(encoding="utf-8")
    for needle in ("function Get-SchemaSnapshot", "function Write-SchemaReport", "schema_snapshot.sql", "$SchemaBefore = Get-SchemaSnapshot",
                   "Write-SchemaReport $SchemaBefore (Get-SchemaSnapshot)", "Tables created now:", "Tables already there:", "Tables altered:"):
        assert needle in text, needle
