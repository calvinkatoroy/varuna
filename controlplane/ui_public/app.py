"""Varuna public-plane dashboard (SRS §3.1, §4.11).

Internet-facing, Caddy-fronted. Holds no finding content: login, agent install, scan
submission (through the Approval Gate), job/agent status, Approval Queue, and a Standard
user's own sanitized Executive Summaries. Pro findings review + full report archive live
on the private plane (ui_private, Tailscale-only, NFR-24).

Pages are gated by role (§2.3); there is no dashboard picker. An account with no registered
agent is forced to the Install Agent page first (REQ-71).
"""
import os
import sys

for _d in ("common", "report"):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", _d))

import streamlit as st

import auth
import classifier
import dispatch
import generator
import models
import redis_store
import store as report_store
import tokens

st.set_page_config(page_title="Varuna", layout="wide")

MODES = {
    "VA Only (Katana + Nuclei)": ["katana", "nuclei"],
    "Injection Focus (Katana + SQLMap)": ["katana", "sqlmap"],
    "Full Web (Katana + Nuclei + SQLMap)": ["katana", "nuclei", "sqlmap"],
}
AUTH_WARNING = "Only scan targets you are explicitly authorized to test. Prefer staging over production."


def _client_ip() -> str:
    try:
        return st.context.headers.get("X-Forwarded-For", "ui")   # set by Caddy in prod
    except Exception:
        return "ui"


def login_page():
    st.title("Varuna — Web VAPT")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Log in"):
            try:
                acct = auth.authenticate(u, p, _client_ip())
                st.session_state.user = acct.username
                st.session_state.role = acct.role
                st.rerun()
            except auth.LockedOut:
                st.error("Too many failed attempts. Please try again later.")
            except auth.BadCredentials:
                st.error("Invalid username or password.")


def install_agent_page(user):
    st.header("Install Your Agent")
    st.write(
        "Before your first scan, install the Varuna agent on your own machine. "
        "It runs the scan locally and reports back. This is a one-time step."
    )
    if st.button("Generate enrollment token"):
        st.session_state.enroll_token = tokens.generate_enrollment_token(user)
    if "enroll_token" in st.session_state:
        st.success("Run this once on your machine, then refresh:")
        st.code(f"python agent.py {st.session_state.enroll_token}")
    if st.button("I've installed it — refresh"):
        st.rerun()


def _submit(user, role, target, tools, **kw):
    try:
        res = dispatch.submit_scan(user, role, target, tools, **kw)
    except classifier.ClassifyRejected as e:
        st.error(f"Target rejected (could not be classified safely): {e}")
        return
    except dispatch.OfflineAgent as e:
        st.error(str(e))
        return
    if res["state"] == "pending_approval":
        st.warning(f"Submitted. This is a cloud target, so it awaits Pro approval. Job ID: {res['job_id']}")
    else:
        st.success(f"Scan dispatched to your agent. Job ID: {res['job_id']}")


def new_scan_standard(user):
    st.header("New Scan")
    st.info(AUTH_WARNING)
    target = st.text_input("Target URL or hostname")
    name = st.text_input("Your name")
    division = st.text_input("Division")
    ack = st.checkbox("I confirm I am authorized to scan this target")
    if st.button("Submit"):
        if not target:
            st.error("Target is required.")
        elif not ack:
            st.error("You must confirm authorization before submitting.")
        else:
            _submit(user, models.ROLE_STANDARD, target,
                    ["katana", "nuclei", "sqlmap"], division=division or name)


def new_scan_pro(user):
    st.header("New Scan")
    st.info(AUTH_WARNING)
    target = st.text_input("Target (URL, hostname, or IP)")
    mode = st.selectbox("Scan mode", list(MODES))
    template = st.selectbox("Report template", generator.TEMPLATES)
    cookie = st.text_input("Session cookie for authenticated scan (optional)")
    aggressive = st.checkbox("Enable aggressive SQLMap (--dump / --os-shell). Pro only, off by default.")
    ack = st.checkbox("I confirm I am authorized to scan this target")
    if st.button("Launch"):
        if not target:
            st.error("Target is required.")
        elif not ack:
            st.error("You must confirm authorization before launching.")
        else:
            _submit(user, models.ROLE_PRO, target, MODES[mode],
                    opts={"template": template, "cookie": cookie, "aggressive": aggressive})


