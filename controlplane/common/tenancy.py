"""Per-tenant visibility (v2, hard rule): a client sees only its own rows; any security-team
role sees all. Pure functions, stdlib only, so isolation is unit-testable without Redis/DB."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import models


@dataclass(frozen=True)
class Scope:
    org_id: Optional[str]    # None = every organization (staff only)


def scope_for(user: dict) -> Scope:
    if models.is_client(user["role"]):
        if not user.get("org_id"):
            raise PermissionError("client without an organization")
        return Scope(user["org_id"])
    if models.is_team(user["role"]):
        return Scope(None)
    raise PermissionError("role has no access to tenant data")


def visible_to(viewer_role: str, viewer_name: str, owner_name: str) -> bool:
    if models.is_team(viewer_role):
        return True
    return viewer_name == owner_name


def filter_owned(viewer_role: str, viewer_name: str, items: list[dict],
                 owner_key: str = "submitter") -> list[dict]:
    if models.is_team(viewer_role):
        return list(items)
    return [it for it in items if it.get(owner_key) == viewer_name]
