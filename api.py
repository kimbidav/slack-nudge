"""Slack Nudge API — FastAPI web service for the Lovable frontend."""
from __future__ import annotations

import os
import sys
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from slack_nudge.slack_client import SlackAPI
from slack_nudge.config import Config
from slack_nudge.nudge import run_nudge_check
from scheduler import start_scheduler, add_user_job, remove_user_job
from db import get_supabase, get_user, upsert_user, save_nudge_run, get_nudge_history

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
if not SLACK_TOKEN:
    raise RuntimeError("SLACK_BOT_TOKEN must be set")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the scheduler on startup."""
    start_scheduler()
    yield


app = FastAPI(title="Slack Nudge API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response models ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    schedule_hour: int = 15  # default 8am PT = 15 UTC

class UpdateScheduleRequest(BaseModel):
    schedule_hour: int

class RunNudgeRequest(BaseModel):
    email: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/api/users")
def register_user(req: RegisterRequest):
    """Register a new user: validate their email against Slack, save to DB."""
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Invalid email address")

    # Validate against Slack
    slack = SlackAPI(SLACK_TOKEN)
    try:
        slack_user_id = slack.get_user_id_by_email(email)
    except RuntimeError:
        raise HTTPException(404, f"No Slack user found for {email}")

    # Get display name from Slack
    try:
        info = slack.client.users_info(user=slack_user_id)
        profile = info["user"].get("profile", {})
        display_name = (
            profile.get("display_name")
            or profile.get("real_name")
            or email.split("@")[0]
        )
    except Exception:
        display_name = email.split("@")[0]

    # Save to Supabase
    user = upsert_user(
        email=email,
        slack_user_id=slack_user_id,
        display_name=display_name,
        schedule_hour=req.schedule_hour,
    )

    # Add to scheduler
    add_user_job(email, req.schedule_hour)

    return {
        "ok": True,
        "email": email,
        "slack_user_id": slack_user_id,
        "display_name": display_name,
        "schedule_hour": req.schedule_hour,
    }


@app.get("/api/users/{email}")
def get_user_info(email: str):
    """Get a registered user's settings."""
    user = get_user(email.strip().lower())
    if not user:
        raise HTTPException(404, "User not registered")
    return user


@app.put("/api/users/{email}/schedule")
def update_schedule(email: str, req: UpdateScheduleRequest):
    """Update a user's daily nudge schedule."""
    email = email.strip().lower()
    user = get_user(email)
    if not user:
        raise HTTPException(404, "User not registered")

    upsert_user(
        email=email,
        slack_user_id=user["slack_user_id"],
        display_name=user["display_name"],
        schedule_hour=req.schedule_hour,
    )
    add_user_job(email, req.schedule_hour)

    return {"ok": True, "schedule_hour": req.schedule_hour}


@app.put("/api/users/{email}/toggle")
def toggle_active(email: str):
    """Toggle a user's active status (pause/resume)."""
    email = email.strip().lower()
    user = get_user(email)
    if not user:
        raise HTTPException(404, "User not registered")

    new_active = not user.get("active", True)
    sb = get_supabase()
    sb.table("users").update({"active": new_active}).eq("email", email).execute()

    if new_active:
        add_user_job(email, user["schedule_hour"])
    else:
        remove_user_job(email)

    return {"ok": True, "active": new_active}


@app.post("/api/nudge/run")
def run_nudge_now(req: RunNudgeRequest):
    """Manually trigger a nudge check for a user. Runs in background."""
    email = req.email.strip().lower()
    user = get_user(email)
    if not user:
        raise HTTPException(404, "User not registered")

    def _run():
        try:
            _run_nudge_for_user(email, user["slack_user_id"])
        except Exception as e:
            print(f"[ERROR] Nudge run failed for {email}: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"ok": True, "message": f"Nudge check started for {email}"}


@app.get("/api/nudge/history/{email}")
def nudge_history(email: str, limit: int = 10):
    """Get recent nudge run history for a user."""
    email = email.strip().lower()
    history = get_nudge_history(email, limit=limit)
    return {"runs": history}


# ── Core nudge runner ────────────────────────────────────────────────────────

def _run_nudge_for_user(email: str, slack_user_id: str):
    """Run a nudge check for a specific user and save results."""
    cfg = Config(
        slack_bot_token=SLACK_TOKEN,
        user_email=email,
        user_slack_id=slack_user_id,
        nudge_dm_only=True,
        nudge_tracker_path=f".nudge_tracker_{email.replace('@', '_').replace('.', '_')}.json",
        gmail_credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", "./credentials.json"),
        gmail_token_path=os.getenv("GMAIL_TOKEN_PATH", "./gmail_token.json"),
    )

    print(f"[NUDGE] Running check for {email}...")
    results = run_nudge_check(cfg, dm_only=True)
    print(f"[NUDGE] Done for {email}: {results['nudges_sent']} nudges sent")

    # Save to DB
    save_nudge_run(
        user_email=email,
        submissions_checked=results["submissions_checked"],
        nudges_needed=results["nudges_needed"],
        nudges_sent=results["nudges_sent"],
        details=results,
    )

    return results
