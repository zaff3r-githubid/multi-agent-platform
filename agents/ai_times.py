# agents/ai_times.py
import httpx
import os
import logging
from datetime import datetime, timedelta, timezone
from agents.base_agent import BaseAgent
from orchestrator.llm_queue import llm_queue
from utils.email_sender import send_html_email, build_email_wrapper
from database.db import get_conn
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root regardless of where Python is run from
load_dotenv(Path(__file__).parent.parent / ".env")
logger = logging.getLogger(__name__)

# Read at runtime inside the class, not at import time
YT_SEARCH  = "https://www.googleapis.com/youtube/v3/search"

# ── Search queries ─────────────────────────────────────────────────────────
# Two separate queries to get two distinct categories as required
NEWS_QUERY        = "artificial intelligence news today 2026"
PERSONALITY_QUERY = "artificial intelligence interview podcast researcher"


class AITimes(BaseAgent):
    name = "ai_times"

    async def _fetch_videos(
        self,
        client: httpx.AsyncClient,
        query: str,
        category: str,
        max_results: int = 5,
        api_key: str = None
    ) -> list:
        """
        Fetches videos from YouTube Data API v3.
        
        Args:
            query:       Search term to send to YouTube
            category:    'news' or 'personality' — stored in DB for filtering
            max_results: How many videos to fetch (5 for each category)
            
        Returns:
            List of video dicts with id, title, channel, thumbnail, url
        """
        # published_after = 96 hours ago (gives more results than 24h)
        since = (
            datetime.now(timezone.utc) - timedelta(hours=96)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            r = await client.get(YT_SEARCH, params={
                "key":            api_key,
                "q":              query,
                "part":           "snippet",
                "type":           "video",
                "order":          "relevance",
                "publishedAfter": since,
                "maxResults":     max_results,
                "relevanceLanguage": "en",
            })
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception as e:
            logger.error(f"[AITimes] YouTube fetch failed for '{query}': {e}")
            return []

        videos = []
        for item in items:
            vid_id  = item["id"].get("videoId")
            if not vid_id:
                continue
            snippet = item["snippet"]
            videos.append({
                "video_id":  vid_id,
                "title":     snippet.get("title", ""),
                "channel":   snippet.get("channelTitle", ""),
                "thumbnail": snippet["thumbnails"].get("medium", {}).get("url", ""),
                "url":       f"https://www.youtube.com/watch?v={vid_id}",
                "category":  category,
            })

        logger.info(f"[AITimes] Fetched {len(videos)} {category} videos")
        return videos

    async def _run_logic(self) -> str:

        # Read API key at runtime — ensures .env is loaded first
        YT_API_KEY = os.getenv("YOUTUBE_API_KEY")

        if not YT_API_KEY or YT_API_KEY == "your_youtube_api_key_here":
            raise ValueError("YOUTUBE_API_KEY not set in .env")

        async with httpx.AsyncClient(timeout=30) as client:

            # ── 1. Fetch both categories ──────────────────────────────────────
            news_videos = await self._fetch_videos(
                client, NEWS_QUERY, "news", max_results=5, api_key=YT_API_KEY
            )
            personality_videos = await self._fetch_videos(
                client, PERSONALITY_QUERY, "personality", max_results=5, api_key=YT_API_KEY
            )

        all_videos = news_videos + personality_videos

        if not all_videos:
            return "No videos found — check YouTube API key"

        # ── 2. Generate LLM blurbs + save to DB ──────────────────────────────
        now = datetime.utcnow()
        processed = []

        with get_conn() as conn:
            for video in all_videos:
                # Check if already in database (avoid duplicates)
                existing = conn.execute(
                    "SELECT id FROM videos WHERE video_id=?",
                    (video["video_id"],)
                ).fetchone()

                if existing:
                    # Already suggested before — skip entirely
                    # This prevents the same video appearing in future emails/dashboard
                    logger.info(
                        f"[AITimes] Skipping already-seen video: {video['title'][:50]}"
                    )
                    continue

                # Generate blurb with Qwen3
                blurb = await llm_queue.submit(
                    prompt=(
                        f"YouTube video title: \"{video['title']}\"\n"
                        f"Channel: {video['channel']}\n"
                        f"Category: {video['category']}\n\n"
                        "Write exactly 1 sentence explaining why this video matters "
                        "for someone following AI developments. Be specific and insightful."
                    ),
                    system="You are an AI research analyst curating content for professionals.",
                    agent_name=self.name
                )

                video["blurb"] = blurb

                # Save to database
                conn.execute(
                    "INSERT OR IGNORE INTO videos"
                    " (video_id, title, channel, thumbnail, url, category, blurb, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        video["video_id"], video["title"], video["channel"],
                        video["thumbnail"], video["url"], video["category"],
                        blurb, now
                    )
                )
                processed.append(video)

            conn.commit()

        # ── 3. Split back into categories for email ───────────────────────────
        news_final        = [v for v in processed if v.get("category") == "news"]
        personality_final = [v for v in processed if v.get("category") == "personality"]

        # ── 4. Build HTML email ───────────────────────────────────────────────
        def video_card(v: dict) -> str:
            """Builds one video card for the email."""
            return f"""
            <div style="margin-bottom:20px;padding:16px;border:1px solid #e5e7eb;
                        border-radius:8px;background:#ffffff">
                <div style="display:flex;gap:14px;align-items:flex-start">
                    <img src="{v.get('thumbnail','')}"
                         style="width:140px;height:80px;object-fit:cover;
                                border-radius:6px;flex-shrink:0">
                    <div>
                        <a href="{v.get('url','')}" style="font-size:14px;font-weight:700;
                           color:#1a1d27;text-decoration:none">
                            {v.get('title','')}
                        </a>
                        <div style="color:#6b7280;font-size:12px;margin:4px 0">
                            {v.get('channel','')}
                        </div>
                        <div style="color:#374151;font-size:13px;margin-top:6px;
                                    line-height:1.5">
                            {v.get('blurb','')}
                        </div>
                    </div>
                </div>
            </div>
            """

        news_cards        = "".join(video_card(v) for v in news_final)
        personality_cards = "".join(video_card(v) for v in personality_final)

        content = f"""
        <div style="margin-bottom:28px">
            <h2 style="color:#1a1d27;border-bottom:3px solid #60a5fa;
                       padding-bottom:8px;margin-bottom:16px">
                📰 AI News Videos
            </h2>
            <p style="color:#6b7280;font-size:13px;margin-bottom:16px">
                Latest AI news from the past 48 hours
            </p>
            {news_cards if news_cards else "<p style='color:#9ca3af'>No news videos found today.</p>"}
        </div>

        <div>
            <h2 style="color:#1a1d27;border-bottom:3px solid #a78bfa;
                       padding-bottom:8px;margin-bottom:16px">
                🎙️ AI Personality & Interview Videos
            </h2>
            <p style="color:#6b7280;font-size:13px;margin-bottom:16px">
                Conversations with AI researchers, founders, and thought leaders
            </p>
            {personality_cards if personality_cards else "<p style='color:#9ca3af'>No personality videos found today.</p>"}
        </div>
        """

        html = build_email_wrapper(
            "AI-Times — Daily Video Digest",
            content,
            "AI-Times"
        )

        send_html_email("🤖 AI-Times — Daily Video Digest", html)

        return (
            f"Fetched {len(news_final)} news + "
            f"{len(personality_final)} personality videos, sent digest"
        )