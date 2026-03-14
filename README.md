# Slack Nudge

Daily scanner that identifies stale candidate submissions in Slack Connect channels and sends follow-up notifications via **Slack DM** and **email**.

Works for any user — just enter your email on first run.

## What it does

1. Finds all **Slack Connect** (externally shared) channels you're a member of
2. Scans for messages containing LinkedIn URLs (candidate submissions)
3. Reads emoji reactions to understand status:
   - ✅ = in process (explicit)
   - ⛔ = closed / rejected
   - No emoji = unclear, may need follow-up
4. Flags submissions sitting for 3+ days without a ✅ or ⛔
5. Sends a **Slack DM** with clickable thread links
6. Sends an **HTML email** with hyperlinked Slack threads

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your `SLACK_BOT_TOKEN`. On first run, you'll be prompted for your email address.

### Gmail setup (for email notifications)

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a project
2. Enable the **Gmail API**
3. OAuth consent screen → add scope: `gmail.send`
4. Credentials → Create OAuth 2.0 Client ID → **Desktop app** → Download JSON
5. Save as `credentials.json` in the project root
6. First run will open a browser for one-time authorization

## Usage

```bash
# First run — prompts for your email, then scans
python -m slack_nudge --dm-only

# Pass email directly (skips onboarding)
python -m slack_nudge --email you@company.com --dm-only

# Dry run (preview only, nothing sent)
python -m slack_nudge --dm-only --dry-run

# Full mode (thread replies + DM + email)
python -m slack_nudge
```

## Daily schedule (macOS launchd)

```bash
cp com.candidatelabs.nudge-check.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.candidatelabs.nudge-check.plist
```

Runs weekdays at 8:00 AM. Logs to `./logs/nudge-check.log`.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | *(required)* | Slack User OAuth Token (`xoxp-...`) |
| `USER_EMAIL` | *(prompted)* | Your email — used to find your Slack user and send notifications |
| `LOOKBACK_DAYS` | `60` | How far back to scan Slack |
| `NUDGE_DAYS` | `3` | Days without emoji before flagging |
| `NUDGE_DM_ONLY` | `false` | If true, skip thread replies |
| `NUDGE_TRACKER_PATH` | `.nudge_tracker.json` | Nudge history file |
| `GMAIL_CREDENTIALS_PATH` | `./credentials.json` | Google OAuth credentials |
| `GMAIL_TOKEN_PATH` | `./gmail_token.json` | Cached Gmail token |
