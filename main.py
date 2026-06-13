# main.py
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

# ── Logging setup ─────────────────────────────────────────────────────────────
# Configure BEFORE any imports that use logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

# ── Project imports ───────────────────────────────────────────────────────────
from database.db import init_db, get_conn
from orchestrator.llm_queue import llm_queue
from orchestrator.resource_monitor import record_metrics, latest_metrics, metrics_history
from orchestrator.scheduler import create_scheduler
from orchestrator.deadlock_guard import watchdog_loop
from agents.ai_times import AITimes
from agents.mailman import Mailman
from agents.wallstreet_wolf import WallstreetWolf
from agents.arabic_word import ArabicWordAgent
from agents.inbox_cleaner import InboxCleaner
from agents.leverage import Leverage

# ── Instantiate all agents ────────────────────────────────────────────────────
AGENTS = {
    "ai_times":       AITimes(),
    "mailman":        Mailman(),
    "wallstreet_wolf": WallstreetWolf(),
    "arabic_word":    ArabicWordAgent(),
    "inbox_cleaner":  InboxCleaner(),
    "leverage":       Leverage(),
}

scheduler = None


# ── Lifespan — runs on startup and shutdown ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Code before 'yield' runs on startup.
    Code after 'yield' runs on shutdown.
    """
    global scheduler

    logger.info("=" * 55)
    logger.info("  Multi-Agent Platform — Starting Up")
    logger.info("=" * 55)

    # 1. Initialise database
    init_db()
    logger.info("Database ready ✓")

    # 2. Start scheduler
    scheduler = create_scheduler(AGENTS, record_metrics)
    scheduler.start()
    logger.info("Scheduler started ✓")

    # 2b. Restore any paused agents from DB
    with get_conn() as conn:
        paused_rows = conn.execute(
            "SELECT agent_name FROM agent_schedule_state WHERE paused=1"
        ).fetchall()
    for row in paused_rows:
        try:
            scheduler.pause_job(row["agent_name"])
            logger.info(f"Restored paused state for: {row['agent_name']}")
        except Exception:
            pass

    # 3. Start watchdog in background
    asyncio.create_task(watchdog_loop(AGENTS))
    logger.info("Watchdog started ✓")

    # 4. Record initial metrics
    await record_metrics()
    logger.info("Resource monitor ready ✓")

    logger.info("=" * 55)
    logger.info("  Dashboard → http://localhost:8000")
    logger.info("=" * 55)

    yield  # App is now running — handle requests

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down...")
    if scheduler:
        scheduler.shutdown(wait=False)
    logger.info("Platform stopped ✓")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Multi-Agent Platform",
    description="5-agent AI automation platform powered by Qwen3",
    lifespan=lifespan
)

# Serve frontend files at /static
app.mount("/static", StaticFiles(directory="frontend"), name="static")


# ── API Routes ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serves the main dashboard HTML page."""
    with open("frontend/index.html") as f:
        return f.read()


@app.get("/api/status")
async def get_status():
    """
    Returns live status of all agents + resources + LLM queue.
    Called by the dashboard every 5 seconds.
    """
    # Build paused lookup from DB
    with get_conn() as conn:
        paused_rows = conn.execute(
            "SELECT agent_name, paused FROM agent_schedule_state"
        ).fetchall()
    paused_map = {r["agent_name"]: bool(r["paused"]) for r in paused_rows}

    agents_status = []
    for a in AGENTS.values():
        s = a.status()
        s["is_paused"] = paused_map.get(a.name, False)
        agents_status.append(s)

    return {
        "agents":    agents_status,
        "llm_queue": llm_queue.status(),
        "resources": await latest_metrics(),
    }


@app.get("/api/resources/history")
async def get_resource_history():
    """Returns last 60 resource readings for the dashboard chart."""
    return await metrics_history(60)


