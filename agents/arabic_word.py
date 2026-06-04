# agents/arabic_word.py
"""
Agent-4: Quranic Arabic Word of the Day

Features:
- Curated word lists at 3 difficulty levels (Beginner/Intermediate/Advanced)
- AlQuran Cloud API for verse text (Arabic, English, Urdu) and audio URL
- Qwen3 analysis: root, verb form (I-X), meanings, root family, contextual explanation
- Spaced Repetition System (SRS) — 3-box Leitner system
- Daily email with micro-quiz from previous day's word
- Sunday weekly recap email
- Dashboard tab with root family tree visualisation
"""

import httpx
import json
import logging
import random
from datetime import datetime, date, timedelta
from pathlib import Path
from agents.base_agent import BaseAgent
from orchestrator.llm_queue import llm_queue
from utils.email_sender import send_html_email, build_email_wrapper
from utils.arabic_word_lists import ALL_WORDS
from database.db import get_conn
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
logger = logging.getLogger(__name__)

# ── AlQuran Cloud API endpoints ───────────────────────────────────────────────
QURAN_VERSE_URL  = "https://api.alquran.cloud/v1/ayah/{ref}"
QURAN_EN_URL     = "https://api.alquran.cloud/v1/ayah/{ref}/en.sahih"
QURAN_UR_URL     = "https://api.alquran.cloud/v1/ayah/{ref}/ur.jalandhry"
QURAN_AUDIO_URL  = "https://api.alquran.cloud/v1/ayah/{ref}/ar.alafasy"
# Mishary Rashid Alafasy recitation — widely used and clear pronunciation


