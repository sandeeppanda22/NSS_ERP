"""
The route table itself (DB-free): a decorator that ends up above the WRONG function registers a helper as an endpoint, and FastAPI then asks the caller for the
helper's arguments ("cur is required", "user_account is required", "person is required" - a 422 on a request that was perfectly good). Nothing else notices:
the helper still imports and works when called directly. So:

  * no (method, path) is registered twice - the first registration silently wins and the real handler never runs;
  * no endpoint takes a database cursor / connection or the caller's context as a REQUEST field (query, path, header or body): those come from Depends();
  * the year transition - the route that showed it on 2026-11-23 - is served by transition_year, whose only request field is its body.
"""
from collections import Counter

from api.main import app

ROUTES = [r for r in app.routes if getattr(r, "methods", None) and hasattr(r, "dependant")]
FORBIDDEN_FIELDS = {"cur", "cursor", "conn", "connection", "user", "current_user"}      # always supplied by Depends(), never by the caller


def _request_fields(route) -> set[str]:
    d = route.dependant
    return {p.name for p in (*d.path_params, *d.query_params, *d.header_params, *d.cookie_params, *d.body_params)}


def test_the_route_table_is_not_empty():
    assert len(ROUTES) > 300


def test_no_method_and_path_is_registered_twice():
    seen = Counter((m, r.path) for r in ROUTES for m in r.methods if m not in ("HEAD", "OPTIONS"))
    assert [key for key, n in seen.items() if n > 1] == []


def test_no_endpoint_asks_the_caller_for_a_cursor_a_connection_or_the_user_context():
    leaking = {(r.path, r.endpoint.__name__): sorted(_request_fields(r) & FORBIDDEN_FIELDS) for r in ROUTES if _request_fields(r) & FORBIDDEN_FIELDS}
    assert leaking == {}


def test_the_year_transition_is_served_by_its_own_handler():
    route = next(r for r in ROUTES if r.path == "/api/v1/finance/years/{year_pk}/transition")
    assert route.endpoint.__name__ == "transition_year"
    assert _request_fields(route) == {"year_pk", "body"}


def test_a_helper_next_to_a_handler_is_not_a_route():
    """carry_scopes_forward sits right above transition_year in the source; it must stay a plain function."""
    from api.routers import finance as F

    assert F.carry_scopes_forward.__name__ not in {r.endpoint.__name__ for r in ROUTES}
    assert not hasattr(F.carry_scopes_forward, "__wrapped__")
