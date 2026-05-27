"""
Simple email helper using smtplib and configuration from `config.py`.
Intended for local/dev use. Configure SMTP via environment variables or
`config.SMTP_*` values.
"""
import smtplib
from email.message import EmailMessage
from typing import Optional

from config import SMTP_SERVER, SMTP_PORT, SMTP_USE_TLS, SMTP_USERNAME, SMTP_PASSWORD, MAIL_FROM


def send_email(to_address: str, subject: str, body: str, html: Optional[str] = None) -> tuple[bool, str]:
    """Send a simple email. Returns (ok, message).

    For local testing you can run a debugging SMTP server:
    `python -m smtpd -c DebuggingServer -n localhost:1025`
    """
    msg = EmailMessage()
    msg["From"] = MAIL_FROM
    msg["To"] = to_address
    msg["Subject"] = subject
    if html:
        msg.set_content(body)
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(body)

    try:
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
            server.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
            if SMTP_USERNAME and SMTP_PASSWORD:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)

        server.send_message(msg)
        server.quit()
        return True, "Email sent"
    except Exception as e:
        return False, f"Failed to send email: {e}"
