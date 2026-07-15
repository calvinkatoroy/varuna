"""Offboarding data-destruction (NFR-28).

Wipes ALL findings, reports, scan data, and the audit log. Accounts and agent bindings are
NOT touched (remove those separately if the engagement is fully ending). Deliberately a CLI
with a required confirmation, not a UI button, so a destructive action can't be misclicked.

Usage:  python controlplane/wipe_data.py --confirm
Needs Redis reachable (set REDIS_URL for host-run dev).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "report"))
import store  # noqa: E402

if __name__ == "__main__":
    if "--confirm" not in sys.argv:
        print("This DESTROYS all findings, reports, scan data, and the audit log.")
        print("Accounts and agent bindings are kept. Re-run with --confirm to proceed.")
        sys.exit(1)
    print("wiped:", store.wipe_all())
