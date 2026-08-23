"""Shared SMTP sender used by the email handler and the digest.

Credentials come from env vars (set them as GitHub Actions secrets, or a local
.env for development). Nothing is ever read from a tracked config file.
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def configured() -> bool:
    return bool(os.getenv("GITFLOE_MAIL_TO", "").strip() and os.getenv("GITFLOE_SMTP_HOST", "").strip())


def send(subject: str, text: str) -> bool:
    """Send a plain-text email. Returns False if SMTP is not configured."""
    if not configured():
        return False
    recipient = os.getenv("GITFLOE_MAIL_TO", "").strip()
    host = os.getenv("GITFLOE_SMTP_HOST", "").strip()
    port = int(os.getenv("GITFLOE_SMTP_PORT", "587"))
    user = os.getenv("GITFLOE_SMTP_USER", "")
    password = os.getenv("GITFLOE_SMTP_PASS", "")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user or "gitfloe@localhost"
    msg["To"] = recipient
    msg.set_content(text)

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.send_message(msg)
    return True
