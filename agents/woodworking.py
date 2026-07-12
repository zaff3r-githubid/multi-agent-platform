# agents/woodworking.py
"""
Woodworking — Project & Technique Agent

Finds YouTube videos on actual woodworking builds and techniques —
not tool reviews or unboxings. Starting focus: kitchen cabinets
(build, paint, install). Sorted by view count, filtered for recency.

Schedule: weekly (Thursday at 11:00 UTC)
"""

import httpx
import os
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from agents.base_agent import BaseAgent
from orchestrator.llm_queue import llm_queue
from utils.email_sender import send_html_email, build_email_wrapper
from database.db import get_conn
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
logger = logging.getLogger(__name__)

YT_SEARCH = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"

MIN_VIEWS    = 20_000
MAX_AGE_DAYS = 540  # ~18 months
CAP_PER_RUN  = 5

# Excludes tool reviews/unboxings/buying-guides AND design/aesthetic content —
# this agent wants hands-on build process, not gear talk or interior design
EXCLUDE_KEYWORDS = [
    "review", "unboxing", "unbox", "haul", " vs ", "buying guide",
    "which is best", "top 5 tools", "top 10 tools", "best drill", "best saw",
    "design ideas", "kitchen design", "interior design", "decor", "decorating",
    "aesthetic", "trends", "inspiration", "before and after reveal",
    "countertop only", "backsplash ideas",
    "lakh", "crore", "rupee", "₹", "inr",
    "hindi", "telugu", "tamil", "kannada", "marathi", "bengali", "punjabi",
    "urdu", "gujarati", "malayalam", "odia",
    "reaction", "clickbait", "shorts", "#shorts",
]

QUERIES = [
    "how to build cabinet boxes woodworking tutorial",
    "cabinet carcass construction woodworking",
    "face frame cabinet building tutorial woodworking",
    "how to build kitchen cabinets step by step woodworking shop",
    "cabinet door building woodworking tutorial",
    "spray painting cabinets tutorial technique",
    "installing kitchen cabinets step by step tutorial",
]


