"""
Pydantic response models for the Organization API (Tier 2).

All models exclude audit columns (created_at, updated_at, deleted_at)
per the project's API convention established in Tier 0.

Organization type is sourced from Foundation master_data (category
ORGANIZATION_TYPE). Status is sourced from the unified ERP-wide
STATUS category — a single shared category used by all modules.

Raw psycopg2 returns dictionaries — no ORM objects — so
ConfigDict(from_attributes=True) is unnecessary.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class OrganizationTypeResponse(BaseModel):
    """Organization type from nss.master_data (category: ORGANIZATION_TYPE)."""

    organization_type_pk: UUID
    organization_type_code: str
    organization_type_name: str
    description: str | None
    sort_order: int
    is_active: bool


class StatusResponse(BaseModel):
    """Lifecycle status from nss.master_data (category: STATUS)."""

    status_pk: UUID
    status_code: str
    status_name: str
    description: str | None
    sort_order: int
    is_active: bool


class OrganizationResponse(BaseModel):
    """
    Organization with resolved type, status, and parent context.

    Includes type_name, status_name, and parent_name via JOINs so the
    UI can display the full context in a single API call. Geographic FK
    names (country, state, district) are also resolved where present.

    Type fields are aliased from master_data columns for the
    ORGANIZATION_TYPE category. Status fields use the unified
    ERP-wide STATUS category.
    """

    organization_pk: UUID
    organization_id: str | None
    organization_name: str
    organization_code: str | None
    short_code: str | None

    # Classification (resolved from master_data)
    organization_type_pk: UUID
    organization_type_code: str
    organization_type_name: str

    # Lifecycle (resolved from master_data — unified STATUS category)
    status_pk: UUID
    status_code: str
    status_name: str

    # Hierarchy
    parent_organization_pk: UUID | None
    parent_organization_name: str | None
    # The parent's type distinguishes otherwise-identical children, e.g. a
    # central Mahila Sangha (parent = KENDRA) from a local one
    # (parent = a Sakha-like org: SAKHA_SANGHA or SAKHA_ASANA).
    parent_organization_type_code: str | None = None

    # Inline address
    address_line_1: str | None
    address_line_2: str | None

    # Contact information
    phone_number: str | None
    country_phone_code: str | None = None
    mobile_number: str | None
    email: str
    org_email: str | None

    # Online presence
    website_url: str
    org_website_url: str | None
    youtube_channel_url: str
    org_youtube_channel_url: str | None

    # Geographic context (resolved names)
    district_pk: UUID | None
    district_name: str | None
    state_pk: UUID | None
    state_name: str | None
    country_pk: UUID | None
    country_name: str | None
    city_village_pk: UUID | None
    city_village_name: str | None
    postal_code_pk: UUID | None
    postal_code: str | None

    # Coordinates
    latitude: float | None
    longitude: float | None

    is_active: bool


class OrgChildStatsResponse(BaseModel):
    """
    Aggregate statistics for an organization node.

    Used by the org admin sidebar to show counts inline on each
    child card during hierarchy drill-down.  Counts are computed
    dynamically — families use the majority-rule CTE (FAM-036),
    members are counted by HOME Sakha (active sangha_sevi whose home org
    is the Sakha: Parichay Patra holders + that Sakha's own PROBATIONARY
    Darshaks). Visiting Darshaks (home elsewhere) are NOT counted here, so
    a member is never double-counted across the Sakhas they attend. For
    non-Sakha orgs the stats aggregate across all descendant Sakhas.
    """

    organization_pk: UUID
    organization_name: str
    organization_code: str | None
    organization_type_code: str
    family_count: int = 0
    member_count: int = 0
    person_count: int = 0

    # Attendance % (Tier 6, 2026-10-27) — present/(present+absent) across
    # every descendant Sakha's Weekly Sangha Puja history, same
    # computation as attendance.py::organization_stats. None/
    # attendance_tracked=False only when no puja event has been recorded
    # yet anywhere in this child's subtree (pre-adoption), matching
    # /admin/dashboard-stats' own convention.
    attendance_pct: float | None = None
    attendance_tracked: bool = False


class OrgStatsResponse(BaseModel):
    """
    Aggregate statistics for one organization's whole subtree (itself plus
    every descendant), scoped to the requested organization_pk rather than
    the viewer's own admin scope.

    Exists because /admin/dashboard-stats answers "what does the *viewer*
    have access to" — right for the admin's own scope card, wrong the
    moment the Org Dashboard is used to drill into a different org (via
    the Organizations tab's "View Dashboard" button, a child-org link in
    the children table, the org switcher, or an #orgDashboard/<pk> deep
    link). Those all show one org's identity while /admin/dashboard-stats
    would silently report the viewer's entire scope underneath it.

    member_count counts active sangha_sevi by HOME Sakha (Parichay Patra
    holders + that Sakha's own PROBATIONARY Darshaks), excluding visiting
    Darshaks whose home is another Sakha; family_count uses the majority-rule
    Sakha assignment (FAM-036). Both use the same descendant-Sakha subtree as
    /children-stats, so the totals here agree with summing that endpoint's
    per-child rows.
    renewals_due counts PENDING nss.membership_renewal_request rows whose
    Sangha Sevi's home Sakha falls in this org's subtree — real today
    (0 until the renewal module writes rows), not a placeholder.
    attendance_pct (Tier 6, 2026-10-27) — present/(present+absent) across
    every descendant Sakha's Weekly Sangha Puja history, same computation
    as attendance.py::organization_stats and admin.py::dashboard_stats'
    own rollup. None/attendance_tracked=False only when no puja event has
    been recorded yet anywhere in this subtree (pre-adoption).

    parichay_patra_holders + darshaks is an exact partition of member_count
    (every MEMBERSHIP_TYPE except PROBATIONARY carries a Parichay Patra, and
    the column is NOT NULL) — darshaks counts HOME probationary members only,
    never visiting card-holders from another Sakha.

    The per-type organization counts (sakha/mahila/anchalika/zilla/
    patha_chakra/paribarik/kumari/sevak) count active orgs of that
    ORGANIZATION_TYPE inside the subtree. They replace a single "total
    organizations" figure, which was meaningless at Kendra level (NSS/Kendra
    is the one apex org, so everything else is trivially beneath it).
    """

    organization_pk: UUID
    member_count: int = 0
    parichay_patra_holders: int = 0
    darshaks: int = 0
    family_count: int = 0
    sakha_sanghas: int = 0
    mahila_sanghas: int = 0
    anchalika_sanghas: int = 0
    zilla_sanghas: int = 0
    patha_chakras: int = 0
    paribarik_sanghas: int = 0
    kumari_sanghas: int = 0
    sevak_sanghas: int = 0
    renewals_due: int = 0
    attendance_pct: float | None = None
    attendance_tracked: bool = False


class OrgWingResponse(BaseModel):
    """
    One wing body (Mahila / Kumari / Sevak Sangha) summarised over an
    organization's subtree.

    Why wings need their own response instead of more columns on
    OrgStatsResponse: that model's wing fields (mahila_sanghas,
    kumari_sanghas, sevak_sanghas) count ORGANIZATION ROWS. This model
    answers the different question "how many PEOPLE are in this wing",
    which for one of the three wings is derived and for the other two is
    not currently answerable at all. Collapsing both into one int per wing
    would make an unavailable figure indistinguishable from zero.

    member_count is None — never 0 — when the figure cannot be computed;
    member_count_note then carries the reason, so the UI renders "—" with
    an explanation instead of a confident and wrong zero. The same
    null-vs-zero discipline the Sakha dashboard already uses for
    permission failures.

    is_derived distinguishes the two fundamentally different wing models
    documented in MBR-046 vs KUM-012/SEV-015:

      MAHILA_SANGHA — derived. Affiliation is automatic: "the moment any
        female member's Sakha affiliation is recorded, she is
        automatically also affiliated to that Sakha's Mahila Sangha"
        (ORG-BR-096), "all female members" (MBR-046). No enrollment
        record exists or should exist — mahila/05_mahila_table_design.md
        §5.2 explicitly declines a mahila_membership table. So the roster
        is a query over person.gender, and is_derived = True.

      KUMARI_SANGHA / SEVAK_SANGHA — enrollment-based, NOT derivable.
        A Kumari holds a kumari_membership row with its own kumari_id
        (KUM-012: only unmarried girls stay active; KUM-007 leaves the
        age boundary deliberately UNFROZEN); a Sevak holds a
        sevak_participation row created by "an authorized user
        [performing] the enrollment action" (SEV-015). Neither is a
        function of person attributes, so no amount of querying produces
        the roster — somebody has to enroll them. Both tables are
        design-only today (no CREATE TABLE for either exists anywhere in
        database/ddl/), hence member_count = None.

    gender_not_recorded_count is a DATA-QUALITY figure, not a wing
    population: person.gender_master_data_pk is NULLable, so a female
    member whose gender was never captured is invisible to the derived
    Mahila roster. Surfacing the count makes that undercount visible
    instead of silently depressing member_count. It is None for the
    non-derived wings, where gender is not the predicate.
    """

    wing_type_code: str
    wing_type_name: str
    organization_count: int = 0
    member_count: int | None = None
    member_count_note: str | None = None
    is_derived: bool = False
    gender_not_recorded_count: int | None = None


class OrgWingSummaryResponse(BaseModel):
    """
    All three wing bodies for one organization's subtree.

    Tier-independent by construction. The underlying walk is the same
    recursive org_tree -> descendant-Sakhas pattern _ORG_STATS_SQL uses,
    so one implementation serves every level the user asked about:

      SAKHA_SANGHA/ASANA -> subtree is just itself; its own wings
      ANCHALIKA/ZILLA  -> aggregates its descendant Sakhas' wings
      KENDRA           -> aggregates every Sakha NSS-wide

    Anchalika and Zilla can only ever AGGREGATE: the frozen parent-type
    matrix (ORG-BR-090/091/092) permits wings under SAKHA_SANGHA/SAKHA_ASANA (amended 2026-10-31, GDR-008) or (for
    the single central Mahila Sangha) KENDRA only, and ORG-BR-089 makes
    Sakhas the sole legal children of an Anchalika/Zilla. So neither tier
    can own a wing org row, and aggregation is the only meaningful
    reading. Caveat recorded honestly: no rule actually *states* the
    aggregation semantics — ORG-BR-089/090 make it the only possibility,
    but the roll-up itself is this endpoint's interpretation, consistent
    with how /children-stats already aggregates descendant Sakhas.

    For a KENDRA this also happens to be the documented roster of the
    central Mahila Sangha, without special-casing: ORG-BR-096 says a
    female member is affiliated to her Sakha's Mahila Sangha "which is
    understood as part of the Kendra Mahila Sangha". The alternative
    reading (central = only the 9 Parichalana Mandali office-bearers) is
    NOT supported — the Mandali is a governance body, and the bye-law
    quoted in mahila/05_mahila_table_design.md holds that General Body
    membership derives from underlying Mahila Sangha membership.
    """

    organization_pk: UUID
    organization_type_code: str | None = None
    sakha_sangha_count: int = 0
    wings: list[OrgWingResponse]


class WingMemberResponse(BaseModel):
    """
    One person in a derived wing roster.

    Carries sakha_organization_name/code because the wing itself has
    neither: per ORG-BR-104 a wing is "a wing of its Sakha, not an
    independently-identified organization" and both organization_code and
    short_code are NULL on the wing row. The parent Sakha is therefore
    the only meaningful place label, and it is what makes a Kendra- or
    Zilla-level roster readable at all.

    sangha_sevi_id is the member's single permanent identity. Per MBR-046
    a wing member "takes no new identifier" and no wing-specific ID
    sequence exists, so there is deliberately no wing_member_id field
    here to populate.
    """

    sangha_sevi_pk: UUID
    sangha_sevi_id: str | None = None
    person_pk: UUID
    full_name: str
    gender_code: str | None = None
    marital_status_code: str | None = None
    membership_type_code: str | None = None
    status_code: str | None = None
    sakha_organization_pk: UUID
    sakha_organization_name: str | None = None
    sakha_organization_code: str | None = None
    local_sakha_erp_id: str | None = None
    joining_date: date | None = None


class WingMemberListResponse(BaseModel):
    """Paginated derived wing roster. total is a COUNT, not a page length."""

    wing_type_code: str
    organization_pk: UUID
    total: int
    limit: int
    offset: int
    members: list[WingMemberResponse]


class OrganizationHierarchyNodeResponse(BaseModel):
    """
    Organization node in a hierarchical tree.

    Includes depth and path for rendering the full tree.
    Children are not nested — the tree is returned flat with
    depth/path fields for the UI to reconstruct the hierarchy.
    """

    organization_pk: UUID
    organization_name: str
    organization_code: str | None
    organization_type_code: str
    organization_type_name: str
    status_code: str
    status_name: str
    parent_organization_pk: UUID | None
    depth: int
    is_active: bool
