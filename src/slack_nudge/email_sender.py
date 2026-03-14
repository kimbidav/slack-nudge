"""Send emails via the Gmail API."""
from __future__ import annotations

import base64
from email.mime.text import MIMEText
from pathlib import Path

_GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def send_email_via_gmail(
    to: str,
    subject: str,
    body: str,
    credentials_path: str,
    token_path: str,
) -> dict:
    """
    Send an email via the Gmail API as the authenticated user.

    On first use, opens a browser for one-time Gmail send authorization.
    The token is cached to gmail_send_token.json for future sends.
    """
    from googleapiclient.discovery import build
    from .google_auth_helper import get_credentials

    send_token_path = str(Path(token_path).parent / "gmail_send_token.json")
    creds = get_credentials(credentials_path, send_token_path, [_GMAIL_SEND_SCOPE])
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    content_type = "html" if "<a " in body or "<br" in body else "plain"
    mime_msg = MIMEText(body, content_type)
    mime_msg["to"] = to
    mime_msg["subject"] = subject
    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()

    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    return {"ok": True, "message_id": result.get("id")}
