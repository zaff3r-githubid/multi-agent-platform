# Runbook — How to Run & Test the Multi-Agent Platform

> **For instructors, evaluators, or anyone cloning this repo fresh.**
> This guide takes you from zero to a fully running platform in under 30 minutes.

---

## What You Need Before Starting

| Requirement | Details |
|---|---|
| **Mac** (Apple Silicon preferred) | Tested on M5 Pro, 48GB RAM |
| **Minimum RAM** | 16 GB (use `qwen3:8b` if under 32 GB) |
| **Python** | 3.12 or higher |
| **Disk Space** | ~15 GB free (model is ~9 GB) |
| **Internet** | Required for first setup only |
| **Gmail account** | For Mailman agent (OAuth2) |
| **Google account** | For YouTube API key |

---

## Part 1 — One-Time Setup

### Step 1 — Clone the Repository

```bash
git clone https://github.com/zaff3r-githubid/multi-agent-platform.git
cd multi-agent-platform
```

---

### Step 2 — Install LM Studio + Qwen3

**LM Studio** is the app that runs the AI model locally.

1. Download from [lmstudio.ai](https://lmstudio.ai) and install
2. Open LM Studio → click **Discover** tab (search icon)
3. Search for `Qwen3`
4. Download **`Qwen3-14B (Q4_K_M)`** — approximately 9 GB
   - If your machine has less than 32 GB RAM → download `Qwen3-8B` instead
5. Once downloaded → go to **Developer** tab
6. Load the model → click **Start Server**
7. Verify it's running:

```bash
curl http://localhost:1234/v1/models
```

Expected output:
```json
{
  "data": [
    { "id": "qwen/qwen3-14b", "object": "model" }
  ]
}
```

---

### Step 3 — Create Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Verify installation:
```bash
python --version
pip list | grep fastapi
```

---

### Step 4 — Configure Environment Variables

```bash
cp .env.example .env
open -e .env
```

Fill in ALL of the following values:

```ini
# ── LLM (LM Studio) ──────────────────────────────
LLM_BASE_URL=http://localhost:1234/v1
LLM_MODEL=qwen/qwen3-14b

# ── YouTube ──────────────────────────────────────
YOUTUBE_API_KEY=your_youtube_api_key_here

# ── Email ────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_gmail@gmail.com
SMTP_PASSWORD=your_16_char_app_password
EMAIL_RECIPIENT=your_gmail@gmail.com

# ── Database ─────────────────────────────────────
DATABASE_URL=sqlite:///./platform.db

# ── Dashboard ────────────────────────────────────
DASHBOARD_PORT=8000

# ── Mailman ──────────────────────────────────────
KEY_PEOPLE=important@person.com,boss@work.com

# ── Arabic Word of Day ───────────────────────────
ARABIC_DIFFICULTY=beginner
```

---

### Step 5 — Get a YouTube API Key (5 minutes)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project → name it anything
3. Go to **APIs & Services → Library**
4. Search **YouTube Data API v3** → click **Enable**
5. Go to **APIs & Services → Credentials**
6. Click **Create Credentials → API key**
7. Copy the key → paste into `.env` as `YOUTUBE_API_KEY`

---

### Step 6 — Get a Gmail App Password (5 minutes)

> **Why?** Google blocks apps from using your real Gmail password.
> An App Password is a safe 16-character alternative.

1. Make sure **2-Step Verification** is ON at [myaccount.google.com/security](https://myaccount.google.com/security)
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Type any name (e.g. `multi-agent`) → click **Create**
4. Copy the 16-character password (shown only once)
5. Paste into `.env` as `SMTP_PASSWORD` — **no spaces**

---

### Step 7 — Set Up Gmail OAuth (for Mailman Agent)

This lets the Mailman agent read and label your Gmail inbox.

**7a — Enable Gmail API:**
1. In Google Cloud Console → **APIs & Services → Library**
2. Search **Gmail API** → click **Enable**

**7b — Configure OAuth consent screen:**
1. Go to **APIs & Services → OAuth consent screen**
2. Choose **External** → click **Create**
3. Fill in App name: `Multi-Agent Platform`
4. Add your Gmail as support email and developer email
5. Click **Save and Continue** through all steps
6. On **Test Users** page → click **Add Users** → add your Gmail
7. Click **Save and Continue**

**7c — Create OAuth credentials:**
1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Name: `multi-agent-platform`
5. Click **Create** → **Download JSON**
6. Rename the file to `credentials.json`
7. Move it to the project root:

```bash
mv ~/Downloads/client_secret_*.json ./credentials.json
```

**7d — Authorise the app (one time only):**

```bash
python utils/gmail_auth.py
```

A browser window opens → sign in → click **Allow** → close browser.
You should see: `token.json created successfully.`

---

### Step 8 — Initialise the Database

```bash
python -c "from database.db import init_db; init_db()"
```

Expected output: `Database initialised ✓`

Verify the database file was created:
```bash
ls *.db
```

Should show: `platform.db`

---

## Part 2 — Running the Platform

### Every Time You Start

**Terminal 1 — Keep this open the entire time:**
```bash
cd multi-agent-platform
source venv/bin/activate
ulimit -n 4096
python main.py
```

Wait until you see:
```
=======================================================
  Multi-Agent Platform — Starting Up
=======================================================
Database ready ✓
Scheduler started ✓
Watchdog started ✓
Resource monitor ready ✓
=======================================================
  Dashboard → http://localhost:8000
=======================================================
```

**Open the dashboard in your browser:**
```
http://localhost:8000
```

---

## Part 3 — Testing Each Agent

Open a **second terminal window** and run these commands.
Each agent takes 1–3 minutes to complete.

### Test Agent 1 — AI-Times

```bash
cd multi-agent-platform
source venv/bin/activate
curl -X POST http://localhost:8000/api/agents/ai_times/run
```

Watch Terminal 1 for:
```
[ai_times] starting run
[AITimes] Fetched 5 news videos
[AITimes] Fetched 5 personality videos
[LLM Queue] ai_times started (active=1)
...repeated 10 times...
[ai_times] success — Fetched 5 news + 5 personality videos, sent digest
```

✅ Check: AI-Times tab in dashboard shows 10 video cards
✅ Check: Email digest arrives in your inbox

---

### Test Agent 2 — Mailman

```bash
curl -X POST http://localhost:8000/api/agents/mailman/run
```

Watch Terminal 1 for:
```
[Mailman] Found X unread emails
[Mailman] Classified: Subject line → NEWSLETTER
[Mailman] Classified: Subject line → URGENT
[mailman] success — Classified X emails
```

✅ Check: Mailman tab shows pie chart and email list
✅ Check: Gmail inbox shows new labels applied to emails
✅ Check: Summary email arrives in inbox

---

### Test Agent 3 — Wallstreet Wolf

```bash
curl -X POST http://localhost:8000/api/agents/wallstreet_wolf/run
```

Watch Terminal 1 for:
```
[WallstreetWolf] Fetching stock data...
[WallstreetWolf] Fetching FX rates...
[WallstreetWolf] Fetching metals...
[WallstreetWolf] Requesting LLM commentary...
[wallstreet_wolf] success — Fetched 22 stocks, sent market brief
```

✅ Check: Wallstreet Wolf tab shows Top 5 Gainers, Losers, Watchlist
✅ Check: Market brief email arrives in inbox

---

### Test Agent 4 — Arabic Word of the Day

```bash
curl -X POST http://localhost:8000/api/agents/arabic_word/run
```

Watch Terminal 1 for:
```
[ArabicWord] Today's word: كِتَاب (Kitab) — 2:2
[ArabicWord] Verse 2:2 fetched successfully
[ArabicWord] Qwen3 analysis parsed successfully
[arabic_word] success — Word of the day: كِتَاب (Kitab)
```

✅ Check: Arabic Word tab shows full word card with root family tree
✅ Check: Daily word email arrives with verse in 3 languages
✅ Check: Audio link works (plays Quran recitation)

---

### Test All Agents at Once

```bash
curl -X POST http://localhost:8000/api/agents/wallstreet_wolf/run
curl -X POST http://localhost:8000/api/agents/ai_times/run
```

Watch Terminal 1 — you should see the **LLM Queue** managing both:
```
[LLM Queue] wallstreet_wolf waiting — queue depth: 1
[LLM Queue] wallstreet_wolf started (active=1)
[LLM Queue] ai_times waiting — queue depth: 1
[LLM Queue] wallstreet_wolf done (active=0)
[LLM Queue] ai_times started (active=1)
```

✅ This proves deadlock prevention is working — only one agent
   uses Qwen3 at a time, others wait in queue.

---

## Part 4 — Running Tests

```bash
cd multi-agent-platform
source venv/bin/activate
pytest tests/ -v
```

Expected output:
```
tests/test_arabic_word.py::TestWordLists::test_beginner_list_has_words PASSED
tests/test_arabic_word.py::TestWordLists::test_verse_refs_have_correct_format PASSED
...
tests/test_orchestrator.py::TestLLMQueue::test_single_concurrent_call PASSED
tests/test_orchestrator.py::TestBaseAgent::test_failed_run_retries_three_times PASSED
...
============================================================
48 passed in 0.65s
============================================================
```

---

## Part 5 — API Endpoints Reference

All endpoints are available while `main.py` is running.

### Status & Monitoring

```bash
# Full platform status (agents + resources + LLM queue)
curl http://localhost:8000/api/status | python3 -m json.tool

# Resource alarm check
curl http://localhost:8000/api/alarm

# Resource history (last 60 readings)
curl http://localhost:8000/api/resources/history | python3 -m json.tool
```

### Agent Triggers

```bash
# Trigger any agent manually
curl -X POST http://localhost:8000/api/agents/ai_times/run
curl -X POST http://localhost:8000/api/agents/mailman/run
curl -X POST http://localhost:8000/api/agents/wallstreet_wolf/run
curl -X POST http://localhost:8000/api/agents/arabic_word/run
```

### Data Endpoints

```bash
# Latest stock data
curl http://localhost:8000/api/stocks | python3 -m json.tool

# Latest YouTube videos
curl http://localhost:8000/api/videos | python3 -m json.tool

# Classified emails
curl http://localhost:8000/api/emails | python3 -m json.tool

# Today's Arabic word
curl http://localhost:8000/api/arabic/today | python3 -m json.tool

# Word history (SRS)
curl http://localhost:8000/api/arabic/history | python3 -m json.tool
```

---

## Part 6 — Dashboard Walkthrough

Open `http://localhost:8000` and explore 5 tabs:

| Tab | What to Look For |
|---|---|
| **Overview** | Live CPU/RAM/disk/threads updating every 5s. Agent status cards. Resource history chart. LLM Queue indicator. |
| **AI-Times** | Two columns: AI News videos and Personality/Interview videos. Each card has thumbnail, channel, and AI-generated blurb. |
| **Mailman** | Doughnut chart showing email category breakdown. Email list with AI summaries and colour-coded category badges. |
| **Wallstreet Wolf** | Top 5 Gainers (green), Top 5 Losers (red), Full Watchlist of 22 stocks. |
| **Arabic Word** | Today's Arabic word in large display. English + Urdu meanings. Verse in 3 languages. Audio link. Root family tree. SRS progress buttons. |

**Dark/Light toggle** — top right corner of the hero banner.

---

## Part 7 — Troubleshooting

**`curl: Failed to connect to localhost port 8000`**
→ `main.py` is not running. Start it in Terminal 1.

**`model qwen/qwen3-14b not found`**
→ LM Studio server is not running. Open LM Studio → Developer tab → Start Server.

**`YOUTUBE_API_KEY not set`**
→ Check your `.env` file. Make sure there are no spaces around the `=` sign.

**`SMTP Authentication Error`**
→ You are using your real Gmail password. Use a Gmail App Password instead (16 characters, no spaces).

**`token.json not found`**
→ Run `python utils/gmail_auth.py` and complete the browser flow.

**`database is locked`**
→ This is handled automatically (WAL mode + 30s timeout). If it persists, restart `main.py`.

**`Too many open files`**
→ Run `ulimit -n 4096` before starting `main.py`.

**LLM response is very slow**
→ Confirm LM Studio is using the GPU. Check LM Studio → Developer tab for tokens/second.
   Should be 30–50 tok/s on Apple Silicon.

**Agent shows `error` status on dashboard**
→ Click **▶ Run** again — the retry logic will attempt 3 times automatically.
   Check Terminal 1 for the specific error message.

---

## Part 8 — Stopping the Platform

```bash
# In Terminal 1 — press:
Control + C
```

The platform shuts down gracefully:
```
Shutting down...
Platform stopped ✓
```

---

## Quick Start Summary (After First Setup)

Once everything is configured, starting the platform every time is just:

```bash
# 1. Open LM Studio → Developer tab → Start Server

# 2. In terminal:
cd multi-agent-platform
source venv/bin/activate
ulimit -n 4096
python main.py

# 3. Open browser:
# http://localhost:8000
```

That's it! 🚀
