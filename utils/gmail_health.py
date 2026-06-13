"""
Lightweight Gmail token health-check.

Call check_gmail_token() before any agent that uses the Gmail API.
It makes a single cheap API call (getProfile) and raises a clear
RuntimeError if the token is expired or revoked, rather than letting
the agent crash mid-run with a cryptic OAuth error.
"""

import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN_PATH = Path(__file__).parent.parent / "token.json"

REAUTH_MSG = (
    "Gmail token is expired or revoked. "
    "Re-authenticate by running:  python utils/gmail_auth.py"
)


def check_gmail_token() -> None:
    """
    Verifies the Gmail token is valid before an agent run.
    Raises RuntimeError with a clear re-auth instruction if not.
    """
    if not TOKEN_PATH.exists():
        raise RuntimeError(
            "token.json not found. Run:  python utils/gmail_auth.py"
        )

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

        # Try to refresh if expired
        if creds.expired and creds.refresh_token:
            logger.info("[GmailHealth] Token expired — attempting refresh...")
            creds.refresh(Request())
            # Save refreshed token
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
            logger.info("[GmailHealth] Token refreshed successfully.")

        # Cheap API call to confirm the token actually works
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        service.users().getProfile(userId="me").execute()
        logger.info("[GmailHealth] Gmail token OK.")

    except RefreshError as e:
        logger.error(f"[GmailHealth] Token refresh failed: {e}")
        raise RuntimeError(REAUTH_MSG) from e

    except HttpError as e:
        logger.error(f"[GmailHealth] Gmail API error during health check: {e}")
        raise RuntimeError(REAUTH_MSG) from e

    except Exception as e:
        logger.error(f"[GmailHealth] Unexpected error during token check: {e}")
        raise RuntimeError(REAUTH_MSG) from e
