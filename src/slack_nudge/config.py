from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import os
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    slack_bot_token: str
    user_email: str = ""
    lookback_days: int = 60
    unclear_followup_days: int = 7
    inactivity_days: int = 5
    include_confused_close: bool = False
    # Nudge settings
    nudge_days: int = 3  # Days without ✅ or ⛔ before nudging
    user_slack_id: Optional[str] = None
    nudge_tracker_path: str = ".nudge_tracker.json"
    nudge_dm_only: bool = False  # If True, send DM summary only (no thread replies)
    # Gmail (for email notifications)
    gmail_credentials_path: str = "./credentials.json"
    gmail_token_path: str = "./gmail_token.json"

    @property
    def lookback_timedelta(self) -> timedelta:
        return timedelta(days=self.lookback_days)

    @property
    def unclear_followup_timedelta(self) -> timedelta:
        return timedelta(days=self.unclear_followup_days)

    @property
    def inactivity_timedelta(self) -> timedelta:
        return timedelta(days=self.inactivity_days)


def load_config() -> Config:
    """Load configuration from environment variables / .env file."""
    load_dotenv(override=True)

    slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
    if not slack_bot_token:
        raise RuntimeError(
            "SLACK_BOT_TOKEN must be set in environment or .env file."
        )

    # USER_EMAIL with DK_EMAIL as backward-compat fallback
    user_email = os.getenv("USER_EMAIL") or os.getenv("DK_EMAIL") or ""

    def _int_env(name: str, default: int) -> int:
        val = os.getenv(name)
        if not val:
            return default
        try:
            return int(val)
        except ValueError:
            return default

    user_slack_id = os.getenv("USER_SLACK_ID") or os.getenv("DK_USER_ID") or None

    return Config(
        slack_bot_token=slack_bot_token,
        user_email=user_email,
        lookback_days=_int_env("LOOKBACK_DAYS", 60),
        unclear_followup_days=_int_env("UNCLEAR_FOLLOWUP_DAYS", 7),
        inactivity_days=_int_env("INACTIVITY_DAYS", 5),
        include_confused_close=os.getenv("INCLUDE_CONFUSED_CLOSE", "false").lower() in {"1", "true", "yes", "y"},
        nudge_days=_int_env("NUDGE_DAYS", 3),
        user_slack_id=user_slack_id,
        nudge_tracker_path=os.getenv("NUDGE_TRACKER_PATH", ".nudge_tracker.json"),
        nudge_dm_only=os.getenv("NUDGE_DM_ONLY", "false").lower() in {"1", "true", "yes", "y"},
        gmail_credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", "./credentials.json"),
        gmail_token_path=os.getenv("GMAIL_TOKEN_PATH", "./gmail_token.json"),
    )
