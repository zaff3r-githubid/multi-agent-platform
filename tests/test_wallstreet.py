# tests/test_wallstreet.py
"""
Tests for Wallstreet Wolf agent:
- Ticker configuration
- Data structure validation
- Agent name and inheritance
"""
import pytest
from agents.wallstreet_wolf import WallstreetWolf, ALL_TICKERS, TICKERS, FX_PAIRS, METALS


class TestWallstreetWolfConfig:

    def test_minimum_ticker_count(self):
        """Must track at least 20 stocks as required by assignment."""
        assert len(ALL_TICKERS) >= 20

    def test_ticker_groups_exist(self):
        """All four sector groups must be present."""
        assert "Tech"    in TICKERS
        assert "Finance" in TICKERS
        assert "Energy"  in TICKERS
        assert "Index"   in TICKERS

    def test_key_tickers_present(self):
        """Core stocks must be in the watchlist."""
        assert "AAPL" in TICKERS["Tech"]
        assert "MSFT" in TICKERS["Tech"]
        assert "NVDA" in TICKERS["Tech"]
        assert "JPM"  in TICKERS["Finance"]
        assert "SPY"  in TICKERS["Index"]

    def test_all_tickers_flat_matches_groups(self):
        """ALL_TICKERS must equal the flattened sum of all groups."""
        flat = [t for group in TICKERS.values() for t in group]
        assert sorted(flat) == sorted(ALL_TICKERS)

    def test_no_duplicate_tickers(self):
        """No ticker should appear twice."""
        assert len(ALL_TICKERS) == len(set(ALL_TICKERS))

    def test_fx_pairs_present(self):
        """Currency pairs must be configured."""
        assert len(FX_PAIRS) >= 3
        assert "USD/CAD" in FX_PAIRS
        assert "USD/EUR" in FX_PAIRS

    def test_metals_present(self):
        """Gold and Silver must be configured."""
        assert "Gold"   in METALS
        assert "Silver" in METALS


class TestWallstreetWolfAgent:

    def test_agent_name(self):
        """Agent must identify as wallstreet_wolf."""
        agent = WallstreetWolf()
        assert agent.name == "wallstreet_wolf"

    def test_initial_status(self):
        """Agent starts in never_run state."""
        agent = WallstreetWolf()
        s = agent.status()
        assert s["last_status"]  == "never_run"
        assert s["last_run"]     is None
        assert s["crash_count"]  == 0
        assert s["is_running"]   == False

    def test_inherits_base_agent(self):
        """WallstreetWolf must inherit from BaseAgent."""
        from agents.base_agent import BaseAgent
        assert isinstance(WallstreetWolf(), BaseAgent)

    def test_has_run_logic(self):
        """Agent must implement _run_logic."""
        import asyncio
        agent = WallstreetWolf()
        import inspect
        assert inspect.iscoroutinefunction(agent._run_logic)
