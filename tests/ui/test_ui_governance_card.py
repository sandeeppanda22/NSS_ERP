"""
Source-level tests for the shared governance-body card markup.

Every governance-body card in the app renders from ONE markup block, copied
verbatim into the three places that need it:

  1. frontend/dashboard.html — the member dashboard's Governance tab
     (driven by dashboard.js, looping `grp.bodies`);
  2. frontend/dashboard.html — the embedded org-dashboard Governance section
     (driven by org-dashboard.js, looping `govBodies`);
  3. frontend/admin.html — the same embedded org-dashboard Governance section,
     reached through admin.html's "View Dashboard" overlay, which also runs
     org-dashboard.js.

Owner request (2026-10-23): these three surfaces must look identical. This
project has no HTML component/include/templating mechanism (static pages +
Alpine, no build step), so the copies cannot be deduplicated in markup — the
only thing that can keep them from drifting is a test. That is this file.

Each copy is wrapped in `GOV-BODY-CARD:START` / `GOV-BODY-CARD:END` marker
comments. The copies live at different nesting depths, so they are compared
after dedenting every line; everything else must match character for
character. Colours come only from the `NSS.GOV_BODY_*` constants in
nss-config.js, never from hand-written Tailwind/hex literals.

Needs no browser and no running server — it parses the shipped files directly
(same style as test_ui_badges.py).
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"

START = "GOV-BODY-CARD:START"
END = "GOV-BODY-CARD:END"

# Expected copy count per page — and nowhere else in frontend/*.html.
EXPECTED_PER_FILE = {"dashboard.html": 2, "admin.html": 1}
EXPECTED_TOTAL = 3

# The shared constants every copy must bind to. Updated 2026-10-24: the
# flat string constants became per-body-type FUNCTIONS (owner ask — "give
# different different colors to all body types"), so the markup now calls
# NSS.govBodyCardClass(b.body_type_code) etc. rather than referencing a bare
# constant; the intent of this check (theme comes from nss-config.js, not a
# hand-written literal) is unchanged, only the literal to search for is.
REQUIRED_CONSTANTS = [
    "NSS.govBodyCardClass(",
    "NSS.govBodyTitleClass(",
    "NSS.govBodyButtonClass(",
]

# Literals that must NOT appear inside a card — the theme is owned by the
# nss-config.js constants (and, below them, badges.css / nss-layout.css).
FORBIDDEN_LITERALS = ["bg-violet-50", "text-violet-800", "bg-orange-50", "#B45309"]

BLOCK_RE = re.compile(
    re.escape(START) + r".*?" + re.escape(END), re.DOTALL
)


def _html_files() -> list[Path]:
    return sorted(FRONTEND.glob("*.html"))


def _read(path: Path) -> str:
    assert path.exists(), f"expected file missing: {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


def _blocks() -> list[tuple[str, str]]:
    """Every GOV-BODY-CARD block as (relative-path, raw text), in file order."""
    found: list[tuple[str, str]] = []
    for path in _html_files():
        text = _read(path)
        for m in BLOCK_RE.finditer(text):
            found.append((str(path.relative_to(REPO_ROOT)), m.group(0)))
    return found


def _normalize(block: str) -> list[str]:
    """Dedent each line and drop trailing whitespace — nesting depth differs
    per site, nothing else may."""
    return [line.strip() for line in block.splitlines()]


# ── 1. Exactly three copies, in the expected files ─────────────────────────


def test_marker_counts_are_balanced():
    """Every START has a matching END (an unbalanced marker silently hides a
    copy from the identity check below)."""
    for path in _html_files():
        text = _read(path)
        starts, ends = text.count(START), text.count(END)
        assert starts == ends, (
            f"{path.relative_to(REPO_ROOT)}: {starts} {START} markers vs "
            f"{ends} {END} markers — unbalanced"
        )


def test_exactly_three_card_blocks_in_expected_files():
    per_file: dict[str, int] = {}
    for rel, _ in _blocks():
        per_file[rel] = per_file.get(rel, 0) + 1

    expected = {f"frontend/{name}": n for name, n in EXPECTED_PER_FILE.items()}
    assert per_file == expected, (
        "governance-body card copies are not where they should be.\n"
        f"  expected: {expected}\n  found:    {per_file}\n"
        "If you added a new governance surface, add its copy here too — the "
        "card must stay one block, not a fourth divergent variant."
    )
    assert sum(per_file.values()) == EXPECTED_TOTAL


# ── 2. All three copies identical modulo indentation ───────────────────────


def test_all_card_blocks_are_identical():
    blocks = _blocks()
    assert len(blocks) == EXPECTED_TOTAL, (
        f"expected {EXPECTED_TOTAL} card blocks, found {len(blocks)} — "
        "see test_exactly_three_card_blocks_in_expected_files"
    )

    ref_path, ref_block = blocks[0]
    ref_lines = _normalize(ref_block)

    for other_path, other_block in blocks[1:]:
        other_lines = _normalize(other_block)
        if other_lines == ref_lines:
            continue
        # Report the first difference, with both sides.
        detail = "line counts differ"
        for i, (a, b) in enumerate(zip(ref_lines, other_lines)):
            if a != b:
                detail = f"first difference at block line {i + 1}:\n    {ref_path}: {a!r}\n    {other_path}: {b!r}"
                break
        else:
            shorter, longer = sorted(
                [(ref_path, ref_lines), (other_path, other_lines)],
                key=lambda t: len(t[1]),
            )
            detail = (
                f"{shorter[0]} has {len(shorter[1])} lines, "
                f"{longer[0]} has {len(longer[1])}; first extra line: "
                f"{longer[1][len(shorter[1])]!r}"
            )
        pytest.fail(
            "governance-body card markup has drifted between "
            f"{ref_path} and {other_path}.\n  {detail}\n"
            "The three copies must stay identical (modulo indentation) — "
            "edit one, edit all three."
        )


# ── 3. Theme comes only from the shared NSS constants ──────────────────────


@pytest.mark.parametrize("constant", REQUIRED_CONSTANTS)
def test_every_block_binds_the_shared_constants(constant: str):
    missing = [rel for rel, block in _blocks() if constant not in block]
    assert not missing, (
        f"governance-body card copies that do not reference {constant}: "
        f"{missing} — the theme must come from nss-config.js, not literals."
    )


@pytest.mark.parametrize("literal", FORBIDDEN_LITERALS)
def test_no_hand_written_theme_literals_in_blocks(literal: str):
    offenders = [rel for rel, block in _blocks() if literal in block]
    assert not offenders, (
        f"governance-body card copies contain the hand-written theme literal "
        f"{literal!r}: {offenders} — it belongs in the NSS.GOV_BODY_* "
        "constants in nss-config.js only."
    )
