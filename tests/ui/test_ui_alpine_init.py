"""
Alpine 3 runs a component's own `init()` automatically. A page that ALSO says
x-init="init()" runs the whole startup twice (2026-11-09: every admin request
was doubled, 26 parallel calls against a 15-connection pool). Source-parsing,
DB-free.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def test_no_page_calls_init_a_second_time_via_x_init():
    offenders = []
    for page in ("admin", "dashboard", "login", "register"):
        html = (FRONTEND / f"{page}.html").read_text()
        for m in re.finditer(r'<[^>]*x-data="(\w+)\(\)"[^>]*>', html):
            if re.search(r'x-init="init\(\)"', m.group(0)):
                offenders.append(f"{page}.html: {m.group(1)}")
    assert not offenders, f"x-init=\"init()\" duplicates Alpine's automatic init(): {offenders}"


def test_the_page_components_really_define_init():
    # If a component lost its init(), removing x-init would silently stop its startup.
    for js, component in (("admin.js", "adminApp"), ("dashboard.js", "dashboardApp"),
                          ("login.js", "loginApp"), ("register.js", "registerApp")):
        src = (FRONTEND / "assets" / "js" / js).read_text()
        body = src[src.index(f"function {component}()"):]
        assert re.search(r"^\s{8}(async )?init\(", body, re.M), component