@app.post("/api/agents/{agent_name}/pause")
async def pause_agent(agent_name: str):
    """Pauses the scheduled runs for an agent. Manual 'Run Now' still works."""
    if agent_name not in AGENTS:
        return JSONResponse({"error": f"Agent '{agent_name}' not found"}, status_code=404)
    try:
        scheduler.pause_job(agent_name)
    except Exception as e:
        logger.warning(f"APScheduler pause failed for {agent_name}: {e}")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO agent_schedule_state (agent_name, paused, updated_at)"
            " VALUES (?, 1, datetime('now'))"
            " ON CONFLICT(agent_name) DO UPDATE SET paused=1, updated_at=datetime('now')",
            (agent_name,)
        )
        conn.commit()
    logger.info(f"[Scheduler] {agent_name} paused")
    return {"agent": agent_name, "status": "paused"}


@app.post("/api/agents/{agent_name}/resume")
async def resume_agent(agent_name: str):
    """Resumes the scheduled runs for an agent."""
    if agent_name not in AGENTS:
        return JSONResponse({"error": f"Agent '{agent_name}' not found"}, status_code=404)
    try:
        scheduler.resume_job(agent_name)
    except Exception as e:
        logger.warning(f"APScheduler resume failed for {agent_name}: {e}")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO agent_schedule_state (agent_name, paused, updated_at)"
            " VALUES (?, 0, datetime('now'))"
            " ON CONFLICT(agent_name) DO UPDATE SET paused=0, updated_at=datetime('now')",
            (agent_name,)
        )
        conn.commit()
    logger.info(f"[Scheduler] {agent_name} resumed")
    return {"agent": agent_name, "status": "resumed"}


@app.post("/api/agents/{agent_name}/run")
async def manual_trigger(agent_name: str):
    """
    Manually triggers an agent run immediately.
    Used by the dashboard 'Run' buttons and curl commands.
    """
    if agent_name not in AGENTS:
        return JSONResponse(
            {"error": f"Agent '{agent_name}' not found"},
            status_code=404
        )
    # create_task = run in background, don't wait for it to finish
    asyncio.create_task(AGENTS[agent_name].run())
    return {"message": f"{agent_name} triggered", "status": "running"}


@app.get("/api/observability")
async def get_observability():
    """
    Returns AI token usage stats and cloud cost comparison.
    Powers the AI Observability section on the dashboard.
    """
    from database.db import get_conn
    from datetime import datetime, timezone

    live = llm_queue.observability()

    # ── Per-agent token breakdown (today) ────────────────────────────────────
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_conn() as conn:

        # Per-agent totals for today
        agent_rows = conn.execute(
            "SELECT agent_name,"
            " SUM(total_tokens) as tokens,"
            " AVG(tokens_per_sec) as avg_speed,"
            " AVG(response_time_ms) as avg_ms,"
            " COUNT(*) as calls"
            " FROM llm_usage"
            " WHERE DATE(called_at) = ?"
            " GROUP BY agent_name",
            (today,)
        ).fetchall()

        # Lifetime totals
        lifetime_row = conn.execute(
            "SELECT SUM(total_tokens) as total,"
            " AVG(tokens_per_sec) as avg_speed,"
            " COUNT(*) as total_calls"
            " FROM llm_usage"
        ).fetchone()

        # Last 20 calls for the response time sparkline
        history_rows = conn.execute(
            "SELECT agent_name, total_tokens, tokens_per_sec,"
            " response_time_ms, called_at"
            " FROM llm_usage ORDER BY id DESC LIMIT 20"
        ).fetchall()

    lifetime_tokens = lifetime_row["total"] or 0
    avg_speed       = round(lifetime_row["avg_speed"] or 0, 1)
    total_calls     = lifetime_row["total_calls"] or 0

    # ── Cloud cost comparison (per 1M tokens, combined input+output est.) ────
    # Prices as of 2025 — input/output averaged for simplicity
    CLOUD_PRICES = {
        "GPT-4o":          10.00,
        "GPT-4o Mini":      0.60,
        "Claude Sonnet":    9.00,
        "Claude Haiku":     1.25,
        "Gemini 1.5 Pro":   7.00,
        "Gemini Flash":     0.30,
    }

    tokens_m = lifetime_tokens / 1_000_000  # convert to millions

    cost_comparison = [
        {
            "provider": name,
            "cost_per_million": price,
            "estimated_cost":   round(tokens_m * price, 4),
            "you_saved":        round(tokens_m * price, 4),
        }
        for name, price in CLOUD_PRICES.items()
    ]

    return {
        "live":             live,
        "lifetime_tokens":  lifetime_tokens,
        "avg_speed_tokps":  avg_speed,
        "total_calls":      total_calls,
        "agents_today":     [dict(r) for r in agent_rows],
        "cost_comparison":  cost_comparison,
        "history":          [dict(r) for r in reversed(history_rows)],
    }


