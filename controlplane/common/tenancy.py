"""Per-tenant visibility (v2, hard rule): a client sees only its own rows; any security-team
role sees all. Pure functions, stdlib only, so isolation is unit-testable without Redis/DB."""
from __future__ import annotations

import models


def visible_to(viewer_role: str, viewer_name: str, owner_name: str) -> bool:
    if models.is_team(viewer_role):
        return True
    return viewer_name == owner_name


def filter_owned(viewer_role: str, viewer_name: str, items: list[dict],
                 owner_key: str = "submitter") -> list[dict]:
    if models.is_team(viewer_role):
        return list(items)
    return [it for it in items if it.get(owner_key) == viewer_name]
