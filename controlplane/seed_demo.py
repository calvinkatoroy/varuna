"""Demo-data seeder (local/dev only): three Indonesian client organizations with users, scan
tasks in different stages, findings and reports. Everything goes through the
real db/auth/private_api functions (not HTTP), so org_id is set exactly as in production.
Findings are injected with db.save_findings() instead of running Nuclei/SQLMap; delivery uses the
real LibreOffice PDF conversion. Needs no sysadmin; creates the five demo staff (seed_account.team_defaults) if `rizky` does not exist.

Random client passwords are printed once and written to .demo-credentials.txt (gitignored).
Refuses to run if any organization already exists.

Usage (inside the api-public container, so imports/env match):
  docker compose exec api-public python /app/controlplane/seed_demo.py
"""
from __future__ import annotations

import os
import secrets
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
import models  # noqa: E402
import redis_store  # noqa: E402
import private_api  # noqa: E402

DEMO_CREDS = os.path.join(os.path.dirname(__file__), "..", ".demo-credentials.txt")

ORGS = {
    "PT Samudera Logistik Nusantara": ["budi.santoso", "siti.rahayu"],
    "PT Pelabuhan Bahari Sejahtera": ["agung.wijaya"],
    "CV Mitra Kargo Jaya": ["dewi.lestari"],
}

FINDINGS = {
    "portal.samudera-logistik.co.id": [
        {"name": "SQL Injection", "severity": "critical", "host": "portal.samudera-logistik.co.id",
         "url": "/api/v1/pengiriman/cari", "tool": "sqlmap", "cve": "CWE-89",
         "evidence": "q=1' AND SLEEP(5)-- -  ->  respons 10,1 detik",
         "impact": "Penyerang dapat membaca dan mengubah seluruh basis data pengiriman, termasuk data pelanggan lain.",
         "remediation": "Gunakan prepared statement dan validasi semua masukan pengguna."},
        {"name": "Reflected XSS", "severity": "high", "host": "portal.samudera-logistik.co.id",
         "url": "/lacak?no_resi=", "tool": "nuclei", "cve": "CWE-79",
         "evidence": "<script>alert(1)</script> dipantulkan tanpa di-escape pada halaman hasil",
         "impact": "Penyerang dapat menjalankan JavaScript di browser korban untuk membajak sesi.",
         "remediation": "Encode keluaran sesuai konteks dan terapkan Content-Security-Policy yang ketat."},
        {"name": "Header HSTS tidak ada", "severity": "medium", "host": "portal.samudera-logistik.co.id",
         "url": "", "tool": "nuclei", "cve": "CWE-319",
         "evidence": "Header Strict-Transport-Security tidak ditemukan pada respons HTTPS",
         "impact": "Pengguna dapat diturunkan ke HTTP biasa oleh penyerang di jaringan yang sama.",
         "remediation": "Tambahkan Strict-Transport-Security: max-age=31536000; includeSubDomains."},
    ],
    "tracking.baharisejahtera.co.id": [
        {"name": "Broken access control", "severity": "high", "host": "tracking.baharisejahtera.co.id",
         "url": "/api/v1/kapal/manifest", "tool": "nuclei", "cve": "CWE-284",
         "evidence": "Token pengguna biasa dapat membuka manifest kapal milik pengguna lain",
         "impact": "Setiap pengguna terautentikasi dapat melihat manifest kargo seluruh pelanggan.",
         "remediation": "Terapkan otorisasi di sisi server pada setiap objek; tolak secara default."},
        {"name": "Cookie tanpa flag Secure", "severity": "low", "host": "tracking.baharisejahtera.co.id",
         "url": "", "tool": "nuclei", "cve": "CWE-614",
         "evidence": "Cookie sesi dikirim tanpa atribut Secure melalui HTTPS",
         "impact": "Cookie sesi dapat terkirim lewat koneksi HTTP biasa yang tidak disengaja.",
         "remediation": "Setel Secure dan HttpOnly pada semua cookie sesi."},
    ],
}


def make_job(target: str, submitter: str, org_id: str) -> dict:
    return {
        "id": str(uuid.uuid4()), "target": target, "target_class": "cloud", "org_id": org_id,
        "submitter": submitter, "role": "client", "tools": ["katana", "nuclei", "sqlmap"],
        "opts": {}, "status": models.STATUS_DONE,
        "per_tool_status": {"katana": "done", "nuclei": "done", "sqlmap": "done"},
    }


