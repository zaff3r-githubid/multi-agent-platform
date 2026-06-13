# agents/leverage.py
"""
Leverage — AI Tool Learning Agent

Fetches the most-watched, highest-value YouTube videos across 3 categories:
  1. AI Tool Tutorials     — how to use specific AI tools to their full potential
  2. Top Ranked AI Tools   — best-of rankings, comparisons, what's worth learning
  3. AI Tools That Make Money — freelancing, automation, income streams with AI

Unlike AI-Times (sorted by date), Leverage sorts by viewCount so only
content the community has already validated as valuable makes the cut.
A minimum view threshold filters out low-quality uploads.

Schedule: twice weekly (Mon + Thu at 09:00 UTC)
"""

import httpx
import os
import logging
from datetime import datetime, timezone
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

MIN_VIEWS = 30_000  # Skip videos below this threshold

# Negative keyword filter — applied to title + channel before LLM call
# Catches clickbait, unrelated content, and low-effort channels
EXCLUDE_KEYWORDS = [
    "crypto", "web3", "nft", "get rich quick", "passive income",
    "drama", "reaction", "sora reaction", "clickbait",
    "lakh", "crore", "rupee", "₹", "inr",
    "hindi", "telugu", "tamil", "kannada", "marathi",
]

CATEGORIES = {
    "tutorial": {
        "label":   "AI Tool Tutorials",
        "icon":    "🎓",
        "color":   "#60a5fa",
        "queries": [
            "how to use AI tools full tutorial 2025",
            "ChatGPT tips tricks full potential tutorial",
            "Claude AI tutorial how to use effectively",
            "Cursor AI coding tutorial beginner to advanced",
            "Perplexity AI tutorial complete guide",
        ],
    },
    "ranked": {
        "label":   "Top Ranked AI Tools",
        "icon":    "🏆",
        "color":   "#a78bfa",
        "queries": [
            "best AI tools 2025 ranked",
            "top AI tools you should be using right now",
            "must have AI tools 2025",
            "AI tools that will blow your mind",
        ],
    },
    "deep_dive": {
        "label":   "AI Suite Deep Dives",
        "icon":    "🔬",
        "color":   "#34d399",
        "queries": [
            "Claude Anthropic full tutorial deep dive 2025",
            "ChatGPT OpenAI complete guide full potential 2025",
            "Google Gemini deep dive tutorial how to use",
            "DeepSeek AI tutorial full walkthrough 2025",
            "ElevenLabs tutorial complete guide voice AI",
            "NotebookLM Google deep dive tutorial",
            "OpenAI Sora tutorial how to use full guide",
            "Anthropic Claude advanced features masterclass",
        ],
    },
}


