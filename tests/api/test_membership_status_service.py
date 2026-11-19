"""DB-free checks for the Membership Status rules (api/services/membership_status_service.py)."""
import re
from pathlib import Path

from api.services import membership_status_service as svc

ROOT = Path(__file__).resolve().parents[2]


def test_status_list_matches_the_frontend_filter():
    js = (ROOT / "frontend/assets/js/nss-config.js").read_text()
    m = re.search(r"MEMBERSHIP_STATUS_FILTER:\s*\[([^\]]*)\]", js)
    assert m, "NSS.MEMBERSHIP_STATUS_FILTER missing"
    assert tuple(re.findall(r'"([A-Z_]+)"', m.group(1))) == svc.MEMBERSHIP_STATUS_CODES


def test_attendance_block_list_matches_the_frontend():
    js = (ROOT / "frontend/assets/js/nss-config.js").read_text()
    m = re.search(r"ATTENDANCE_BLOCKED_STATUSES:\s*\[([^\]]*)\]", js)
    assert tuple(re.findall(r'"([A-Z_]+)"', m.group(1))) == svc.ATTENDANCE_BLOCKED_STATUS_CODES


def test_rules():
    assert "RESIGNED" not in svc.MEMBERSHIP_STATUS_CODES          # a post matter, not membership
    assert set(svc.ATTENDANCE_BLOCKED_STATUS_CODES) == {"SUSPENDED", "EXPELLED", "DECEASED"}
    assert svc.TERMINAL_STATUS_CODES == ("DECEASED",)
    assert set(svc.APPROVER_POSITION_CODES) == {"PARICHALAK", "PRESIDENT"}


def test_routes_registered_and_login_only():
    from api.main import app
    paths = {r.path for r in app.routes if "membership-status" in r.path}
    assert len(paths) == 6


def test_login_barred_statuses_are_the_attendance_ones():
    from api.services.rbac_service import LOGIN_BARRED_STATUS_CODES
    assert set(LOGIN_BARRED_STATUS_CODES) == {"SUSPENDED", "EXPELLED", "DECEASED"}
    assert svc.ATTENDANCE_BLOCKED_STATUS_CODES == LOGIN_BARRED_STATUS_CODES


def test_every_request_applies_the_bar_and_login_says_why():
    rbac = (ROOT / "api/services/rbac_service.py").read_text()
    assert "_LOGIN_BARRED_EXISTS_SQL.format(person_pk_expr=\"ua.person_pk\")" in rbac   # load_user_context
    auth = (ROOT / "api/routers/auth.py").read_text()
    assert "member_login_barred_status(cur, person_pk)" in auth
