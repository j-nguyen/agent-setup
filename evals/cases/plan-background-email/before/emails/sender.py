"""Outgoing email over SMTP. Tests replace `transport` with a fake."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage


class SmtpTransport:
    def __init__(self, host: str = "smtp.internal", port: int = 587, timeout: float = 20.0):
        self.host, self.port, self.timeout = host, port, timeout

    def send(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as s:
            s.starttls()
            s.send_message(msg)


transport = SmtpTransport()


def send_email(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = "Shopfront <hello@shopfront.example>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    transport.send(msg)
