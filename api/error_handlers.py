"""
NSS ERP — Application-wide error handlers.

Purpose: every failed request must come back with a `detail` string a
person can read and act on. Before these handlers existed, three classes
of failure reached the browser as bare status codes:

  1. Pydantic validation (422) returned `detail` as a LIST OF OBJECTS,
     e.g. [{"type": "missing", "loc": ["body", "date_of_birth"], ...}].
     Every frontend error slot renders a string, so the user saw the
     literal text "[object Object] [object Object]".
  2. psycopg2 integrity errors (duplicate key, FK, NOT NULL, CHECK)
     were never caught anywhere in api/, so they escaped as an
     unhandled 500 whose body carries no `detail` at all — the UI fell
     through to its "Failed (500)." placeholder.
  3. Any other unexpected exception, likewise.

Design rule: the SERVER owns the wording. Callers already do
`data.detail || "<fallback>"`, so returning a plain string here fixes
every page at once without touching each call site.

These are safety nets, not a licence to skip endpoint-level handling.
Where an endpoint can say something more specific — naming the Sakha and
the number, as helpers.insert_sakha_affiliation does — it still should,
and its HTTPException takes precedence over anything here.

Authority: Tier 5 design decision (2026-09-25) — user-facing error
messages must be meaningful, never a raw status code.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import psycopg2
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Field-name humanisation ──────────────────────────────────────────────

# Names whose mechanical de-snake-casing reads badly. Kept deliberately
# short — add an entry only when the generic path produces something a
# user would not recognise.
_FIELD_LABELS = {
    "local_sakha_erp_id": "Local Sakha number",
    "sangha_sevi_pk": "Sangha Sevi",
    "person_pk": "Person",
    "organization_pk": "Organization",
    "membership_type_pk": "Membership type",
    "gender_master_data_pk": "Gender",
    "login_id": "Login ID",
    "role_code": "Role",
    "scope_level": "Scope level",
    "short_code": "Short code",
}

# Positional prefixes FastAPI puts in `loc` that mean nothing to a user.
_LOC_PREFIXES = {"body", "query", "path", "header", "cookie"}


def humanize_field(name: str) -> str:
    """
    Turn a schema field name into something printable.

    'date_of_birth' -> 'Date of birth'
    'gender_master_data_pk' -> 'Gender'   (via _FIELD_LABELS)

    Trailing '_master_data_pk' / '_pk' are surrogate-key plumbing and are
    stripped; '_id' is NOT stripped, because for several NSS fields the
    'id' is the meaningful part the user actually types.
    """
    if name in _FIELD_LABELS:
        return _FIELD_LABELS[name]

    cleaned = name
    for suffix in ("_master_data_pk", "_pk"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break

    cleaned = cleaned.replace("_", " ").strip()
    if not cleaned:
        return "Value"
    return cleaned[0].upper() + cleaned[1:]


def _field_from_loc(loc) -> str:
    """Pick the user-meaningful part out of a Pydantic `loc` tuple."""
    parts = [str(p) for p in (loc or []) if str(p) not in _LOC_PREFIXES]
    if not parts:
        return "Request"
    # Integer path segments are list indices — report the parent field.
    named = [p for p in parts if not p.isdigit()]
    return humanize_field(named[-1] if named else parts[-1])


def _sentence_for(err: dict) -> str:
    """Render one Pydantic error dict as a complete sentence."""
    field = _field_from_loc(err.get("loc"))
    err_type = err.get("type", "")
    ctx = err.get("ctx") or {}

    if err_type in ("missing", "value_error.missing"):
        return f"{field} is required."
    if err_type in ("string_too_short", "too_short"):
        limit = ctx.get("min_length") or ctx.get("min_items")
        return (
            f"{field} is too short (minimum {limit} characters)."
            if limit else f"{field} is too short."
        )
    if err_type in ("string_too_long", "too_long"):
        limit = ctx.get("max_length") or ctx.get("max_items")
        return (
            f"{field} is too long (maximum {limit} characters)."
            if limit else f"{field} is too long."
        )
    if err_type == "string_pattern_mismatch":
        return f"{field} is not in the expected format."
    if err_type.startswith("uuid"):
        return f"{field} must be a valid identifier."
    if "date" in err_type and "parsing" in err_type:
        return f"{field} must be a valid date."
    if err_type.startswith("int_") or err_type.startswith("float_"):
        return f"{field} must be a number."
    if err_type == "bool_parsing":
        return f"{field} must be true or false."
    if err_type == "enum":
        allowed = ctx.get("expected")
        return (
            f"{field} must be one of: {allowed}."
            if allowed else f"{field} is not an allowed value."
        )

    # Unrecognised type — fall back to Pydantic's own wording, which is
    # terse but still far better than a status code.
    msg = (err.get("msg") or "is not valid").strip()
    if msg and msg[0].isupper() and not msg.startswith(field):
        return f"{field}: {msg}."
    return f"{field} {msg}."


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Flatten Pydantic's list-of-objects `detail` into one readable string.

    Returns 422 with e.g.
        "Date of birth is required. Gender is required."
    instead of a JSON array the UI can only stringify.
    """
    errors = exc.errors() or []
    sentences: list[str] = []
    for err in errors:
        try:
            sentence = _sentence_for(err)
        except Exception:  # never let message-building 500 a request
            logger.warning("Could not format validation error: %r", err)
            sentence = "A submitted value is not valid."
        if sentence not in sentences:
            sentences.append(sentence)

    detail = " ".join(sentences) if sentences else "The submitted data is not valid."
    logger.info(
        "Validation failure on %s %s: %s",
        request.method, request.url.path, detail,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": detail},
    )