class ArabicWordAgent(BaseAgent):
    name = "arabic_word"

    # ── SRS Box schedule ──────────────────────────────────────────────────────
    # Box 1 (New/Struggling) → review every 1 day
    # Box 2 (Learning)       → review every 3 days
    # Box 3 (Known)          → review every 7 days
    SRS_INTERVALS = {1: 1, 2: 3, 3: 7}

    async def _run_logic(self) -> str:

        difficulty = self._get_difficulty_setting()
        today      = date.today()
        is_sunday  = today.weekday() == 6

        # ── 1. Pick word using SRS algorithm ─────────────────────────────────
        word_data = self._pick_word(difficulty, today)

        if not word_data:
            return "No word available for today"

        word, transliteration, root, root_trans, verse_ref = word_data

        logger.info(f"[ArabicWord] Today's word: {word} ({transliteration}) — {verse_ref}")

        # ── 2. Fetch verse data from AlQuran Cloud API ────────────────────────
        verse_data = await self._fetch_verse(verse_ref)

        # ── 3. Generate comprehensive Qwen3 analysis ─────────────────────────
        analysis = await self._analyse_word(
            word, transliteration, root, root_trans,
            verse_data, verse_ref
        )

        # ── 4. Fetch yesterday's word for quiz ────────────────────────────────
        yesterday_quiz = self._get_yesterday_quiz()

        # ── 5. Save to database ───────────────────────────────────────────────
        word_id = self._save_word(
            word, transliteration, root, root_trans,
            difficulty, analysis, verse_data, verse_ref, today
        )

        # ── 6. Send daily email ───────────────────────────────────────────────
        await self._send_daily_email(
            word, transliteration, root, root_trans,
            analysis, verse_data, verse_ref, yesterday_quiz
        )

        # ── 7. Sunday weekly recap ────────────────────────────────────────────
        if is_sunday:
            await self._send_weekly_recap()

        return f"Word of the day: {word} ({transliteration}) — analysis sent"

    # ── SRS: Pick word ────────────────────────────────────────────────────────

    def _get_difficulty_setting(self) -> str:
        """Read difficulty from .env, default to beginner."""
        import os
        return os.getenv("ARABIC_DIFFICULTY", "beginner").lower()

    def _pick_word(self, difficulty: str, today: date) -> tuple | None:
        """
        SRS-aware word selection.
        Priority order:
        1. Words due for review today (SRS boxes 2 and 3)
        2. New words from the word list not yet seen
        3. Random word from list as fallback
        """
        word_list = ALL_WORDS.get(difficulty, ALL_WORDS["beginner"])

        with get_conn() as conn:
            # Check for SRS review words due today
            due_row = conn.execute(
                "SELECT word, transliteration, root, root_transliteration, verse_ref"
                " FROM arabic_words"
                " WHERE difficulty=? AND next_review<=? AND srs_box < 3"
                " ORDER BY srs_box ASC, next_review ASC LIMIT 1",
                (difficulty, str(today))
            ).fetchone()

            if due_row:
                logger.info(f"[ArabicWord] SRS review word selected: {due_row['word']}")
                return tuple(due_row)

            # Get already seen words
            seen = set(
                row[0] for row in conn.execute(
                    "SELECT word FROM arabic_words WHERE difficulty=?",(difficulty,)
                ).fetchall()
            )

        # Find unseen words
        unseen = [w for w in word_list if w[0] not in seen]

        if unseen:
            return random.choice(unseen)

        # All words seen — pick random from full list
        return random.choice(word_list)

    # ── AlQuran Cloud API ─────────────────────────────────────────────────────

    async def _fetch_verse(self, verse_ref: str) -> dict:
        """
        Fetches Arabic text, English translation, Urdu translation,
        and audio URL for a given verse reference (e.g. '2:255').
        """
        result = {
            "arabic": "", "english": "", "urdu": "",
            "audio_url": "", "surah_name": "", "ayah_number": ""
        }

        async with httpx.AsyncClient(timeout=30) as client:

            # Arabic text
            try:
                r = await client.get(QURAN_VERSE_URL.format(ref=verse_ref))
                if r.status_code == 200:
                    data = r.json().get("data", {})
                    result["arabic"]      = data.get("text", "")
                    result["surah_name"]  = data.get("surah", {}).get("englishName", "")
                    result["ayah_number"] = str(data.get("numberInSurah", ""))
            except Exception as e:
                logger.warning(f"[ArabicWord] Arabic fetch failed: {e}")

            # English translation (Sahih International)
            try:
                r = await client.get(QURAN_EN_URL.format(ref=verse_ref))
                if r.status_code == 200:
                    result["english"] = r.json().get("data", {}).get("text", "")
            except Exception as e:
                logger.warning(f"[ArabicWord] English fetch failed: {e}")

            # Urdu translation (Jalandhry)
            try:
                r = await client.get(QURAN_UR_URL.format(ref=verse_ref))
                if r.status_code == 200:
                    result["urdu"] = r.json().get("data", {}).get("text", "")
            except Exception as e:
                logger.warning(f"[ArabicWord] Urdu fetch failed: {e}")

            # Audio URL (Alafasy recitation)
            try:
                r = await client.get(QURAN_AUDIO_URL.format(ref=verse_ref))
                if r.status_code == 200:
                    result["audio_url"] = r.json().get("data", {}).get("audio", "")
            except Exception as e:
                logger.warning(f"[ArabicWord] Audio fetch failed: {e}")

        logger.info(f"[ArabicWord] Verse {verse_ref} fetched successfully")
        return result

    # ── Qwen3 Analysis ────────────────────────────────────────────────────────

    async def _analyse_word(
        self,
        word: str,
        transliteration: str,
        root: str,
        root_trans: str,
        verse_data: dict,
        verse_ref: str
    ) -> dict:
        """
        Single comprehensive Qwen3 call that returns:
        - Verb form analysis (Form I-X)
        - English and Urdu meanings
        - Root family (5-6 related words)
        - Contextual explanation
        - Tomorrow's micro-quiz question
        """

        prompt = f"""You are an expert in Quranic Arabic linguistics and Classical Arabic morphology.

Analyze the Arabic word: {word} (transliteration: {transliteration})
Root letters: {root} ({root_trans})
This word appears in Quran verse {verse_ref}: "{verse_data.get('arabic', '')}"
English meaning of verse: "{verse_data.get('english', '')}"

Provide your analysis as a valid JSON object with EXACTLY these fields:

{{
  "meaning_en": "Clear English meaning of this specific word",
  "meaning_ur": "Clear Urdu meaning of this word in Urdu script",
  "verb_form": "If this is a verb or derived from a verb pattern, state which Form (I through X) and explain how the form shifts the meaning. If it is a noun, explain its morphological pattern (e.g. فَعَّال pattern indicating intensity). Keep this to 2-3 sentences.",
  "root_family": [
    {{"word": "Arabic word 1", "transliteration": "...", "meaning": "English meaning", "quran_occurrence": "brief note on where/how used in Quran"}},
    {{"word": "Arabic word 2", "transliteration": "...", "meaning": "English meaning", "quran_occurrence": "..."}},
    {{"word": "Arabic word 3", "transliteration": "...", "meaning": "English meaning", "quran_occurrence": "..."}},
    {{"word": "Arabic word 4", "transliteration": "...", "meaning": "English meaning", "quran_occurrence": "..."}},
    {{"word": "Arabic word 5", "transliteration": "...", "meaning": "English meaning", "quran_occurrence": "..."}}
  ],
  "contextual_explanation": "2-3 sentences explaining the deeper Quranic significance of this word. Why is this word used here specifically? What does understanding this word unlock in the verse?",
  "quiz_question": {{
    "question": "A multiple choice question testing understanding of this word or its root, suitable for someone learning Quranic Arabic",
    "options": {{
      "A": "First option",
      "B": "Second option",
      "C": "Third option",
      "D": "Fourth option"
    }},
    "correct": "A",
    "explanation": "Brief explanation of why the correct answer is right"
  }}
}}

Return ONLY the JSON object. No preamble, no explanation outside the JSON."""

        response = await llm_queue.submit(
            prompt=prompt,
            system="You are a Quranic Arabic linguistics expert. Always respond with valid JSON only.",
            agent_name=self.name
        )

        # Parse JSON response
        try:
            # Clean response — remove markdown code blocks if present
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            clean = clean.strip()
            analysis = json.loads(clean)
            logger.info(f"[ArabicWord] Qwen3 analysis parsed successfully")
            return analysis
        except json.JSONDecodeError as e:
            logger.error(f"[ArabicWord] JSON parse failed: {e}\nResponse: {response[:200]}")
            # Return safe defaults if JSON parsing fails
            return {
                "meaning_en": f"Meaning of {word}",
                "meaning_ur": "",
                "verb_form": "Analysis unavailable",
                "root_family": [],
                "contextual_explanation": response[:500],
                "quiz_question": None
            }

    # ── Database ──────────────────────────────────────────────────────────────

    def _save_word(
        self, word, transliteration, root, root_trans,
        difficulty, analysis, verse_data, verse_ref, today
    ) -> int:
        """Saves today's word to the database. Returns the row ID."""
        next_review = str(today + timedelta(days=self.SRS_INTERVALS[1]))

        with get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO arabic_words"
                " (word, transliteration, root, root_transliteration, difficulty,"
                "  meaning_en, meaning_ur, verb_form, root_family,"
                "  contextual_explanation, verse_ref, verse_ar, verse_en, verse_ur,"
                "  audio_url, quiz_question, srs_box, next_review, fetched_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    word, transliteration, root, root_trans, difficulty,
                    analysis.get("meaning_en", ""),
                    analysis.get("meaning_ur", ""),
                    analysis.get("verb_form", ""),
                    json.dumps(analysis.get("root_family", []), ensure_ascii=False),
                    analysis.get("contextual_explanation", ""),
                    verse_ref,
                    verse_data.get("arabic", ""),
                    verse_data.get("english", ""),
                    verse_data.get("urdu", ""),
                    verse_data.get("audio_url", ""),
                    json.dumps(analysis.get("quiz_question"), ensure_ascii=False),
                    1,
                    next_review,
                    datetime.utcnow()
                )
            )
            conn.commit()
            return cursor.lastrowid

    def _get_yesterday_quiz(self) -> dict | None:
        """Fetches yesterday's word's quiz question for today's email."""
        with get_conn() as conn:
            row = conn.execute(
                "SELECT word, transliteration, quiz_question"
                " FROM arabic_words"
                " ORDER BY id DESC LIMIT 1 OFFSET 1"
                # OFFSET 1 skips today's word (just inserted), gets yesterday's
            ).fetchone()

        if not row or not row["quiz_question"]:
            return None

        try:
            quiz = json.loads(row["quiz_question"])
            quiz["word"]            = row["word"]
            quiz["transliteration"] = row["transliteration"]
            return quiz
        except Exception:
            return None

    # ── Email ─────────────────────────────────────────────────────────────────

    async def _send_daily_email(
        self, word, transliteration, root, root_trans,
        analysis, verse_data, verse_ref, yesterday_quiz
    ):
        """Builds and sends the daily word of the day email."""

        root_family = analysis.get("root_family", [])

        # Root family tree HTML
        root_tree_html = ""
        if root_family:
            family_cards = "".join(f"""
            <div style="background:#f5f3ff;border:1px solid #ddd6fe;border-radius:8px;
                        padding:12px;text-align:center;min-width:120px">
                <div style="font-size:20px;font-weight:700;
                            color:#5b21b6;direction:rtl">{item.get('word','')}</div>
                <div style="font-size:11px;color:#7c3aed;
                            margin:2px 0">{item.get('transliteration','')}</div>
                <div style="font-size:12px;color:#374151;
                            font-weight:600">{item.get('meaning','')}</div>
                <div style="font-size:11px;color:#6b7280;
                            margin-top:4px">{item.get('quran_occurrence','')}</div>
            </div>
            """ for item in root_family)

            root_tree_html = f"""
            <div style="margin-bottom:24px">
                <h3 style="color:#5b21b6;margin-bottom:4px">
                    🌳 Root Family: {root} ({root_trans})
                </h3>
                <p style="color:#6b7280;font-size:13px;margin-bottom:12px">
                    All these words branch from the same 3-letter root
                </p>
                <div style="display:flex;flex-wrap:wrap;gap:10px;
                            justify-content:center;padding:16px;
                            background:#faf5ff;border-radius:8px;
                            border:1px solid #e9d5ff">
                    <div style="background:#5b21b6;color:white;border-radius:8px;
                                padding:12px 20px;text-align:center;font-weight:700">
                        <div style="font-size:22px;direction:rtl">{root}</div>
                        <div style="font-size:11px;opacity:0.8">{root_trans}</div>
                        <div style="font-size:11px;opacity:0.8">ROOT</div>
                    </div>
                    {family_cards}
                </div>
            </div>
            """

        # Quiz section from yesterday's word
        quiz_html = ""
        if yesterday_quiz:
            options_html = "".join(
                f"""<div style="padding:8px 12px;margin:4px 0;
                              background:#f9fafb;border:1px solid #e5e7eb;
                              border-radius:6px;font-size:13px">
                    <b>{letter}.</b> {text}
                </div>"""
                for letter, text in yesterday_quiz.get("options", {}).items()
            )
            quiz_html = f"""
            <div style="background:#fffbeb;border:1px solid #fde68a;
                        border-radius:8px;padding:16px;margin-bottom:24px">
                <h3 style="color:#92400e;margin:0 0 12px">
                    🧠 Retention Quiz — Yesterday's Word:
                    {yesterday_quiz.get('word','')}
                    ({yesterday_quiz.get('transliteration','')})
                </h3>
                <p style="font-weight:600;color:#374151;margin-bottom:8px">
                    {yesterday_quiz.get('question','')}
                </p>
                {options_html}
                <details style="margin-top:10px">
                    <summary style="cursor:pointer;color:#7c3aed;
                                    font-size:13px;font-weight:600">
                        Reveal Answer
                    </summary>
                    <div style="margin-top:8px;padding:10px;background:#f0fdf4;
                                border-radius:6px;font-size:13px">
                        <b>Correct Answer: {yesterday_quiz.get('correct','')}</b><br>
                        {yesterday_quiz.get('explanation','')}
                    </div>
                </details>
            </div>
            """

        # Audio section
        audio_html = ""
        if verse_data.get("audio_url"):
            audio_html = f"""
            <div style="background:#f0fdf4;border:1px solid #bbf7d0;
                        border-radius:8px;padding:14px;margin-bottom:20px">
                <h3 style="color:#166534;margin:0 0 8px">🎧 Listen to the Verse</h3>
                <p style="color:#374151;font-size:13px;margin:0 0 8px">
                    Recited by Mishary Rashid Alafasy
                </p>
                <a href="{verse_data['audio_url']}"
                   style="background:#16a34a;color:white;padding:8px 16px;
                          border-radius:6px;text-decoration:none;font-size:13px">
                    ▶ Play Verse {verse_ref}
                </a>
            </div>
            """

        content = f"""
        <!-- Main word card -->
        <div style="background:linear-gradient(135deg,#1e1b4b,#312e81);
                    border-radius:12px;padding:28px;text-align:center;
                    margin-bottom:24px">
            <div style="font-size:52px;color:white;direction:rtl;
                        font-weight:700;margin-bottom:8px">{word}</div>
            <div style="font-size:20px;color:#a5b4fc;
                        margin-bottom:4px">{transliteration}</div>
            <div style="font-size:14px;color:#818cf8">
                Root: {root} ({root_trans})
            </div>
        </div>

        <!-- Meanings -->
        <div style="display:grid;grid-template-columns:1fr 1fr;
                    gap:12px;margin-bottom:24px">
            <div style="background:#eff6ff;border-radius:8px;padding:14px">
                <div style="font-size:11px;color:#3b82f6;font-weight:700;
                            text-transform:uppercase;margin-bottom:4px">
                    English Meaning
                </div>
                <div style="font-size:16px;font-weight:700;color:#1e40af">
                    {analysis.get('meaning_en','')}
                </div>
            </div>
            <div style="background:#fdf4ff;border-radius:8px;
                        padding:14px;text-align:right">
                <div style="font-size:11px;color:#a21caf;font-weight:700;
                            text-transform:uppercase;margin-bottom:4px">
                    Urdu Meaning
                </div>
                <div style="font-size:16px;font-weight:700;
                            color:#86198f;direction:rtl">
                    {analysis.get('meaning_ur','')}
                </div>
            </div>
        </div>

        <!-- Verb Form Analysis -->
        <div style="background:#fff7ed;border-left:4px solid #f97316;
                    padding:14px;border-radius:6px;margin-bottom:24px">
            <h3 style="color:#c2410c;margin:0 0 8px">
                📐 Morphological Analysis
            </h3>
            <p style="color:#374151;font-size:14px;
                      line-height:1.6;margin:0">
                {analysis.get('verb_form','')}
            </p>
        </div>

        <!-- Verse -->
        <div style="background:#f8fafc;border:1px solid #e2e8f0;
                    border-radius:8px;padding:16px;margin-bottom:24px">
            <div style="font-size:11px;color:#64748b;font-weight:700;
                        text-transform:uppercase;margin-bottom:12px">
                Quran {verse_ref} — {verse_data.get('surah_name','')}
            </div>
            <div style="font-size:22px;direction:rtl;line-height:2;
                        color:#1e293b;margin-bottom:12px;text-align:right">
                {verse_data.get('arabic','')}
            </div>
            <div style="font-size:14px;color:#334155;font-style:italic;
                        margin-bottom:8px;line-height:1.6">
                {verse_data.get('english','')}
            </div>
            <div style="font-size:14px;color:#334155;direction:rtl;
                        line-height:1.8">
                {verse_data.get('urdu','')}
            </div>
        </div>

        <!-- Audio -->
        {audio_html}

        <!-- Root family tree -->
        {root_tree_html}

        <!-- Contextual explanation -->
        <div style="background:#f0fdf4;border-left:4px solid #22c55e;
                    padding:14px;border-radius:6px;margin-bottom:24px">
            <h3 style="color:#166534;margin:0 0 8px">
                💡 Quranic Context
            </h3>
            <p style="color:#374151;font-size:14px;
                      line-height:1.6;margin:0">
                {analysis.get('contextual_explanation','')}
            </p>
        </div>

        <!-- Quiz -->
        {quiz_html}

        <div style="text-align:center;padding:16px;
                    background:#f8fafc;border-radius:8px;
                    font-size:13px;color:#64748b">
            Open your dashboard at
            <a href="http://localhost:8000" style="color:#6366f1">
                localhost:8000
            </a>
            to interact with the root tree and update your SRS progress.
        </div>
        """

        html = build_email_wrapper(
            f"🌙 Quranic Arabic Word of the Day — {word} ({transliteration})",
            content,
            "Arabic Word of the Day"
        )

        send_html_email(
            f"🌙 Word of the Day: {word} — {analysis.get('meaning_en','')}",
            html
        )
        logger.info(f"[ArabicWord] Daily email sent for word: {word}")

    async def _send_weekly_recap(self):
        """Sends a Sunday recap of the week's 7 words."""
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT word, transliteration, meaning_en, meaning_ur,"
                " root, verse_ref, srs_box"
                " FROM arabic_words"
                " ORDER BY id DESC LIMIT 7"
            ).fetchall()

        if not rows:
            return

        cards = "".join(f"""
        <div style="border:1px solid #e5e7eb;border-radius:8px;
                    padding:14px;margin-bottom:12px;
                    background:{'#f0fdf4' if row['srs_box']==3 else '#fffbeb' if row['srs_box']==2 else '#fef2f2'}">
            <div style="display:flex;justify-content:space-between;
                        align-items:center">
                <div>
                    <span style="font-size:20px;font-weight:700;
                                 color:#1e293b;direction:rtl">
                        {row['word']}
                    </span>
                    <span style="color:#6b7280;font-size:14px;
                                 margin-left:8px">
                        {row['transliteration']}
                    </span>
                </div>
                <div style="font-size:11px;font-weight:700;
                            padding:3px 10px;border-radius:12px;
                            background:{'#dcfce7' if row['srs_box']==3 else '#fef9c3' if row['srs_box']==2 else '#fee2e2'};
                            color:{'#166534' if row['srs_box']==3 else '#854d0e' if row['srs_box']==2 else '#991b1b'}">
                    {'✅ Known' if row['srs_box']==3 else '📖 Learning' if row['srs_box']==2 else '🔄 Review'}
                </div>
            </div>
            <div style="color:#374151;font-size:13px;margin-top:6px">
                <b>English:</b> {row['meaning_en']} &nbsp;|&nbsp;
                <b>Root:</b> {row['root']} &nbsp;|&nbsp;
                <b>Verse:</b> {row['verse_ref']}
            </div>
            <div style="color:#374151;font-size:13px;
                        direction:rtl;margin-top:4px">
                {row['meaning_ur']}
            </div>
        </div>
        """ for row in rows)

        content = f"""
        <div style="background:#f0f9ff;border-left:4px solid #3b82f6;
                    padding:14px;border-radius:6px;margin-bottom:20px">
            <h2 style="margin:0;color:#1e40af">
                📚 Weekly Arabic Review — {date.today().strftime('%B %d, %Y')}
            </h2>
            <p style="color:#374151;margin:8px 0 0;font-size:14px">
                Here are the 7 words you studied this week.
                Green = mastered, Yellow = learning, Red = needs review.
            </p>
        </div>
        {cards}
        <div style="text-align:center;padding:14px;
                    background:#faf5ff;border-radius:8px;
                    font-size:14px;color:#6b7280;margin-top:8px">
            Keep going! Consistent daily practice is the key to
            mastering Quranic Arabic. 🌙
        </div>
        """

        html = build_email_wrapper(
            "🌙 Weekly Quranic Arabic Review",
            content,
            "Arabic Word of the Day"
        )
        send_html_email("🌙 Weekly Arabic Review — 7 Words This Week", html)
        logger.info("[ArabicWord] Weekly recap email sent")

    def update_srs(self, word_id: int, knew_it: bool):
        """
        Called from the dashboard when user clicks 'I knew this' or 'Still learning'.
        Moves word up or down the SRS box and updates next review date.
        """
        with get_conn() as conn:
            row = conn.execute(
                "SELECT srs_box FROM arabic_words WHERE id=?",
                (word_id,)
            ).fetchone()

            if not row:
                return

            current_box = row["srs_box"]

            if knew_it:
                new_box = min(current_box + 1, 3)  # Max box is 3
            else:
                new_box = max(current_box - 1, 1)  # Min box is 1

            next_review = str(
                date.today() + timedelta(days=self.SRS_INTERVALS[new_box])
            )

            conn.execute(
                "UPDATE arabic_words SET srs_box=?, next_review=? WHERE id=?",
                (new_box, next_review, word_id)
            )

            # Log the feedback
            conn.execute(
                "INSERT INTO srs_feedback (word_id, knew_it, reviewed_at)"
                " VALUES (?, ?, ?)",
                (word_id, 1 if knew_it else 0, datetime.utcnow())
            )
            conn.commit()

        logger.info(
            f"[ArabicWord] SRS updated for word {word_id}: "
            f"box {current_box} → {new_box}, next review: {next_review}"
        )
