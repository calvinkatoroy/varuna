"""Bootstrap an account (REQ-69: no self-registration; provisioned by config or a Pro user).

Usage:  python controlplane/seed_account.py <username> <password> <standard|pro>
Needs Redis reachable (set REDIS_URL for host-run dev, e.g. redis://localhost:6379/0).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "common"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()  # repo-root .env, for host-run dev (REDIS_URL, ...)

import auth  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[3] not in ("standard", "pro"):
        print("usage: python controlplane/seed_account.py <username> <password> <standard|pro>")
        sys.exit(1)
    username, password, role = sys.argv[1], sys.argv[2], sys.argv[3]
    auth.create_account(username, password, role)
    print(f"created {role} account: {username}")
