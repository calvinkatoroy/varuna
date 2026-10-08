"""Provision accounts (no self-registration; accounts come from this script or the sysadmin).

Usage:
  python controlplane/seed_account.py --bootstrap
    creates the one sysadmin "admin" with a RANDOM password, printed once and written to
    .admin-credentials.txt (repo root, gitignored). Refuses if a sysadmin already exists.
  python controlplane/seed_account.py --team-defaults [--dev]
    seeds the staff accounts rizky/pentester, dewi/lead_pentester, agus/lead_cyber,
    sari/governance, hendra/manager with a RANDOM password each, printed once: copy them now.
    --dev uses the password "changeme" instead (local testing only).
  python controlplane/seed_account.py --rotate-defaults
    gives every staff account still on "changeme" a fresh random password, printed once.
  python controlplane/seed_account.py <username> <password> <role> [--org <organization name>]
    role is one of: sysadmin, pentester, lead_pentester, lead_cyber, governance, manager, client.
    A client needs --org (created if missing); staff must not have one.

Needs VARUNA_DB pointing at the same SQLite file the running API services use.
"""
import os
import secrets
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "common"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()  # repo-root .env, for host-run dev (VARUNA_DB, ...)

import auth  # noqa: E402
import db  # noqa: E402
from models import ROLES  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADMIN_CREDS = os.path.join(REPO_ROOT, ".admin-credentials.txt")

TEAM_DEFAULTS = [
    ("rizky", "pentester"), ("dewi", "lead_pentester"), ("agus", "lead_cyber"),
    ("sari", "governance"), ("hendra", "manager"),
]


def usage() -> None:
    print(__doc__)
    sys.exit(1)


def bootstrap(creds_path: str = ADMIN_CREDS) -> str:
    """Create the sysadmin "admin" with a random password; returns it. Refuses if one exists."""
    if any(a["role"] == "sysadmin" for a in db.list_accounts()):
        raise RuntimeError("a sysadmin already exists; --bootstrap only runs on a fresh install")
    pw = secrets.token_urlsafe(12)
    auth.create_account("admin", pw, "sysadmin")
    with open(creds_path, "w", encoding="utf-8") as f:
        f.write(f"admin {pw}\n")
    return pw


def team_defaults(dev: bool = False) -> list[tuple[str, str, str]]:
    """Create the five staff accounts -> [(username, role, password)]."""
    out = []
    for username, role in TEAM_DEFAULTS:
        pw = "changeme" if dev else secrets.token_urlsafe(12)
        auth.create_account(username, pw, role)
        out.append((username, role, pw))
    return out


def get_or_create_org(name: str) -> str:
    return next((o["id"] for o in db.list_orgs() if o["name"] == name.strip()), None) or db.create_org(name)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--bootstrap"]:
        try:
            pw = bootstrap()
        except RuntimeError as e:
            print(f"refused: {e}")
            sys.exit(1)
        print(f"created sysadmin account: admin / {pw}")
        print(f"Shown once; also written to {ADMIN_CREDS} (gitignored). Store it in a password manager.")
        sys.exit(0)

    if args in (["--team-defaults"], ["--team-defaults", "--dev"]):
        dev = len(args) == 2
        for username, role, pw in team_defaults(dev):
            print(f"created {role} account: {username} / {pw}")
        print("Dev passwords: never use outside local testing." if dev else "Shown once. Store them in a password manager.")
        sys.exit(0)

    if args == ["--rotate-defaults"]:
        weak = auth.default_password_accounts()
        for username in weak:
            pw = secrets.token_urlsafe(12)
            auth.admin_reset_password(username, pw)
            print(f"{username} / {pw}")
        print("Shown once. Store them in a password manager." if weak else "No staff account uses the default password.")
        sys.exit(0)

    org = None
    if len(args) == 5 and args[3] == "--org":
        org, args = args[4], args[:3]
    if len(args) != 3 or args[2] not in ROLES:
        usage()
    username, password, role = args
    try:
        auth.create_account(username, password, role, org_id=get_or_create_org(org) if org else None)
    except ValueError as e:
        print(f"refused: {e}")
        sys.exit(1)
    print(f"created {role} account: {username}" + (f" in {org}" if org else ""))
