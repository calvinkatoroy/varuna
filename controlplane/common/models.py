"""Shared data models for Varuna's control plane.

Plain dataclasses, stdlib only. Deliberately no pydantic here so this module stays
importable from every control-plane service (browser API, agent API, private API) without
pulling a web framework into the shared layer; FastAPI validates request bodies at its own
edge. Everything round-trips to JSON via to_dict / from_dict for Redis storage.

Finding fields follow SRS REQ-33; enrichment fields (REQ-35) and OWASP tag (REQ-62)
are optional and filled by later pipeline stages (REQ-36 keeps a finding when
enrichment fails, so they stay Optional).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

# Roles (SRS §4.11 v2): one client role + five security-team roles.
ROLE_CLIENT = "client"
ROLE_SYSADMIN = "sysadmin"
ROLE_PENTESTER = "pentester"
ROLE_LEAD = "lead_pentester"
ROLE_LEAD_CYBER = "lead_cyber"
ROLE_GOVERNANCE = "governance"
ROLE_MANAGER = "manager"
ROLES = (ROLE_CLIENT, ROLE_SYSADMIN, ROLE_PENTESTER, ROLE_LEAD, ROLE_LEAD_CYBER, ROLE_GOVERNANCE, ROLE_MANAGER)
SECURITY_TEAM = frozenset({ROLE_PENTESTER, ROLE_LEAD, ROLE_LEAD_CYBER, ROLE_GOVERNANCE, ROLE_MANAGER})

# Back-compat aliases (v1 used standard/pro); keep imports resolving during migration.
ROLE_STANDARD = ROLE_CLIENT
ROLE_PRO = ROLE_PENTESTER


def is_team(role: str) -> bool:
    return role in SECURITY_TEAM


def is_client(role: str) -> bool:
    return role == ROLE_CLIENT


def is_sysadmin(role: str) -> bool:
    return role == ROLE_SYSADMIN


def can_approve(role: str) -> bool:
    return role == ROLE_LEAD


def can_review(role: str) -> bool:
    return role in (ROLE_PENTESTER, ROLE_LEAD, ROLE_GOVERNANCE)

# Target classification (REQ-14).
CLASS_LOCAL = "local"
CLASS_CLOUD = "cloud"

# Proposal status (v2): a scan proposal awaits lead-pentester approval before any scan runs.
# Where a scan runs: on the client's own computer (their agent) or by Varuna (the cloud scanner on the host).
SCAN_LOCAL, SCAN_CLOUD = "local", "cloud"
# The cloud scanner is an ordinary agent enrolled under this reserved name (clients cannot register it).
CLOUD_AGENT = "varuna-cloud"

PROPOSAL_PENDING = "pending"
PROPOSAL_APPROVED = "approved"
PROPOSAL_REJECTED = "rejected"
PROPOSAL_STATUSES = (PROPOSAL_PENDING, PROPOSAL_APPROVED, PROPOSAL_REJECTED)

# Report review pipeline stages (v2): reporter -> lead -> governance -> delivered.
REPORT_REPORTER = "in_review_reporter"
REPORT_LEAD = "in_review_lead"
REPORT_GOVERNANCE = "in_review_governance"
REPORT_DELIVERED = "delivered"
REPORT_STAGES = (REPORT_REPORTER, REPORT_LEAD, REPORT_GOVERNANCE, REPORT_DELIVERED)


def report_stage_owner(stage: str) -> frozenset:
    """Roles allowed to edit/forward at a stage. Lead can also act at the reporter stage
    (sees all, may edit). Governance forwarding delivers to the client."""
    return {
        REPORT_REPORTER: frozenset({ROLE_PENTESTER, ROLE_LEAD}),
        REPORT_LEAD: frozenset({ROLE_LEAD}),
        REPORT_GOVERNANCE: frozenset({ROLE_GOVERNANCE}),
    }.get(stage, frozenset())


# Overall job status (REQ-23).
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
JOB_STATUSES = (STATUS_QUEUED, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED)

# Severity order, critical first (REQ-38).
SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")


def severity_rank(sev: str) -> int:
    """Sort key: lower rank = more severe. Unknown severities sort last."""
    s = (sev or "").strip().lower()
    return SEVERITY_ORDER.index(s) if s in SEVERITY_ORDER else len(SEVERITY_ORDER)


@dataclass
class Finding:
    # REQ-33 core fields.
    name: str
    severity: str
    host: str
    url: str = ""
    description: str = ""
    cve: Optional[str] = None
    cvss: Optional[float] = None
    cwe: Optional[str] = None
    tool: str = ""              # "manual" for hand-entered findings (REQ-58)
    evidence: str = ""
    # Reporting Intelligence (REQ-62).
    owasp: Optional[str] = None
    # AI enrichment (REQ-35); absent until enrichment runs.
    impact: Optional[str] = None
    remediation: Optional[str] = None
    risk_rating: Optional[str] = None
    # ponytail: single tool/evidence string is enough until correlation (Phase E, REQ-61/64)
    # needs to merge multiple sources; widen to lists there, not before.

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        fields = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in fields})


@dataclass
class Job:
    id: str
    target: str
    target_class: str          # CLASS_LOCAL | CLASS_CLOUD (REQ-14)
    submitter: str
    role: str
    tools: list = field(default_factory=list)
    opts: dict = field(default_factory=dict)
    status: str = STATUS_QUEUED
    per_tool_status: dict = field(default_factory=dict)   # tool -> status (REQ-23)
    error: Optional[str] = None
    scan_mode: str = "local"           # local = the client's agent runs it; cloud = the cloud scanner does
    executor: Optional[str] = None     # agent username allowed to run this job when it is not the submitter
    org_id: Optional[str] = None       # owning organization, copied from the account/proposal (never request input)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        fields = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in fields})


@dataclass
class Account:
    username: str
    password_hash: str         # bcrypt (NFR-22); never plaintext
    role: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Account":
        fields = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in fields})


if __name__ == "__main__":
    # Self-check (ponytail: one runnable check for the serialization logic).
    f = Finding(name="SQLi", severity="Critical", host="http://t.local",
                url="http://t.local/?id=1", tool="sqlmap", evidence="id=1'")
    assert Finding.from_dict(f.to_dict()) == f, "Finding round-trip failed"
    # Unknown keys are dropped, not crashed on.
    assert Finding.from_dict({**f.to_dict(), "bogus": 1}) == f, "extra-key drop failed"

    j = Job(id="abc", target="http://t.local", target_class=CLASS_LOCAL,
            submitter="calvin", role=ROLE_PRO, tools=["katana", "nuclei"])
    assert Job.from_dict(j.to_dict()) == j, "Job round-trip failed"

    # Severity sorts critical-first, unknowns last (REQ-38).
    sevs = ["low", "critical", "bogus", "high", "info", "medium"]
    assert sorted(sevs, key=severity_rank) == \
        ["critical", "high", "medium", "low", "info", "bogus"], "severity sort wrong"

    print("models.py self-check OK")
