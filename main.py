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
from database.db import init_db
from orchestrator.llm_queue import llm_queue
from orchestrator.resource_monitor import record_metrics, latest_metrics, metrics_history
from orchestrator.scheduler import create_scheduler
from orchestrator.deadlock_guard import watchdog_loop
from agents.ai_times import AITimes
from agents.mailman import Mailman
from agents.wallstreet_wolf import WallstreetWolf
from agents.arabic_word import ArabicWordAgent

# ── Instantiate all agents ────────────────────────────────────────────────────
AGENTS = {
    "ai_times":       AITimes(),
    "mailman":        Mailman(),
    "wallstreet_wolf": WallstreetWolf(),
    "arabic_word":    ArabicWordAgent(),
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
    return {
        "agents":    [a.status() for a in AGENTS.values()],
        "llm_queue": llm_queue.status(),
        "resources": await latest_metrics(),
    }


@app.get("/api/resources/history")
async def get_resource_history():
    """Returns last 60 resource readings for the dashboard chart."""
    return await metrics_history(60)


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