import datetime  # noqa: E402
import ingest  # noqa: E402
import seed_account  # noqa: E402
import workflow  # noqa: E402

def _window() -> tuple[str, str]:
    now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
    return (now - datetime.timedelta(hours=1)).isoformat(), (now + datetime.timedelta(days=7)).isoformat()


def task(org_id: str, client: str, host: str, notes: str, **extra) -> str:
    nb, na = _window()
    return db.create_proposal({"org_id": org_id, "submitter": client, "target": f"https://{host}", "notes": notes,
                               "scan_mode": "cloud", "not_before": nb, "not_after": na, **extra})


def scanned(org_id: str, client: str, host: str, notes: str) -> str:
    """A task whose scan finished (findings injected, report v1 generated), assigned to rizky."""
    job = make_job(f"https://{host}", client, org_id)
    redis_store.set_job(job)
    tid = task(org_id, client, host, notes, stage="completed", assignee="rizky", job_id=job["id"])
    db.save_findings(job["id"], client, org_id, FINDINGS.get(host, []))
    ingest.start_review(job, editor="rizky")
    return tid


def review(tid: str, steps: list[tuple[str, str]]) -> None:
    for actor, to in steps:
        workflow.transition(tid, to, actor, org_id=None, on_deliver=private_api._deliver_task)


def seed(creds_path: str = DEMO_CREDS) -> dict:
    """Seed the demo orgs; returns {org name: org_id}. Raises RuntimeError if orgs already exist."""
    if db.list_orgs():
        raise RuntimeError("organizations already exist; wipe first (wipe_data.py --all) to reseed")
    org_ids, creds = {}, []
    for org, users in ORGS.items():
        org_ids[org] = db.create_org(org)
        for u in users:
            pw = secrets.token_urlsafe(9)
            auth.create_account(u, pw, models.ROLE_CLIENT, org_id=org_ids[org])
            creds.append(f"{u} {pw}")
    sam, bah, mit = (org_ids[o] for o in ORGS)

    if not db.get_account("rizky"):   # the demo walks tasks through the real workflow: it needs the five staff
        for username, role, pw in seed_account.team_defaults():
            print(f"created {role} account: {username} / {pw}")

    # Samudera / budi: fully delivered engagement (real PDF conversion + encryption).
    tid = scanned(sam, "budi.santoso", "portal.samudera-logistik.co.id", "Pengujian kepatuhan portal pelanggan")
    review(tid, [("rizky", "review_lead_pentester"), ("dewi", "review_lead_cyber"), ("agus", "review_governance"),
                 ("sari", "review_manager"), ("hendra", "delivered")])
    rid = db.get_report_by_job(db.get_proposal(tid, org_id=None)["job_id"])["id"]
    print(f"budi.santoso: laporan {rid} DELIVERED, password PDF: {db.get_report(rid, org_id=None)['pdf_password']}")

    # Samudera / siti: tugas masuk, belum diambil pentester.
    task(sam, "siti.rahayu", "api.samudera-logistik.co.id", "Pengujian sebelum rilis. Kontak: Siti Rahayu, 0812-5550-0101",
         path="/v2", port=443)
    print("siti.rahayu: tugas menunggu pentester")

    # Bahari / agung: scan selesai, laporan menunggu tinjauan governance.
    tid = scanned(bah, "agung.wijaya", "tracking.baharisejahtera.co.id", "Pengujian berkala")
    review(tid, [("rizky", "review_lead_pentester"), ("dewi", "review_lead_cyber"), ("agus", "review_governance")])
    print("agung.wijaya: laporan di tahap governance")

    # Mitra / dewi.lestari: ditolak dengan alasan yang jelas.
    tid = task(mit, "dewi.lestari", "app.mitrakargo.co.id", "Pengujian berkala")
    workflow.transition(tid, "declined", "rizky", org_id=None, comment=(
        "Kami belum dapat memverifikasi bahwa CV Mitra Kargo Jaya memiliki situs ini. "
        "Mohon balas dengan bukti kepemilikan (misalnya berkas yang dapat kami akses dari situs tersebut)."))
    print("dewi.lestari: tugas ditolak dengan alasan")

    with open(creds_path, "w", encoding="utf-8") as f:
        f.write("\n".join(creds) + "\n")
    print("\nKredensial klien (ditampilkan sekali; juga di " + os.path.abspath(creds_path) + "):")
    print("\n".join(creds))
    return org_ids


if __name__ == "__main__":
    try:
        seed()
    except RuntimeError as e:
        print(f"refused: {e}")
        sys.exit(1)
