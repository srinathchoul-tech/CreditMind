import logging
import json
import os
import smtplib
import urllib.error
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from env_loader import load_env_file

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()
else:
    load_env_file()


LOGGER = logging.getLogger(__name__)
_LAST_EMAIL_ERROR = ""


def _sender_credentials() -> tuple[str, str]:
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    # SENDER_APP_PASSWORD is a Gmail App Password, NOT your Gmail login password.
    # Generate it from: Google Account -> Security -> 2-Step Verification -> App Passwords
    sender_app_password = (
        os.getenv("SENDER_APP_PASSWORD", "").strip()
        or os.getenv("SENDER_PASSWORD", "").strip()
    )
    return sender_email, sender_app_password


def _resend_credentials() -> tuple[str, str]:
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    email_from = os.getenv("EMAIL_FROM", "").strip()
    return resend_api_key, email_from


def _looks_placeholder(value: str) -> bool:
    lowered = str(value or "").strip().lower()
    return (
        not lowered
        or "your_gmail" in lowered
        or "your_16_digit_app_password" in lowered
        or "example.com" in lowered
    )


def email_config_ready() -> tuple[bool, str]:
    resend_api_key, email_from = _resend_credentials()
    if resend_api_key and email_from and not _looks_placeholder(email_from):
        return True, ""

    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    sender_app_password = os.getenv("SENDER_APP_PASSWORD", "").strip() or os.getenv("SENDER_PASSWORD", "").strip()
    if _looks_placeholder(sender_email):
        return False, "SENDER_EMAIL is missing/placeholder and Resend is not configured."
    if _looks_placeholder(sender_app_password):
        return False, "SENDER_APP_PASSWORD is missing/placeholder and Resend is not configured."
    return True, ""


