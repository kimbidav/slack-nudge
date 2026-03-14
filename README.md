# Slack Nudge

Daily scanner that identifies stale candidate submissions in Slack and sends follow-up notifications via **Slack DM** and **email**.

## What it does

1. Scans all `candidatelabs-*` Slack channels for messages containing LinkedIn URLs (candidate submissions)
2. Reads emoji reactions to understand status:
   - ✅ = in process (explicit)
   - ⛔ = closed / rejected
   - No emoji = unclear, may need follow-up
3. Flags submissions that have been sitting for 3+ days without a ✅ or ⛔
4. Sends a **Slack DM** with clickable thread links
5. Sends an **HTML email** with hyperlinked Slack threads to the configured email address

## Setup

```bash
cd ~/Desktop/slack-nudge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

### Gmail setup (for email notifications)

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a project
2. Enable the **Gmail API**
3. OAuth consent screen → add scope: `gmail.send`
4. Credentials → Create OAuth 2.0 Client ID → **Desktop app** → Download JSON
5. Save as `credentials.json` in the project root
6. First run will open a browser for one-time authorization

## Usage

```bash
# Run nudge check (DM-only mode)
python -m slack_nudge --dm-only

# Dry run (preview only, nothing sent)
python -m slack_nudge --dm-only --dry-run

# Full mode (thread replies + DM + email)
python -m slack_nudge
```

## Daily schedule (macOS launchd)

A plist is provided to run the nudge check every weekday at 8:00 AM:

```bash
cp com.candidatelabs.nudge-check.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.candidatelabs.nudge-check.plist
```

Manage:
```bash
launchctl list | grep candidatelabs         # Check status
launchctl unload ~/Library/LaunchAgents/com.candidatelabs.nudge-check.plist  # Stop
launchctl load ~/Library/LaunchAgents/com.candidatelabs.nudge-check.plist    # Start
```

Logs: `./logs/nudge-check.log`

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | *(required)* | Slack User OAuth Token (`xoxp-...`) |
| `DK_EMAIL` | `dkimball@candidatelabs.com` | Email for Slack user lookup + email notifications |
| `LOOKBACK_DAYS` | `60` | How far back to scan Slack |
| `NUDGE_DAYS` | `3` | Days without emoji before flagging |
| `NUDGE_DM_ONLY` | `false` | If true, skip thread replies |
| `NUDGE_TRACKER_PATH` | `.nudge_tracker.json` | Nudge history file |
| `GMAIL_CREDENTIALS_PATH` | `./credentials.json` | Google OAuth credentials |
| `GMAIL_TOKEN_PATH` | `./gmail_token.json` | Cached Gmail token |
