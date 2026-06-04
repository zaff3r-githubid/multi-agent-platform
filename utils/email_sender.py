# utils/email_sender.py
import smtplib
import os
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)

def send_html_email(subject: str, html_body: str, recipient: str = None) -> bool:
    """
    Sends an HTML formatted email via Gmail SMTP.

    Args:
        subject:   Email subject line
        html_body: Full HTML content of the email body
        recipient: Override recipient (defaults to EMAIL_RECIPIENT in .env)

    Returns:
        True if sent successfully, False if failed
        (Returns False instead of raising — one failed email
        should not crash the entire agent run)
    """
    host      = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port      = int(os.getenv("SMTP_PORT", 587))
    user      = os.getenv("SMTP_USER")
    password  = os.getenv("SMTP_PASSWORD")
    to        = recipient or os.getenv("EMAIL_RECIPIENT", user)

    # ── Validate config ───────────────────────────────────────────────────────
    if not all([user, password, to]):
        logger.error("Email config incomplete — check SMTP_USER, SMTP_PASSWORD, EMAIL_RECIPIENT in .env")
        return False

    # ── Build the email ───────────────────────────────────────────────────────
    msg = MIMEMultipart("alternative")
    # "alternative" means we're sending HTML (with plain text fallback option)

    msg["Subject"] = subject
    msg["From"]    = f"Multi-Agent Platform <{user}>"
    msg["To"]      = to
    msg["X-Mailer"] = "Multi-Agent-Platform/1.0"
    # X-Mailer is a custom header identifying our app — good practice

    # Attach plain text fallback (for email clients that don't render HTML)
    plain_text = f"This email requires an HTML-capable email client.\n\nSubject: {subject}"
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    # Order matters — HTML must be attached LAST (it takes priority)

    # ── Send via Gmail SMTP ───────────────────────────────────────────────────
    try:
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            # ehlo() = "hello" handshake with the SMTP server
            server.starttls()
            # starttls() = upgrade connection to encrypted TLS
            # This is why we use port 587 (TLS) not 465 (SSL)
            server.login(user, password)
            server.sendmail(user, to, msg.as_string())

        logger.info(f"Email sent: '{subject}' → {to}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP Authentication failed — check your Gmail App Password in .env")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending '{subject}': {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        return False


def build_email_wrapper(title: str, content: str, agent_name: str) -> str:
    """
    Wraps any HTML content in a consistent, professional email template.
    All agents use this so every email looks polished and on-brand.

    Args:
        title:      Big heading at top of email
        content:    The agent's specific HTML content (cards, tables, etc.)
        agent_name: Shown in footer

    Returns:
        Complete HTML email string ready to send
    """
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: #f4f4f4;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 680px;
                margin: 0 auto;
                background: #ffffff;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #1a1d27 0%, #2d3148 100%);
                color: white;
                padding: 28px 32px;
            }}
            .header h1 {{
                margin: 0;
                font-size: 22px;
                font-weight: 700;
            }}
            .header p {{
                margin: 6px 0 0;
                opacity: 0.7;
                font-size: 13px;
            }}
            .body {{
                padding: 28px 32px;
            }}
            .footer {{
                background: #f8f8f8;
                border-top: 1px solid #eee;
                padding: 16px 32px;
                font-size: 11px;
                color: #999;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{title}</h1>
                <p>Generated by Multi-Agent Platform · {now}</p>
            </div>
            <div class="body">
                {content}
            </div>
            <div class="footer">
                Sent by {agent_name} agent · Multi-Agent Auto-Scheduling Platform
                · Running locally on Qwen3-14B via LM Studio
            </div>
        </div>
    </body>
    </html>
    """