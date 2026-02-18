# backend/core/services/email.py
"""
Email sending for manual bridge-review notifications.
Supports SMTP (env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM)
or Resend (env: RESEND_API_KEY). If neither is configured, logs and no-ops.
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger("Apex.Email")


def send_email(
    to: str,
    subject: str,
    body_plain: str,
    body_html: Optional[str] = None,
) -> bool:
    """
    Send an email to the given address.
    Returns True if sent (or no-op when no provider configured), False on send failure.
    """
    if not to or not to.strip():
        logger.warning("send_email: empty 'to' address, skipping")
        return False

    to = to.strip()
    from_addr = os.getenv("SMTP_FROM") or os.getenv("RESEND_FROM") or "noreply@apex.local"

    # Resend
    resend_key = os.getenv("RESEND_API_KEY")
    if resend_key:
        return _send_via_resend(to=to, from_addr=from_addr, subject=subject, body_plain=body_plain, body_html=body_html, api_key=resend_key)

    # SMTP
    smtp_host = os.getenv("SMTP_HOST")
    if smtp_host:
        return _send_via_smtp(to=to, from_addr=from_addr, subject=subject, body_plain=body_plain, body_html=body_html)

    logger.info("Email would be sent (no SMTP or Resend configured): to=%s subject=%s", to, subject)
    return True


def _send_via_smtp(
    to: str,
    from_addr: str,
    subject: str,
    body_plain: str,
    body_html: Optional[str],
) -> bool:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        msg.attach(MIMEText(body_plain, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP(host, port) as server:
            if port == 587:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(from_addr, [to], msg.as_string())
        logger.info("Email sent via SMTP to %s", to)
        return True
    except Exception as e:
        logger.error("SMTP send failed: %s", e, exc_info=True)
        return False


def _send_via_resend(
    to: str,
    from_addr: str,
    subject: str,
    body_plain: str,
    body_html: Optional[str],
    api_key: str,
) -> bool:
    try:
        import requests
        url = "https://api.resend.com/emails"
        payload = {
            "from": from_addr,
            "to": [to],
            "subject": subject,
            "text": body_plain,
        }
        if body_html:
            payload["html"] = body_html
        r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        if r.status_code in (200, 201):
            logger.info("Email sent via Resend to %s", to)
            return True
        logger.error("Resend API error: %s %s", r.status_code, r.text)
        return False
    except Exception as e:
        logger.error("Resend send failed: %s", e, exc_info=True)
        return False
