# utils/gmail_auth.py
"""
Run this script ONCE to authorise Gmail access.
It opens a browser window, you log in and grant permission,
and it saves a token.json file for future use.
After that, Mailman uses token.json automatically — no re-authorisation needed.
"""
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path

# These scopes define what we're allowed to do with Gmail
# gmail.modify = read emails, apply labels, star messages
# We do NOT request gmail.send — Mailman reads only, email sending uses SMTP
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def authorise():
    creds_path = Path(__file__).parent.parent / "credentials.json"
    token_path = Path(__file__).parent.parent / "token.json"

    if not creds_path.exists():
        print("ERROR: credentials.json not found in project root!")
        print("Follow the Gmail OAuth setup in PROGRESS.md first.")
        return

    print("Opening browser for Gmail authorisation...")
    print("Sign in with the Gmail account you want Mailman to monitor.")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(creds_path), SCOPES
    )
    creds = flow.run_local_server(port=0)

    with open(token_path, "w") as f:
        f.write(creds.to_json())

    print(f"token.json created at {token_path}")
    print("Mailman is now authorised!")

if __name__ == "__main__":
    authorise()