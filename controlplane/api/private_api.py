"""Browser-facing JSON API, private plane (SRS §4.7, §4.6a, NFR-24).

Replaces the Streamlit private UI. Bound to the Tailscale interface only in production, no
public listener: full Findings Review, Manual Findings Input, and the full report archive
across all users and all four templates. Pro-only (require_pro on every endpoint).
"""
from __future__ import annotations

import io
import os
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
from deps import current_user, require_pro, require_team  # noqa: E402

app = FastAPI(title="Varuna Private API (Tailscale plane)")
_CORS = os.environ.get("VARUNA_CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=_CORS, allow_methods=["*"], allow_headers=["*"])
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _mime(fname: str) -> str:
    return "application/pdf" if fname.endswith(".pdf") else DOCX_MIME


class LoginBody(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(body: LoginBody, x_forwarded_for: str = Header(default="api")):
    """Security-team sign-in (NFR-24): same credentials/throttle as the public plane, but only
    team roles get a token here, so a rejected client login never leaves a session behind."""
    try:
        token = jwt_auth.login(body.username, body.password, x_forwarded_for)
    except auth.LockedOut:
        raise HTTPException(status_code=429, detail="too many failed attempts; try again later")
    except auth.BadCredentials:
        raise HTTPException(status_code=401, detail="invalid username or password")
    if not models.is_team(jwt_auth.verify(token)["role"]):
        raise HTTPException(status_code=403, detail="that account doesn't have security-team access")
    return {"token": token}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


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
        data = generator.generate(job, db.get_findings(body.job_id), body.template)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    rid = db.create_report(job_id=body.job_id, owner=job["submitter"], template=body.template)
    fname = f"{rid}_v1.docx"
    report_store.save_report_file(fname, data)
    db.add_report_version(rid, filename=fname, editor=user["username"], note="auto-generated v1")
    audit.log("report_created", actor=user["username"], report=rid, job=body.job_id)
    return {"report_id": rid, "stage": models.REPORT_REPORTER}


MAX_UPLOAD = 25 * 1024 * 1024


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
    if new_stage == models.REPORT_DELIVERED:
        _deliver_report(rid)   # governance sign-off: produce the protected PDF + password
    else:
        db.set_report(rid, stage=new_stage)
    audit.log("report_forward", actor=user["username"], report=rid, stage=new_stage)
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
    db.set_report(rid, stage=new_stage)
    audit.log("report_sendback", actor=user["username"], report=rid, stage=new_stage)
    return {"report_id": rid, "stage": new_stage}