# ── Database integrity errors ────────────────────────────────────────────

async def integrity_error_handler(
    request: Request, exc: psycopg2.IntegrityError
) -> JSONResponse:
    """
    Convert a constraint violation into a readable conflict message.

    Covers UniqueViolation, ForeignKeyViolation, NotNullViolation and
    CheckViolation. Constraint names are internal, so they are logged but
    never sent to the browser.

    Endpoints that can name the specific clash should keep raising their
    own HTTPException — this only catches what would otherwise be a 500.
    """
    diag = getattr(exc, "diag", None)
    constraint = getattr(diag, "constraint_name", None)
    column = getattr(diag, "column_name", None)

    logger.error(
        "Integrity violation on %s %s (constraint=%s column=%s): %s",
        request.method, request.url.path, constraint, column, exc,
    )

    if isinstance(exc, psycopg2.errors.UniqueViolation):
        code = status.HTTP_409_CONFLICT
        detail = (
            "That value is already used by another record. "
            "Values that must stay unique cannot be reused — "
            "please enter a different one."
        )
    elif isinstance(exc, psycopg2.errors.ForeignKeyViolation):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
        detail = (
            "This record refers to something that does not exist "
            "(or has been removed). Please refresh the page and "
            "re-select the related record."
        )
    elif isinstance(exc, psycopg2.errors.NotNullViolation):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
        field = humanize_field(column) if column else "A required field"
        detail = f"{field} is required and cannot be left blank."
    elif isinstance(exc, psycopg2.errors.CheckViolation):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
        detail = (
            "The combination of values you entered is not allowed by a "
            "validation rule. Please review the entries and try again."
        )
    else:
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
        detail = (
            "The data could not be saved because it breaks a database "
            "rule. Please review the entries and try again."
        )

    return JSONResponse(status_code=code, content={"detail": detail})


# ── Catch-all ────────────────────────────────────────────────────────────

async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Last resort: a readable 500 plus a reference code for the logs.

    Deliberately says nothing about the internal failure — the traceback
    goes to the server log against `reference`, so a user can quote a
    short code and it can be found without exposing internals.

    "Nothing was saved" is accurate: get_write_connection rolls the
    transaction back on any exception before returning the connection
    to the pool.
    """
    reference = uuid4().hex[:8].upper()
    logger.exception(
        "Unhandled error [%s] on %s %s",
        reference, request.method, request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": (
                "Something went wrong on our side and the request could "
                "not be completed. Nothing was saved. Please try again — "
                f"if it keeps happening, quote reference {reference}."
            ),
            "reference": reference,
        },
    )


async def pool_busy_handler(request: Request, exc: Exception) -> JSONResponse:
    """Every database connection stayed in use past DB_POOL_WAIT_SECONDS: ask the
    client to retry shortly instead of reporting a server fault."""
    logging.getLogger(__name__).warning("database pool busy: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "The server is busy right now. Please try again in a moment."},
        headers={"Retry-After": "2"},
    )
