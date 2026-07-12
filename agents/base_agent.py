# agents/base_agent.py
import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from database.db import get_conn

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Every agent inherits from this class and only needs to implement
    _run_logic() — all the logging, error handling, crash recovery,
    and status reporting is handled here automatically.
    
    ABC = Abstract Base Class — means you cannot create a BaseAgent
    directly, you must create a subclass (AITimes, Mailman, etc.)
    """

    name: str = "base"          # Each subclass overrides this with its own name
    retry_attempts: int = 3     # How many times to retry after a crash
    retry_delay: int = 5        # Seconds to wait between retry attempts

    # Shared across every agent instance — only one agent's _run_logic()
    # executes at a time, not just their LLM calls.
    _global_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self):
        self._last_run: datetime | None = None
        self._last_status: str = "never_run"
        self._last_message: str = ""
        self._is_running: bool = False
        self._crash_count: int = 0
        # Tracks how many times this agent has crashed
        # If it keeps crashing, we stop retrying to avoid infinite loops

    @abstractmethod
    async def _run_logic(self) -> str:
        """
        THIS is what each agent must implement — their actual job.
        
        @abstractmethod means any class inheriting BaseAgent MUST
        provide its own version of this method or Python raises an error.
        
        Should return a short status message string e.g.:
        "Fetched 10 videos, sent email"
        "Classified 5 emails, 1 urgent"
        """
        ...

    async def run(self):
        """
        Called by the scheduler when it's time for this agent to work.
        
        Wraps _run_logic() with:
        - Duplicate run prevention (won't start if already running)
        - Automatic retry on failure (up to retry_attempts times)
        - Database logging (every run recorded)
        - Error isolation (exceptions don't crash the whole platform)
        """

        # ── Prevent duplicate runs ────────────────────────────────────────────
        if self._is_running:
            logger.warning(f"[{self.name}] already running — skipping this trigger")
            return
        # If the scheduler fires again before the previous run finished,
        # we skip rather than running two copies simultaneously

        self._is_running = True
        started = datetime.now(timezone.utc)
        self._last_status = "running"
        logger.info(f"[{self.name}] starting run")

        # ── Global agent lock ────────────────────────────────────────────────
        # Only one agent's _run_logic() executes at a time across the whole
        # platform — waits here if another agent is mid-run.
        async with BaseAgent._global_lock:
            # ── Retry loop ────────────────────────────────────────────────────
            for attempt in range(1, self.retry_attempts + 1):
                try:
                    message = await self._run_logic()
                    # If we get here, the run succeeded
                    self._last_status = "success"
                    self._last_message = message
                    self._crash_count = 0
                    # Reset crash count on success
                    self._record(started, "success", message)
                    logger.info(f"[{self.name}] success — {message}")
                    break
                    # Break out of retry loop — no need to retry on success

                except Exception as e:
                    logger.error(f"[{self.name}] attempt {attempt}/{self.retry_attempts} failed: {e}")

                    if attempt < self.retry_attempts:
                        # Not the last attempt — wait and retry
                        logger.info(f"[{self.name}] retrying in {self.retry_delay}s...")
                        await asyncio.sleep(self.retry_delay)
                    else:
                        # All attempts exhausted — record as error
                        self._last_status = "error"
                        self._last_message = str(e)
                        self._crash_count += 1
                        self._record(started, "error", str(e))
                        logger.error(f"[{self.name}] all {self.retry_attempts} attempts failed. "
                                     f"Crash count: {self._crash_count}")

        self._last_run = started
        self._is_running = False
        # Always release the running flag so the next scheduled run can proceed

    async def force_restart(self):
        """
        Called by the orchestrator watchdog if this agent appears stuck.
        Resets the running flag and triggers a fresh run.
        This is the 'detect and restart crashed agents' requirement.
        """
        logger.warning(f"[{self.name}] force restart triggered")
        self._is_running = False
        self._last_status = "restarted"
        self._crash_count = 0
        await self.run()

    def status(self) -> dict:
        """
        Returns current agent status — called by the dashboard API
        every 5 seconds to update the agent status panel.
        """
        return {
            "name":          self.name,
            "last_run":      self._last_run.isoformat() if self._last_run else None,
            "last_status":   self._last_status,
            "last_message":  self._last_message,
            "is_running":    self._is_running,
            "crash_count":   self._crash_count,
        }

    def _record(self, started: datetime, status: str, message: str):
        """
        Writes a row to the agent_runs table in SQLite.
        Called after every run (success or failure).
        Private method — only used internally by this class (hence the _ prefix).
        """
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO agent_runs"
                " (agent_name, status, started_at, finished_at, message)"
                " VALUES (?, ?, ?, ?, ?)",
                (self.name, status, started, datetime.now(timezone.utc), message)
            )
            conn.commit()