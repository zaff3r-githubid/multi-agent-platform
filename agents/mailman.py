# agents/mailman.py
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from agents.base_agent import BaseAgent
from orchestrator.llm_queue import llm_queue
from utils.email_sender import send_html_email, build_email_wrapper
from database.db import get_conn
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent.parent / ".env")
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# ── 7 categories required by assignment ──────────────────────────────────────
CATEGORIES = [
    "URGENT",
    "ACTION_REQUIRED",
    "FOLLOW_UP",
    "NEWSLETTER",
    "NOTIFICATION",
    "PERSONAL",
    "OTHER"
]


def _get_gmail_service():
    """
    Loads token.json and returns an authenticated Gmail API service.
    Automatically refreshes the token if it has expired.
    """
    token_path = Path(__file__).parent.parent / "token.json"
    creds_path = Path(__file__).parent.parent / "credentials.json"

    if not token_path.exists():
        raise FileNotFoundError(
            "token.json not found — run python utils/gmail_auth.py first"
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Auto-refresh expired token — no manual re-authorisation needed
    if creds.expired and creds.refresh_token:
        logger.info("[Mailman] Refreshing expired Gmail token...")
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _get_or_create_label(service, name: str) -> str:
    """
    Returns the Gmail label ID for a given name.
    Creates the label if it doesn't exist yet.
    """
    labels = service.users().labels().list(
        userId="me"
    ).execute().get("labels", [])

    for label in labels:
        if label["name"].upper() == name.upper():
            return label["id"]

    # Label doesn't exist — create it
    new_label = service.users().labels().create(
        userId="me",
        body={
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show"
        }
    ).execute()
    logger.info(f"[Mailman] Created Gmail label: {name}")
    return new_label["id"]


class Mailman(BaseAgent):
    name = "mailman"

    async def _run_logic(self) -> str:

        # Load key people list from .env
        key_people_raw = os.getenv("KEY_PEOPLE", "")
        key_people = [
            email.strip().lower()
            for email in key_people_raw.split(",")
            if email.strip()
        ]

        service = _get_gmail_service()

        # ── 1. Fetch unread emails ────────────────────────────────────────────
        results = service.users().messages().list(
            userId="me",
            labelIds=["INBOX"],
            q="is:unread",
            maxResults=20
        ).execute()

        messages = results.get("messages", [])

        if not messages:
            logger.info("[Mailman] No unread emails found")
            return "No unread emails"

        logger.info(f"[Mailman] Found {len(messages)} unread emails")

        classified   = 0
        urgent_list  = []
        key_people_emails = []
        category_counts = {cat: 0 for cat in CATEGORIES}

        for msg in messages:
            # ── 2. Get email details ──────────────────────────────────────────
            full = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()

            headers = {
                h["name"]: h["value"]
                for h in full["payload"]["headers"]
            }
            sender  = headers.get("From", "")
            subject = headers.get("Subject", "(no subject)")
            snippet = full.get("snippet", "")

            # ── 3. Skip already classified emails ────────────────────────────
            with get_conn() as conn:
                existing = conn.execute(
                    "SELECT id FROM email_log WHERE gmail_id=?",
                    (msg["id"],)
                ).fetchone()
            if existing:
                continue

            # ── 4. Classify with Qwen3 ────────────────────────────────────────
            category = await llm_queue.submit(
                prompt=(
                    f"Classify this email into exactly ONE category.\n\n"
                    f"Categories: {', '.join(CATEGORIES)}\n\n"
                    f"From: {sender}\n"
                    f"Subject: {subject}\n"
                    f"Preview: {snippet[:200]}\n\n"
                    f"Rules:\n"
                    f"- URGENT: needs immediate attention or response\n"
                    f"- ACTION_REQUIRED: needs a task or response but not urgent\n"
                    f"- FOLLOW_UP: waiting on someone or need to check back\n"
                    f"- NEWSLETTER: marketing, subscriptions, digests\n"
                    f"- NOTIFICATION: automated system notifications\n"
                    f"- PERSONAL: from a real person, casual\n"
                    f"- OTHER: anything else\n\n"
                    f"Reply with the category label ONLY. No explanation."
                ),
                system="You are an email classifier. Reply with exactly one category label.",
                agent_name=self.name
            )

            # Clean up response — take first word, uppercase
            category = category.strip().split()[0].upper()
            if category not in CATEGORIES:
                category = "OTHER"

            category_counts[category] += 1

            # ── 5. Generate AI summary ────────────────────────────────────────
            ai_summary = await llm_queue.submit(
                prompt=(
                    f"Summarise this email in one short sentence (max 15 words).\n\n"
                    f"From: {sender}\n"
                    f"Subject: {subject}\n"
                    f"Preview: {snippet[:200]}"
                ),
                system="You summarise emails in one concise sentence.",
                agent_name=self.name
            )

            # ── 6. Apply Gmail label ──────────────────────────────────────────
            try:
                label_id = _get_or_create_label(service, category)
                service.users().messages().modify(
                    userId="me",
                    id=msg["id"],
                    body={"addLabelIds": [label_id]}
                ).execute()

                # Star urgent emails
                if category == "URGENT":
                    service.users().messages().modify(
                        userId="me",
                        id=msg["id"],
                        body={"addLabelIds": ["STARRED"]}
                    ).execute()
                    urgent_list.append(subject)

            except Exception as e:
                logger.warning(f"[Mailman] Label apply failed: {e}")

            # ── 7. Check key people ───────────────────────────────────────────
            sender_email = sender.lower()
            for kp in key_people:
                if kp in sender_email:
                    key_people_emails.append({
                        "sender":  sender,
                        "subject": subject,
                        "summary": ai_summary
                    })
                    # Star key people emails too
                    try:
                        service.users().messages().modify(
                            userId="me",
                            id=msg["id"],
                            body={"addLabelIds": ["STARRED"]}
                        ).execute()
                    except Exception:
                        pass
                    break

            # ── 8. Save to database ───────────────────────────────────────────
            with get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO email_log"
                    " (gmail_id, sender, subject, snippet,"
                    "  classification, ai_summary, classified_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        msg["id"], sender, subject, snippet,
                        category, ai_summary, datetime.utcnow()
                    )
                )
                conn.commit()

            classified += 1
            logger.info(f"[Mailman] Classified: {subject[:40]} → {category}")

        # ── 9. Send daily summary email ───────────────────────────────────────
        if classified > 0:
            await self._send_summary_email(
                classified, category_counts,
                urgent_list, key_people_emails
            )

        result = (
            f"Classified {classified} emails — "
            f"{category_counts.get('URGENT', 0)} urgent, "
            f"{len(key_people_emails)} from key people"
        )
        return result

    async def _send_summary_email(
        self,
        total: int,
        counts: dict,
        urgent: list,
        key_people: list
    ):
        """Builds and sends the daily email summary."""

        # Category breakdown bars
        category_rows = "".join(f"""
        <tr>
            <td style="padding:6px 12px;font-weight:600;
                       color:#374151;width:160px">{cat}</td>
            <td style="padding:6px 12px">
                <div style="background:#e5e7eb;border-radius:4px;
                            height:18px;width:200px">
                    <div style="background:#6366f1;border-radius:4px;
                                height:18px;width:{min(count * 20, 200)}px">
                    </div>
                </div>
            </td>
            <td style="padding:6px 12px;color:#6b7280">{count}</td>
        </tr>
        """ for cat, count in counts.items() if count > 0)

        # Urgent section
        urgent_html = ""
        if urgent:
            urgent_items = "".join(
                f"<li style='color:#dc2626;margin:4px 0'>{s}</li>"
                for s in urgent
            )
            urgent_html = f"""
            <div style="background:#fef2f2;border-left:4px solid #ef4444;
                        padding:14px;border-radius:6px;margin-bottom:20px">
                <h3 style="color:#dc2626;margin:0 0 8px">
                    🚨 Urgent Emails ({len(urgent)})
                </h3>
                <ul style="margin:0;padding-left:20px">{urgent_items}</ul>
            </div>
            """

        # Key people section
        key_people_html = ""
        if key_people:
            kp_items = "".join(f"""
            <div style="border:1px solid #e5e7eb;border-radius:6px;
                        padding:10px;margin-bottom:8px">
                <div style="font-weight:600;color:#1f2937">{e['sender']}</div>
                <div style="color:#6b7280;font-size:13px">{e['subject']}</div>
                <div style="color:#374151;font-size:13px;
                            margin-top:4px">{e['summary']}</div>
            </div>
            """ for e in key_people)
            key_people_html = f"""
            <h3 style="color:#1f2937;margin-bottom:12px">
                ⭐ Key People ({len(key_people)})
            </h3>
            {kp_items}
            """

        content = f"""
        <div style="background:#f0f9ff;border-left:4px solid #3b82f6;
                    padding:14px;border-radius:6px;margin-bottom:20px">
            <h3 style="margin:0;color:#1e40af">
                📬 {total} emails classified
            </h3>
        </div>

        {urgent_html}
        {key_people_html}

        <h3 style="color:#1f2937;margin-bottom:12px">
            📊 Category Breakdown
        </h3>
        <table style="border-collapse:collapse;margin-bottom:20px">
            {category_rows}
        </table>
        """

        html = build_email_wrapper(
            "Mailman — Email Summary",
            content,
            "Mailman"
        )
        send_html_email("📬 Mailman — Email Summary", html)
        logger.info("[Mailman] Summary email sent")