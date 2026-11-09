"""Schemas for the live-refresh change feed (api/routers/live.py)."""

from pydantic import BaseModel


class LiveTableChange(BaseModel):
    """One watched table and the change number of its latest committed write. No record data, no ids."""
    table_name: str
    change_seq: int


class LiveChangesResponse(BaseModel):
    """GET /live/changes - every watched table with its current change number.

    No cursor: the client keeps the last change_seq it saw per table and treats a larger value as a change.
    """
    changed: list[LiveTableChange]
