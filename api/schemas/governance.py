"""
NSS ERP — Governance pydantic schemas (Tier 6).

Unified Body Governance Model (GOV-BR-004). Mirrors the conventions in
schemas/admin.py: UUID for every *_pk field; request-side dates are
`str | None` (parsed server-side with parse_optional_date — ISO
YYYY-MM-DD only, DD/MM/YYYY is a frontend display concern); response-side
dates are `date | None` (psycopg2 returns real date objects, pydantic
serializes them to ISO automatically).

Status columns are VARCHAR + CHECK at the DB layer (not master_data FKs),
so every status field here is a plain `str` validated with a `pattern`
regex mirroring the table's CHECK constraint list.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

BODY_STATUS_PATTERN = r"^(ACTIVE|RECONSTITUTED|HISTORICAL|INACTIVE)$"
ASSIGNMENT_STATUS_PATTERN = r"^(ASSIGNED|ACTIVE|ENDED|HISTORICAL|RESIGNED)$"
ACTING_STATUS_PATTERN = r"^(ASSIGNED|ACTIVE|ENDED|HISTORICAL)$"
ELECTION_STATUS_PATTERN = r"^(SCHEDULED|NOMINATION|VOTING|COMPLETED|CANCELLED)$"
ELECTION_TYPE_PATTERN = r"^(ELECTION|NOMINATION)$"
NOMINATION_STATUS_PATTERN = r"^(NOMINATED|ACCEPTED|WITHDRAWN|REJECTED)$"
RESULT_STATUS_PATTERN = r"^(DECLARED|UNCONTESTED|TIE|VACANT|CANCELLED)$"


# ── Body Type Master (catalog) ──────────────────────────────────────────

class CreateBodyTypeRequest(BaseModel):
    body_type_code: str = Field(..., max_length=50)
    body_type_name: str = Field(..., max_length=150)
    description: str | None = None


class UpdateBodyTypeRequest(BaseModel):
    body_type_name: str | None = Field(None, max_length=150)
    description: str | None = None


class BodyTypeResponse(BaseModel):
    body_type_master_pk: UUID
    body_type_code: str
    body_type_name: str
    description: str | None = None
    is_active: bool


# ── Position Master (catalog) ───────────────────────────────────────────

class CreatePositionRequest(BaseModel):
    position_code: str = Field(..., max_length=50)
    position_name: str = Field(..., max_length=150)
    description: str | None = None
    display_order: int = 0


class UpdatePositionRequest(BaseModel):
    position_name: str | None = Field(None, max_length=150)
    description: str | None = None
    display_order: int | None = None


class PositionResponse(BaseModel):
    position_master_pk: UUID
    position_code: str
    position_name: str
    description: str | None = None
    display_order: int
    is_active: bool


# ── Body Master ──────────────────────────────────────────────────────────

class CreateBodyRequest(BaseModel):
    body_type_master_pk: UUID
    body_code: str = Field(..., max_length=50)
    body_name: str = Field(..., max_length=200)
    description: str | None = None
    organization_pk: UUID | None = Field(
        None, description="NULL for NSS-wide/Kendra-level bodies (GOV-BR-058)."
    )
    effective_from: str | None = Field(None, description="ISO (YYYY-MM-DD), optional")
    effective_to: str | None = Field(None, description="ISO (YYYY-MM-DD), optional")


class UpdateBodyRequest(BaseModel):
    body_name: str | None = Field(None, max_length=200)
    description: str | None = None
    body_status: str | None = Field(None, pattern=BODY_STATUS_PATTERN)
    effective_from: str | None = None
    effective_to: str | None = None


class BodyResponse(BaseModel):
    body_master_pk: UUID
    body_type_master_pk: UUID
    body_type_name: str | None = None
    body_type_code: str | None = None
    body_code: str
    body_name: str
    description: str | None = None
    organization_pk: UUID | None = None
    organization_name: str | None = None
    body_status: str
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool
    # Populated only when GET /bodies is called with include_members=true:
    # the identical composition shape /public/national-bodies returns (both
    # go through _assemble_bodies_with_members), so every governance-body
    # card in the frontend renders from ONE member shape. 2026-10-23, owner
    # request for uniform governance cards.
    members: list[dict] | None = None
    member_count: int | None = None
    scope_label: str | None = None


class BodyListResponse(BaseModel):
    items: list[BodyResponse]
    total: int
    page: int
    page_size: int


# ── Body Member Assignment ──────────────────────────────────────────────

class CreateAssignmentRequest(BaseModel):
    position_master_pk: UUID
    person_pk: UUID
    sangha_sevi_pk: UUID = Field(
        ..., description="Required — the holder's active Sangha Sevi membership. "
        "A non-member cannot hold a governance position (GOV-BR-056/074)."
    )
    effective_from: str = Field(..., description="ISO (YYYY-MM-DD)")
    effective_to: str | None = None
    assignment_reference: str | None = Field(None, max_length=100)
    remarks: str | None = None


class EndAssignmentRequest(BaseModel):
    effective_to: str = Field(..., description="ISO (YYYY-MM-DD) — the last active day")
    remarks: str | None = None


class ResignAssignmentRequest(BaseModel):
    """Voluntary self-withdrawal by the office holder (2026-10-15). Strictly
    self-service: only the person named on the assignment may call this —
    no admin, scope-holder or NSS-wide override. Always sets
    assignment_status = RESIGNED (never ENDED)."""
    effective_to: str = Field(..., description="ISO (YYYY-MM-DD) — the last active day")
    resignation_reason: str = Field(..., min_length=1, description="Why the holder is resigning")


class RequestAssignmentRemovalRequest(BaseModel):
    """Forced-removal request against any body/position (GOV-BR item #18,
    generalized 2026-10-15 beyond the original Advisory-Board-only, super-admin
    break-glass version). Filed by the body's own scoped admin or one of its
    own office bearers; takes effect only once the body's own sitting
    President (or, if that seat is vacant, another of its own sitting office
    bearers) approves it. gb_resolution_reference is mandatory — the real
    approval is the body's own General Body meeting resolution; the President's
    sign-off records that outcome, it is not a personal/discretionary call."""
    reason: str = Field(..., min_length=1, description="Why this forced removal is being requested")
    gb_resolution_reference: str = Field(
        ..., min_length=1, max_length=100,
        description="Reference to the GB meeting resolution that approved this removal "
                    "(or the Sakha GB resolution, for a Sevak Sangha Executive seat)",
    )


class DecideAssignmentRemovalRequest(BaseModel):
    """Approve or reject a pending forced-removal request. effective_to is
    required on approval (ignored on rejection)."""
    effective_to: str | None = Field(None, description="ISO (YYYY-MM-DD) — required when approving")
    remarks: str | None = None


class AssignmentResponse(BaseModel):
    body_member_assignment_pk: UUID
    body_master_pk: UUID
    position_master_pk: UUID
    position_name: str | None = None
    # position_master.position_code — added 2026-10-23 (frontend position-badge
    # sweep) so the Assignments tab / org-dashboard composition views can key
    # NSS.positionBadgeClass() off the stable code, not the display name.
    position_code: str | None = None
    person_pk: UUID
    person_name: str | None = None
    sangha_sevi_pk: UUID
    effective_from: date
    effective_to: date | None = None
    assignment_status: str
    assignment_reference: str | None = None
    remarks: str | None = None
    resignation_reason: str | None = None
    is_active: bool
    # Holder's current home Sakha (added 2026-10-24 for the admin Assignments
    # tab's Sakha filter). Both optional/None-default — a holder with no active
    # Sangha Sevi, or a body whose seats aren't Sakha-nominated, yields NULLs.
    # Additive: every existing caller keeps working.
    sakha_name: str | None = None
    sakha_organization_pk: UUID | None = None


class AssignmentListResponse(BaseModel):
    items: list[AssignmentResponse]
    total: int


# ── Acting Position Assignment ──────────────────────────────────────────

class CreateActingAssignmentRequest(BaseModel):
    position_master_pk: UUID
    person_pk: UUID
    effective_from: str = Field(..., description="ISO (YYYY-MM-DD)")
    effective_to: str | None = None
    reason: str | None = None
    remarks: str | None = None


class EndActingAssignmentRequest(BaseModel):
    effective_to: str = Field(..., description="ISO (YYYY-MM-DD) — the last active day")
    remarks: str | None = None


class ActingAssignmentResponse(BaseModel):
    acting_position_assignment_pk: UUID
    body_master_pk: UUID
    position_master_pk: UUID
    position_name: str | None = None
    # position_code / body_name are additive display fields (2026-10-23):
    # admin.html already keyed NSS.positionBadgeClass() off position_code on
    # this payload (it was silently undefined, so every acting badge fell
    # back to badge-muted), and the member dashboard's delegation list needs
    # the body name because its rows span several bodies.
    position_code: str | None = None
    body_name: str | None = None
    person_pk: UUID
    person_name: str | None = None
    effective_from: date
    effective_to: date | None = None
    acting_status: str
    reason: str | None = None
    remarks: str | None = None
    is_active: bool


class ActingAssignmentListResponse(BaseModel):
    items: list[ActingAssignmentResponse]
    total: int


# ── Member-facing "act on my behalf" delegation (owner asks #2/#3/#4) ────
#
# Same underlying table as the admin acting-assignment endpoints above
# (nss.acting_position_assignment — no schema change), but initiated by a
# sitting office bearer from their own dashboard for a position THEY
# currently hold. body_master_pk therefore travels in the body rather than
# the path: the member endpoints are mounted under /me/..., not under
# /bodies/{pk}/..., so the caller's own seat (not a URL) selects the body.
# The response deliberately reuses ActingAssignmentResponse — one row
# shape for one table.

class CreateMyActingDelegationRequest(BaseModel):
    body_master_pk: UUID
    position_master_pk: UUID = Field(
        ..., description="Must be a position the caller currently holds on that body."
    )
    person_pk: UUID = Field(
        ..., description="The nominee — must already be a current member of the same body."
    )
    effective_from: str = Field(..., description="ISO (YYYY-MM-DD)")
    effective_to: str | None = None
    reason: str | None = None


# ── Batch self-delegation (owner ask, 2026-10-24) ────────────────────────
#
# The member dashboard now renders ONE candidate table per (governance
# body, position-the-caller-holds) slot and makes EVERY table mandatory,
# then shows a single combined confirmation table ("every body should get
# their own table.. after selecting the on behalf they selected persons
# should be in a single table for confirmation"). Confirm therefore has to
# create N delegations at once, and must be all-or-nothing: with every
# table mandatory, a partial success (2 of 3 created, the 3rd rejected)
# would leave a half-delegated state the member cannot easily unwind. So
# the batch travels as ONE request instead of N client-side POSTs, and the
# handler wraps the whole loop in a SAVEPOINT.
#
# The shared effective_from/effective_to/reason sit at the top level, not
# per item: the UI collects one date range and one reason for the whole
# batch (the owner's single-confirmation-table framing).

class MyActingDelegationBatchItem(BaseModel):
    """One (body, position-I-hold, nominee) triple inside a batch."""
    body_master_pk: UUID
    position_master_pk: UUID = Field(
        ..., description="Must be a position the caller currently holds on that body."
    )
    person_pk: UUID = Field(
        ..., description="The nominee — must already be a current member of the same body."
    )


class CreateMyActingDelegationBatchRequest(BaseModel):
    items: list[MyActingDelegationBatchItem] = Field(
        ...,
        description="One entry per (body, position) slot being delegated. Must be "
                    "non-empty and must not repeat a (body, position) pair.",
    )
    effective_from: str = Field(..., description="ISO (YYYY-MM-DD) — applies to every item")
    effective_to: str | None = None
    reason: str | None = None


# ── Admin-initiated acting-delegation approval workflow (owner ask #5,
# 2026-10-23 decision A) ──────────────────────────────────────────────────
#
# When an admin (not the sitting office bearer) names someone to act on a
# seat via the existing POST /bodies/{pk}/acting-assignments, the row now
# lands as PENDING_APPROVAL and sits there until the CONCERNED PERSON (the
# nominee) approves or rejects it. Mirrors body_member_assignment's
# PENDING_REMOVAL request/approve/reject pattern. No new request-body shape
# is needed for approve/reject — effective dates were already fixed when
# the admin filed the row; only an optional remarks note travels here.

class DecideActingAssignmentRequest(BaseModel):
    """Approve or reject a PENDING_APPROVAL acting assignment. Only the
    concerned person (the nominee named on the row) may call either."""
    remarks: str | None = None


# ── Election ─────────────────────────────────────────────────────────────

class CreateElectionRequest(BaseModel):
    election_code: str = Field(..., max_length=50)
    body_master_pk: UUID
    organization_pk: UUID | None = Field(
        None,
        description="Ignored by the handler — organization_pk is always derived "
                    "server-side from body_master.organization_pk (GOV-BR-059). "
                    "Kept on the request for backward compatibility only; do not "
                    "rely on a client-supplied value taking effect.",
    )
    election_name: str = Field(..., max_length=200)
    description: str | None = None
    election_type: str = Field(
        "ELECTION",
        pattern=ELECTION_TYPE_PATTERN,
        description="ELECTION (default) → contested cycle: nominations, then a "
                    "ballot, then results declared from the tally. NOMINATION → "
                    "selection/consensus cycle with no ballot: posts are filled "
                    "directly from the ACCEPTED nominations and each result is "
                    "declared UNCONTESTED. Consensus is attempted first where the "
                    "governance rules follow the Selection + Election model "
                    "(GOV-BR-042). Fixed at creation — it cannot be changed later.",
    )
    election_date: str = Field(..., description="ISO (YYYY-MM-DD)")
    nomination_start_date: str | None = None
    nomination_end_date: str | None = None
    voting_start_date: str | None = None
    voting_end_date: str | None = None
    is_secret_ballot: bool = Field(
        False,
        description="TRUE → secret ballot: the choice row carries a NULL voter "
                    "and the voter is recorded only in the participation ledger, "
                    "so a ballot can never be traced to a member. FALSE (default) "
                    "→ open ballot, attributable. GOV-BR-045 (resolved).",
    )
    remarks: str | None = None


class UpdateElectionStatusRequest(BaseModel):
    election_status: str = Field(..., pattern=ELECTION_STATUS_PATTERN)


class ElectionResponse(BaseModel):
    election_pk: UUID
    election_code: str
    body_master_pk: UUID
    body_name: str | None = None
    organization_pk: UUID | None = None
    election_name: str
    description: str | None = None
    election_type: str = "ELECTION"
    election_date: date
    nomination_start_date: date | None = None
    nomination_end_date: date | None = None
    voting_start_date: date | None = None
    voting_end_date: date | None = None
    election_status: str
    remarks: str | None = None
    is_active: bool
    is_secret_ballot: bool = False


class ElectionListResponse(BaseModel):
    items: list[ElectionResponse]
    total: int
    page: int
    page_size: int


# ── Election Nomination ─────────────────────────────────────────────────

class CreateNominationRequest(BaseModel):
    position_master_pk: UUID
    candidate_person_pk: UUID
    proposer_person_pk: UUID | None = None
    nomination_date: str | None = None
    remarks: str | None = None
    # GOV-BR-043-A: Parichalak-approved exception letting a PROBATIONARY
    # candidate stand for Sakha President/Secretary. The approver is never
    # client-supplied — only the currently-seated Parichalak can invoke this,
    # and the server derives the approver identity from the authenticated
    # actor (see create_nomination). This field is the one thing the
    # Parichalak types; ignored (and unnecessary) for any other candidate.
    probationary_exception_reason: str | None = None


class UpdateNominationStatusRequest(BaseModel):
    nomination_status: str = Field(..., pattern=NOMINATION_STATUS_PATTERN)


class ParichalakStatusResponse(BaseModel):
    """
    GOV-BR-043-A: lets the frontend ask "is the logged-in member currently
    the Parichalak?" without re-deriving it client-side from
    /public/national-bodies. Backs the Parichalak-only "probationary
    candidate exception" nomination action on the member dashboard —
    see _resolve_current_parichalak_sangha_sevi_pk in
    api/routers/governance.py (the single source of truth this mirrors).
    """
    is_parichalak: bool
    sangha_sevi_pk: UUID | None = None


class NominationResponse(BaseModel):
    election_nomination_pk: UUID
    election_pk: UUID
    position_master_pk: UUID
    position_name: str | None = None
    # position_master.position_code — same 2026-10-23 position-badge addition
    # as AssignmentResponse.position_code.
    position_code: str | None = None
    candidate_person_pk: UUID
    candidate_name: str | None = None
    proposer_person_pk: UUID | None = None
    proposer_name: str | None = None
    nomination_date: date | None = None
    nomination_status: str
    remarks: str | None = None
    probationary_exception_approver_sangha_sevi_pk: UUID | None = None
    probationary_exception_reason: str | None = None
    is_active: bool


class NominationListResponse(BaseModel):
    items: list[NominationResponse]
    total: int


# ── Election Vote ────────────────────────────────────────────────────────
# VOTE SECRECY — RESOLVED 2026-10-09 (GOV-BR-045 / SOL-GOV-004 §12.6):
# secrecy is a per-election switch (election.is_secret_ballot). In a SECRET
# election the choice row (election_vote) carries a NULL voter and the voter
# is recorded only in the participation ledger (election_vote_participation),
# so the two can never be joined back to reveal a member's choice. In an OPEN
# election the voter is stored on the choice row (attributable). One member,
# one vote PER POSITION is enforced in BOTH modes by the participation ledger.
# Ballots are IMMUTABLE once cast (DB trigger); they are cleared only via the
# reset flow (hard DELETE). See database/ddl/08_governance/.

class CastVoteRequest(BaseModel):
    """Officer-recorded ballot (GOVERNANCE_MANAGE) — the voter is named."""
    election_nomination_pk: UUID
    voter_person_pk: UUID = Field(..., description="The member casting the ballot.")
    remarks: str | None = None


class SelfCastVoteRequest(BaseModel):
    """
    Member self-service ballot: the voter is the authenticated user, so no
    voter_person_pk is accepted from the client. Gated on a valid login plus
    bylaw voter-eligibility (active NSS member, not Associate/Honorary),
    permitted only while the election is in the VOTING window.
    """
    election_nomination_pk: UUID
    remarks: str | None = None


class ResetBallotsRequest(BaseModel):
    """
    Clear cast ballots for an election (GOV-BR-045 reset flow). Hard-DELETEs
    the choice rows and participation records (ballots are immutable; reset is
    the only way to clear them). Two authorities:
      - PRESIDENT_UNILATERAL: the President resets on their own authority.
      - ADMIN_WITH_PRESIDENT_APPROVAL: an administrator resets with the
        President's recorded approval (president_person_pk required).
    """
    reset_mode: str = Field(
        ...,
        pattern="^(PRESIDENT_UNILATERAL|ADMIN_WITH_PRESIDENT_APPROVAL)$",
    )
    position_master_pk: UUID | None = Field(
        None,
        description="Reset only this position's ballots; omit to reset the "
                    "whole election.",
    )
    president_person_pk: UUID | None = Field(
        None,
        description="Required when reset_mode is ADMIN_WITH_PRESIDENT_APPROVAL "
                    "— the President whose approval authorises the reset.",
    )
    reason: str = Field(..., min_length=3, max_length=500)


class ResetBallotsResponse(BaseModel):
    election_pk: UUID
    position_master_pk: UUID | None = None
    votes_deleted: int
    participation_deleted: int
    message: str


class VoteResponse(BaseModel):
    election_vote_pk: UUID
    election_pk: UUID
    election_nomination_pk: UUID
    position_master_pk: UUID
    voter_person_pk: UUID | None = Field(
        None,
        description="NULL for a secret-ballot election (never attributable).",
    )
    is_secret_ballot: bool = False
    cast_at: datetime | None = None
    remarks: str | None = None


class TallyRow(BaseModel):
    position_master_pk: UUID
    position_name: str | None = None
    # position_master.position_code — same 2026-10-23 position-badge addition
    # as AssignmentResponse.position_code.
    position_code: str | None = None
    election_nomination_pk: UUID
    candidate_person_pk: UUID
    candidate_name: str | None = None
    vote_count: int


class TallyResponse(BaseModel):
    items: list[TallyRow]


# ── Self-service "open to vote" (member dashboard, GOV-BR-045) ─────────────

class VotableNominationRow(BaseModel):
    election_nomination_pk: UUID
    position_master_pk: UUID
    position_name: str | None = None
    candidate_person_pk: UUID
    candidate_name: str | None = None


class OpenElectionRow(BaseModel):
    election_pk: UUID
    election_code: str
    election_name: str
    body_master_pk: UUID
    body_name: str | None = None
    is_secret_ballot: bool
    voting_end_date: str | None = None
    nominations: list[VotableNominationRow] = []
    voted_position_pks: list[UUID] = []


class OpenElectionListResponse(BaseModel):
    items: list[OpenElectionRow]




class DeclareResultRequest(BaseModel):
    position_master_pk: UUID
    winning_nomination_pk: UUID | None = None
    winner_person_pk: UUID | None = None
    vote_count: int | None = Field(None, ge=0)
    result_status: str = Field("DECLARED", pattern=RESULT_STATUS_PATTERN)
    declared_at: str | None = Field(None, description="ISO datetime, optional")
    remarks: str | None = None


class ApplyResultRequest(BaseModel):
    effective_from: str | None = Field(
        None, description="ISO (YYYY-MM-DD); defaults to today if omitted"
    )
    sangha_sevi_pk: UUID | None = None
    assignment_reference: str | None = Field(None, max_length=100)


class ResultResponse(BaseModel):
    election_result_pk: UUID
    election_pk: UUID
    position_master_pk: UUID
    position_name: str | None = None
    # position_master.position_code — same 2026-10-23 position-badge addition
    # as AssignmentResponse.position_code.
    position_code: str | None = None
    winning_nomination_pk: UUID | None = None
    winner_person_pk: UUID | None = None
    winner_name: str | None = None
    vote_count: int | None = None
    result_status: str
    declared_at: datetime | None = None
    remarks: str | None = None
    is_active: bool


class ResultListResponse(BaseModel):
    items: list[ResultResponse]
    total: int


class ApplyResultResponse(BaseModel):
    body_member_assignment_pk: UUID
    election_result_pk: UUID
    message: str
