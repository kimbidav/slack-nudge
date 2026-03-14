"""Supabase database helpers for user management and nudge history."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from supabase import create_client, Client


_client: Optional[Client] = None


def get_supabase() -> Client:
    """Get or create the Supabase client."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
        _client = create_client(url, key)
    return _client


def upsert_user(
    email: str,
    slack_user_id: str,
    display_name: str,
    schedule_hour: int,
) -> Dict[str, Any]:
    """Insert or update a user record."""
    sb = get_supabase()
    data = {
        "email": email,
        "slack_user_id": slack_user_id,
        "display_name": display_name,
        "schedule_hour": schedule_hour,
        "active": True,
    }
    result = sb.table("users").upsert(data, on_conflict="email").execute()
    return result.data[0] if result.data else data


def get_user(email: str) -> Optional[Dict[str, Any]]:
    """Get a user by email, or None if not found."""
    sb = get_supabase()
    result = sb.table("users").select("*").eq("email", email).execute()
    return result.data[0] if result.data else None


def get_all_active_users() -> List[Dict[str, Any]]:
    """Get all active users for scheduling."""
    sb = get_supabase()
    result = sb.table("users").select("*").eq("active", True).execute()
    return result.data or []


def save_nudge_run(
    user_email: str,
    submissions_checked: int,
    nudges_needed: int,
    nudges_sent: int,
    details: dict,
) -> None:
    """Save a nudge run result to the database."""
    sb = get_supabase()
    sb.table("nudge_runs").insert({
        "user_email": user_email,
        "ran_at": datetime.now(tz=timezone.utc).isoformat(),
        "submissions_checked": submissions_checked,
        "nudges_needed": nudges_needed,
        "nudges_sent": nudges_sent,
        "details": details,
    }).execute()


def get_nudge_history(email: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent nudge runs for a user."""
    sb = get_supabase()
    result = (
        sb.table("nudge_runs")
        .select("*")
        .eq("user_email", email)
        .order("ran_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []
