# agents/wallstreet_wolf.py
import yfinance as yf
import httpx
import logging
from datetime import datetime
from agents.base_agent import BaseAgent
from orchestrator.llm_queue import llm_queue
from utils.email_sender import send_html_email, build_email_wrapper
from database.db import get_conn
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# ── Watchlist ─────────────────────────────────────────────────────────────────
TICKERS = {
    "Tech":    ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD"],
    "Finance": ["JPM", "GS", "BAC", "V", "MA"],
    "Energy":  ["XOM", "CVX", "NEE", "BP"],
    "Index":   ["SPY", "QQQ", "DIA", "IWM", "VTI"],
}
ALL_TICKERS = [t for group in TICKERS.values() for t in group]

# ── Currency pairs ────────────────────────────────────────────────────────────
FX_PAIRS = {
    "USD/CAD": "CAD=X",
    "USD/EUR": "EUR=X",
    "USD/GBP": "GBP=X",
    "USD/JPY": "JPY=X",
    "USD/PKR": "PKR=X",
}

# ── Precious metals ───────────────────────────────────────────────────────────
METALS = {
    "Gold":   "GC=F",
    "Silver": "SI=F",
}


class WallstreetWolf(BaseAgent):
    name = "wallstreet_wolf"

    async def _run_logic(self) -> str:

        # ── 1. Fetch stock data ───────────────────────────────────────────────
        logger.info("[WallstreetWolf] Fetching stock data...")
        raw = yf.download(ALL_TICKERS, period="2d", progress=False, auto_adjust=True)

        close  = raw["Close"]
        volume = raw["Volume"]

        # Calculate % change from previous close
        change = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100).round(2)
        prices = close.iloc[-1].round(2)

        # ── 2. Fetch FX rates ─────────────────────────────────────────────────
        logger.info("[WallstreetWolf] Fetching FX rates...")
        fx_data = {}
        for pair_name, symbol in FX_PAIRS.items():
            try:
                ticker = yf.Ticker(symbol)
                hist   = ticker.history(period="2d")
                if len(hist) >= 2:
                    rate       = round(hist["Close"].iloc[-1], 4)
                    prev_rate  = round(hist["Close"].iloc[-2], 4)
                    fx_change  = round((rate - prev_rate) / prev_rate * 100, 2)
                    fx_data[pair_name] = {"rate": rate, "change": fx_change}
                else:
                    fx_data[pair_name] = {"rate": 0, "change": 0}
            except Exception as e:
                logger.warning(f"FX fetch failed for {pair_name}: {e}")
                fx_data[pair_name] = {"rate": 0, "change": 0}

        # ── 3. Fetch metals ───────────────────────────────────────────────────
        logger.info("[WallstreetWolf] Fetching metals...")
        metals_data = {}
        for metal_name, symbol in METALS.items():
            try:
                ticker = yf.Ticker(symbol)
                hist   = ticker.history(period="2d")
                if len(hist) >= 2:
                    price      = round(hist["Close"].iloc[-1], 2)
                    prev_price = round(hist["Close"].iloc[-2], 2)
                    chg        = round((price - prev_price) / prev_price * 100, 2)
                    metals_data[metal_name] = {"price": price, "change": chg}
                else:
                    metals_data[metal_name] = {"price": 0, "change": 0}
            except Exception as e:
                logger.warning(f"Metals fetch failed for {metal_name}: {e}")
                metals_data[metal_name] = {"price": 0, "change": 0}

        # ── 4. Save stocks to database ────────────────────────────────────────
        now = datetime.utcnow()
        with get_conn() as conn:
            for ticker in ALL_TICKERS:
                try:
                    conn.execute(
                        "INSERT INTO stocks (ticker, price, change_pct, volume, fetched_at)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (
                            ticker,
                            float(prices.get(ticker, 0)),
                            float(change.get(ticker, 0)),
                            int(volume.iloc[-1].get(ticker, 0)),
                            now,
                        )
                    )
                except Exception as e:
                    logger.warning(f"DB insert failed for {ticker}: {e}")
            conn.commit()

        # ── 5. Find top 5 gainers and losers ─────────────────────────────────
        change_dict = {t: float(change.get(t, 0)) for t in ALL_TICKERS}
        sorted_tickers = sorted(change_dict.items(), key=lambda x: x[1])

        top_losers  = sorted_tickers[:5]       # 5 worst performers
        top_gainers = sorted_tickers[-5:][::-1] # 5 best performers

        # ── 6. Ask Qwen3 for market commentary ───────────────────────────────
        logger.info("[WallstreetWolf] Requesting LLM commentary...")
        mover_lines = "\n".join(
            [f"{t}: {v:+.2f}%" for t, v in top_gainers + top_losers]
        )
        commentary = await llm_queue.submit(
            prompt=(
                f"Today's top stock movers:\n{mover_lines}\n\n"
                "Write a concise 3-sentence market commentary for a daily briefing email. "
                "Mention the biggest gainer and biggest loser. "
                "Suggest one possible reason for each move. "
                "Keep it factual and professional. No bullet points."
            ),
            system="You are a professional financial analyst writing a daily market brief.",
            agent_name=self.name
        )

        # ── 7. Build HTML email ───────────────────────────────────────────────
        def color(val):
            return "color:#22c55e" if val >= 0 else "color:#ef4444"

        def arrow(val):
            return "▲" if val >= 0 else "▼"

        # Block 1 — Top 5 Gainers
        gainers_rows = "".join(
            f"<tr>"
            f"<td><b>{t}</b></td>"
            f"<td>${prices.get(t, 0):.2f}</td>"
            f"<td style='{color(v)}'>{arrow(v)} {abs(v):.2f}%</td>"
            f"</tr>"
            for t, v in top_gainers
        )

        # Block 2 — Top 5 Losers
        losers_rows = "".join(
            f"<tr>"
            f"<td><b>{t}</b></td>"
            f"<td>${prices.get(t, 0):.2f}</td>"
            f"<td style='{color(v)}'>{arrow(v)} {abs(v):.2f}%</td>"
            f"</tr>"
            for t, v in top_losers
        )

        # Block 3 — Full Watchlist
        watchlist_rows = "".join(
            f"<tr>"
            f"<td><b>{t}</b></td>"
            f"<td>${prices.get(t, 0):.2f}</td>"
            f"<td style='{color(change_dict.get(t,0))}'>"
            f"{arrow(change_dict.get(t,0))} {abs(change_dict.get(t,0)):.2f}%</td>"
            f"</tr>"
            for t in ALL_TICKERS
        )

        # FX rows
        fx_rows = "".join(
            f"<tr>"
            f"<td><b>{pair}</b></td>"
            f"<td>{d['rate']}</td>"
            f"<td style='{color(d['change'])}'>{arrow(d['change'])} {abs(d['change']):.2f}%</td>"
            f"</tr>"
            for pair, d in fx_data.items()
        )

        # Metals rows
        metals_rows = "".join(
            f"<tr>"
            f"<td><b>{metal}</b></td>"
            f"<td>${d['price']:,.2f}</td>"
            f"<td style='{color(d['change'])}'>{arrow(d['change'])} {abs(d['change']):.2f}%</td>"
            f"</tr>"
            for metal, d in metals_data.items()
        )

        table_style = (
            "width:100%;border-collapse:collapse;font-family:monospace;"
            "font-size:13px;margin-bottom:24px"
        )
        th_style = (
            "text-align:left;padding:8px;background:#1a1d27;"
            "color:#9ca3af;font-size:11px;text-transform:uppercase"
        )
        td_style = "padding:7px 8px;border-bottom:1px solid #f0f0f0"

        content = f"""
        <div style="background:#f0fdf4;border-left:4px solid #22c55e;
                    padding:16px;border-radius:6px;margin-bottom:24px">
            <p style="margin:0;font-size:14px;color:#166534">{commentary}</p>
        </div>

        <h3 style="color:#22c55e">▲ Top 5 Gainers</h3>
        <table style="{table_style}">
            <tr>
                <th style="{th_style}">Ticker</th>
                <th style="{th_style}">Price</th>
                <th style="{th_style}">Change</th>
            </tr>
            {gainers_rows}
        </table>

        <h3 style="color:#ef4444">▼ Top 5 Losers</h3>
        <table style="{table_style}">
            <tr>
                <th style="{th_style}">Ticker</th>
                <th style="{th_style}">Price</th>
                <th style="{th_style}">Change</th>
            </tr>
            {losers_rows}
        </table>

        <h3 style="color:#60a5fa">Full Watchlist</h3>
        <table style="{table_style}">
            <tr>
                <th style="{th_style}">Ticker</th>
                <th style="{th_style}">Price</th>
                <th style="{th_style}">Change</th>
            </tr>
            {watchlist_rows}
        </table>

        <h3 style="color:#a78bfa">Currency Exchange</h3>
        <table style="{table_style}">
            <tr>
                <th style="{th_style}">Pair</th>
                <th style="{th_style}">Rate</th>
                <th style="{th_style}">Change</th>
            </tr>
            {fx_rows}
        </table>

        <h3 style="color:#fbbf24">Precious Metals</h3>
        <table style="{table_style}">
            <tr>
                <th style="{th_style}">Metal</th>
                <th style="{th_style}">Price (USD/oz)</th>
                <th style="{th_style}">Change</th>
            </tr>
            {metals_rows}
        </table>
        """

        html = build_email_wrapper(
            "Wallstreet Wolf — Daily Market Brief",
            content,
            "Wallstreet Wolf"
        )

        send_html_email("Wallstreet Wolf — Daily Market Brief", html)
        return f"Fetched {len(ALL_TICKERS)} stocks, sent market brief"