def active_scans_page(user, role):
    st.header("Active Scans")
    jid = st.text_input("Job ID")
    if not jid:
        return
    job = redis_store.get_job(jid)
    if not job:
        st.error("No such job (it may have expired after 24h).")
        return
    online = tokens.is_online(job["submitter"])
    st.write(f"**Status:** {job['status']}  |  **Agent:** {'online' if online else 'offline'}")
    if job.get("per_tool_status"):
        st.write("**Per-tool:**", job["per_tool_status"])
    if job.get("status") == models.STATUS_QUEUED and job.get("role") == models.ROLE_STANDARD \
            and job.get("target_class") == classifier.CLASS_CLOUD:
        appr = redis_store.get_approval(jid)
        if appr and appr.get("status") == "pending":
            st.info("Pending Pro approval (cloud target).")
    st.button("Refresh")   # ponytail: manual refresh; 5s auto-refresh (REQ-24) needs a component

    if job.get("status") == models.STATUS_DONE and role == models.ROLE_STANDARD:
        if st.button("Generate Report"):
            findings = redis_store.get_findings(jid)
            data = generator.generate(job, findings, "Executive Summary")
            report_store.save_report(user, jid, "Executive Summary", data)
            st.download_button("Download .docx", data, file_name=f"{jid}_Executive_Summary.docx")
    elif job.get("status") == models.STATUS_DONE and role == models.ROLE_PRO:
        st.info("Review findings and generate full reports on the private dashboard (Tailscale).")


def approval_queue_page(user):
    st.header("Approval Queue")
    pending = dispatch.pending_approvals()
    if not pending:
        st.info("No pending requests.")
        return
    for req in pending:
        jid = req["job_id"]
        st.divider()
        st.write(f"**{req.get('submitter')}** ({req.get('division', '')}) → `{req.get('target')}` "
                 f"[{req.get('target_class')}]  ·  {req.get('timestamp', '')}")
        reason = st.text_input("Reject reason", key=f"r_{jid}")
        c1, c2 = st.columns(2)
        if c1.button("Approve", key=f"a_{jid}"):
            try:
                dispatch.approve_request(jid, user)
                st.rerun()
            except dispatch.OfflineAgent as e:
                st.error(str(e))
        if c2.button("Reject", key=f"x_{jid}"):
            dispatch.reject_request(jid, user, reason or "no reason given")
            st.rerun()


def reports_page(user):
    st.header("Reports")
    reports = report_store.list_reports(user)
    if not reports:
        st.info("No reports yet. Generate one from a completed scan.")
        return
    for r in reports:
        c1, c2 = st.columns([3, 1])
        c1.write(f"{r['file']}  ·  {r['template']}  ·  {r['ts']}")
        c2.download_button("Download", report_store.read_report(r["file"]),
                           file_name=r["file"], key=r["file"])


def main():
    if "user" not in st.session_state:
        login_page()
        return
    user, role = st.session_state.user, st.session_state.role
    st.sidebar.write(f"**{user}** · {role}")
    if st.sidebar.button("Log out"):
        st.session_state.clear()
        st.rerun()

    if not redis_store.get_agent(user):        # REQ-71: agent required before any scan page
        install_agent_page(user)
        return

    pages = ["New Scan", "Active Scans"]
    if role == models.ROLE_PRO:
        pages.append("Approval Queue")
    else:
        pages.append("Reports")
    choice = st.sidebar.radio("Navigate", pages)

    if choice == "New Scan":
        (new_scan_pro if role == models.ROLE_PRO else new_scan_standard)(user)
    elif choice == "Active Scans":
        active_scans_page(user, role)
    elif choice == "Approval Queue":
        approval_queue_page(user)
    elif choice == "Reports":
        reports_page(user)


main()
