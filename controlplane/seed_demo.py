"""Demo-data seeder (local/dev only): three Indonesian client organizations with users, scan
proposals in different states, findings and review-pipeline reports. Everything goes through the
real db/auth/private_api functions (not HTTP), so org_id is set exactly as in production.
Findings are injected with db.save_findings() instead of running Nuclei/SQLMap; delivery uses the
real LibreOffice PDF conversion. Needs no sysadmin and no staff accounts.

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
from tenancy import Scope  # noqa: E402

DEMO_CREDS = os.path.join(os.path.dirname(__file__), "..", ".demo-credentials.txt")

ORGS = {
    "PT Samudera Logistik Nusantara": ["budi.santoso", "siti.rahayu"],
    "PT Pelabuhan Bahari Sejahtera": ["agung.wijaya"],
    "CV Mitra Kargo Jaya": ["dewi.lestari"],
}

# Staff identities used only to push demo reports through the review stages.
PENTESTER = {"username": "rizky", "role": "pentester"}
LEAD = {"username": "dewi", "role": "lead_pentester"}
GOVERNANCE = {"username": "sari", "role": "governance"}
ALL = Scope(None)

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


def propose(org_id: str, client: str, host: str, purpose: str, division: str, **extra) -> str:
    return db.create_proposal({
        "org_id": org_id, "submitter": client, "target": f"https://{host}", "mode": "standard",
        "purpose": purpose, "division": division, "environment": "production",
        "authorization_attested": True, "scan_mode": "cloud", **extra,
    })


def scanned(org_id: str, client: str, host: str, purpose: str, division: str) -> dict:
    """An approved proposal whose scan finished: job + findings stored, ready for review."""
    pid = propose(org_id, client, host, purpose, division)
    job = make_job(f"https://{host}", client, org_id)
    redis_store.set_job(job)
    db.update_proposal(pid, status="approved", job_id=job["id"])
    db.save_findings(job["id"], client, org_id, FINDINGS.get(host, []))
    return job


def review(job: dict, stages: list[dict]) -> str:
    """Generate v1 of the report, then forward it once per actor in `stages`."""
    rid = private_api.pipeline_create(
        private_api.PipelineCreateBody(job_id=job["id"], template="Full Technical"), user=PENTESTER, scope=ALL)["report_id"]
    for actor in stages:
        private_api.pipeline_forward(rid, user=actor, scope=ALL)
    return rid


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

    # Samudera / budi: fully delivered engagement (real PDF conversion + encryption).
    job = scanned(sam, "budi.santoso", "portal.samudera-logistik.co.id", "kepatuhan", "TI")
    rid = review(job, [PENTESTER, LEAD, GOVERNANCE])
    print(f"budi.santoso: laporan {rid} DELIVERED, password PDF: {db.get_report(rid, org_id=None)['pdf_password']}")

    # Samudera / siti: proposal masuk, belum ada tindakan.
    propose(sam, "siti.rahayu", "api.samudera-logistik.co.id", "pengujian sebelum rilis", "Pengembangan Aplikasi",
            in_scope="api.samudera-logistik.co.id", emergency_contact="Siti Rahayu, 0812-5550-0101")
    print("siti.rahayu: proposal pending")

    # Bahari / agung: scan selesai, laporan menunggu tinjauan governance.
    job = scanned(bah, "agung.wijaya", "tracking.baharisejahtera.co.id", "pengujian berkala", "Operasional Pelabuhan")
    rid = review(job, [PENTESTER, LEAD])
    print(f"agung.wijaya: laporan {rid} di tahap governance")

    # Mitra / dewi.lestari: ditolak dengan alasan yang jelas.
    pid = propose(mit, "dewi.lestari", "app.mitrakargo.co.id", "pengujian berkala", "Keuangan")
    db.update_proposal(pid, status="rejected", reject_reason=(
        "Kami belum dapat memverifikasi bahwa CV Mitra Kargo Jaya memiliki situs ini. "
        "Mohon balas dengan bukti kepemilikan (misalnya berkas yang dapat kami akses dari situs tersebut)."))
    print("dewi.lestari: proposal ditolak dengan alasan")

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
