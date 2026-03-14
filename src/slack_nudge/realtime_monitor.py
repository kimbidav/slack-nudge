"""Slack Nudge runner — periodic check for stale submissions.

Can be run manually, on a schedule via cron/launchd, or as a module.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .config import load_config
from .nudge import run_nudge_check
from .onboarding import needs_onboarding, run_onboarding


def run_single_check(dry_run: bool = False, dm_only: bool = None, email: str = None) -> None:
    """Run a single nudge check."""
    cfg = load_config()

    # Override email from CLI flag
    if email:
        cfg.user_email = email

    # Onboarding if no email configured
    if needs_onboarding(cfg.user_email):
        cfg.user_email = run_onboarding(cfg.slack_bot_token)

    print(f"[{datetime.now(tz=timezone.utc).isoformat()}] Running nudge check for {cfg.user_email}...")
    print(f"Nudge threshold: {cfg.nudge_days} days without checkmark or no-entry emoji")
    effective_dm_only = dm_only if dm_only is not None else cfg.nudge_dm_only
    if effective_dm_only:
        print("Mode: DM-only (no thread replies)")
    print()

    results = run_nudge_check(cfg, dry_run=dry_run, dm_only=dm_only)

    print()
    print("=" * 50)
    print("NUDGE CHECK RESULTS")
    print("=" * 50)
    print(f"Submissions checked: {results['submissions_checked']}")
    print(f"Nudges needed: {results['nudges_needed']}")
    if dry_run:
        print("Nudges sent: (dry run - none sent)")
    else:
        print(f"Nudges sent: {results['nudges_sent']}")

    if results['submissions_needing_nudge']:
        print("\nSubmissions needing nudge:")
        for sub in results['submissions_needing_nudge']:
            print(f"  - {sub['candidate_name']} in #{sub['channel_name']} ({sub['days_since_submission']} days)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Slack Nudge — candidate follow-up scanner")
    parser.add_argument("--dry-run", action="store_true", help="Preview nudges without sending")
    parser.add_argument("--dm-only", action="store_true", default=None, help="Send DM summary only, no thread replies")
    parser.add_argument("--email", type=str, default=None, help="Your email address (skips onboarding)")

    args = parser.parse_args()
    run_single_check(dry_run=args.dry_run, dm_only=args.dm_only or None, email=args.email)
