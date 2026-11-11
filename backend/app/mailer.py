"""Outbound email that is sent only after the surrounding transaction commits.

Request handlers call queue_email(db, ...) next to their in-app notify()
calls. Messages wait in the session and are handed to a background thread on
commit, so a rolled-back request never emails anyone and a slow SMTP server
never delays an API response. Delivery failures are logged, never raised:
the in-app notification remains the source of truth.
"""
import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage

from sqlalchemy import event
from sqlalchemy.orm import Session

from . import config

log = logging.getLogger("hrms.mail")
_OUTBOX_KEY = "hrms_email_outbox"
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hrms-mail")


def queue_email(db: Session, to: str | None, subject: str, body: str) -> None:
    """Send an email once db commits. Silently ignores a missing address."""
    if not to:
        return
    if not db.in_transaction():
        # Tie the message to a transaction so the commit/rollback events fire.
        db.begin()
    db.info.setdefault(_OUTBOX_KEY, []).append((to, subject, body))


def app_link(path: str) -> str:
    return f"{config.FRONTEND_URL}{path}" if config.FRONTEND_URL else path


def _deliver(to: str, subject: str, body: str) -> None:
    if config.EMAIL_BACKEND == "disabled":
        return
    if config.EMAIL_BACKEND == "console":
        log.warning("EMAIL (console backend) to=%s subject=%s\n%s", to, subject, body)
        return
    message = EmailMessage()
    message["From"] = config.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        if config.EMAIL_BACKEND == "gmail_api":
            from .gmail_api import send
            send(message)
            return
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as smtp:
            if config.SMTP_USE_TLS:
                smtp.starttls()
            smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception:  # noqa: BLE001 - delivery must never break the app
        log.exception("Email delivery failed to=%s subject=%s", to, subject)


@event.listens_for(Session, "after_commit")
def _flush_outbox(session: Session) -> None:
    for item in session.info.pop(_OUTBOX_KEY, []):
        _executor.submit(_deliver, *item)


@event.listens_for(Session, "after_soft_rollback")
def _discard_outbox(session: Session, previous_transaction) -> None:
    # Fires on every rollback() call, even one that never touched the DB
    # (after_rollback would miss those). Savepoint rollbacks keep the outbox.
    if not previous_transaction.nested:
        session.info.pop(_OUTBOX_KEY, None)
