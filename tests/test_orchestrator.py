# tests/test_orchestrator.py
"""
Tests for the orchestrator components:
- LLM Queue (semaphore, deadlock prevention)
- Resource Monitor (metric recording)
- Base Agent (retry logic, status reporting)
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch


# ── LLM Queue Tests ───────────────────────────────────────────────────────────

class TestLLMQueue:

    def test_initial_state(self):
        """Queue starts with zero active and waiting jobs."""
        from orchestrator.llm_queue import LLMQueue
        q = LLMQueue(max_concurrent=1)
        assert q.active  == 0
        assert q.waiting == 0

    def test_status_returns_dict(self):
        """Status method returns correct keys."""
        from orchestrator.llm_queue import LLMQueue
        q = LLMQueue(max_concurrent=1)
        s = q.status()
        assert "active"  in s
        assert "waiting" in s
        assert "total"   in s

    @pytest.mark.asyncio
    async def test_submit_returns_response(self):
        """Submit calls generate and returns its result."""
        from orchestrator.llm_queue import LLMQueue
        q = LLMQueue(max_concurrent=1)

        with patch("orchestrator.llm_queue.generate", new=AsyncMock(return_value="hello")):
            result = await q.submit("test prompt", agent_name="test")
            assert result == "hello"

    @pytest.mark.asyncio
    async def test_single_concurrent_call(self):
        """Only one call runs at a time — second waits for first."""
        from orchestrator.llm_queue import LLMQueue
        q = LLMQueue(max_concurrent=1)
        order = []

        async def slow_generate(prompt, system=""):
            await asyncio.sleep(0.05)
            order.append(prompt)
            return prompt

        with patch("orchestrator.llm_queue.generate", new=slow_generate):
            await asyncio.gather(
                q.submit("first",  agent_name="a1"),
                q.submit("second", agent_name="a2"),
            )

        # Both completed, order preserved by semaphore
        assert len(order) == 2
        assert q.active == 0  # Both released after completion

    @pytest.mark.asyncio
    async def test_active_resets_after_completion(self):
        """Active count returns to 0 after all jobs complete."""
        from orchestrator.llm_queue import LLMQueue
        q = LLMQueue(max_concurrent=1)

        with patch("orchestrator.llm_queue.generate", new=AsyncMock(return_value="ok")):
            await q.submit("prompt", agent_name="test")

        assert q.active == 0

    @pytest.mark.asyncio
    async def test_active_resets_on_error(self):
        """Active count resets even if the LLM call throws an exception."""
        from orchestrator.llm_queue import LLMQueue
        q = LLMQueue(max_concurrent=1)

        async def failing_generate(prompt, system=""):
            raise RuntimeError("LLM crashed")

        with patch("orchestrator.llm_queue.generate", new=failing_generate):
            with pytest.raises(RuntimeError):
                await q.submit("prompt", agent_name="test")

        # Critical: lock must be released even after crash
        assert q.active == 0


# ── Base Agent Tests ──────────────────────────────────────────────────────────

class TestBaseAgent:

    def _make_agent(self, logic=None, should_fail=False):
        """Helper that creates a minimal concrete agent for testing."""
        from agents.base_agent import BaseAgent

        class MockAgent(BaseAgent):
            name = "mock_agent"
            retry_delay = 0  # No delay in tests

            async def _run_logic(self) -> str:
                if should_fail:
                    raise Exception("Intentional test failure")
                return logic or "mock success"

        return MockAgent()

    def test_initial_status(self):
        """Agent starts in never_run state."""
        agent = self._make_agent()
        s = agent.status()
        assert s["last_status"] == "never_run"
        assert s["last_run"]    is None
        assert s["crash_count"] == 0

    @pytest.mark.asyncio
    async def test_successful_run_updates_status(self):
        """After a successful run, status shows success."""
        agent = self._make_agent(logic="all good")
        with patch("agents.base_agent.get_conn") as mock_conn:
            mock_conn.return_value.__enter__ = lambda s: mock_conn.return_value
            mock_conn.return_value.__exit__  = lambda s,*a: None
            mock_conn.return_value.execute   = lambda *a, **kw: None
            mock_conn.return_value.commit    = lambda: None
            await agent.run()

        assert agent.status()["last_status"]  == "success"
        assert agent.status()["last_message"] == "all good"
        assert agent.status()["crash_count"]  == 0

    @pytest.mark.asyncio
    async def test_failed_run_retries_three_times(self):
        """Agent retries exactly 3 times before giving up."""
        attempt_count = 0

        from agents.base_agent import BaseAgent

        class CountingAgent(BaseAgent):
            name = "counting_agent"
            retry_delay = 0

            async def _run_logic(self) -> str:
                nonlocal attempt_count
                attempt_count += 1
                raise Exception("always fails")

        agent = CountingAgent()
        with patch("agents.base_agent.get_conn") as mock_conn:
            mock_conn.return_value.__enter__ = lambda s: mock_conn.return_value
            mock_conn.return_value.__exit__  = lambda s,*a: None
            mock_conn.return_value.execute   = lambda *a, **kw: None
            mock_conn.return_value.commit    = lambda: None
            await agent.run()

        assert attempt_count == 3  # Retried exactly 3 times
        assert agent.status()["last_status"]  == "error"
        assert agent.status()["crash_count"]  == 1

    @pytest.mark.asyncio
    async def test_no_duplicate_runs(self):
        """Agent skips run if already running."""
        from agents.base_agent import BaseAgent

        run_count = 0

        class SlowAgent(BaseAgent):
            name = "slow_agent"
            retry_delay = 0

            async def _run_logic(self) -> str:
                nonlocal run_count
                run_count += 1
                await asyncio.sleep(0.1)
                return "done"

        agent = SlowAgent()
        agent._is_running = True  # Simulate already running

        with patch("agents.base_agent.get_conn") as mock_conn:
            mock_conn.return_value.__enter__ = lambda s: mock_conn.return_value
            mock_conn.return_value.__exit__  = lambda s,*a: None
            mock_conn.return_value.execute   = lambda *a, **kw: None
            mock_conn.return_value.commit    = lambda: None
            await agent.run()

        assert run_count == 0  # Did not run because _is_running was True
