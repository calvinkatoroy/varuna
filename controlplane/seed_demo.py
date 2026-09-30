"""Demo-data seeder (local/dev only): populates realistic supporting data across the pipeline
by calling the REAL endpoint functions directly (not HTTP, not hand-replicated logic) - same
business logic production uses, just orchestrated from a script instead of a browser. Findings
are injected via db.save_findings() directly rather than run through actual Nuclei/SQLMap, so
this takes seconds instead of the many minutes a real scan needs; everything else (proposal
approval, report generation, review-pipeline forwarding, PDF encryption via real LibreOffice)
is the genuine code path.

Deliberately leaves any proposal already in "scanning" (job created, no report yet) alone -
that's reserved for a live demo of the real agent + SSE progress.

Usage (inside the api-public container, so imports/env match):
  docker compose exec api-public python /app/controlplane/seed_demo.py
"""
from __future__ import annotations

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "report"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

import auth  # noqa: E402
import db  # noqa: E402
import generator  # noqa: E402
import models  # noqa: E402
import pdf_deliver  # noqa: E402
import redis_store  # noqa: E402
import store as report_store  # noqa: E402
import browser  # noqa: E402
import private_api  # noqa: E402

CLIENTS = ["globex", "initech", "umbrella"]


def user(username: str, role: str) -> dict:
    return {"username": username, "role": role}


def ensure_account(username: str, role: str) -> None:
    if not db.get_account(username):
        auth.create_account(username, "demo1234", role)


# Reusable, realistic finding sets (adapted from the same copy already used in the frontend's
# own mock fixtures this session, so the demo reads consistently either way).
FINDING_SETS = {
    "globex": [
        {"name": "Reflected XSS", "severity": "high", "host": "app.globex.io", "url": "/search?q=",
         "tool": "nuclei", "cve": "CWE-79",
         "evidence": "<script>alert(1)</script> reflected unescaped in response body",
         "impact": "An attacker can execute arbitrary JavaScript in a victim's browser session, enabling session hijacking or credential theft.",
         "remediation": "Context-encode output, set a strict Content-Security-Policy, and use an auto-escaping template engine."},
        {"name": "Missing HSTS header", "severity": "medium", "host": "app.globex.io", "url": "",
         "tool": "nuclei", "cve": "CWE-319",
         "evidence": "No Strict-Transport-Security header on HTTPS responses",
         "impact": "Visitors can be downgraded to plain HTTP by a network attacker, exposing traffic.",
         "remediation": "Add Strict-Transport-Security: max-age=31536000; includeSubDomains."},
    ],
    "initech": [
        {"name": "SQL Injection", "severity": "critical", "host": "portal.initech.com", "url": "/api/v1/invoices/search",
         "tool": "sqlmap", "cve": "CWE-89",
         "evidence": "q=1' AND SLEEP(5)-- -  ->  10.1s response",
         "impact": "Full database read/write access, including other tenants' invoice data.",
         "remediation": "Parameterize the query / use prepared statements. Validate and sanitize all user input."},
        {"name": "Broken access control", "severity": "high", "host": "portal.initech.com", "url": "/api/v1/admin/users",
         "tool": "nuclei", "cve": "CWE-284",
         "evidence": "A standard-role token reaches /admin/users and returns all records",
         "impact": "Any authenticated user can enumerate the full user directory, including admins.",
         "remediation": "Enforce server-side authorization on every object reference; deny by default."},
        {"name": "Missing rate limiting on login", "severity": "medium", "host": "portal.initech.com", "url": "/auth/login",
         "tool": "nuclei", "cve": "CWE-307",
         "evidence": "5,000 login attempts accepted from one IP in under a minute",
         "impact": "Enables credential-stuffing and brute-force attacks against user accounts.",
         "remediation": "Add exponential backoff / lockout after repeated failures; rate-limit by IP and account."},
    ],
    "umbrella": [
        {"name": "Outdated jQuery 1.12.4", "severity": "medium", "host": "shop.umbrella.co", "url": "/static/js/vendor.js",
         "tool": "nuclei", "cve": "CVE-2020-11022",
         "evidence": "jQuery 1.12.4 fingerprinted, known XSS in .html()",
         "impact": "A known-vulnerable library increases exposure to XSS if user input reaches the affected sink.",
         "remediation": "Upgrade to a supported jQuery release and re-test dependent widgets."},
        {"name": "Cookie without Secure flag", "severity": "low", "host": "shop.umbrella.co", "url": "",
         "tool": "nuclei", "cve": "CWE-614",
         "evidence": "Session cookie set without Secure over HTTPS",
         "impact": "Session cookie could be exposed over an accidental plain-HTTP connection.",
         "remediation": "Set Secure and HttpOnly on all session cookies."},
    ],
}


