"""Browser-facing JSON API, private plane (SRS §4.7, §4.6a, NFR-24).

Replaces the Streamlit private UI. Bound to the Tailscale interface only in production, no
public listener: full Findings Review, Manual Findings Input, and the full report archive
across all users and all four templates. Pro-only (require_pro on every endpoint).
"""
from __future__ import annotations

import io
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()  # repo-root .env, for host-run dev (REDIS_URL, JWT_SECRET, ...)

from fastapi import Depends, FastAPI, File, Header, HTTPException, Response, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import secrets  # noqa: E402

import audit  # noqa: E402
import notify  # noqa: E402
import totp  # noqa: E402
import board  # noqa: E402
import db  # noqa: E402
import generator  # noqa: E402
import ingest  # noqa: E402
import models  # noqa: E402
import pdf_deliver  # noqa: E402
import redis_store  # noqa: E402
import report_pipeline  # noqa: E402
import store as report_store  # noqa: E402
import auth  # noqa: E402
import jwt_auth  # noqa: E402
import browser  # noqa: E402  (proposal/scan/finding logic is shared; only the auth plane differs)
from deps import current_user, mfa_required, require_lead, require_pro, require_team, require_team_setup  # noqa: E402

app = FastAPI(title="Varuna Private API (Tailscale plane)")
_CORS = os.environ.get("VARUNA_CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=_CORS, allow_methods=["*"], allow_headers=["*"])
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _mime(fname: str) -> str:
    return "application/pdf" if fname.endswith(".pdf") else DOCX_MIME


@app.on_event("startup")
def _warn_default_passwords() -> None:
    secret = jwt_auth.JWT_SECRET
    if secret == "dev-only-change-me" or len(secret) < 32:
        print("WARNING: JWT_SECRET is the built-in dev value or shorter than 32 characters. Anyone who knows it can forge "
              "logins. Set a long random value (openssl rand -hex 32).", flush=True)
    no_mfa = [a["username"] for a in db.list_accounts() if a["role"] != "client" and not a["totp_enabled"]]
    if no_mfa:
        print(f"NOTE: team accounts without two-factor: {', '.join(no_mfa)}. Enable it from the account menu.", flush=True)
    weak = auth.default_password_accounts()
    if weak:
        print(f"WARNING: team accounts still use the default password 'changeme': {', '.join(weak)}. "
              "Change them (POST /api/password or the admin reset) before any non-local use.", flush=True)


class LoginBody(BaseModel):
    username: str
    password: str
    code: str | None = None      # authenticator code, required once two-factor is enabled


@app.post("/api/login")
def login(body: LoginBody, x_forwarded_for: str = Header(default="api")):
    """Security-team sign-in (NFR-24): same credentials/throttle as the public plane, but only
    team roles get a token here, so a rejected client login never leaves a session behind."""
    try:
        token = jwt_auth.login(body.username, body.password, x_forwarded_for, body.code)
    except auth.LockedOut:
        raise HTTPException(status_code=429, detail="too many failed attempts; try again later")
    except auth.MfaRequired:
        raise HTTPException(status_code=401, detail="mfa_required")   # the UI then asks for the code
    except auth.BadCredentials as e:
        raise HTTPException(status_code=401, detail=str(e))
    if not models.is_team(jwt_auth.verify(token)["role"]):
        raise HTTPException(status_code=403, detail="that account doesn't have security-team access")
    return {"token": token}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


class PasswordBody(BaseModel):
    current: str
    new: str


@app.post("/api/password")
def change_password(body: PasswordBody, user: dict = Depends(require_team_setup)):
    try:
        auth.change_password(user["username"], body.current, body.new)
    except auth.BadCredentials as e:
        raise HTTPException(status_code=403, detail=str(e))
    except auth.AuthError as e:
        raise HTTPException(status_code=422, detail=str(e))
    audit.log("password_changed", actor=user["username"])
    return {"ok": True}


# --- two-factor (TOTP) for team accounts: enrol with an authenticator app, then logins need a code ---
class CodeBody(BaseModel):
    code: str


class MfaDisableBody(BaseModel):
    password: str
    code: str = ""


@app.get("/api/mfa")
def mfa_status(user: dict = Depends(require_team_setup)):
    acct = db.get_account(user["username"]) or {}
    return {"enabled": bool(acct.get("totp_enabled")), "required": mfa_required()}


@app.post("/api/mfa/setup")
def mfa_setup(user: dict = Depends(require_team_setup)):
    """New secret (not enforced until confirmed). Shown once here; the app also gets the otpauth URI."""
    secret = auth.mfa_begin(user["username"])
    return {"secret": secret, "uri": totp.otpauth_uri(user["username"], secret)}


@app.post("/api/mfa/enable")
def mfa_enable(body: CodeBody, user: dict = Depends(require_team_setup)):
    try:
        auth.mfa_confirm(user["username"], body.code)
    except auth.BadCredentials as e:
        raise HTTPException(status_code=422, detail=str(e))
    except auth.AuthError as e:
        raise HTTPException(status_code=409, detail=str(e))
    audit.log("mfa_enabled", actor=user["username"])
    return {"enabled": True}


@app.post("/api/mfa/disable")
def mfa_disable(body: MfaDisableBody, user: dict = Depends(require_team_setup)):
    try:
        auth.mfa_disable(user["username"], body.password, body.code)
    except auth.BadCredentials as e:
        raise HTTPException(status_code=403, detail=str(e))
    audit.log("mfa_disabled", actor=user["username"])
    return {"enabled": False}


# --- account administration (lead pentester): provision/disable team accounts and reset
# passwords without shell access to the server. ---
class AccountBody(BaseModel):
    username: str
    password: str
    role: str


class ResetBody(BaseModel):
    password: str


@app.get("/api/admin/accounts")
def admin_accounts(user: dict = Depends(require_lead)):
    return db.list_accounts()


@app.post("/api/admin/accounts")
def admin_create_account(body: AccountBody, user: dict = Depends(require_lead)):
    if body.role not in models.ROLES:
        raise HTTPException(status_code=422, detail="unknown role")
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,32}", body.username):
        raise HTTPException(status_code=422, detail="username must be 3-32 letters, digits, dot, dash or underscore")
    if db.get_account_ci(body.username):
        raise HTTPException(status_code=409, detail="username already taken")
    try:
        auth._check_new_password(body.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=422, detail=str(e))
    auth.create_account(body.username, body.password, body.role)
    audit.log("account_created", actor=user["username"], account=body.username, role=body.role)
    return {"username": body.username, "role": body.role}


