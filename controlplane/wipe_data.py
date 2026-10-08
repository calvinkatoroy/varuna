"""Offboarding data-destruction (NFR-28).

Wipes ALL findings, reports, scan data, and the audit log. Accounts and agent bindings are
NOT touched by default. With --all the accounts, organizations, proposals and report records
are destroyed too (a full reset: re-run seed_account.py --bootstrap afterwards). Deliberately a
CLI with a required confirmation, not a UI button, so a destructive action can't be misclicked.

Usage:  python controlplane/wipe_data.py --confirm
        python controlplane/wipe_data.py --all --confirm
Needs Redis reachable (set REDIS_URL for host-run dev).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "report"))
import db  # noqa: E402
import store  # noqa: E402


def wipe(everything: bool = False) -> dict:
    counts = store.wipe_all()
    if everything:
        counts.update(db.wipe_tenancy())
    return counts


if __name__ == "__main__":
    everything = "--all" in sys.argv
    if "--confirm" not in sys.argv:
        print("This DESTROYS all findings, reports, scan data, and the audit log.")
        if everything:
            print("--all: it ALSO destroys every account, organization, proposal and report record.")
        else:
            print("Accounts and agent bindings are kept.")
        print("Re-run with --confirm to proceed.")
        sys.exit(1)
    print("wiped:", wipe(everything))
