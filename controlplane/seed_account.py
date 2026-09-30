"""Bootstrap an account (REQ-69: no self-registration; provisioned by config or a lead/admin).

Usage:
  python controlplane/seed_account.py <username> <password> <role>
    role is one of: client, pentester, lead_pentester, reporter, governance, soc
  python controlplane/seed_account.py --team-defaults [--dev]
    seeds the four team accounts (riyan/lead_pentester, dimas/pentester, aisah/reporter,
    hani/governance) with a RANDOM password each, printed once: copy them now.
    --dev uses the password "changeme" instead (local testing only).
  python controlplane/seed_account.py --rotate-defaults
    gives every team account still on "changeme" a fresh random password, printed once.

Needs Redis reachable (set REDIS_URL for host-run dev, e.g. redis://localhost:6379/0) and
VARUNA_DB pointing at the same SQLite file the running API services use.
"""
import os
import secrets
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "common"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()  # repo-root .env, for host-run dev (REDIS_URL, VARUNA_DB, ...)

import auth  # noqa: E402
from models import ROLES  # noqa: E402

TEAM_DEFAULTS = [
    ("riyan", "lead_pentester"), ("dimas", "pentester"),
    ("aisah", "reporter"), ("hani", "governance"),
]


def usage() -> None:
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    if sys.argv[1:] in (["--team-defaults"], ["--team-defaults", "--dev"]):
        dev = len(sys.argv) == 3
        for username, role in TEAM_DEFAULTS:
            pw = "changeme" if dev else secrets.token_urlsafe(12)
            auth.create_account(username, pw, role)
            print(f"created {role} account: {username} / {pw}")
        print("Dev passwords: never use outside local testing." if dev else "Shown once. Store them in a password manager.")
        sys.exit(0)

    if sys.argv[1:] == ["--rotate-defaults"]:
        weak = auth.default_password_accounts()
        for username in weak:
            pw = secrets.token_urlsafe(12)
            auth.admin_reset_password(username, pw)
            print(f"{username} / {pw}")
        print("Shown once. Store them in a password manager." if weak else "No team account uses the default password.")
        sys.exit(0)

    if len(sys.argv) != 4 or sys.argv[3] not in ROLES:
        usage()
    username, password, role = sys.argv[1], sys.argv[2], sys.argv[3]
    auth.create_account(username, password, role)
    print(f"created {role} account: {username}")
