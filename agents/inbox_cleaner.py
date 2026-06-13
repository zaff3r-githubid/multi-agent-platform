# agents/inbox_cleaner.py
"""
InboxCleaner — Bonus Agent (not part of core assignment)

What it does:
  1. Connects to Gmail using the existing OAuth2 token (same as Mailman)
  2. Finds all emails under the CATEGORY_PROMOTIONS label
  3. Compiles a unique sender list BEFORE touching anything
  4. Saves that sender list to the DB for the dashboard report
  5. Skips whitelisted senders (set INBOX_CLEANER_WHITELIST in .env)
  6. Moves remaining promotional emails to Trash (NOT permanent delete)
  7. Sends a summary email with count trashed + the unsubscribe report

Schedule: daily at 02:00 UTC (configurable via INBOX_CLEANER_RUN_HOUR)
"""

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

from agents.base_agent import BaseAgent
from database.db import get_conn
from utils.email_sender import send_html_email, build_email_wrapper
from utils.gmail_health import check_gmail_token

load_dotenv(Path(__file__).parent.parent / ".env")
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _get_gmail_service():
    """Reuses the same token.json as Mailman — no separate auth needed."""
    token_path = Path(__file__).parent.parent / "token.json"

    if not token_path.exists():
        raise FileNotFoundError(
            "token.json not found — run python utils/gmail_auth.py first"
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds.expired and creds.refresh_token:
        logger.info("[InboxCleaner] Refreshing expired Gmail token...")
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _extract_email_address(raw_from: str) -> str:
    """
    Extracts the plain email address from a 'From' header.
    e.g. 'Shopify <noreply@shopify.com>' → 'noreply@shopify.com'
    """
    match = re.search(r'<(.+?)>', raw_from)
    if match:
        return match.group(1).strip().lower()
    return raw_from.strip().lower()


def _extract_display_name(raw_from: str) -> str:
    """
    Extracts the display name from a 'From' header.
    e.g. 'Shopify <noreply@shopify.com>' → 'Shopify'
    Falls back to the email address if no display name.
    """
    match = re.search(r'^(.+?)\s*<', raw_from)
    if match:
        name = match.group(1).strip().strip('"').strip("'")
        if name:
            return name
    return _extract_email_address(raw_from)


class InboxCleaner(BaseAgent):
    name = "inbox_cleaner"

    async def _run_logic(self) -> str:

        check_gmail_token()

        # ── Load config from .env ─────────────────────────────────────────────
        whitelist_raw = os.getenv("INBOX_CLEANER_WHITELIST", "")
        whitelist = {
            e.strip().lower()
            for e in whitelist_raw.split(",")
            if e.strip()
        }

        permanent_delete = os.getenv(
            "INBOX_CLEANER_PERMANENT_DELETE", "false"
        ).lower() == "true"

        service    = _get_gmail_service()
        today      = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now        = datetime.now(timezone.utc)

        trashed_count    = 0
        whitelisted_count = 0
        # sender_map: email → {display_name, email, count, subjects[], last_seen}
        sender_map: dict = {}

        # ── 1. Fetch all emails in CATEGORY_PROMOTIONS ────────────────────────
        logger.info("[InboxCleaner] Fetching Promotions label emails...")

        page_token = None
        all_messages = []

        while True:
            kwargs = {
                "userId":    "me",
                "labelIds":  ["CATEGORY_PROMOTIONS"],
                "maxResults": 500,
            }
            if page_token:
                kwargs["pageToken"] = page_token

            result = service.users().messages().list(**kwargs).execute()
            msgs   = result.get("messages", [])
            all_messages.extend(msgs)

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        if not all_messages:
            logger.info("[InboxCleaner] No promotional emails found — inbox clean!")
            return "No promotional emails found"

        logger.info(f"[InboxCleaner] Found {len(all_messages)} promotional emails")

        # ── 2. Build sender report + move to trash ────────────────────────────
        for msg in all_messages:
            try:
                full = service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject"]
                ).execute()

                headers = {
                    h["name"]: h["value"]
                    for h in full["payload"]["headers"]
                }
                raw_from     = headers.get("From", "")
                subject      = headers.get("Subject", "(no subject)")
                sender_email = _extract_email_address(raw_from)
                display_name = _extract_display_name(raw_from)

                # ── Track sender stats for the report ────────────────────────
                if sender_email not in sender_map:
                    sender_map[sender_email] = {
                        "display_name": display_name,
                        "email":        sender_email,
                        "count":        0,
                        "subjects":     [],
                        "whitelisted":  sender_email in whitelist,
                    }
                sender_map[sender_email]["count"] += 1
                if len(sender_map[sender_email]["subjects"]) < 3:
                    sender_map[sender_email]["subjects"].append(subject)

                # ── Decide action ─────────────────────────────────────────────
                if sender_email in whitelist:
                    action = "whitelisted"
                    whitelisted_count += 1
                    logger.debug(
                        f"[InboxCleaner] Skipping whitelisted: {sender_email}"
                    )
                else:
                    # Move to trash (or permanent delete if flag set)
                    if permanent_delete:
                        service.users().messages().delete(
                            userId="me", id=msg["id"]
                        ).execute()
                        action = "deleted"
                    else:
                        service.users().messages().trash(
                            userId="me", id=msg["id"]
                        ).execute()
                        action = "trashed"
                    trashed_count += 1

                # ── Save to DB ────────────────────────────────────────────────
                with get_conn() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO inbox_cleaner_log"
                        " (run_date, sender, sender_email, subject,"
                        "  gmail_id, action, cleaned_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            today, display_name, sender_email,
                            subject[:200], msg["id"], action, now
                        )
                    )
                    conn.commit()

            except Exception as e:
                logger.warning(
                    f"[InboxCleaner] Error processing msg {msg['id']}: {e}"
                )
                continue

        logger.info(
            f"[InboxCleaner] Done — trashed: {trashed_count}, "
            f"whitelisted: {whitelisted_count}, "
            f"unique senders: {len(sender_map)}"
        )

        # ── 3. Send summary email ─────────────────────────────────────────────
        await self._send_summary_email(
            trashed_count, whitelisted_count, sender_map, today
        )

        return (
            f"Trashed {trashed_count} promo emails · "
            f"{len(sender_map)} unique senders · "
            f"{whitelisted_count} whitelisted"
        )

    async def _send_summary_email(
        self,
        trashed:      int,
        whitelisted:  int,
        sender_map:   dict,
        run_date:     str,
    ):
        """Builds and sends the daily InboxCleaner summary email."""

        # Sort senders by email count descending
        sorted_senders = sorted(
            sender_map.values(), key=lambda x: x["count"], reverse=True
        )

        sender_rows = ""
        for s in sorted_senders:
            wl_badge = (
                '<span style="background:#d1fae5;color:#065f46;'
                'padding:2px 8px;border-radius:10px;font-size:10px">'
                '✓ whitelisted</span>'
                if s["whitelisted"]
                else '<span style="background:#fee2e2;color:#991b1b;'
                'padding:2px 8px;border-radius:10px;font-size:10px">'
                '✗ unsubscribe?</span>'
            )
            sample_subjects = "<br>".join(
                f'<span style="color:#6b7280;font-size:11px">— {sub}</span>'
                for sub in s["subjects"]
            )
            sender_rows += f"""
            <tr style="border-bottom:1px solid #f3f4f6">
                <td style="padding:8px 12px;font-weight:600;color:#1f2937">
                    {s['display_name']}<br>
                    <span style="font-weight:400;font-size:11px;
                                 color:#9ca3af">{s['email']}</span>
                </td>
                <td style="padding:8px 12px;text-align:center;
                           font-weight:700;color:#6366f1">{s['count']}</td>
                <td style="padding:8px 12px">{wl_badge}</td>
                <td style="padding:8px 12px">{sample_subjects}</td>
            </tr>
            """

        content = f"""
        <div style="background:#ecfdf5;border-left:4px solid #10b981;
                    padding:14px;border-radius:6px;margin-bottom:20px">
            <h3 style="margin:0;color:#065f46">
                🗑 {trashed} promotional emails moved to Trash
            </h3>
            <p style="margin:6px 0 0;color:#047857;font-size:13px">
                {whitelisted} emails kept (whitelisted) ·
                {len(sender_map)} unique senders found
            </p>
        </div>

        <div style="background:#eff6ff;border-left:4px solid #3b82f6;
                    padding:12px;border-radius:6px;margin-bottom:20px;
                    font-size:12px;color:#1e40af">
            💡 Review the list below on your dashboard and decide
            who to unsubscribe from. Add senders to
            <code>INBOX_CLEANER_WHITELIST</code> in your .env to keep
            their emails in future.
        </div>

        <h3 style="color:#1f2937;margin-bottom:12px">
            📋 Sender Report — {run_date}
        </h3>
        <table style="width:100%;border-collapse:collapse;
                      border:1px solid #e5e7eb;border-radius:6px">
            <thead>
                <tr style="background:#f9fafb">
                    <th style="padding:8px 12px;text-align:left;
                               color:#374151;font-size:11px">Sender</th>
                    <th style="padding:8px 12px;text-align:center;
                               color:#374151;font-size:11px">Count</th>
                    <th style="padding:8px 12px;text-align:left;
                               color:#374151;font-size:11px">Status</th>
                    <th style="padding:8px 12px;text-align:left;
                               color:#374151;font-size:11px">Recent Subjects</th>
                </tr>
            </thead>
            <tbody>{sender_rows}</tbody>
        </table>
        """

        html = build_email_wrapper(
            "InboxCleaner — Promotions Report",
            content,
            "InboxCleaner"
        )
        send_html_email(
            f"🗑 InboxCleaner — {trashed} emails trashed · {run_date}",
            html
        )
        logger.info("[InboxCleaner] Summary email sent")
