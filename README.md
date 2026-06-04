# Multi-Agent Auto-Scheduling Platform

> A fully local AI-powered multi-agent system — five specialized agents orchestrated by a central scheduler, running entirely on your machine using LM Studio (Qwen3-14B). No hosted LLM APIs.

---

## What This Does

This platform runs five AI agents on a schedule, all powered by a local Qwen3-14B LLM via LM Studio:

| Agent | What it does |
|---|---|
| **Main Orchestrator** | Manages all agents, monitors CPU/RAM/disk/threads, queues LLM calls, prevents deadlocks, restarts crashed agents |
| **AI-Times** | Fetches today's top AI YouTube videos (5 news + 5 personality), generates LLM blurbs, emails an HTML digest |
| **Mailman** | Monitors Gmail inbox, classifies emails into 7 categories with Qwen3, applies labels, stars urgent mail, sends daily summary |
| **Wallstreet Wolf** | Tracks 20+ stocks via Yahoo Finance, shows top 5 gainers/losers, LLM market commentary, currency pairs, Gold & Silver, daily email |
| **Arabic Word of the Day** | Fetches Quranic Arabic vocabulary from AlQuran Cloud API, generates root analysis, verb form (I-X), English/Urdu meanings, spaced repetition system, daily email with micro-quiz |

A web dashboard at `localhost:8000` shows live agent status, resource usage, LLM queue, stock data, video cards, email classifications, and the Arabic word of the day.

---

## Agent-4 Use Case Proposal

This agent helps users learn Quranic Arabic vocabulary through daily immersion. Each day it selects a key Arabic word from a curated list (Beginner/Intermediate/Advanced), queries the AlQuran Cloud API for the verse containing that word, and uses Qwen3-14B to generate a comprehensive linguistic analysis including the 3-letter root, verb form (Form I through X) with meaning-shift explanation, English and Urdu meanings, and a root family tree showing 5-6 related words. A 3-box Leitner spaced repetition system tracks which words the user has mastered. Daily emails include a micro-quiz from the previous day's word to reinforce retention. The dashboard displays an interactive root family visualisation, embedded audio from Mishary Alafasy's recitation, and SRS progress tracking. A Sunday weekly recap email reviews all 7 words from the week with mastery status. This agent is uniquely personal, culturally meaningful, and demonstrates the LLM's multilingual capability beyond typical use cases.