@app.post("/api/admin/accounts/{username}/reset-password")
def admin_reset_password(username: str, body: ResetBody, user: dict = Depends(require_lead)):
    try:
        auth.admin_reset_password(username, body.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=404 if "no such" in str(e) else 422, detail=str(e))
    audit.log("password_reset", actor=user["username"], account=username)
    return {"ok": True}


@app.post("/api/admin/accounts/{username}/reset-mfa")
def admin_reset_mfa(username: str, user: dict = Depends(require_lead)):
    """Recovery for a lost phone: clears the user's two-factor so they can enrol again."""
    if not auth.mfa_reset(username):
        raise HTTPException(status_code=404, detail="no such account")
    audit.log("mfa_reset", actor=user["username"], account=username)
    return {"ok": True}


@app.post("/api/admin/accounts/{username}/{action}")
def admin_set_disabled(username: str, action: str, user: dict = Depends(require_lead)):
    if action not in ("disable", "enable"):
        raise HTTPException(status_code=404, detail="unknown action")
    if action == "disable" and username == user["username"]:
        raise HTTPException(status_code=409, detail="you cannot disable your own account")
    if not db.set_account(username, disabled=1 if action == "disable" else 0):
        raise HTTPException(status_code=404, detail="no such account")
    audit.log(f"account_{action}d", actor=user["username"], account=username)
    return {"ok": True}


# --- team actions that used to live on the public plane (NFR-24): same logic as browser.py,
# served here so team tokens are not needed on the internet-facing API at all. ---
@app.post("/api/proposals/{pid}/approve")
def approve_proposal(pid: str, user: dict = Depends(require_lead)):
    return browser.approve_proposal(pid, user)


@app.post("/api/proposals/{pid}/reject")
def reject_proposal(pid: str, body: browser.RejectBody, user: dict = Depends(require_lead)):
    return browser.reject_proposal(pid, body, user)


