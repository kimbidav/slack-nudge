# Slack Nudge

Daily scanner that identifies stale candidate submissions in Slack Connect channels and sends follow-up notifications via **Slack DM** and **email**.

Works for any user — teammates onboard via the web frontend.

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

## Architecture

```
Lovable Frontend  ──▶  Railway API (FastAPI)  ──▶  Slack API
                              │                       │
                              ▼                       ▼
                          Supabase              Gmail API
                       (users, history)      (email notifications)
```

- **Frontend**: Lovable-hosted React app for onboarding + dashboard
- **API**: FastAPI on Railway — runs nudge scans, manages schedules
- **Scheduler**: APScheduler runs each user's daily scan at their chosen time
- **Auth**: Single shared Slack user token scans on behalf of all users

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/users` | Register: validate email against Slack, save to DB |
| GET | `/api/users/:email` | Get user settings |
| PUT | `/api/users/:email/schedule` | Update daily schedule hour |
| PUT | `/api/users/:email/toggle` | Pause/resume daily nudges |
| POST | `/api/nudge/run` | Trigger a nudge check now |
| GET | `/api/nudge/history/:email` | Recent nudge run results |

## Deploy to Railway

1. Create a Supabase project and run `supabase_schema.sql`
2. Push this repo to GitHub
3. Connect to Railway and set environment variables:

```env
SLACK_BOT_TOKEN=xoxp-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
GMAIL_CREDENTIALS_PATH=./credentials.json
GMAIL_TOKEN_PATH=./gmail_token.json
```

Railway auto-detects the `Procfile` and deploys.

## CLI Usage (local)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# First run — prompts for your email, then scans
python -m slack_nudge --dm-only

# Pass email directly
python -m slack_nudge --email you@company.com --dm-only

# Dry run (preview only)
python -m slack_nudge --dm-only --dry-run
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | *(required)* | Slack User OAuth Token (`xoxp-...`) |
| `SUPABASE_URL` | *(required for API)* | Supabase project URL |
| `SUPABASE_KEY` | *(required for API)* | Supabase anon key |
| `USER_EMAIL` | *(prompted / via API)* | Your email for CLI mode |
| `LOOKBACK_DAYS` | `60` | How far back to scan Slack |
| `NUDGE_DAYS` | `3` | Days without emoji before flagging |
| `GMAIL_CREDENTIALS_PATH` | `./credentials.json` | Google OAuth credentials |
| `GMAIL_TOKEN_PATH` | `./gmail_token.json` | Cached Gmail token |