class Leverage(BaseAgent):
    name = "leverage"

    async def _fetch_top_videos(
        self,
        client: httpx.AsyncClient,
        query: str,
        category: str,
        api_key: str,
        max_results: int = 5,
    ) -> list:
        """
        Searches YouTube with order=viewCount and filters by MIN_VIEWS.
        Returns a list of video dicts enriched with actual view counts.
        """
        try:
            r = await client.get(YT_SEARCH, params={
                "key":              api_key,
                "q":                query,
                "part":             "snippet",
                "type":             "video",
                "order":            "viewCount",
                "maxResults":       max_results,
                "relevanceLanguage": "en",
                "regionCode":       "US",
                "videoDuration":    "medium",  # 4–20 min — excludes shorts and 3h streams
            })
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception as e:
            logger.error(f"[Leverage] YouTube search failed for '{query}': {e}")
            return []

        if not items:
            return []

        # Fetch view counts in one batch call
        video_ids = [i["id"].get("videoId") for i in items if i["id"].get("videoId")]
        if not video_ids:
            return []

        try:
            stats_r = await client.get(YT_VIDEOS, params={
                "key":  api_key,
                "id":   ",".join(video_ids),
                "part": "statistics",
            })
            stats_r.raise_for_status()
            stats_map = {
                s["id"]: int(s["statistics"].get("viewCount", 0))
                for s in stats_r.json().get("items", [])
            }
        except Exception as e:
            logger.warning(f"[Leverage] Stats fetch failed: {e} — skipping view filter")
            stats_map = {}

        videos = []
        for item in items:
            vid_id = item["id"].get("videoId")
            if not vid_id:
                continue
            views = stats_map.get(vid_id, 0)
            if views < MIN_VIEWS:
                logger.info(f"[Leverage] Skipping low-view video ({views:,} views): {item['snippet']['title'][:50]}")
                continue
            snippet = item["snippet"]
            title   = snippet.get("title", "")
            channel = snippet.get("channelTitle", "")

            # Negative keyword filter — drop clickbait and irrelevant content
            combined = (title + " " + channel).lower()
            if any(kw in combined for kw in EXCLUDE_KEYWORDS):
                logger.info(f"[Leverage] Excluded by keyword filter: {title[:50]}")
                continue

            videos.append({
                "video_id":  vid_id,
                "title":     title,
                "channel":   channel,
                "thumbnail": snippet["thumbnails"].get("medium", {}).get("url", ""),
                "url":       f"https://www.youtube.com/watch?v={vid_id}",
                "category":  category,
                "views":     views,
            })

        # Sort by view count descending so best videos come first
        videos.sort(key=lambda v: v["views"], reverse=True)
        logger.info(f"[Leverage] '{query}' → {len(videos)} videos passed view filter")
        return videos

    async def _run_logic(self) -> str:

        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key or api_key == "your_youtube_api_key_here":
            raise ValueError("YOUTUBE_API_KEY not set in .env")

        now = datetime.now(timezone.utc)
        all_processed: dict[str, list] = {cat: [] for cat in CATEGORIES}
        total_new = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for cat_key, cat_info in CATEGORIES.items():
                seen_this_run: set[str] = set()

                for query in cat_info["queries"]:
                    videos = await self._fetch_top_videos(
                        client, query, cat_key, api_key, max_results=5
                    )

                    with get_conn() as conn:
                        for video in videos:
                            vid_id = video["video_id"]

                            # Skip dupes within this run
                            if vid_id in seen_this_run:
                                continue
                            seen_this_run.add(vid_id)

                            # Skip already seen in DB
                            existing = conn.execute(
                                "SELECT id FROM leverage_videos WHERE video_id=?",
                                (vid_id,)
                            ).fetchone()
                            if existing:
                                logger.info(f"[Leverage] Already seen: {video['title'][:50]}")
                                continue

                            # LLM blurb — tight, grounded, no hype
                            blurb = await llm_queue.submit(
                                prompt=(
                                    f"Title: \"{video['title']}\"\n"
                                    f"Channel: {video['channel']}\n"
                                    f"Category: {cat_info['label']}\n\n"
                                    "Write 2 sentences maximum.\n"
                                    "Sentence 1: What specific AI tool or workflow does this video teach?\n"
                                    "Sentence 2: What concrete skill or outcome will the viewer walk away with?\n\n"
                                    "Rules:\n"
                                    "- Be specific — name the actual tool if clear from the title\n"
                                    "- No hype words: avoid 'incredible', 'insane', 'game-changing', 'mind-blowing'\n"
                                    "- Do not invent features or capabilities not implied by the title\n"
                                    "- Write in plain, professional English"
                                ),
                                system=(
                                    "You are a technical content analyst writing factual, "
                                    "jargon-free summaries of AI tutorial videos. "
                                    "You only describe what is clearly stated — you never guess or embellish."
                                ),
                                agent_name=self.name
                            )

                            conn.execute(
                                "INSERT OR IGNORE INTO leverage_videos"
                                " (video_id, title, channel, thumbnail, url,"
                                "  category, views, blurb, fetched_at)"
                                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (
                                    vid_id, video["title"], video["channel"],
                                    video["thumbnail"], video["url"],
                                    cat_key, video["views"], blurb, now
                                )
                            )
                            conn.commit()

                            video["blurb"] = blurb
                            all_processed[cat_key].append(video)
                            total_new += 1

                            # Cap at 4 new videos per category per run
                            if len(all_processed[cat_key]) >= 4:
                                break

                    if len(all_processed[cat_key]) >= 4:
                        break

        if total_new == 0:
            return "No new videos found — all already seen or below view threshold"

        # ── Build HTML email ──────────────────────────────────────────────────
        def video_card(v: dict, accent: str) -> str:
            views_fmt = f"{v['views']:,}"
            return f"""
            <div style="margin-bottom:16px;padding:14px;border:1px solid #e5e7eb;
                        border-left:4px solid {accent};border-radius:8px;
                        background:#ffffff">
                <div style="display:flex;gap:14px;align-items:flex-start">
                    <img src="{v.get('thumbnail','')}"
                         style="width:130px;height:74px;object-fit:cover;
                                border-radius:6px;flex-shrink:0">
                    <div style="flex:1">
                        <a href="{v.get('url','')}"
                           style="font-size:13px;font-weight:700;
                                  color:#1a1d27;text-decoration:none">
                            {v.get('title','')}
                        </a>
                        <div style="display:flex;gap:12px;align-items:center;
                                    margin:4px 0">
                            <span style="color:#6b7280;font-size:11px">
                                {v.get('channel','')}
                            </span>
                            <span style="background:{accent}18;color:{accent};
                                         font-size:10px;padding:1px 8px;
                                         border-radius:10px;font-weight:600">
                                👁 {views_fmt} views
                            </span>
                        </div>
                        <div style="color:#374151;font-size:12px;margin-top:6px;
                                    line-height:1.5">
                            {v.get('blurb','')}
                        </div>
                    </div>
                </div>
            </div>
            """

        sections_html = ""
        for cat_key, cat_info in CATEGORIES.items():
            videos = all_processed[cat_key]
            if not videos:
                continue
            cards = "".join(video_card(v, cat_info["color"]) for v in videos)
            sections_html += f"""
            <div style="margin-bottom:32px">
                <h2 style="color:#1a1d27;border-bottom:3px solid {cat_info['color']};
                           padding-bottom:8px;margin-bottom:16px;font-size:16px">
                    {cat_info['icon']} {cat_info['label']}
                </h2>
                {cards}
            </div>
            """

        html = build_email_wrapper("Leverage — AI Tool Picks", sections_html, "Leverage")
        send_html_email("🚀 Leverage — Top AI Tool Videos", html)

        counts = {k: len(v) for k, v in all_processed.items()}
        return (
            f"New videos — tutorials:{counts['tutorial']} "
            f"ranked:{counts['ranked']} deep_dive:{counts['deep_dive']} · email sent"
        )
