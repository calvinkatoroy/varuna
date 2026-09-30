"""Bootstrap an account (REQ-69: no self-registration; provisioned by config or a lead/admin).

Usage:
  python controlplane/seed_account.py <username> <password> <role>
    role is one of: client, pentester, lead_pentester, reporter, governance, soc
  python controlplane/seed_account.py --team-defaults
    seeds the four demo team accounts the frontend's TeamLogin points at in dev
    (riyan/lead_pentester, dimas/pentester, aisah/reporter, hani/governance), each with
    password "changeme" - for local/dev use only, never run this against a real deployment.

Needs Redis reachable (set REDIS_URL for host-run dev, e.g. redis://localhost:6379/0) and
VARUNA_DB pointing at the same SQLite file the running API services use.
"""
import os
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
    if sys.argv[1:] == ["--team-defaults"]:
        for username, role in TEAM_DEFAULTS:
            auth.create_account(username, "changeme", role)
            print(f"created {role} account: {username} / changeme")
        print("Change these passwords before any non-local deployment.")
        sys.exit(0)

    if len(sys.argv) != 4 or sys.argv[3] not in ROLES:
        usage()
    username, password, role = sys.argv[1], sys.argv[2], sys.argv[3]
    auth.create_account(username, password, role)
    print(f"created {role} account: {username}")