def get_last_email_error() -> str:
    return _LAST_EMAIL_ERROR


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    global _LAST_EMAIL_ERROR
    _LAST_EMAIL_ERROR = ""

    recipient = str(to_email or "").strip()
    if not recipient:
        _LAST_EMAIL_ERROR = "Recipient email is missing."
        LOGGER.warning(_LAST_EMAIL_ERROR)
        return False

    config_ok, config_message = email_config_ready()
    if not config_ok:
        _LAST_EMAIL_ERROR = config_message
        LOGGER.warning(_LAST_EMAIL_ERROR)
        return False

    resend_api_key, email_from = _resend_credentials()
    if resend_api_key and email_from and not _looks_placeholder(email_from):
        try:
            payload = {
                "from": email_from,
                "to": [recipient],
                "subject": subject,
                "html": html_body,
            }
            req = urllib.request.Request(
                url="https://api.resend.com/emails",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                body = response.read().decode("utf-8")
                status_ok = 200 <= int(getattr(response, "status", 0) or 0) < 300
                if status_ok:
                    return True
                _LAST_EMAIL_ERROR = f"Resend API non-success response: {body}"
                LOGGER.warning(_LAST_EMAIL_ERROR)
                return False
        except urllib.error.HTTPError as exc:
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                error_body = str(exc)
            _LAST_EMAIL_ERROR = f"Resend HTTP error {exc.code}: {error_body}"
            LOGGER.warning(_LAST_EMAIL_ERROR)
            return False
        except Exception as exc:  # pragma: no cover - network runtime behavior
            _LAST_EMAIL_ERROR = f"Resend send failed: {exc}"
            LOGGER.warning(_LAST_EMAIL_ERROR)
            # Fall through to SMTP fallback if SMTP creds exist.

    sender_email, sender_app_password = _sender_credentials()
    if not sender_email or not sender_app_password or not recipient:
        if not _LAST_EMAIL_ERROR:
            _LAST_EMAIL_ERROR = "Email skipped: Resend failed and SMTP credentials are missing."
        LOGGER.warning(_LAST_EMAIL_ERROR)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    last_exc: Exception | None = None
    # Try TLS first (587), then SSL (465) as fallback.
    for mode, port in (("starttls", 587), ("ssl", 465)):
        try:
            if mode == "starttls":
                with smtplib.SMTP("smtp.gmail.com", port, timeout=20) as smtp:
                    smtp.starttls()
                    smtp.login(sender_email, sender_app_password)
                    smtp.sendmail(sender_email, [recipient], msg.as_string())
            else:
                with smtplib.SMTP_SSL("smtp.gmail.com", port, timeout=20) as smtp:
                    smtp.login(sender_email, sender_app_password)
                    smtp.sendmail(sender_email, [recipient], msg.as_string())
            return True
        except Exception as exc:  # pragma: no cover - depends on SMTP runtime config
            last_exc = exc
            LOGGER.warning("Email send attempt failed on mode=%s port=%s: %s", mode, port, exc)

    _LAST_EMAIL_ERROR = str(last_exc) if last_exc else "Unknown SMTP failure."
    LOGGER.exception("Email send failed after retries: %s", _LAST_EMAIL_ERROR)
    return False


def _format_rupee(amount: float | int | None) -> str:
    try:
        value = float(amount or 0)
        return f"{value:,.0f}"
    except Exception:
        return str(amount or "0")


def notify_officer_new_application(
    officer_email: str,
    applicant_name: str,
    business_name: str,
    loan_amount: float | int | None,
    application_id: str,
) -> bool:
    subject = f"CreditMind: New Loan Application Received - {business_name or 'Business'}"
    submitted_on = datetime.now().strftime("%d %B %Y, %I:%M %p")

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;background:#ffffff;color:#1f2937;line-height:1.5;">
      <p>Dear Credit Officer,</p>
      <p>A new loan application has been submitted and is awaiting your review.</p>
      <table style="border-collapse:collapse;min-width:480px;">
        <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Applicant Name</b></td><td style="padding:8px;border:1px solid #d1d5db;">{escape(applicant_name or '-')}</td></tr>
        <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Business Name</b></td><td style="padding:8px;border:1px solid #d1d5db;">{escape(business_name or '-')}</td></tr>
        <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Loan Amount</b></td><td style="padding:8px;border:1px solid #d1d5db;">INR {_format_rupee(loan_amount)}</td></tr>
        <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Application ID</b></td><td style="padding:8px;border:1px solid #d1d5db;">{escape(application_id or '-')}</td></tr>
        <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Submitted On</b></td><td style="padding:8px;border:1px solid #d1d5db;">{escape(submitted_on)}</td></tr>
      </table>
      <p>Please log in to the CreditMind Officer Portal to review the application and uploaded documents.</p>
      <p style="font-size:12px;color:#6b7280;">This is an automated notification from CreditMind. Do not reply to this email.</p>
    </body></html>
    """
    return send_email(officer_email, subject, html_body)


def notify_seeker_decision(
    seeker_email: str,
    applicant_name: str,
    business_name: str,
    loan_amount: float | int | None,
    decision: str,
    officer_remarks: str,
    decided_at: str,
) -> bool:
    normalized_decision = str(decision or "").strip().lower()
    pretty_decision = normalized_decision.capitalize() if normalized_decision else "Decision"
    accent = "#f59e0b"
    opening = (
        "Your loan application has been reviewed. "
        "A conditional decision has been made - please read the officer's remarks carefully and take the required action."
    )
    if normalized_decision == "approved":
        accent = "#16a34a"
        opening = (
            "We are pleased to inform you that your loan application has been reviewed and Approved."
        )
    elif normalized_decision == "rejected":
        accent = "#dc2626"
        opening = (
            "After careful review of your loan application, we regret to inform you that your application has not been approved at this time."
        )

    subject = f"CreditMind: Your Loan Application Decision - {pretty_decision}"
    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;background:#ffffff;color:#1f2937;line-height:1.5;">
      <div style="border-left:6px solid {accent};padding:10px 14px;background:#f9fafb;margin-bottom:14px;">
        <b>{escape(pretty_decision)} Decision Update</b>
      </div>
      <p>Dear {escape(applicant_name or 'Applicant')},</p>
      <p>{escape(opening)}</p>
      <table style="border-collapse:collapse;min-width:520px;">
        <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Business Name</b></td><td style="padding:8px;border:1px solid #d1d5db;">{escape(business_name or '-')}</td></tr>
        <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Loan Amount</b></td><td style="padding:8px;border:1px solid #d1d5db;">INR {_format_rupee(loan_amount)}</td></tr>
        <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Decision</b></td><td style="padding:8px;border:1px solid #d1d5db;">{escape(pretty_decision)}</td></tr>
        <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Officer Remarks</b></td><td style="padding:8px;border:1px solid #d1d5db;">{escape(officer_remarks or '-')}</td></tr>
        <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Decision Date</b></td><td style="padding:8px;border:1px solid #d1d5db;">{escape(decided_at or datetime.now().strftime("%d %B %Y, %I:%M %p"))}</td></tr>
      </table>
      <p style="font-size:12px;color:#6b7280;">This is an automated notification from CreditMind Lending Platform. For queries, contact your branch.</p>
    </body></html>
    """
    return send_email(seeker_email, subject, html_body)
