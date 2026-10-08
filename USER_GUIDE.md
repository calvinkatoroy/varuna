# Varuna user guide

Three audiences: clients who ask for a scan, the security team who run and review it, and whoever
installs and runs the system. Each section stands alone.

## 1. Clients

You get a written, reviewed security report for a system you own. You never see scan tools, other
clients, or unreviewed results.

### Get started
1. Your account is created for you by the system administrator, who gives you a username, a temporary password
   and your organization. Sign in at the address you were given. You must choose a new password the first time.
   There is no self-registration.
2. Add an email in **Profile** if you want to be able to reset a forgotten password (optional).
3. Choose **New task**. First choose **where the scan runs**:
   - **By Varuna (cloud):** nothing to install. Varuna scans your website from its own computer. Only for websites
     that are open on the internet. This is the easiest choice.
   - **On my computer:** you install one small program that runs the scan inside your network. Choose this for
     internal or private systems (for example an address like `10.x.x.x`, `localhost` or `intranet.company`).
   Then enter the **target**, an optional **path** and **port**, **notes** for the pentester (test account,
   pages to skip) and the **time limit**: the scan only runs between these two times (shown in your timezone).
   You must own the target or be authorized to test it.
4. A pentester accepts the task and starts or schedules the scan. If they cannot take it you see the reason
   and can send a new task.

### Install your agent (only for "On my computer")
If you chose a cloud scan, skip this: your dashboard unlocks once a pentester accepts your task.

1. After a pentester accepts your task, choose **Download installer (Windows)**. No command line is needed.
2. Double-click the downloaded file **Install-Varuna**. If Windows says "Windows protected your PC", click
   **More info**, then **Run anyway**.
3. Wait a few minutes for "Done". Your screen unlocks by itself when the agent is detected.
4. The installer only works for one hour. If it stops working, download it again.

Prefer PowerShell? Open "I'd rather use PowerShell" on the same screen for the one-line command.

### Follow your scan and read the result
- **Overview** shows agent status, the latest scan and your latest report.
- **Tasks** lists every request, its status (waiting, accepted, scheduled, scanning, paused, in review, delivered, declined, expired) and a timeline. A declined task shows the reason. A scan that stops (for example the agent went offline) shows as paused until the pentester resumes it. A task that was not started before your time limit ended shows as expired: send a new task.
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
in the message (it works for 30 minutes and once). No email on file, or no message arrives: ask the system administrator.

## 2. Security team

Sign in on the private address (`/team`), which needs the team network (Tailscale).

### First sign in
- Use the password you were given and change it: avatar menu, **Change password**.
- Two-factor is mandatory. The first time you sign in you must set it up: choose **Set up**, add the key
  to an authenticator app (Google or Microsoft Authenticator, Authy, 1Password), enter the 6-digit code.
  From then on every sign in asks for a code. Lost phone: the system administrator resets it.

### Who does what
| Role | Does |
|---|---|
| Pentester | Claims tasks, starts or schedules scans, suspends and resumes, submits the finished scan for review, runs advanced scans |
| Lead pentester | Everything a pentester does on any task, then the first review (approve or send back); only role that may enable aggressive scan options |
| Lead cybersecurity | Second review |
| Governance | Third review, re-issues report passwords |
| Manager | Final review; approving delivers the protected PDF to the client |

### The board
Pentesters see every column: Tasks, Scans (pending, scheduled, in progress, suspended), Completed, the four
reviews, Delivered, Declined / Expired. Every other reviewer sees only their own review list and Delivered.
Open a card to act. Buttons you cannot use say why. Moves that cannot be undone take a second tap.

1. **Tasks.** **Claim** makes you the assignee. **Decline** needs a reason; the client sees it.
2. **Scans.** The assignee or a lead pentester can **Start now** (inside the client's time limit, with the
   agent or cloud scanner online) or **Schedule** a start time and maximum duration (default 240 minutes),
   both with optional scan options. **Suspend** needs a reason; **Resume** continues it. A scheduled scan whose
   agent is offline for 15 minutes is suspended automatically; nothing retries silently after that. A scan
   that fails is suspended with the error. A suspended task whose time limit ended can only be closed (expired).
3. **Completed.** Edit the report (download, change, **Upload new**, or regenerate in another template; every
   version is kept), then **Submit for review**.
4. **Reviews.** Each reviewer **Approves** (next review) or **Sends back** (previous step, comment required;
   the first review sends back to Completed). Only that stage's role edits the report there.
   The manager's approval converts the latest version to a password-protected PDF and delivers it.

If the client lost the password, governance uses **Re-issue password**. It is shown once to governance,
who passes it to the client by a different channel than the file.

### Findings
**Findings** lists raw findings for review. Mark each as true or false positive and open or fixed before the
report is finalised.

### Advanced scan
**New scan** is the pentester form: tools, depth, rate, authentication. Destructive options (SQLMap
dump, OS shell, high risk or level) are lead pentester only and need an explicit opt-in tick. Clients can never set
them.

## 3. Administrators

- Install and configure: `README.md` (quick start) and `DEPLOY.md` (full).
- First install: `seed_account.py --bootstrap` creates the one system administrator `admin` with a random password
  (printed once and written to `.admin-credentials.txt`). Dev/demo staff: `seed_account.py --team-defaults`
  (random passwords, store what it prints).
- The system administrator signs in on the team address and uses the **System administrator** console to create
  organizations (disable or enable them), create client users (each belongs to one organization) and staff, set
  an email, change a role, disable or enable an account, reset a password (a new temporary password is shown once
  and must be changed at the next sign in) and reset two-factor. At least one active administrator must remain.
  The administrator does not scan or review.
- Required before real use: a long random `JWT_SECRET`, `VARUNA_REQUIRE_MFA=1`, a public domain through
  the Cloudflare tunnel, SMTP settings if you want email resets, the daily backup task
  (`backup-host.ps1 -Register`).
- Team plane stays on Tailscale only. Do not publish port 8010.
- Logs: `docker compose logs api-private` (startup prints warnings about weak secrets, missing two-factor,
  default passwords).
- Restore: `docker compose stop`, then
  `docker compose cp backups/<date>/db/<file>.db api-public:/dbdata/varuna.db` and
  `docker compose cp backups/<date>/reports/. api-public:/data/reports`, then `docker compose start`.