@app.get("/api/stocks")
async def get_stocks():
    """Returns latest stock data for the dashboard."""
    from database.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT ticker, price, change_pct, fetched_at FROM stocks"
            " WHERE fetched_at = (SELECT MAX(fetched_at) FROM stocks)"
            " ORDER BY change_pct DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/videos")
async def get_videos():
    """Returns latest YouTube videos for the dashboard."""
    from database.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT video_id, title, channel, thumbnail, url, category, blurb"
            " FROM videos ORDER BY id DESC LIMIT 10"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/emails")
async def get_emails():
    """Returns classified emails for the dashboard."""
    from database.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT sender, subject, classification, ai_summary, classified_at"
            " FROM email_log ORDER BY id DESC LIMIT 20"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/arabic/today")
async def get_arabic_today():
    """Returns today's Arabic word for the dashboard."""
    from database.db import get_conn
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM arabic_words ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else {}


@app.get("/api/arabic/history")
async def get_arabic_history():
    """Returns last 7 Arabic words for the SRS progress view."""
    from database.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, word, transliteration, meaning_en, meaning_ur,"
            " root, srs_box, next_review, fetched_at"
            " FROM arabic_words ORDER BY id DESC LIMIT 7"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/arabic/srs/{word_id}")
async def update_srs(word_id: int, knew_it: bool):
    """
    Updates SRS box for a word from dashboard feedback.
    knew_it=true → move up a box
    knew_it=false → move down a box
    """
    AGENTS["arabic_word"].update_srs(word_id, knew_it)
    return {"message": f"SRS updated for word {word_id}"}


@app.get("/api/alarm")
async def get_alarm():
    """
    Returns current resource alarm status.
    Dashboard polls this to show/hide the alarm banner.
    """
    metrics = await latest_metrics()
    alarms  = []

    THRESHOLD = 90.0
    ACTIONS = {
        "cpu":  "CPU critical! Check Activity Monitor, reduce concurrent agents.",
        "ram":  "RAM critical! Close unused apps or restart LM Studio.",
        "disk": "Disk critical! Delete old files or clear system caches.",
    }

    for key, label in [("cpu", "CPU"), ("ram", "RAM"), ("disk", "Disk")]:
        val = metrics.get(key, 0)
        if val and val >= THRESHOLD:
            alarms.append({
                "resource": label,
                "value":    round(val, 1),
                "action":   ACTIONS[key]
            })

    return {"alarms": alarms}


