"""
Every frontend script must at least PARSE (DB-free; needs node). The source-parsing UI tests read these files as text, so a
missing bracket - for example the closing parenthesis of the chain of mixin installs at the end of admin.js - passes them all and
only shows as a blank page in the browser. ``node --check`` compiles a file without running it.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

JS = sorted((Path(__file__).resolve().parents[2] / "frontend" / "assets" / "js").glob("*.js"))
node = shutil.which("node")


@pytest.mark.skipif(node is None, reason="node not available")
@pytest.mark.parametrize("script", JS, ids=[p.name for p in JS])
def test_the_script_parses(script):
    out = subprocess.run([node, "--check", str(script)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr


def test_there_are_scripts_to_check():
    assert len(JS) >= 20
