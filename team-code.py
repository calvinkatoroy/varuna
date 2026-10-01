"""Print the current 6-digit authenticator code for a team account (demo helper).
Usage:  python team-code.py riyan        (secrets come from the gitignored .team-credentials.txt)
For real use, add each secret to an authenticator app instead (Enter a setup key, time based)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "controlplane" / "common"))
import totp  # noqa: E402

user = sys.argv[1] if len(sys.argv) > 1 else sys.exit(__doc__)
creds = dict(l.split(": ", 1) for l in (pathlib.Path(__file__).parent / ".team-credentials.txt").read_text().splitlines() if ": " in l)
print(totp.code_at(creds[f"{user}_totp_secret"]))
