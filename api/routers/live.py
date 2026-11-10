"""
Live-refresh change feed (owner decision 2026-11-03, "go ahead with your
recommendation": data should refresh without a manual reload; marker-table
design approved the same day).

``GET /api/v1/live/changes`` answers ONE question: "what is the latest change
number of each watched table?". It reads ``nss.live_change_marker`` (one tiny
row per watched table, ~60 rows) and returns ``{table_name, change_seq}`` for
tables on ``LIVE_FEED_TABLES``. The marker rows are bumped by a statement-level
trigger (``nss.fn_live_change_marker()``, ``ddl/12_live_refresh/``) with
``nextval('nss.live_change_seq')``, so a bump becomes visible exactly when the
writing transaction COMMITS and disappears on rollback: no clock, no look-back
window, no dependence on the audit log. No row data and no ids ever leave this
endpoint; a page that learns "table X changed" re-runs its OWN scoped loaders,
so permissions and admin scope are untouched. Login only (any signed-in
user); the per-user limit (``LIVE_CHANGES_RATE_LIMIT``) replaces the global
per-IP one, as for the attendance /live poll.

Contract: there is deliberately NO cursor. ``change_seq`` is a global sequence
taken at write time, not commit time, so a single global "since" cursor could
skip a slower transaction that commits later with a smaller number. The reply
therefore always lists every watched table with its current ``change_seq`` and
the CLIENT compares per table with the value it saw last (for one table the
number order equals the commit order: concurrent writers queue on that table's
marker row). The first reply of a page only establishes the baseline.
"""

from fastapi import APIRouter, Depends, Request

from api.config import settings
from api.database import get_connection
from api.dependencies.auth import get_current_user
from api.rate_limit import limiter, user_or_ip_key
from api.schemas.live import LiveChangesResponse, LiveTableChange
from api.services.rbac_service import UserContext

router = APIRouter(prefix="/api/v1/live", tags=["Live"])

# The ONE authoritative list of tables whose changes the feed may disclose
# (internal / credential / session / counter tables are deliberately absent).
# It must equal the table list in database/ddl/12_live_refresh/02_live_change_triggers.sql
# (the triggers that bump the markers; an entry there may carry a '!col,...'
# suffix of ignored UPDATE columns); tests/api/test_live_changes.py parses
# that file and fails on any difference.
# frontend/assets/js/{admin,dashboard}.js declare which tab each table refreshes
# (LIVE_TABLE_TABS); tests/api/test_live_changes.py asserts every table named
# there is in this set. election_vote / election_vote_participation are
# withheld on purpose: ballot timing is not something every member should see.
LIVE_FEED_TABLES = frozenset({
    # Registration / claim approvals + change requests
    "registration_claim", "membership_change_request",
    # Correspondence (list, detail, approval chain)
    "correspondence", "correspondence_document", "correspondence_finance_reference",
    "correspondence_approval_step",
    # Governance (bodies, assignments, acting, elections / nominations / results)
    "body_master", "body_member_assignment", "acting_position_assignment",
    "election", "election_nomination", "election_result",
    # Organization dashboards (stats cards)
    "organization", "membership_sakha_affiliation", "parichaya_patra",
    "family_group", "darshak_attendance_registration",
    # Assets & Property
    "property", "asset", "custodianship", "maintenance_record",
    "property_statutory_record", "property_document", "asset_document",
    # Finance (Tier 12)
    "financial_year", "financial_scope", "fund_master", "financial_transaction",
    "financial_receipt", "financial_payment", "financial_transfer",
    # Member dashboard "Pending Items"
    "organization_reparent_request", "organization_reparent_step",
    # Batch 2 - Users tab + user detail. user_account's routine login churn
    # (failed_login_attempts, locked_until, last_failed_login_at, last_login_at)
    # does NOT bump its marker: the SQL entry carries an ignored-column suffix
    # ('user_account!col,...'); this whitelist names tables only.
    "user_account", "user_role", "admin_scope", "role_master",
    # Person / Member directories, credentials, member dashboard personal + membership
    "person", "person_address", "sangha_sevi", "anumati_patra", "membership_journey_event",
    "membership_renewal_request",
    # Member dashboard family tab
    "family_relationship", "family_head_history", "family_admin", "family_link",
    "family_transition_history",
    # Governance catalogue (member dashboard)
    "body_type_master", "position_master",
    # Reference data, geography (+ location approvals), settings, festival calendar
    "master_category", "master_data", "document_master",
    "country", "state", "district", "city_village", "postal_code", "post_office",
    "system_setting", "festival_master", "festival_calendar_date",
})

@router.get("/changes", response_model=LiveChangesResponse)
# Per-USER limit (replaces the global per-IP one): every open page polls.
@limiter.limit(settings.LIVE_CHANGES_RATE_LIMIT, key_func=user_or_ip_key)
def live_changes(
    request: Request,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
):
    """
    The current ``change_seq`` of every whitelisted table (committed writes
    only). Reveals only THAT a watched table changed, never what changed.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, change_seq
            FROM   nss.live_change_marker
            WHERE  table_name = ANY(%s)
            ORDER  BY table_name
            """,
            (sorted(LIVE_FEED_TABLES),),
        )
        changed = [LiveTableChange(table_name=r[0], change_seq=r[1]) for r in cur.fetchall()]
    return LiveChangesResponse(changed=changed)