class Woodworking(BaseAgent):
    name = "woodworking"

    async def _fetch_top_videos(self, client: httpx.AsyncClient, query: str, api_key: str) -> list:
        published_after = (
            datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            r = await client.get(YT_SEARCH, params={
                "key":               api_key,
                "q":                 query,
                "part":              "snippet",
                "type":              "video",
                "order":             "viewCount",
                "maxResults":        5,
                "relevanceLanguage": "en",
                "regionCode":        "US",
                "videoDuration":     "long",  # 20+ min — real project tutorials, not gear talk
                "publishedAfter":    published_after,
            })
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception as e:
            logger.error(f"[Woodworking] YouTube search failed for '{query}': {e}")
            return []

        video_ids = [i["id"].get("videoId") for i in items if i["id"].get("videoId")]
        if not video_ids:
            return []

        try:
            stats_r = await client.get(YT_VIDEOS, params={
                "key": api_key, "id": ",".join(video_ids), "part": "statistics",
            })
            stats_r.raise_for_status()
            stats_map = {
                s["id"]: int(s["statistics"].get("viewCount", 0))
                for s in stats_r.json().get("items", [])
            }
        except Exception as e:
            logger.warning(f"[Woodworking] Stats fetch failed: {e} — skipping view filter")
            stats_map = {}

        videos = []
        for item in items:
            vid_id = item["id"].get("videoId")
            if not vid_id:
                continue
            views = stats_map.get(vid_id, 0)
            if views < MIN_VIEWS:
                continue
            snippet = item["snippet"]
            title   = snippet.get("title", "")
            channel = snippet.get("channelTitle", "")
            combined = (title + " " + channel).lower()
            if any(kw in combined for kw in EXCLUDE_KEYWORDS):
                continue
            videos.append({
                "video_id":  vid_id,
                "title":     title,
                "channel":   channel,
                "thumbnail": snippet["thumbnails"].get("medium", {}).get("url", ""),
                "url":       f"https://www.youtube.com/watch?v={vid_id}",
                "views":     views,
            })

        videos.sort(key=lambda v: v["views"], reverse=True)
        return videos

    async def _run_logic(self) -> str:
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key or api_key == "your_youtube_api_key_here":
            raise ValueError("YOUTUBE_API_KEY not set in .env")

        now = datetime.now(timezone.utc)
        processed = []
        seen_this_run: set[str] = set()

        async with httpx.AsyncClient(timeout=30) as client:
            for query in QUERIES:
                if len(processed) >= CAP_PER_RUN:
                    break
                videos = await self._fetch_top_videos(client, query, api_key)

                with get_conn() as conn:
                    for video in videos:
                        if len(processed) >= CAP_PER_RUN:
                            break
                        vid_id = video["video_id"]
                        if vid_id in seen_this_run:
                            continue
                        seen_this_run.add(vid_id)

                        existing = conn.execute(
                            "SELECT id FROM woodworking_videos WHERE video_id=?", (vid_id,)
                        ).fetchone()
                        if existing:
                            continue

                        blurb = await llm_queue.submit(
                            prompt=(
                                f"Title: \"{video['title']}\"\n"
                                f"Channel: {video['channel']}\n\n"
                                "Write exactly 2 plain sentences, no labels or numbering.\n"
                                "First sentence: what specific woodworking project or technique this teaches.\n"
                                "Second sentence: what concrete skill or result the viewer walks away with.\n\n"
                                "Rules:\n"
                                "- Be specific — name the actual technique or project stage if clear from the title\n"
                                "- No hype words: avoid 'incredible', 'insane', 'game-changing'\n"
                                "- Do not invent steps or tools not implied by the title\n"
                                "- Do not prefix sentences with 'Sentence 1', 'Sentence 2', or any label\n"
                                "- Write in plain, professional English"
                            ),
                            system=(
                                "You are a technical content analyst writing factual, "
                                "jargon-free summaries of woodworking project videos. "
                                "You only describe what is clearly stated — you never guess or embellish."
                            ),
                            agent_name=self.name
                        )

                        conn.execute(
                            "INSERT OR IGNORE INTO woodworking_videos"
                            " (video_id, title, channel, thumbnail, url, views, blurb, fetched_at)"
                            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (vid_id, video["title"], video["channel"],
                             video["thumbnail"], video["url"], video["views"], blurb, now)
                        )
                        conn.commit()

                        video["blurb"] = blurb
                        processed.append(video)

        if not processed:
            return "No new videos found — all already seen or below view threshold"

        def video_card(v: dict) -> str:
            views_fmt = f"{v['views']:,}"
            return f"""
            <div style="margin-bottom:16px;padding:14px;border:1px solid #e5e7eb;
                        border-left:4px solid #b45309;border-radius:8px;background:#ffffff">
                <div style="display:flex;gap:14px;align-items:flex-start">
                    <img src="{v.get('thumbnail','')}"
                         style="width:130px;height:74px;object-fit:cover;border-radius:6px;flex-shrink:0">
                    <div style="flex:1">
                        <a href="{v.get('url','')}"
                           style="font-size:13px;font-weight:700;color:#1a1d27;text-decoration:none">
                            {v.get('title','')}
                        </a>
                        <div style="display:flex;gap:12px;align-items:center;margin:4px 0">
                            <span style="color:#6b7280;font-size:11px">{v.get('channel','')}</span>
                            <span style="background:#b4530918;color:#b45309;font-size:10px;
                                         padding:1px 8px;border-radius:10px;font-weight:600">
                                👁 {views_fmt} views
                            </span>
                        </div>
                        <div style="color:#374151;font-size:12px;margin-top:6px;line-height:1.5">
                            {v.get('blurb','')}
                        </div>
                    </div>
                </div>
            </div>
            """

        cards = "".join(video_card(v) for v in processed)
        body = f"""
        <div style="margin-bottom:32px">
            <h2 style="color:#1a1d27;border-bottom:3px solid #b45309;padding-bottom:8px;
                       margin-bottom:16px;font-size:16px">
                🪚 Woodworking — Kitchen Cabinets
            </h2>
            {cards}
        </div>
        """

        html = build_email_wrapper("Woodworking — Project Picks", body, "Woodworking")
        send_html_email("🪚 Woodworking — Top Videos", html)

        return f"New videos: {len(processed)} · email sent"
