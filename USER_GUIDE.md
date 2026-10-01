# Varuna user guide

Three audiences: clients who ask for a scan, the security team who run and review it, and whoever
installs and runs the system. Each section stands alone.

## 1. Clients

You get a written, reviewed security report for a system you own. You never see scan tools, other
clients, or unreviewed results.

### Get started
1. Open the Varuna address you were given and choose **Register**. Pick a username and a password of at
   least 8 characters. Add an email if you want to be able to reset a forgotten password (optional).
2. Registering only creates your account. Nothing runs yet.
3. Fill in the **scan proposal**. First choose **where the scan runs**:
   - **By Varuna (cloud):** nothing to install. Varuna scans your website from its own computer. Only for websites
     that are open on the internet. This is the easiest choice.
   - **On my computer:** you install one small program that runs the scan inside your network. Choose this for
     internal or private systems (for example an address like `10.x.x.x`, `localhost` or `intranet.company`).
   Then enter what to test, why, and which division you are from. Tick the authorization box: you must own the
     target or be authorized to test it. The lead pentester checks this before approving.
4. Wait for approval. The screen shows "Waiting for approval". If the proposal is rejected you will see
   the reason and can submit a corrected one.

### Install your agent (only for "On my computer")
If you chose a cloud scan, skip this: your dashboard unlocks as soon as the proposal is approved.

1. After approval, choose **Download installer (Windows)**. No command line is needed.
2. Double-click the downloaded file **Install-Varuna**. If Windows says "Windows protected your PC", click
   **More info**, then **Run anyway**.
3. Wait a few minutes for "Done". Your screen unlocks by itself when the agent is detected.
4. The installer only works for one hour. If it stops working, download it again.

Prefer PowerShell? Open "I'd rather use PowerShell" on the same screen for the one-line command.

### Follow your scan and read the result
- **Overview** shows agent status, the latest scan and your latest report.
- **Proposals** lists every request and its status.
- **Findings** lists the issues found in your scans.
- **Reports** holds your delivered reports. A report only appears after the security team has reviewed and
  delivered it.

### Open a delivered report
1. In **Reports** choose **Download protected PDF**.
2. Choose **Show password**. The password is shown **once**: copy it straight away and keep it
   separate from the file.
3. Lost it? Ask governance to re-issue a new password.

### Forgot your password
On the log in screen choose **Forgot your password?**, enter your registration email and follow the link
in the message (it works for 30 minutes and once). No email on file, or no message arrives: ask your lead
pentester.

## 2. Security team

Sign in on the private address (`/team`), which needs the team network (Tailscale).

### First sign in
- Use the password you were given and change it: avatar menu, **Change password**.
- Two-factor is mandatory. The first time you sign in you must set it up: choose **Set up**, add the key
  to an authenticator app (Google or Microsoft Authenticator, Authy, 1Password), enter the 6-digit code.
  From then on every sign in asks for a code. Lost phone: the lead pentester resets it.

### Who does what
| Role | Does |
|---|---|
| Lead pentester | Approves or rejects proposals, verifies authorization, reviews reports, manages team accounts |
| Pentester | Runs advanced scans, sees all clients |
| Reporter | First review of a report, edits and uploads versions |
| Governance | Final review, delivers the report to the client, re-issues passwords |
| SOC | General team access |

### The pipeline (Board)
Columns: Pending approval, Scanning, Reporter, Lead, Governance, Delivered, Rejected.

1. **Pending approval.** The lead opens the card (**Review and decide**), checks the target and the
   authorization statement, then **Approve** or **Reject**. Both ask for a second tap to confirm. Rejecting
   needs a reason; the client sees it.
2. **Scanning.** Live progress shows on the card. A scan with no sign of the agent for 15 minutes is marked
   failed. Finished scans create the report automatically at the Reporter stage.
3. **Reporter, Lead, Governance.** Each reviewer opens the report (**Open review**):
   - Download the Word file, edit it, then **Upload new** to save a new version. Every version is kept.
   - Change the template if needed: Full Technical, Formal Handover, Executive Summary, Raw Findings.
   - **Send back** returns it to the previous stage with a note. **Forward** passes it on.
4. **Governance** uses **Deliver to client**. The system converts the approved version to a password
   protected PDF. The client can see it from that moment.

If the client lost the password, governance uses **Re-issue password**. It is shown once to governance,
who passes it to the client by a different channel than the file.

### Findings
**Findings** lists raw findings for review. Mark each as true or false positive and open or fixed before the
report is finalised.

### Advanced scan
**New scan** is the pentester form: tools, depth, rate, authentication. Destructive options (SQLMap
dump, OS shell, high risk or level) are lead-only and need an explicit opt-in tick. Clients can never set
them.

### Accounts (lead pentester)
Avatar menu, **Team accounts**: create, disable, reset a password, reset two-factor.

## 3. Administrators

- Install and configure: `README.md` (quick start) and `DEPLOY.md` (full).
- Seed team accounts with random passwords: `seed_account.py --team-defaults`. Store what it prints.
- Required before real use: a long random `JWT_SECRET`, `VARUNA_REQUIRE_MFA=1`, a public domain through
  the Cloudflare tunnel, SMTP settings if you want email resets, the daily backup task
  (`backup-host.ps1 -Register`).
- Team plane stays on Tailscale only. Do not publish port 8010.
- Logs: `docker compose logs api-private` (startup prints warnings about weak secrets, missing two-factor,
  default passwords).
- Restore: `docker compose stop`, then
  `docker compose cp backups/<date>/db/<file>.db api-public:/dbdata/varuna.db` and
  `docker compose cp backups/<date>/reports/. api-public:/data/reports`, then `docker compose start`.