@app.get("/api/inbox-cleaner/report")
async def get_inbox_cleaner_report():
    """
    Returns the InboxCleaner sender report for the dashboard.
    Shows unique senders, email counts, and whitelist status.
    """
    from database.db import get_conn
    with get_conn() as conn:
        # Latest run date
        latest = conn.execute(
            "SELECT MAX(run_date) as run_date FROM inbox_cleaner_log"
        ).fetchone()
        run_date = latest["run_date"] if latest else None

        # Sender summary — group by sender_email, sum counts
        senders = conn.execute(
            """
            SELECT sender, sender_email,
                   COUNT(*) as email_count,
                   MAX(action) as action,
                   MAX(cleaned_at) as last_seen
            FROM inbox_cleaner_log
            GROUP BY sender_email
            ORDER BY email_count DESC
            """
        ).fetchall()

        # Today's stats
        stats = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN action='trashed'     THEN 1 ELSE 0 END) as trashed,
                SUM(CASE WHEN action='whitelisted' THEN 1 ELSE 0 END) as whitelisted,
                COUNT(DISTINCT sender_email)                           as unique_senders
            FROM inbox_cleaner_log
            WHERE run_date = (SELECT MAX(run_date) FROM inbox_cleaner_log)
            """
        ).fetchone()

    # Fix datetime format for JS — replace space with T so JS Date() parses correctly
    sender_list = []
    for r in senders:
        row = dict(r)
        if row.get("last_seen"):
            row["last_seen"] = str(row["last_seen"]).replace(" ", "T")
        sender_list.append(row)

    return {
        "run_date":  run_date,
        "stats":     dict(stats) if stats else {},
        "senders":   sender_list,
    }


@app.post("/api/arabic/clear")
async def clear_arabic_history():
    """
    Deletes all rows from arabic_words and srs_feedback tables.
    Resets word history and SRS progress so the agent starts fresh.
    """
    from database.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM arabic_words")
        conn.execute("DELETE FROM srs_feedback")
        conn.commit()
    logger.info("[ArabicWord] Word history and SRS progress cleared")
    return {"message": "Arabic word history cleared"}


@app.post("/api/inbox-cleaner/clear")
async def clear_inbox_cleaner_report():
    """Deletes all rows from inbox_cleaner_log — resets the sender report."""
    from database.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM inbox_cleaner_log")
        conn.commit()
    logger.info("[InboxCleaner] Sender report cleared")
    return {"message": "Sender report cleared"}


@app.post("/api/inbox-cleaner/whitelist")
async def whitelist_sender(sender_email: str):
    """
    Adds a sender email to INBOX_CLEANER_WHITELIST in .env
    and updates all their DB records to 'whitelisted'.
    """
    from pathlib import Path

    env_path = Path(".env")

    if not env_path.exists():
        return JSONResponse({"error": ".env file not found"}, status_code=404)

    content = env_path.read_text()
    email   = sender_email.strip().lower()

    # Find existing whitelist line
    lines   = content.splitlines()
    updated = False
    new_lines = []

    for line in lines:
        if line.startswith("INBOX_CLEANER_WHITELIST="):
            current = line.split("=", 1)[1].strip()
            existing_emails = [
                e.strip().lower() for e in current.split(",") if e.strip()
            ]
            if email not in existing_emails:
                existing_emails.append(email)
            new_val = ",".join(existing_emails)
            new_lines.append(f"INBOX_CLEANER_WHITELIST={new_val}")
            updated = True
        else:
            new_lines.append(line)

    # If INBOX_CLEANER_WHITELIST line didn't exist yet, add it
    if not updated:
        new_lines.append(f"INBOX_CLEANER_WHITELIST={email}")

    env_path.write_text("\n".join(new_lines) + "\n")

    # Also update in-memory os.environ so current session respects it immediately
    current_wl = os.getenv("INBOX_CLEANER_WHITELIST", "")
    existing   = [e.strip().lower() for e in current_wl.split(",") if e.strip()]
    if email not in existing:
        existing.append(email)
    os.environ["INBOX_CLEANER_WHITELIST"] = ",".join(existing)

    # Update DB records for this sender to 'whitelisted'
    from database.db import get_conn
    with get_conn() as conn:
        conn.execute(
            "UPDATE inbox_cleaner_log SET action='whitelisted'"
            " WHERE sender_email=?",
            (email,)
        )
        conn.commit()

    logger.info(f"[InboxCleaner] Whitelisted: {email}")
    return {"message": f"{email} added to whitelist", "status": "whitelisted"}


@app.post("/api/inbox-cleaner/unsubscribe")
async def unsubscribe_sender(sender_email: str):
    """
    Finds the List-Unsubscribe header from the most recent email
    from this sender and attempts to unsubscribe programmatically.

    Returns:
      - method: 'one_click' | 'link' | 'mailto' | 'not_found'
      - url: the unsubscribe URL (if method is 'link')
      - message: human-readable result
    """
    import re
    import httpx
    from pathlib import Path
    from database.db import get_conn
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    # ── 1. Find a gmail_id for this sender ───────────────────────────────────
    with get_conn() as conn:
        row = conn.execute(
            "SELECT gmail_id FROM inbox_cleaner_log"
            " WHERE sender_email=? AND gmail_id IS NOT NULL"
            " ORDER BY cleaned_at DESC LIMIT 1",
            (sender_email.strip().lower(),)
        ).fetchone()

    if not row or not row["gmail_id"]:
        return JSONResponse(
            {"method": "not_found",
             "message": "No stored email found for this sender — "
                        "re-run InboxCleaner to refresh"},
            status_code=404
        )

    gmail_id = row["gmail_id"]

    # ── 2. Get Gmail service ──────────────────────────────────────────────────
    token_path = Path("token.json")
    if not token_path.exists():
        return JSONResponse(
            {"method": "not_found", "message": "token.json not found"},
            status_code=500
        )

    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
    creds  = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    # ── 3. Fetch email headers ────────────────────────────────────────────────
    try:
        msg = service.users().messages().get(
            userId="me",
            id=gmail_id,
            format="metadata",
            metadataHeaders=["List-Unsubscribe", "List-Unsubscribe-Post"]
        ).execute()
    except Exception as e:
        return JSONResponse(
            {"method": "not_found",
             "message": f"Could not fetch email from Gmail: {e}"},
            status_code=500
        )

    headers = {
        h["name"].lower(): h["value"]
        for h in msg["payload"]["headers"]
    }

    unsub_header = headers.get("list-unsubscribe", "")
    unsub_post   = headers.get("list-unsubscribe-post", "")

    if not unsub_header:
        return {
            "method":  "not_found",
            "message": "This sender does not include a List-Unsubscribe header. "
                       "You will need to unsubscribe manually from inside the email."
        }

    # Parse URLs and mailto from header value: <https://...>, <mailto:...>
    urls     = re.findall(r'<(https?://[^>]+)>', unsub_header)
    mailto   = re.findall(r'<(mailto:[^>]+)>',   unsub_header)
    http_url = urls[0] if urls else None

    # ── 4. Try one-click unsubscribe (RFC 8058) ───────────────────────────────
    if http_url and "one-click" in unsub_post.lower():
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.post(
                    http_url,
                    data={"List-Unsubscribe": "One-Click"},
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
            if resp.status_code < 400:
                logger.info(
                    f"[InboxCleaner] One-click unsubscribed from {sender_email}"
                )
                return {
                    "method":  "one_click",
                    "message": f"Successfully unsubscribed from {sender_email} "
                               f"using one-click method ✓"
                }
        except Exception as e:
            logger.warning(f"[InboxCleaner] One-click unsubscribe failed: {e}")

    # ── 5. Return HTTP link for browser to open ───────────────────────────────
    if http_url:
        return {
            "method":  "link",
            "url":     http_url,
            "message": f"Click the link to complete unsubscribe from {sender_email}"
        }

    # ── 6. Mailto fallback ────────────────────────────────────────────────────
    if mailto:
        return {
            "method":  "mailto",
            "url":     mailto[0],
            "message": f"Send an email to unsubscribe from {sender_email}"
        }

    return {
        "method":  "not_found",
        "message": "Could not determine unsubscribe method for this sender."
    }


# ── Leverage API ─────────────────────────────────────────────────────────────
@app.get("/api/leverage/videos")
async def get_leverage_videos():
    """Returns Leverage videos grouped by category for the dashboard tab."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT video_id, title, channel, thumbnail, url, category, views, blurb, fetched_at"
            " FROM leverage_videos ORDER BY views DESC, fetched_at DESC"
        ).fetchall()
    grouped = {"tutorial": [], "ranked": [], "money": []}
    for r in rows:
        cat = r["category"]
        if cat in grouped:
            grouped[cat].append({
                "video_id":  r["video_id"],
                "title":     r["title"],
                "channel":   r["channel"],
                "thumbnail": r["thumbnail"],
                "url":       r["url"],
                "views":     r["views"],
                "blurb":     r["blurb"],
                "fetched_at": str(r["fetched_at"]),
            })
    return grouped


@app.post("/api/leverage/clear")
async def clear_leverage_videos():
    """Clears all Leverage videos — resets the seen list so next run fetches fresh content."""
    with get_conn() as conn:
        conn.execute("DELETE FROM leverage_videos")
        conn.commit()
    return {"status": "ok", "message": "Leverage video history cleared"}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("DASHBOARD_PORT", 8000)),
        reload=False,
        log_level="info"
    )