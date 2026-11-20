"""
DB-free checks of the shared member-search predicate (api/routers/membership.py): the placeholders and the parameters must line up,
and a name PREFIX must match on its own - trigram similarity alone compares the query with the whole name, so "Sand" scored 0.444
against "Sandeep" (cut-off 0.45) and a 4-letter search found nothing although 3 and 5 letters did.
"""
from api.routers.membership import _MEMBER_SEARCH_PREDICATE_SQL, _member_search_params


def test_placeholders_and_params_line_up():
    _, params = _member_search_params("Sand")
    assert _MEMBER_SEARCH_PREDICATE_SQL.count("%s") == len(params) == 11


def test_name_prefix_is_matched_directly_for_first_and_last_name():
    sql = _MEMBER_SEARCH_PREDICATE_SQL
    assert "p.first_name ILIKE %s" in sql and "p.last_name ILIKE %s" in sql
    name_q, params = _member_search_params("Sand")
    # order: 3 id prefixes, 2 trigram, 2 name prefixes, mobile, email, sakha substring, kendra number
    assert params[3:5] == ("Sand", "Sand") and params[5:7] == ("Sand%", "Sand%")
    assert params[7:9] == ("Sand%", "Sand%") and params[9] == "%Sand%" and params[10] == "Sand%"


def test_email_like_query_cuts_the_name_part_at_the_separator():
    name_q, params = _member_search_params("aniket.mishra")
    assert name_q == "aniket" and params[5:7] == ("aniket%", "aniket%") and params[7] == "aniket.mishra%"
