"""Print a one-time enrollment token (or, with --online, whether the scanner is checking in) for the cloud scanner (the agent that runs cloud-mode scans on this host).

Run inside a control-plane container:  python /app/controlplane/mint_cloud_token.py
start-varuna.ps1 does this once, then enrols the host's agent with it. Enrolling again later simply replaces
the scanner's token."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "common"))
import models  # noqa: E402
import tokens  # noqa: E402

if "--online" in sys.argv:       # is the scanner currently checking in?
    print(tokens.is_online(models.CLOUD_AGENT))
else:
    print(tokens.generate_enrollment_token(models.CLOUD_AGENT))
