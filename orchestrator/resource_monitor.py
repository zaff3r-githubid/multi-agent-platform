# orchestrator/resource_monitor.py
import asyncio
import psutil
import logging
from datetime import datetime
from database.db import get_conn

logger = logging.getLogger(__name__)

# ── Alarm thresholds ─────────────────────────────────────────────────────────
THRESHOLD = 90.0  # Trigger alarm when any resource exceeds this %

# Suggested corrective actions shown on dashboard when alarm fires
CORRECTIVE_ACTIONS = {
    "cpu": (
        "CPU usage critical! Suggested actions: "
        "1) Check Activity Monitor for runaway processes. "
        "2) Reduce number of concurrent agents. "
        "3) Switch to qwen3:8b for lighter LLM inference."
    ),
    "ram": (
        "RAM usage critical! Suggested actions: "
        "1) Close unused applications. "
        "2) Restart the LM Studio model to free memory. "
        "3) Switch to a smaller Qwen3 model variant."
    ),
    "disk": (
        "Disk usage critical! Suggested actions: "
        "1) Delete old platform.db entries using DB cleanup. "
        "2) Clear system caches in ~/Library/Caches. "
        "3) Move large files to external storage."
    ),
}


async def record_metrics() -> dict:
    """
    Takes a snapshot of system resources and saves to database.
    Called every 30 seconds by the scheduler.
    Returns the metrics dict (also used by the alarm checker).
    """
    cpu   = psutil.cpu_percent(interval=1)
    # interval=1 means measure CPU over 1 second — more accurate than instant snapshot

    ram   = psutil.virtual_memory().percent
    disk  = psutil.disk_usage('/').percent
    threads = psutil.Process().num_threads()
    # num_threads() counts threads in THIS process (our platform)

    now = datetime.utcnow()

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO resource_metrics (cpu_pct, ram_pct, disk_pct, threads, recorded_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (cpu, ram, disk, threads, now)
        )
        conn.commit()

    logger.debug(f"Metrics recorded — CPU:{cpu}% RAM:{ram}% Disk:{disk}% Threads:{threads}")

    metrics = {
        "cpu":     cpu,
        "ram":     ram,
        "disk":    disk,
        "threads": threads,
        "recorded_at": now.isoformat(),
        "alarms":  []   # Will be populated below if thresholds exceeded
    }

    # ── Check thresholds and attach alarm messages ────────────────────────────
    if cpu >= THRESHOLD:
        logger.warning(f"CPU ALARM: {cpu}%")
        metrics["alarms"].append({
            "resource": "cpu",
            "value":    cpu,
            "message":  CORRECTIVE_ACTIONS["cpu"]
        })

    if ram >= THRESHOLD:
        logger.warning(f"RAM ALARM: {ram}%")
        metrics["alarms"].append({
            "resource": "ram",
            "value":    ram,
            "message":  CORRECTIVE_ACTIONS["ram"]
        })

    if disk >= THRESHOLD:
        logger.warning(f"DISK ALARM: {disk}%")
        metrics["alarms"].append({
            "resource": "disk",
            "value":    disk,
            "message":  CORRECTIVE_ACTIONS["disk"]
        })

    return metrics


async def latest_metrics() -> dict:
    """
    Returns the most recent metrics row from the database.
    Called by the dashboard API endpoint every 5 seconds.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT cpu_pct, ram_pct, disk_pct, threads, recorded_at"
            " FROM resource_metrics ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if row:
        return {
            "cpu":        row["cpu_pct"],
            "ram":        row["ram_pct"],
            "disk":       row["disk_pct"],
            "threads":    row["threads"],
            "recorded_at": row["recorded_at"],
        }
    # Return zeros if no data yet (first startup)
    return {"cpu": 0, "ram": 0, "disk": 0, "threads": 0, "recorded_at": None}


async def metrics_history(n: int = 60) -> list:
    """
    Returns the last n readings for the dashboard chart.
    The chart shows a scrolling window of the last 60 readings (30 min of data).
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT cpu_pct, ram_pct, disk_pct, threads, recorded_at"
            " FROM resource_metrics ORDER BY id DESC LIMIT ?",
            (n,)
        ).fetchall()

    # Reverse so oldest is first (left side of chart = oldest)
    return [dict(r) for r in reversed(rows)]


async def cleanup_old_metrics(keep_days: int = 7):
    """
    Deletes metrics older than keep_days to prevent database bloat.
    Called once daily by the scheduler.
    """
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM resource_metrics"
            " WHERE recorded_at < datetime('now', ?)",
            (f"-{keep_days} days",)
        )
        conn.commit()
    logger.info(f"Cleaned up resource metrics older than {keep_days} days")