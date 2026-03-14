"""Allow running as `python -m slack_nudge`."""
from .realtime_monitor import run_single_check

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Slack Nudge — candidate follow-up scanner")
    parser.add_argument("--dry-run", action="store_true", help="Preview nudges without sending")
    parser.add_argument("--dm-only", action="store_true", default=None, help="Send DM summary only, no thread replies")
    parser.add_argument("--email", type=str, default=None, help="Your email address (skips onboarding)")
    args = parser.parse_args()
    run_single_check(dry_run=args.dry_run, dm_only=args.dm_only or None, email=args.email)
