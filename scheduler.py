"""APScheduler-based daily nudge job scheduler."""
from __future__ import annotations

import os
import sys

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

_scheduler: BackgroundScheduler | None = None


def _get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def start_scheduler():
    """Start the scheduler and load all active users' jobs."""
    from db import get_all_active_users

    sched = _get_scheduler()

    users = get_all_active_users()
    for user in users:
        _add_job(sched, user["email"], user["schedule_hour"])

    sched.start()
    print(f"[SCHEDULER] Started with {len(users)} active user(s)")


def add_user_job(email: str, schedule_hour: int):
    """Add or update a user's daily nudge job."""
    sched = _get_scheduler()
    job_id = f"nudge_{email}"

    # Remove existing job if any
    if sched.get_job(job_id):
        sched.remove_job(job_id)

    _add_job(sched, email, schedule_hour)
    print(f"[SCHEDULER] Scheduled nudge for {email} at {schedule_hour}:00 UTC")


def remove_user_job(email: str):
    """Remove a user's daily nudge job (pause)."""
    sched = _get_scheduler()
    job_id = f"nudge_{email}"
    if sched.get_job(job_id):
        sched.remove_job(job_id)
        print(f"[SCHEDULER] Removed job for {email}")


def _add_job(sched: BackgroundScheduler, email: str, hour: int):
    """Add a cron job for a user."""
    job_id = f"nudge_{email}"

    sched.add_job(
        _run_user_nudge,
        trigger=CronTrigger(hour=hour, minute=0),
        id=job_id,
        args=[email],
        replace_existing=True,
        misfire_grace_time=3600,  # allow 1hr grace if server was down
    )


def _run_user_nudge(email: str):
    """Scheduled job: run nudge check for a user."""
    from db import get_user

    user = get_user(email)
    if not user or not user.get("active", True):
        print(f"[SCHEDULER] Skipping inactive user {email}")
        return

    # Import here to avoid circular imports
    from api import _run_nudge_for_user

    try:
        _run_nudge_for_user(email, user["slack_user_id"])
    except Exception as e:
        print(f"[SCHEDULER] Nudge failed for {email}: {e}")
