"""Report review pipeline transitions (v2): reporter -> lead -> governance -> delivered.

Pure and role-gated, so the state machine is unit-testable without Redis/DB/HTTP. The caller
(private API) persists the new stage and handles delivery side effects. PermissionError = the
role does not own the current stage (-> 403); ValueError = illegal transition (-> 409).
"""
from __future__ import annotations

import models

_ORDER = [models.REPORT_REPORTER, models.REPORT_LEAD,
          models.REPORT_GOVERNANCE, models.REPORT_DELIVERED]


def can_act(stage: str, role: str) -> bool:
    return role in models.report_stage_owner(stage)


def advance(stage: str, role: str) -> str:
    """Forward one stage. Raises PermissionError (wrong role) or ValueError (past delivered)."""
    i = _ORDER.index(stage)
    if i >= len(_ORDER) - 1:
        raise ValueError("report is already delivered")
    if not can_act(stage, role):
        raise PermissionError(f"{role} may not act at {stage}")
    return _ORDER[i + 1]


def send_back(stage: str, role: str) -> str:
    """Return the report one stage earlier. Same gating as advance."""
    if not can_act(stage, role):
        raise PermissionError(f"{role} may not act at {stage}")
    i = _ORDER.index(stage)
    if i == 0:
        raise ValueError("report is at the first stage")
    return _ORDER[i - 1]


if __name__ == "__main__":
    assert advance(models.REPORT_REPORTER, "reporter") == models.REPORT_LEAD
    assert send_back(models.REPORT_GOVERNANCE, "governance") == models.REPORT_LEAD
    for bad in (("pentester",), ):
        try:
            advance(models.REPORT_REPORTER, bad[0]); raise SystemExit("no guard")
        except PermissionError:
            pass
    print("report_pipeline.py self-check OK")
