"""Per-tenant visibility (hard rule): a client sees only its organization's rows; any
security-team role sees all. Pure functions, stdlib only, so isolation is unit-testable without Redis/DB."""
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


def visible(scope: Scope, row_org: str) -> bool:
    return scope.org_id is None or scope.org_id == row_org