def make_job(target: str, submitter: str) -> dict:
    return {
        "id": str(uuid.uuid4()), "target": target, "target_class": "cloud",
        "submitter": submitter, "role": "client", "tools": ["katana", "nuclei", "sqlmap"],
        "opts": {}, "status": models.STATUS_DONE, "per_tool_status": {"katana": "done", "nuclei": "done", "sqlmap": "done"},
    }


def seed_proposal_at(client: str, target: str, purpose: str, division: str) -> tuple[str, dict]:
    ensure_account(client, models.ROLE_CLIENT)
    pid = db.create_proposal({
        "submitter": client, "target": target, "mode": "standard", "purpose": purpose,
        "division": division, "environment": "production", "authorization_attested": True,
    })
    job = make_job(target, client)
    redis_store.set_job(job)
    db.update_proposal(pid, status="approved", job_id=job["id"])
    db.save_findings(job["id"], client, FINDING_SETS.get(client, []))
    return pid, job


def main():
    # Idempotent: a second run would duplicate every seeded report. Wipe first to reseed.
    if any(db.list_proposals(submitter=c) for c in CLIENTS):
        print("Demo data already seeded (globex/initech/umbrella have proposals); skipping.")
        return
    # Team accounts (riyan/dimas/aisah/hani) are seeded separately via
    # `seed_account.py --team-defaults` - not repeated here.
    lead, reporter, gov = user("riyan", "lead_pentester"), user("aisah", "reporter"), user("hani", "governance")

    # globex: parked mid-review (reporter stage) - aisah has real work waiting.
    _, job_g = seed_proposal_at("globex", "http://app.globex.io", "compliance", "IT")
    r = private_api.pipeline_create(private_api.PipelineCreateBody(job_id=job_g["id"], template="Full Technical"), user=reporter)
    rid_g = r["report_id"]
    print(f"globex: report {rid_g} at reporter stage")

    # initech: one stage further - lead has real work waiting.
    _, job_i = seed_proposal_at("initech", "https://portal.initech.com", "pre-release", "Engineering")
    r = private_api.pipeline_create(private_api.PipelineCreateBody(job_id=job_i["id"], template="Full Technical"), user=reporter)
    rid_i = r["report_id"]
    private_api.pipeline_forward(rid_i, user=reporter)   # -> lead
    print(f"initech: report {rid_i} at lead stage")

    # umbrella: one stage further still - governance has real work waiting.
    _, job_u = seed_proposal_at("umbrella", "https://shop.umbrella.co", "periodic", "E-commerce")
    r = private_api.pipeline_create(private_api.PipelineCreateBody(job_id=job_u["id"], template="Full Technical"), user=reporter)
    rid_u = r["report_id"]
    private_api.pipeline_forward(rid_u, user=reporter)   # -> lead
    private_api.pipeline_forward(rid_u, user=lead)        # -> governance
    print(f"umbrella: report {rid_u} at governance stage")

    # acme: a fully DELIVERED engagement (past history), on top of the live "scanning" one -
    # real LibreOffice conversion + pypdf encryption, so Reports/password-reveal are genuine.
    pid_a, job_a = seed_proposal_at("acme", "https://mail.acme.io", "compliance", "IT")
    r = private_api.pipeline_create(private_api.PipelineCreateBody(job_id=job_a["id"], template="Full Technical"), user=reporter)
    rid_a = r["report_id"]
    private_api.pipeline_forward(rid_a, user=reporter)   # -> lead
    private_api.pipeline_forward(rid_a, user=lead)        # -> governance
    private_api.pipeline_forward(rid_a, user=gov)         # -> delivered (real PDF)
    print(f"acme: report {rid_a} DELIVERED, password: {db.get_report(rid_a)['pdf_password']}")

    # A pending proposal with no action taken yet, for the team to approve/reject live if wanted.
    ensure_account("stark", models.ROLE_CLIENT)
    db.create_proposal({
        "submitter": "stark", "target": "https://api.stark-industries.io", "mode": "standard",
        "purpose": "incident", "division": "SecOps", "authorization_attested": True,
    })
    print("stark: fresh pending proposal, untouched")

    print("\nSeed complete. The acme testphp.vulnweb.com proposal (if present) was left alone for the live demo.")


if __name__ == "__main__":
    main()
