# orchestrator/llm_queue.py
import asyncio
import logging
from datetime import datetime, timezone
from utils.llm_client import generate_with_usage
from database.db import get_conn

logger = logging.getLogger(__name__)


class LLMQueue:
    """
    Controls access to Qwen3 — only ONE agent can call the model at a time.
    Other agents wait in line. This prevents overload and deadlocks.

    Uses asyncio.Semaphore(1) — the "single key bathroom" pattern.
    Also captures token usage for the AI Observability dashboard.
    """

    def __init__(self, max_concurrent: int = 1):
        self._sem      = asyncio.Semaphore(max_concurrent)
        self._active:  int = 0
        self._waiting: int = 0
        self._total:   int = 0

        # ── Observability counters (in-memory, fast) ──────────────────────
        self._tokens_today:       int   = 0
        self._tokens_lifetime:    int   = 0
        self._last_tokens_per_sec: float = 0.0
        self._last_response_ms:   int   = 0
        self._today_date:         str   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @property
    def active(self) -> int:
        return self._active

    @property
    def waiting(self) -> int:
        return self._waiting

    def _reset_daily_if_needed(self):
        """Resets today's token counter at midnight UTC."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._today_date:
            self._tokens_today = 0
            self._today_date   = today

    async def submit(
        self,
        prompt:     str,
        system:     str = "",
        agent_name: str = "unknown"
    ) -> str:
        """
        Every agent calls this instead of calling generate() directly.
        Waits if LLM is busy, then runs and captures token usage.
        """
        self._waiting += 1
        logger.info(f"[LLM Queue] {agent_name} waiting — queue depth: {self._waiting}")

        async with self._sem:
            self._waiting -= 1
            self._active  += 1
            self._total   += 1
            logger.info(
                f"[LLM Queue] {agent_name} started "
                f"(active={self._active}, total={self._total})"
            )

            try:
                result = await generate_with_usage(prompt, system)

                # ── Capture observability data ────────────────────────────
                self._reset_daily_if_needed()
                self._tokens_today        += result.total_tokens
                self._tokens_lifetime     += result.total_tokens
                self._last_tokens_per_sec  = result.tokens_per_sec
                self._last_response_ms     = result.response_time_ms

                # Persist to database for historical charts
                try:
                    with get_conn() as conn:
                        conn.execute(
                            "INSERT INTO llm_usage"
                            " (agent_name, prompt_tokens, completion_tokens,"
                            "  total_tokens, response_time_ms, tokens_per_sec, called_at)"
                            " VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                agent_name,
                                result.prompt_tokens,
                                result.completion_tokens,
                                result.total_tokens,
                                result.response_time_ms,
                                result.tokens_per_sec,
                                datetime.now(timezone.utc),
                            )
                        )
                        conn.commit()
                except Exception as db_err:
                    # DB logging failure should never crash the agent
                    logger.warning(f"[LLM Queue] Usage DB write failed: {db_err}")

                logger.info(
                    f"[LLM Queue] {agent_name} done — "
                    f"{result.total_tokens} tokens, "
                    f"{result.tokens_per_sec} tok/s, "
                    f"{result.response_time_ms}ms"
                )
                return result.text

            except Exception as e:
                logger.error(f"[LLM Queue] {agent_name} error: {e}")
                raise
            finally:
                self._active -= 1

    def status(self) -> dict:
        """Returns current queue state — used by the dashboard."""
        return {
            "active":  self._active,
            "waiting": self._waiting,
            "total":   self._total,
        }

    def observability(self) -> dict:
        """Returns token usage stats for the AI Observability dashboard."""
        self._reset_daily_if_needed()
        return {
            "tokens_today":        self._tokens_today,
            "tokens_lifetime":     self._tokens_lifetime,
            "last_tokens_per_sec": self._last_tokens_per_sec,
            "last_response_ms":    self._last_response_ms,
        }


# Singleton — one queue controls everything
llm_queue = LLMQueue(max_concurrent=1)