@app.post("/api/scans")
def submit_scan(body: browser.ScanBody, user: dict = Depends(require_team)):
    return browser.submit_scan(body, user)


@app.get("/api/scans/{job_id}/events")
async def scan_events(job_id: str, user: dict = Depends(require_team)):
    """Live scan progress for the team (the public plane refuses team tokens, NFR-24)."""
    return await browser.scan_events(job_id, user)


@app.get("/api/findings")
def list_findings(user: dict = Depends(require_team)):
    return browser.list_findings(user)


@app.post("/api/findings/{fid}/status")
def set_finding_status(fid: str, body: browser.FindingStatusBody, user: dict = Depends(require_team)):
    return browser.set_finding_status(fid, body, user)


@app.get("/api/findings/{job_id}")
def findings(job_id: str, user: dict = Depends(require_pro)):
    return db.get_findings(job_id)


class ManualBody(BaseModel):
    name: str
    severity: str
    host: str
    url: str = ""
    description: str = ""
    evidence: str = ""


@app.post("/api/findings/{job_id}/manual")
def add_manual(job_id: str, body: ManualBody, user: dict = Depends(require_pro)):
    try:
        return ingest.add_manual_finding(job_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class VerdictBody(BaseModel):
    verdict: str   # "tp" | "fp"


@app.post("/api/findings/{fid}/verdict")
def set_finding_verdict(fid: str, body: VerdictBody, user: dict = Depends(require_team)):
    if body.verdict not in ("tp", "fp"):
        raise HTTPException(status_code=422, detail="verdict must be tp or fp")
    if not db.get_finding(fid):
        raise HTTPException(status_code=404, detail="no such finding")
    db.set_finding(fid, verdict=body.verdict)
    return {"ok": True}


# --- scan suspend/resume (v2, phase-boundary): the agent checks in with GET
# /agent/jobs/{id}/suspended (controlplane/api/main.py) before each tool phase and blocks
# there while suspended - see agent/scan.py's checkpoint. Not instant mid-tool pause. ---
@app.post("/api/pipeline/scans/{job_id}/suspend")
def suspend_scan(job_id: str, user: dict = Depends(require_team)):
    if not redis_store.get_job(job_id):
        raise HTTPException(status_code=404, detail="no such job")
    redis_store.set_suspended(job_id, True)
    audit.log("scan_suspended", actor=user["username"], job=job_id)
    return {"ok": True}


@app.post("/api/pipeline/scans/{job_id}/resume")
def resume_scan(job_id: str, user: dict = Depends(require_team)):
    if not redis_store.get_job(job_id):
        raise HTTPException(status_code=404, detail="no such job")
    redis_store.set_suspended(job_id, False)
    audit.log("scan_resumed", actor=user["username"], job=job_id)
    return {"ok": True}


# --- team pipeline board (v2): kanban view composed from proposals + jobs + reports ---
@app.get("/api/pipeline/board")
def pipeline_board(user: dict = Depends(require_team)):
    board.reap_stalled()   # opportunistic: no scheduler needed, the board is polled while anyone watches
    return board.build_board()


@app.get("/api/pipeline/detail/{id}")
def pipeline_detail(id: str, user: dict = Depends(require_team)):
    """Card detail for the review drawer: the proposal it started as (with its own scope/RoE
    if the id itself is a proposal id) or the report's originating proposal (if id is a report
    id), plus version history where applicable."""
    p = db.get_proposal(id)
    if p:
        return {
            "proposal": {
                "purpose": p["purpose"], "division": p["division"],
                "environment": p["environment"], "authorized": p["authorization_attested"],
            },
        }
    r = _require_report(id)
    rp = db.get_proposal_by_job(r["job_id"])
    return {
        "proposal": {
            "purpose": (rp or {}).get("purpose", ""), "division": (rp or {}).get("division", ""),
            "environment": (rp or {}).get("environment", ""),
            "authorized": bool((rp or {}).get("authorization_attested")),
        },
        "versions": db.list_report_versions(id),
    }


@app.get("/api/reports/all")
def all_reports(user: dict = Depends(require_pro)):
    return report_store.list_all_reports()


class GenerateBody(BaseModel):
    job_id: str
    template: str


@app.post("/api/reports/generate")
def generate_report(body: GenerateBody, user: dict = Depends(require_pro)):
    job = redis_store.get_job(body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
    try:
        data = generator.generate(job, db.get_findings(body.job_id), body.template)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return report_store.save_report(user["username"], body.job_id, body.template, data)


@app.get("/api/reports/{fname}/download")
def download_report(fname: str, user: dict = Depends(require_pro)):
    try:
        data = report_store.read_report(fname)
    except OSError:
        raise HTTPException(status_code=404, detail="no such report")
    return Response(content=data, media_type=_mime(fname),
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# --- report review pipeline (v2): reporter -> lead -> governance -> delivered ---
class PipelineCreateBody(BaseModel):
    job_id: str
    template: str = "Full Technical"


@app.post("/api/pipeline/reports")
def pipeline_create(body: PipelineCreateBody, user: dict = Depends(require_team)):
    """Start the review pipeline: generate v1 of the report and place it at the reporter stage.
    The report owner is the client who owns the job (tenancy)."""
    job = redis_store.get_job(body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
    try:
        rid = ingest.start_review(job, body.template, editor=user["username"])
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"report_id": rid, "stage": models.REPORT_REPORTER}


MAX_UPLOAD = 25 * 1024 * 1024
DELIVERING = "delivering"   # transient stage while the protected PDF is being produced


def _check_docx(data: bytes) -> None:
    """A review version must be a real, non-empty Word file: it ends up, converted, in the
    client's hands. Reject empty/oversized/non-docx bytes before they enter version history."""
    if not data or len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=422, detail="file is empty or larger than 25 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if "word/document.xml" not in z.namelist():
                raise zipfile.BadZipFile
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="not a valid .docx file")


def _require_report(rid: str) -> dict:
    r = db.get_report(rid)
    if not r:
        raise HTTPException(status_code=404, detail="no such report")
    return r


@app.get("/api/pipeline/reports")
def pipeline_reports(user: dict = Depends(require_team)):
    """Every client's reports in review (team sees all; lead sees all versions)."""
    # The PDF password is view-once and out-of-band: only governance's reissue returns it.
    return [{k: v for k, v in r.items() if k != "pdf_password"} for r in db.list_reports()]


@app.get("/api/pipeline/reports/{rid}/versions")
def pipeline_versions(rid: str, user: dict = Depends(require_team)):
    _require_report(rid)
    return db.list_report_versions(rid)


@app.post("/api/pipeline/reports/{rid}/version")
def pipeline_upload_version(rid: str, file: UploadFile = File(...), note: str = "",
                            user: dict = Depends(require_team)):
    r = _require_report(rid)
    if not report_pipeline.can_act(r["stage"], user["role"]):
        raise HTTPException(status_code=403, detail="you do not own this review stage")
    data = file.file.read(MAX_UPLOAD + 1)
    _check_docx(data)
    next_no = ((db.latest_version(rid) or {}).get("version_no") or 0) + 1
    fname = f"{rid}_v{next_no}.docx"
    report_store.save_report_file(fname, data)
    vno = db.add_report_version(rid, filename=fname, editor=user["username"], note=note)
    audit.log("report_version", editor=user["username"], report=rid, version=vno)
    return {"report_id": rid, "version_no": vno, "file": fname}


class TemplateBody(BaseModel):
    template: str


@app.get("/api/templates")
def list_templates(user: dict = Depends(require_team)):
    return list(generator.TEMPLATES)


@app.post("/api/pipeline/reports/{rid}/template")
def pipeline_change_template(rid: str, body: TemplateBody, user: dict = Depends(require_team)):
    """Regenerate the report from the current findings in another template, as a NEW version
    (history is kept; earlier edits stay downloadable). Only the role that owns the stage."""
    r = _require_report(rid)
    if not report_pipeline.can_act(r["stage"], user["role"]):
        raise HTTPException(status_code=403, detail="you do not own this review stage")
    job = redis_store.get_job(r["job_id"]) or {"id": r["job_id"], "target": "", "submitter": r["owner"]}
    try:
        data = generator.generate(job, db.get_findings(r["job_id"]), body.template)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    next_no = ((db.latest_version(rid) or {}).get("version_no") or 0) + 1
    fname = f"{rid}_v{next_no}.docx"
    report_store.save_report_file(fname, data)
    vno = db.add_report_version(rid, filename=fname, editor=user["username"],
                                note=f"regenerated as {body.template}")
    db.set_report(rid, template=body.template)
    audit.log("report_template", actor=user["username"], report=rid, template=body.template)
    return {"report_id": rid, "version_no": vno, "template": body.template}


@app.get("/api/pipeline/reports/{rid}/versions/{n}/download")
def pipeline_download_version(rid: str, n: int, user: dict = Depends(require_team)):
    v = next((v for v in db.list_report_versions(rid) if v["version_no"] == n), None)
    if not v:
        raise HTTPException(status_code=404, detail="no such version")
    try:
        data = report_store.read_report(v["filename"])
    except OSError:
        raise HTTPException(status_code=404, detail="version file missing")
    return Response(content=data, media_type=DOCX_MIME,
                    headers={"Content-Disposition": f'attachment; filename="{v["filename"]}"'})


@app.post("/api/pipeline/reports/{rid}/forward")
def pipeline_forward(rid: str, user: dict = Depends(require_team)):
    r = _require_report(rid)
    try:
        new_stage = report_pipeline.advance(r["stage"], user["role"])
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    moved = HTTPException(status_code=409, detail="this report was just moved by someone else; refresh")
    if new_stage == models.REPORT_DELIVERED:
        # Claim the transition first ("delivering" is a transient state), so concurrent governance
        # clicks cannot each generate a PDF + password; put it back if delivery fails.
        if not db.claim_report_stage(rid, r["stage"], DELIVERING):
            raise moved
        try:
            _deliver_report(rid)   # governance sign-off: produce the protected PDF + password
        except Exception:
            db.set_report(rid, stage=r["stage"])
            raise
    elif not db.claim_report_stage(rid, r["stage"], new_stage):
        raise moved
    audit.log("report_forward", actor=user["username"], report=rid, stage=new_stage)
    notify.notify(f"Report {rid[:8]} is now at {new_stage}")
    return {"report_id": rid, "stage": new_stage}


def _deliver_report(rid: str) -> None:
    """Convert the latest review version to a password-protected PDF and mark DELIVERED."""
    v = db.latest_version(rid)
    if not v:
        raise HTTPException(status_code=409, detail="no report version to deliver")
    docx = report_store.read_report(v["filename"])
    _check_docx(docx)
    password = secrets.token_urlsafe(9)
    try:
        pdf = pdf_deliver.deliver(docx, password)
    except Exception:
        raise HTTPException(status_code=502, detail="PDF conversion failed; report not delivered")
    fname = f"{rid}_delivered.pdf"
    report_store.save_report_file(fname, pdf)
    db.set_report(rid, stage=models.REPORT_DELIVERED, delivered_pdf=fname,
                  pdf_password=password, password_viewed=0)


@app.post("/api/pipeline/reports/{rid}/reissue-password")
def pipeline_reissue_password(rid: str, user: dict = Depends(require_team)):
    """Governance re-issues the view-once PDF password when the client lost it."""
    if user["role"] != models.ROLE_GOVERNANCE:
        raise HTTPException(status_code=403, detail="only governance re-issues the password")
    r = _require_report(rid)
    if r["stage"] != models.REPORT_DELIVERED or not r["pdf_password"]:
        raise HTTPException(status_code=409, detail="report is not delivered")
    db.set_report(rid, password_viewed=0)   # let the client view it once more
    audit.log("password_reissue", actor=user["username"], report=rid)
    return {"report_id": rid, "password": r["pdf_password"]}


@app.post("/api/pipeline/reports/{rid}/sendback")
def pipeline_sendback(rid: str, user: dict = Depends(require_team)):
    r = _require_report(rid)
    try:
        new_stage = report_pipeline.send_back(r["stage"], user["role"])
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not db.claim_report_stage(rid, r["stage"], new_stage):
        raise HTTPException(status_code=409, detail="this report was just moved by someone else; refresh")
    audit.log("report_sendback", actor=user["username"], report=rid, stage=new_stage)
    notify.notify(f"Report {rid[:8]} was sent back to {new_stage}")
    return {"report_id": rid, "stage": new_stage}
