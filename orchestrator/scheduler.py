# orchestrator/scheduler.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def create_scheduler(agents: dict, resource_monitor_fn) -> AsyncIOScheduler:
    """
    Creates and configures the APScheduler with all agent jobs.
    
    APScheduler is a job scheduler — it runs functions at specified
    times or intervals, similar to cron jobs on Linux.
    
    Args:
        agents: dict of name -> agent instance
        resource_monitor_fn: async function called every 30 seconds
        
    Returns:
        Configured scheduler (not yet started — main.py starts it)
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    # ── Resource monitor — every 30 seconds ──────────────────────────────────
    scheduler.add_job(
        resource_monitor_fn,
        IntervalTrigger(seconds=30),
        id="resource_monitor",
        name="Resource Monitor",
        max_instances=1,
        # max_instances=1 prevents overlap if a run takes longer than 30s
    )

    # ── AI-Times — daily at 07:00 UTC ────────────────────────────────────────
    scheduler.add_job(
        agents["ai_times"].run,
        CronTrigger(hour=7, minute=0),
        id="ai_times",
        name="AI-Times",
        max_instances=1,
    )

    # ── Mailman — every 15 minutes ───────────────────────────────────────────
    scheduler.add_job(
        agents["mailman"].run,
        IntervalTrigger(minutes=15),
        id="mailman",
        name="Mailman",
        max_instances=1,
    )

    # ── Wallstreet Wolf — Mon-Fri at 06:30 UTC ───────────────────────────────
    scheduler.add_job(
        agents["wallstreet_wolf"].run,
        CronTrigger(day_of_week="mon-fri", hour=6, minute=30),
        id="wallstreet_wolf",
        name="Wallstreet Wolf",
        max_instances=1,
    )

    # ── Arabic Word of the Day — daily at 08:00 UTC ──────────────────────────
    scheduler.add_job(
        agents["arabic_word"].run,
        CronTrigger(hour=8, minute=0),
        id="arabic_word",
        name="Arabic Word of the Day",
        max_instances=1,
    )

    # ── Weekly recap — every Sunday at 09:00 UTC ─────────────────────────────
    # (the agent checks internally if it's Sunday, this just ensures it runs)
    scheduler.add_job(
        agents["arabic_word"].run,
        CronTrigger(day_of_week="sun", hour=9, minute=0),
        id="arabic_word_weekly",
        name="Arabic Word — Weekly Recap",
        max_instances=1,
    )

    # ── InboxCleaner — daily at 02:00 UTC ────────────────────────────────────
    # Runs at 2am so it cleans overnight promotions before you start your day
    inbox_cleaner_hour = int(
        __import__("os").getenv("INBOX_CLEANER_RUN_HOUR", "2")
    )
    scheduler.add_job(
        agents["inbox_cleaner"].run,
        CronTrigger(hour=inbox_cleaner_hour, minute=0),
        id="inbox_cleaner",
        name="InboxCleaner",
        max_instances=1,
    )

    # ── DB cleanup — daily at midnight ───────────────────────────────────────
    from orchestrator.resource_monitor import cleanup_old_metrics
    scheduler.add_job(
        cleanup_old_metrics,
        CronTrigger(hour=0, minute=0),
        id="db_cleanup",
        name="DB Cleanup",
        max_instances=1,
    )

    logger.info(
        f"Scheduler configured — {len(scheduler.get_jobs())} jobs registered"
    )
    return scheduler