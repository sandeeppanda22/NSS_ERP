"""Alpine's x-show hides with an inline ``display:none`` and, when showing again,
REMOVES the inline ``display`` property - so an element that carries its layout
as ``style="display:flex|grid"`` loses it the first time it is toggled (the admin
dashboard stat tiles collapsed into stacked full-width boxes). Layout display
modes on x-show elements must therefore come from a class, never inline style.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
PAGES = ["admin.html", "dashboard.html", "login.html", "register.html"]


def _tags(src):
    i, n = 0, len(src)
    while i < n:
        if src[i] == "<" and i + 1 < n and src[i + 1].isalpha():
            j, q = i + 1, None
            while j < n:
                c = src[j]
                if q:
                    if c == q:
                        q = None
                elif c in "\"'":
                    q = c
                elif c == ">":
                    break
                j += 1
            yield src[i:j + 1]
            i = j + 1
        else:
            i += 1


def test_x_show_elements_do_not_carry_display_in_inline_style():
    bad = []
    for page in PAGES:
        path = FRONTEND / page
        if not path.exists():
            continue
        for tag in _tags(path.read_text(encoding="utf-8")):
            if not re.search(r"\sx-show\s*=", tag):
                continue
            m = re.search(r'\sstyle\s*=\s*"([^"]*)"', tag)
            if m and re.search(r"display\s*:\s*(flex|grid|inline-flex)", m.group(1)):
                bad.append(f"{page}: {tag[:120]}")
    assert not bad, "x-show element with inline display (use a class):\n" + "\n".join(bad[:10])
