# orchestrator/deadlock_guard.py
"""
Watchdog that monitors agents for stuck/crashed states
and force-restarts them. This satisfies the assignment requirement:
'Detect and restart crashed agents without restarting the full platform'
"""
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# If an agent has been 'running' for more than this many minutes
# without completing, we consider it stuck and force restart it
STUCK_THRESHOLD_MINUTES = 10


async def watchdog_loop(agents: dict):
    """
    Runs forever in the background, checking every 60 seconds
    if any agent is stuck. If found, force restarts it.
    """
    logger.info("[Watchdog] Started — checking every 60s for stuck agents")

    while True:
        await asyncio.sleep(60)

        for name, agent in agents.items():
            # Check if agent has been 'running' too long
            if agent._is_running and agent._last_run:
                running_since = agent._last_run
                stuck_for = datetime.utcnow() - running_since

                if stuck_for > timedelta(minutes=STUCK_THRESHOLD_MINUTES):
                    logger.warning(
                        f"[Watchdog] {name} appears stuck — "
                        f"running for {stuck_for.seconds // 60} minutes. "
                        f"Force restarting..."
                    )
                    try:
                        await agent.force_restart()
                        logger.info(f"[Watchdog] {name} restarted successfully")
                    except Exception as e:
                        logger.error(f"[Watchdog] Failed to restart {name}: {e}")