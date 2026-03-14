"""Lightweight first-run onboarding — prompts for email and saves to .env."""
from __future__ import annotations

from pathlib import Path

from .slack_client import SlackAPI


def needs_onboarding(user_email: str) -> bool:
    """Return True if USER_EMAIL is not configured."""
    return not user_email


def run_onboarding(slack_token: str) -> str:
    """
    Interactive onboarding: ask for email, validate against Slack, save to .env.

    Returns the validated email address.
    """
    print()
    print("=" * 50)
    print("  Slack Nudge — First-time setup")
    print("=" * 50)
    print()

    slack = SlackAPI(slack_token)

    while True:
        email = input("Enter your email address: ").strip()
        if not email or "@" not in email:
            print("Please enter a valid email address.")
            continue

        print(f"Looking up {email} in Slack...", end=" ", flush=True)
        try:
            user_id = slack.get_user_id_by_email(email)
            print(f"found! (user ID: {user_id})")
            break
        except RuntimeError:
            print("not found.")
            print("No Slack user matches that email. Please try again.")
            continue

    # Save to .env
    env_path = Path(".env")
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        if "USER_EMAIL" not in content:
            with open(env_path, "a", encoding="utf-8") as f:
                f.write(f"\nUSER_EMAIL={email}\n")
    else:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"USER_EMAIL={email}\n")

    print(f"\nSaved USER_EMAIL={email} to .env")
    print("Scanning your Slack Connect channels...\n")
    return email
