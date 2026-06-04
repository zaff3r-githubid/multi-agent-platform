# orchestrator/llm_queue.py
import asyncio
import logging
from utils.llm_client import generate

logger = logging.getLogger(__name__)

class LLMQueue:
    """
    Controls access to Qwen3 — only ONE agent can call the model at a time.
    Other agents wait in line. This prevents overload and deadlocks.
    
    Uses asyncio.Semaphore(1) — the "single key bathroom" pattern.
    """

    def __init__(self, max_concurrent: int = 1):
        self._sem = asyncio.Semaphore(max_concurrent)
        # Semaphore(1) = only 1 agent can hold the key at a time
        self._active: int = 0      # How many agents are currently using the LLM
        self._waiting: int = 0     # How many agents are waiting in line
        self._total: int = 0       # Total requests processed (lifetime counter)

    @property
    def active(self) -> int:
        return self._active

    @property
    def waiting(self) -> int:
        return self._waiting

    async def submit(self, prompt: str, system: str = "", agent_name: str = "unknown") -> str:
        """
        Every agent calls this instead of calling generate() directly.
        If the LLM is busy, this waits automatically until it's free.
        """
        self._waiting += 1
        logger.info(f"[LLM Queue] {agent_name} waiting — queue depth: {self._waiting}")

        async with self._sem:
            # Once we get here, we have the key — LLM is ours to use
            self._waiting -= 1
            self._active += 1
            self._total += 1
            logger.info(f"[LLM Queue] {agent_name} started (active={self._active}, total={self._total})")

            try:
                result = await generate(prompt, system)
                return result
            except Exception as e:
                logger.error(f"[LLM Queue] {agent_name} error: {e}")
                raise
            finally:
                # ALWAYS release the key — even if an error occurred
                # This prevents deadlocks — the next agent can always proceed
                self._active -= 1
                logger.info(f"[LLM Queue] {agent_name} done (active={self._active})")

    def status(self) -> dict:
        """Returns current queue state — used by the dashboard."""
        return {
            "active":  self._active,
            "waiting": self._waiting,
            "total":   self._total,
        }


# Single shared instance — ALL agents import and use this same object
# This is the Singleton pattern — one queue controls everything
llm_queue = LLMQueue(max_concurrent=1)