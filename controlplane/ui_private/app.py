"""Varuna private-plane dashboard (SRS §4.7, §4.6a, §3.1).

Bound to the Tailscale interface only in production (NFR-24), no public listener. Pro-only:
full Findings Review (evidence, CVE, payloads), Manual Findings Input (§4.6a), and the full
report archive across all users and all four templates (REQ-50a). A Standard account that
somehow reaches this app is refused at login.
"""
import os
import sys

for _d in ("common", "pipeline", "report", "api"):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", _d))

import streamlit as st

import auth
import generator
import ingest
import models
import redis_store
import store as report_store

st.set_page_config(page_title="Varuna — Private", layout="wide")

SEV_BADGE = {
    "critical": "🔴 Critical", "high": "🟠 High", "medium": "🟡 Medium",
    "low": "🟢 Low", "info": "🔵 Info",
}


def _client_ip():
    try:
        return st.context.headers.get("X-Forwarded-For", "ui")
    except Exception:
        return "ui"


def login_page():
    st.title("Varuna — Private Dashboard")
    st.caption("Pro access only. Reachable via Tailscale in production (NFR-24).")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Log in"):
            try:
                acct = auth.authenticate(u, p, _client_ip())
                if acct.role != models.ROLE_PRO:
                    st.error("This dashboard is for Pro users only.")
                    return
                st.session_state.user = acct.username
                st.session_state.role = acct.role
                st.rerun()
            except auth.LockedOut:
                st.error("Too many failed attempts. Please try again later.")
            except auth.BadCredentials:
                st.error("Invalid username or password.")


def findings_review_page():
    st.header("Findings Review")
    job_id = st.text_input("Job ID")
    if not job_id:
        return
    findings = redis_store.get_findings(job_id)
    if not findings:
        st.info("No findings for this job yet (scan may still be running, or none were found).")
        return
    for f in sorted(findings, key=lambda x: models.severity_rank(x.get("severity", ""))):
        sev = (f.get("severity") or "info").lower()
        with st.expander(f"{SEV_BADGE.get(sev, sev)} — {f.get('name', 'Finding')}",
                         expanded=sev in ("critical", "high")):   # REQ-39
            st.write(f"**Host:** {f.get('host', '')}   **URL:** {f.get('url', '')}")
            if f.get("owasp"):
                st.write(f"**OWASP:** {f['owasp']}")
            if f.get("cve") or f.get("cwe"):
                st.write(f"**CVE:** {f.get('cve', '-')}   **CVSS:** {f.get('cvss', '-')}   "
                         f"**CWE:** {f.get('cwe', '-')}")
            if f.get("impact"):
                st.write(f"**Impact:** {f['impact']}")
            if f.get("remediation"):
                st.write(f"**Remediation:** {f['remediation']}")
            if f.get("evidence"):
                st.code(f["evidence"])   # monospace (REQ-42)
            st.caption(f"tool: {f.get('tool', '')}")


def manual_input_page():
    st.header("Manual Findings Input")
    st.caption("Add findings from manual testing (business logic, access control, auth) into a job.")
    job_id = st.text_input("Job ID")
    name = st.text_input("Finding name")
    severity = st.selectbox("Severity", ["critical", "high", "medium", "low", "info"])
    host = st.text_input("Host")
    url = st.text_input("URL (optional)")
    description = st.text_area("Description")
    evidence = st.text_area("Evidence / reproduction steps (optional)")
    if st.button("Add finding"):
        if not (job_id and name and host):
            st.error("Job ID, finding name, and host are required.")
            return
        try:
            ingest.add_manual_finding(job_id, {
                "name": name, "severity": severity, "host": host, "url": url,
                "description": description, "evidence": evidence,
            })
            st.success("Finding added, correlated, and enriched into the job.")
        except ValueError as e:
            st.error(str(e))


def reports_page(user):
    st.header("Reports")
    st.subheader("Generate")
    job_id = st.text_input("Job ID", key="gen_job")
    template = st.selectbox("Template", generator.TEMPLATES)   # all four offered (REQ-12)
    if st.button("Generate"):
        job = redis_store.get_job(job_id)
        if not job:
            st.error("No such job.")
        else:
            try:
                data = generator.generate(job, redis_store.get_findings(job_id), template)
                report_store.save_report(user, job_id, template, data)
                st.download_button("Download .docx", data,
                                   file_name=f"{job_id}_{template.replace(' ', '_')}.docx")
            except ValueError as e:
                st.info(f"{e}")   # OWASP-grouped / ILCS Internal land in Phase G

    st.subheader("Archive (all users, all templates)")
    reports = report_store.list_all_reports()
    if not reports:
        st.caption("No reports generated yet.")
    for r in reports:
        c1, c2 = st.columns([3, 1])
        c1.write(f"{r['file']}  ·  {r['template']}  ·  {r['user']}  ·  {r['ts']}")
        c2.download_button("Download", report_store.read_report(r["file"]),
                           file_name=r["file"], key="dl_" + r["file"])


def main():
    if "user" not in st.session_state:
        login_page()
        return
    user = st.session_state.user
    st.sidebar.write(f"**{user}** · pro (private)")
    if st.sidebar.button("Log out"):
        st.session_state.clear()
        st.rerun()
    choice = st.sidebar.radio("Navigate", ["Findings Review", "Manual Findings Input", "Reports"])
    if choice == "Findings Review":
        findings_review_page()
    elif choice == "Manual Findings Input":
        manual_input_page()
    else:
        reports_page(user)


main()