**External API:** [AlQuran Cloud API](https://alquran.cloud/api) — free, no API key required.

---

## Architecture

```
React/HTML Dashboard (localhost:8000)
         │
         ▼
   Main Orchestrator (FastAPI + APScheduler)
   ├── LLM Queue (asyncio.Semaphore — prevents concurrent overload)
   ├── Resource Monitor (psutil — CPU, RAM, Disk, Threads every 30s)
   ├── Deadlock Watchdog (force-restarts stuck agents)
   └── SQLite (logs, schedules, state)
         │
   ┌─────┴─────────────────────────┐
   ▼         ▼          ▼          ▼
AI-Times  Mailman  Wallstreet  Arabic Word
   │         │      Wolf         │
   ▼         ▼       │           ▼
YouTube   Gmail     yfinance   AlQuran
API       API        │         Cloud API
                     ▼
              Yahoo Finance
                     │
         ▼           ▼           ▼
         └───── SMTP Email Output ─────┘
                     │
               LM Studio (Qwen3-14B)
               localhost:1234
```

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | `brew install python@3.12` |
| LM Studio | latest | [lmstudio.ai](https://lmstudio.ai) |
| Git | any | `brew install git` |

### Hardware

- Tested on Apple M5 Pro, 48 GB unified RAM
- Minimum: 16 GB RAM (use `qwen3:8b` instead)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/multi-agent-platform.git
cd multi-agent-platform
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up LM Studio

1. Download [LM Studio](https://lmstudio.ai)
2. Search for and download `Qwen3-14B (Q4_K_M)`
3. Go to Developer tab → Load model → Start Server
4. Verify: `curl http://localhost:1234/v1/models`

### 5. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```ini
LLM_BASE_URL=http://localhost:1234/v1
LLM_MODEL=qwen/qwen3-14b
YOUTUBE_API_KEY=your_youtube_api_key_here
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
EMAIL_RECIPIENT=your_email@gmail.com
DATABASE_URL=sqlite:///./platform.db
DASHBOARD_PORT=8000
KEY_PEOPLE=important@person.com
ARABIC_DIFFICULTY=beginner
```

### 6. Set up Gmail App Password

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Enable 2-Step Verification if not already on
3. Create an App Password for "multi-agent-platform"
4. Paste the 16-character password into `SMTP_PASSWORD`

### 7. Set up YouTube Data API

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → Enable YouTube Data API v3
3. Create an API key → paste into `YOUTUBE_API_KEY`

### 8. Set up Gmail OAuth (for Mailman agent)

1. In Google Cloud Console, enable Gmail API
2. Create OAuth credentials (Desktop app) → download as `credentials.json`
3. Move to project root: `mv ~/Downloads/client_secret_*.json ./credentials.json`
4. Run once to authorise: `python utils/gmail_auth.py`
5. Complete browser flow → `token.json` created automatically

### 9. Initialise the database

```bash
python -c "from database.db import init_db; init_db()"
```

---

## Running the Platform

```bash
source venv/bin/activate
python main.py
```

You should see:

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

Open your browser at `http://localhost:8000`

---

## Dashboard Tabs

| Tab | What it shows |
|---|---|
| **Overview** | Live CPU/RAM/disk/threads, all agent status, resource history chart, LLM queue |
| **AI-Times** | 5 news + 5 personality video cards with thumbnails and AI blurbs |
| **Mailman** | Category breakdown pie chart, classified email list with AI summaries |
| **Wallstreet Wolf** | Top 5 gainers, top 5 losers, full 20+ stock watchlist |
| **Arabic Word** | Today's word card, root family tree, verse in 3 languages, audio link, SRS progress |

---

## Agent Schedule

| Agent | Schedule |
|---|---|
| AI-Times | Daily at 07:00 UTC |
| Mailman | Every 15 minutes |
| Wallstreet Wolf | Mon–Fri at 06:30 UTC |
| Arabic Word of the Day | Daily at 08:00 UTC |
| Weekly Arabic Recap | Sundays at 09:00 UTC |
| Resource Monitor | Every 30 seconds |

### Manual Triggers

```bash
curl -X POST http://localhost:8000/api/agents/ai_times/run
curl -X POST http://localhost:8000/api/agents/mailman/run
curl -X POST http://localhost:8000/api/agents/wallstreet_wolf/run
curl -X POST http://localhost:8000/api/agents/arabic_word/run
```

---

## Running Tests

```bash
pytest tests/ -v
```

Expected output: **48 passed**

---

## Folder Structure

```
multi-agent-platform/
├── README.md
├── PROGRESS.md
├── main.py
├── conftest.py
├── requirements.txt
├── .env.example
├── .gitignore
│
├── orchestrator/
│   ├── scheduler.py
│   ├── resource_monitor.py
│   ├── llm_queue.py
│   └── deadlock_guard.py
│
├── agents/
│   ├── base_agent.py
│   ├── ai_times.py
│   ├── mailman.py
│   ├── wallstreet_wolf.py
│   └── arabic_word.py
│
├── database/
│   ├── models.py
│   └── db.py
│
├── frontend/
│   └── index.html
│
├── utils/
│   ├── llm_client.py
│   ├── email_sender.py
│   ├── gmail_auth.py
│   └── arabic_word_lists.py
│
└── tests/
    ├── test_orchestrator.py
    ├── test_wallstreet.py
    ├── test_arabic_word.py
    └── test_email_sender.py
```

---

## Troubleshooting

**LM Studio not responding**
Make sure the server is started in LM Studio → Developer tab → Start Server

**`token.json` not found**
Run `python utils/gmail_auth.py` and complete browser authorisation

**`SMTP Authentication Error`**
Use a Gmail App Password (16 characters), not your account password

**`database is locked`**
Already handled — SQLite WAL mode and 30s timeout configured in `db.py`

**Dashboard shows no data**
Trigger agents manually using the ▶ Run buttons on the dashboard

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.14 | Backend language |
| LM Studio + Qwen3-14B | Local LLM inference |
| FastAPI + Uvicorn | Web server and API |
| APScheduler | Agent scheduling (cron + interval) |
| SQLite + WAL mode | Persistent storage |
| psutil | System resource monitoring |
| yfinance | Stock market data |
| Google APIs | YouTube Data API + Gmail API |
| AlQuran Cloud API | Quranic verse data and audio |
| httpx | Async HTTP client |
| Chart.js | Dashboard charts |

---

## Licence

MIT
