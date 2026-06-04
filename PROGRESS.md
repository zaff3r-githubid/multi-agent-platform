# Assignment 2 — Multi-Agent Platform: Progress & Learning Guide

> **Purpose:** This file documents every step of building the Multi-Agent Auto-Scheduling Platform.
> It is updated after every completed step. Use it to review, understand, and reference everything we build.
>
> **Legend:** ✅ Completed | ⏳ In Progress | 🔲 Not Started Yet

---

## Table of Contents

1. [What Are We Building?](#1-what-are-we-building)
2. [Download & Setup LM Studio + Qwen3](#2-download--setup-lm-studio--qwen3)
3. [Project Folder Structure](#3-project-folder-structure)
4. [Environment Configuration (.env)](#4-environment-configuration-env)
5. [Database Setup](#5-database-setup)
6. [LM Studio Client](#6-lm-studio-client)
7. [LLM Queue — Deadlock Prevention](#7-llm-queue--deadlock-prevention)
8. [Resource Monitor](#8-resource-monitor)
9. [Base Agent](#9-base-agent)
10. [Orchestrator & Scheduler](#10-orchestrator--scheduler)
11. [Agent-1: AI-Times](#11-agent-1-ai-times)
12. [Agent-2: Mailman](#12-agent-2-mailman)
13. [Agent-3: Wallstreet Wolf](#13-agent-3-wallstreet-wolf)
14. [Agent-4: Quranic Arabic Word of the Day](#14-agent-4-quranic-arabic-word-of-the-day)
15. [FastAPI Backend (main.py)](#15-fastapi-backend-mainpy)
16. [Dashboard Frontend](#16-dashboard-frontend)
17. [Email Sender Utility](#17-email-sender-utility)
18. [Tests](#18-tests)
19. [GitHub Repository](#19-github-repository)
20. [Demo Video](#20-demo-video)

---

## 1. What Are We Building?

### The Big Picture

We are building a **Multi-Agent Auto-Scheduling Platform** — a program that runs on your Mac and manages 5 specialized AI agents automatically, all powered by a local AI model (Qwen3) running through LM Studio.

Think of it like having 5 personal assistants on your computer, each with a specific job, all reporting to a manager (the orchestrator), and all using the same AI brain (Qwen3) to think.

### The 5 Agents

| Agent | Job |
|---|---|
| **Orchestrator** | The manager — coordinates all agents, monitors your computer's health, prevents conflicts |
| **AI-Times** | Fetches today's top AI YouTube videos (5 news + 5 personality) and emails you a digest |
| **Mailman** | Reads your Gmail, classifies each email using AI, applies labels, alerts you about important people |
| **Wallstreet Wolf** | Tracks 20+ stocks, shows top gainers/losers, generates AI market commentary, emails you a brief |
| **Arabic Word of the Day** | Fetches a Quranic Arabic word, explains its root, meaning in English & Urdu, and a verse reference |

### Why Local LLM?

The assignment requires that **all AI inference runs on your Mac** — no sending data to OpenAI or Anthropic's servers. This means:
- Your data stays private
- No API costs per request
- No rate limits
- Works offline

LM Studio is the app that runs the AI model locally. Qwen3 is the actual AI model (like a brain) that LM Studio loads and runs.

### Technology Stack

| Technology | Role | Why We Use It |
|---|---|---|
| **Python 3.12** | Main programming language | Required by assignment |
| **LM Studio** | Runs the AI model locally | Provides OpenAI-compatible local API |
| **Qwen3-14B** | The AI model | Required by assignment; excellent at reasoning |
| **FastAPI** | Web server (serves the dashboard) | Fast, modern, async-friendly |
| **SQLite** | Database (stores all data) | Simple file-based DB, no server needed |
| **APScheduler** | Runs agents on a schedule (cron-like) | Handles timing of all agent tasks |
| **HTML/JS** | Dashboard frontend | Shows live data in the browser |

---

## 2. Download & Setup LM Studio + Qwen3

### Status: ✅ Completed

### What is LM Studio?

LM Studio is an application that lets you download and run AI language models directly on your Mac. It handles all the complex GPU/CPU management so you don't have to. Once running, it exposes a **local web server** (at `http://localhost:1234`) that your Python code can talk to — using the same format as OpenAI's API.

This is why we install the `openai` Python package — not to call OpenAI's cloud, but because LM Studio speaks the same language. It's like using a universal remote to control your own TV.

### What is Qwen3-14B?

Qwen3 is an AI model made by Alibaba. The "14B" means it has **14 billion parameters** — think of parameters as the model's "knowledge units." More parameters = smarter, but needs more RAM.

- **14B requires ~10GB of RAM** to load
- Your Mac has **48GB RAM** — more than enough
- It runs at approximately 30-50 tokens/second on your hardware

### Steps Taken ✅

1. ✅ Opened LM Studio → Discover tab → searched `Qwen3-14B`
2. ✅ Downloaded `Qwen3-14B (Q4_K_M)` — the Q4_K_M means it's compressed (quantized) to save RAM while keeping quality high
3. ✅ Loaded the model in LM Studio → Developer tab → Started the server
4. ✅ Verified the server is running with:

```bash
curl http://localhost:1234/v1/models
```

**Output received:**
```json
{
  "data": [
    {
      "id": "qwen/qwen3-14b",
      "object": "model",
      "owned_by": "organization_owner"
    }
  ]
}
```

This confirms:
- LM Studio server is running on port 1234
- Qwen3-14B is loaded and ready
- The model ID is `qwen/qwen3-14b` — this is what we reference in our code

### Key Concept: Why Port 1234?

A "port" is like a door number on your computer. LM Studio opens door 1234 and listens for requests. When our Python code sends a prompt to `http://localhost:1234/v1/chat/completions`, LM Studio receives it, runs it through Qwen3, and sends back the response — all on your Mac, no internet needed.

---

## 3. Project Folder Structure

### Status: ✅ Completed

### Why Do We Need a Folder Structure?

As projects grow, having all files in one folder becomes messy and hard to manage. We organize code into folders by **responsibility** — each folder handles one specific concern. This is called **Separation of Concerns** and is a fundamental software engineering principle.

### Structure Created

```
multi-agent-platform/           ← Root folder (your project lives here)
│
├── PROGRESS.md                 ← This file!
├── main.py                     ← Entry point — starts everything
├── requirements.txt            ← List of Python packages needed
├── .env                        ← Your secret keys and config (NOT on GitHub)
├── .env.example                ← Template showing what .env needs (safe for GitHub)
├── .gitignore                  ← Tells Git what NOT to upload (secrets, temp files)
│
├── orchestrator/               ← The "manager" layer
│   ├── __init__.py             ← Makes this a Python package
│   ├── scheduler.py            ← Schedules when each agent runs
│   ├── resource_monitor.py     ← Watches CPU, RAM, disk usage
│   ├── llm_queue.py            ← Controls access to the AI model
│   └── deadlock_guard.py       ← Prevents agents from freezing each other
│
├── agents/                     ← Each agent lives here
│   ├── __init__.py
│   ├── base_agent.py           ← Shared code all agents inherit
│   ├── ai_times.py             ← Agent 1: YouTube videos
│   ├── mailman.py              ← Agent 2: Gmail classifier
│   ├── wallstreet_wolf.py      ← Agent 3: Stock tracker
│   └── arabic_word.py          ← Agent 4: Quranic Arabic word of the day
│
├── database/                   ← All database-related code
│   ├── __init__.py
│   ├── models.py               ← Defines the database table structure
│   └── db.py                   ← Functions to connect and query the database
│
├── frontend/                   ← The web dashboard (what you see in browser)
│   ├── index.html              ← Main dashboard page
│   └── dashboard.js            ← JavaScript for live updates and charts
│
├── utils/                      ← Shared helper tools
│   ├── __init__.py
│   ├── llm_client.py           ← Talks to LM Studio
│   ├── email_sender.py         ← Sends HTML emails via Gmail SMTP
│   └── gmail_auth.py           ← Sets up Gmail OAuth for Mailman agent
│
└── tests/                      ← Automated tests to verify code works
    ├── test_orchestrator.py
    ├── test_wallstreet.py
    ├── test_researcher.py
    └── test_email_sender.py
```

### Commands Run ✅

```bash
cd ~
mkdir multi-agent-platform && cd multi-agent-platform
mkdir -p orchestrator agents database frontend utils tests
touch orchestrator/__init__.py agents/__init__.py database/__init__.py utils/__init__.py
touch main.py requirements.txt .gitignore
```

### What is `__init__.py`?

An empty file that tells Python "this folder is a package — you can import code from it." Without it, Python won't recognize the folder as importable. For example, `from agents.base_agent import BaseAgent` only works because `agents/__init__.py` exists.

---

## 4. Environment Configuration (.env)

### Status: ⏳ In Progress

### What is a .env File?

A `.env` file stores **secret configuration values** — things like API keys, passwords, and URLs — separately from your code. This is critical for two reasons:

1. **Security:** You never want passwords or API keys in your code files. If you upload your code to GitHub, anyone can see it.
2. **Flexibility:** Different environments (your Mac, a server, a teammate's machine) can have different values without changing the code.

### How It Works

The `python-dotenv` package reads your `.env` file when the app starts and loads all values as **environment variables** — making them accessible anywhere in your code via `os.getenv("VARIABLE_NAME")`.

For example:
```python
import os
youtube_key = os.getenv("YOUTUBE_API_KEY")  # Reads from .env automatically
```

### What Each Variable Means

```ini
# ── LLM (LM Studio) ──────────────────────────────
LLM_BASE_URL=http://localhost:1234/v1
# Where LM Studio's API server is running (on your Mac, port 1234)

LLM_MODEL=qwen/qwen3-14b
# The exact model ID returned by LM Studio (from the curl test)

# ── YouTube ──────────────────────────────────────
YOUTUBE_API_KEY=your_youtube_api_key_here
# From Google Cloud Console — allows fetching YouTube video data

# ── Email ────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
# Gmail's outgoing email server address

SMTP_PORT=587
# Port 587 is the standard port for secure email sending (TLS)

SMTP_USER=your_email@gmail.com
# Your Gmail address (used as the "from" address)

SMTP_PASSWORD=your_16_char_app_password
# NOT your Gmail password — a special App Password Google generates
# Required because Google blocks regular passwords for app access

EMAIL_RECIPIENT=your_email@gmail.com
# Where the agents send their digest emails (can be same as SMTP_USER)

# ── Database ─────────────────────────────────────
DATABASE_URL=sqlite:///./platform.db
# sqlite:/// = use SQLite (file-based database)
# ./platform.db = create the file called platform.db in the project root

# ── Dashboard ────────────────────────────────────
DASHBOARD_PORT=8000
# The port your web dashboard runs on (open http://localhost:8000 in browser)

# ── Mailman ──────────────────────────────────────
KEY_PEOPLE=boss@work.com,important@person.com
# Comma-separated list of email addresses — Mailman will alert you when
# emails from these people arrive
```

### Why Gmail App Password (Not Your Real Password)?

Google introduced App Passwords as a security measure. When you enable 2-Step Verification, Google stops allowing apps to use your real password via SMTP (email sending protocol). Instead, you generate a 16-character one-time password specifically for this app. It only works for SMTP — it cannot be used to log into your Google account.

### .gitignore — Protecting Your Secrets ✅

The `.gitignore` file tells Git (version control) which files to **never upload to GitHub**:

```
venv/           ← Virtual environment (thousands of files, not needed on GitHub)
__pycache__/    ← Python's compiled files (auto-generated, not needed)
*.pyc           ← Compiled Python files
.env            ← YOUR SECRETS — never upload this!
token.json      ← Gmail OAuth token — contains your Gmail access
credentials.json ← Gmail OAuth credentials — sensitive
platform.db     ← Your database (personal data)
.DS_Store       ← Mac system file, irrelevant to project
```

### Steps Completed

- ✅ Created `.env.example` (safe template for GitHub)
- ✅ Copied to `.env` with `cp .env.example .env`
- ✅ Added YouTube API key
- ✅ Set `LLM_BASE_URL` and `LLM_MODEL`
- ⏳ Gmail App Password (in progress)
- ⏳ KEY_PEOPLE list (fill in your important contacts)

---

## 5. Database Setup

### Status: ✅ Completed

### What is SQLite?

SQLite is a database that lives entirely in **a single file** on your computer (`platform.db`). Unlike MySQL or PostgreSQL, it needs no separate server process — your Python code reads and writes to it directly. Perfect for local applications like this.

Think of it like a very powerful, organized Excel file that your code can query instantly.

### What is a Database Schema?

A schema is the **blueprint** of your database — it defines what tables exist and what columns each table has. We define ours in `database/models.py`.

### Our Tables and Why Each Exists

#### `agent_runs` — The Activity Log
```sql
CREATE TABLE IF NOT EXISTS agent_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,  -- Unique ID for each run
    agent_name  TEXT NOT NULL,                       -- Which agent ran (e.g. "mailman")
    status      TEXT NOT NULL,                       -- 'success', 'error', or 'running'
    started_at  DATETIME NOT NULL,                   -- When it started
    finished_at DATETIME,                            -- When it finished (null if still running)
    message     TEXT                                 -- Result message or error details
);
```
**Why:** Every time an agent runs, we log it. This lets the dashboard show "last run time" and "last status" for each agent. Also useful for debugging — if an agent failed, you can see the error message.

#### `resource_metrics` — System Health Log
```sql
CREATE TABLE IF NOT EXISTS resource_metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cpu_pct     REAL,        -- CPU usage percentage (e.g. 45.2)
    ram_pct     REAL,        -- RAM usage percentage (e.g. 62.1)
    disk_pct    REAL,        -- Disk usage percentage (e.g. 78.0)
    threads     INTEGER,     -- Number of active threads
    recorded_at DATETIME NOT NULL
);
```
**Why:** The orchestrator polls system resources every 30 seconds and stores them here. The dashboard reads this to draw the live resource chart. Also used to trigger alarms when any value exceeds 90%.

#### `stocks` — Stock Price History
```sql
CREATE TABLE IF NOT EXISTS stocks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL,   -- Stock symbol (e.g. "AAPL")
    price       REAL,            -- Current price in USD
    change_pct  REAL,            -- % change from previous close
    volume      INTEGER,         -- Trading volume
    fetched_at  DATETIME NOT NULL
);
```
**Why:** Each time Wallstreet Wolf runs, it saves stock data here. Keeping history lets us show sparkline charts (mini price trend graphs) on the dashboard.

#### `email_log` — Classified Emails
```sql
CREATE TABLE IF NOT EXISTS email_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_id        TEXT UNIQUE,     -- Gmail's unique message ID (prevents duplicates)
    sender          TEXT,            -- Who sent it
    subject         TEXT,            -- Email subject line
    snippet         TEXT,            -- Short preview of the email body
    classification  TEXT,            -- AI's classification (e.g. "URGENT")
    ai_summary      TEXT,            -- AI-generated one-line summary
    classified_at   DATETIME NOT NULL
);
```
**Why:** Mailman logs every classified email so it doesn't re-classify the same email twice (the `UNIQUE` constraint on `gmail_id` prevents duplicates). Also feeds the dashboard's email list view.

#### `videos` — YouTube Videos
```sql
CREATE TABLE IF NOT EXISTS videos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id    TEXT UNIQUE,   -- YouTube's video ID (prevents duplicates)
    title       TEXT,
    channel     TEXT,
    thumbnail   TEXT,          -- URL to thumbnail image
    url         TEXT,          -- Full YouTube URL
    category    TEXT,          -- 'news' or 'personality'
    blurb       TEXT,          -- AI-generated "why this matters" sentence
    fetched_at  DATETIME NOT NULL
);
```
**Why:** AI-Times fetches 5 news + 5 personality videos. We store them so the dashboard can display them with thumbnails, and so we don't re-fetch the same videos.

#### `arabic_words` — Word of the Day History
```sql
CREATE TABLE IF NOT EXISTS arabic_words (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    word            TEXT,          -- The Arabic word
    root            TEXT,          -- The 3-letter root (e.g. ك-ت-ب)
    meaning_en      TEXT,          -- English meaning
    meaning_ur      TEXT,          -- Urdu meaning
    verse_ref       TEXT,          -- Quran reference (e.g. "2:255")
    verse_ar        TEXT,          -- Arabic verse text
    verse_en        TEXT,          -- English translation of verse
    verse_ur        TEXT,          -- Urdu translation of verse
    llm_explanation TEXT,          -- Qwen3's detailed explanation
    fetched_at      DATETIME NOT NULL
);
```
**Why:** Stores each day's word so we can show history on the dashboard and never repeat a word.

### The Database Connection (`database/db.py`)

```python
import sqlite3, os
from database.models import SCHEMA

DB_PATH = os.getenv("DATABASE_URL", "platform.db").replace("sqlite:///./", "")
# Strips the "sqlite:///./" prefix to get just "platform.db"
# os.getenv reads from your .env file

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # check_same_thread=False allows multiple agents to use the DB simultaneously
    conn.row_factory = sqlite3.Row
    # row_factory makes results accessible like dictionaries: row["column_name"]
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)  # Runs all our CREATE TABLE statements
        conn.commit()               # Saves changes permanently
    print("Database initialised ✓")
```

### Test Command Run ✅

```bash
python -c "from database.db import init_db; init_db()"
# Output: Database initialised ✓
```

This created `platform.db` in your project root.

---

## 6. LM Studio Client

### Status: ✅ Completed

### What is This File?

`utils/llm_client.py` is a **thin wrapper** around the LM Studio API. Instead of every agent writing HTTP request code themselves, they all call this one helper. This is the **DRY principle** (Don't Repeat Yourself).

### Why Use the `openai` Package?

LM Studio's API is **deliberately designed to be identical to OpenAI's API format**. This means the `openai` Python package works perfectly with it — just pointed at `localhost:1234` instead of OpenAI's servers. No data ever leaves your Mac.

### The Code

```python
# utils/llm_client.py
import os
from openai import AsyncOpenAI

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
LLM_MODEL    = os.getenv("LLM_MODEL", "qwen/qwen3-14b")

# AsyncOpenAI = async version (non-blocking — can handle multiple agents)
# base_url points to YOUR Mac, not OpenAI's servers
# api_key="lm-studio" is a dummy value — LM Studio doesn't check API keys
_client = AsyncOpenAI(base_url=LLM_BASE_URL, api_key="lm-studio")

async def generate(prompt: str, system: str = "You are a helpful assistant.") -> str:
    response = await _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            # system = instructions telling the AI what role to play
            {"role": "user",   "content": prompt},
            # user = the actual question or task
        ],
        temperature=0.7,
        # temperature controls creativity: 0.0 = robotic/deterministic, 1.0 = very creative
        # 0.7 is a good balance for our use cases
        max_tokens=1024,
        # Maximum length of the response (in tokens, roughly 3/4 of a word each)
    )
    return response.choices[0].message.content.strip()
```

### Key Concept: `async` / `await`

You'll see `async` and `await` throughout this project. Here's what it means:

- **Normal (synchronous) code:** Does one thing at a time. Agent A calls the LLM → waits → gets response → Agent B can go.
- **Async code:** Starts a task, hands control back while waiting, lets other things run. Agent A calls the LLM → while waiting, Agent B can do its work → both finish faster.

This is essential because our agents would otherwise block each other waiting for the AI model.

### Test Completed ✅

```bash
python -c "
import asyncio
from utils.llm_client import generate

async def test():
    r = await generate('Say hello in one sentence.')
    print(r)

asyncio.run(test())
"
```

---

## 7. LLM Queue — Deadlock Prevention

### Status: ✅ Completed

### What Problem Does This Solve?

Imagine 4 agents all try to call Qwen3 at the exact same moment. The model gets overwhelmed, responses slow to a crawl, or worse — agents start waiting for each other in a circle (deadlock). The LLM Queue prevents this.

### How It Works — The Semaphore Pattern

A **Semaphore** is like a single bathroom key. Only one person (agent) can hold the key at a time. Everyone else waits politely in line. When the first person is done, the next one gets the key automatically.

We use `asyncio.Semaphore(1)` which means maximum 1 concurrent LLM call at any time.

### Key Concepts

- **`async with self._sem:`** — This line "acquires" the key. If someone else has it, execution pauses here and waits automatically. No manual checking needed.
- **`finally` block** — The key is ALWAYS released even if an error occurs. This is critical — without it, a crashed agent would hold the key forever and all other agents would freeze (deadlock).
- **Singleton pattern** — We create ONE instance (`llm_queue = LLMQueue()`) at the bottom of the file. All agents import this same object. This guarantees there is truly only one queue controlling everything.

### The Code

```python
# orchestrator/llm_queue.py
import asyncio
import logging
from utils.llm_client import generate

logger = logging.getLogger(__name__)

class LLMQueue:
    def __init__(self, max_concurrent: int = 1):
        self._sem = asyncio.Semaphore(max_concurrent)
        self._active: int = 0
        self._waiting: int = 0
        self._total: int = 0

    @property
    def active(self) -> int:
        return self._active

    @property
    def waiting(self) -> int:
        return self._waiting

    async def submit(self, prompt: str, system: str = "", agent_name: str = "unknown") -> str:
        self._waiting += 1
        logger.info(f"[LLM Queue] {agent_name} waiting — queue depth: {self._waiting}")
        async with self._sem:
            self._waiting -= 1
            self._active += 1
            self._total += 1
            logger.info(f"[LLM Queue] {agent_name} started (active={self._active})")
            try:
                result = await generate(prompt, system)
                return result
            except Exception as e:
                logger.error(f"[LLM Queue] {agent_name} error: {e}")
                raise
            finally:
                self._active -= 1
                logger.info(f"[LLM Queue] {agent_name} done (active={self._active})")

    def status(self) -> dict:
        return {
            "active":  self._active,
            "waiting": self._waiting,
            "total":   self._total,
        }

# Singleton — one queue controls all agents
llm_queue = LLMQueue(max_concurrent=1)
```

### Test Result ✅

```bash
python -c "
import asyncio
from orchestrator.llm_queue import llm_queue

async def test():
    results = await asyncio.gather(
        llm_queue.submit('Say AGENT ONE in capitals only.', agent_name='agent_one'),
        llm_queue.submit('Say AGENT TWO in capitals only.', agent_name='agent_two'),
    )
    print('Agent 1 result:', results[0])
    print('Agent 2 result:', results[1])

asyncio.run(test())
"
```

Output:
```
Agent 1 result: AGENT ONE
Agent 2 result: AGENT TWO
```

Note: The INFO log messages (queue depth, active count) did not show because Python's default logging level is WARNING. These will be visible once we configure logging in `main.py` later.

---

## 8. Resource Monitor

### Status: ✅ Completed

### What Problem Does This Solve?

The orchestrator needs to watch your computer's health and alert you when things get overloaded (CPU/RAM/disk > 90%). It also needs to log metrics to the database so the dashboard can draw live charts.

### How It Works

Every 30 seconds the scheduler calls `record_metrics()` which:
1. Uses `psutil` library to read real system values from macOS
2. Saves them to the `resource_metrics` table in SQLite
3. Checks if any value exceeds 90% — if so, attaches an alarm with a corrective action message
4. Returns the data so the dashboard can display it immediately

### Key Concepts

- **`psutil`** — A Python library that reads system stats (CPU, RAM, disk, threads) directly from the OS. Works on Mac, Windows, and Linux.
- **`cpu_percent(interval=1)`** — Measures CPU over 1 second for accuracy. An instant snapshot would give misleading spikes.
- **`datetime.utcnow()`** — We always store times in UTC (Universal Time) not local time. This avoids timezone confusion — the dashboard converts to local time for display.
- **Corrective Actions** — When an alarm fires, we don't just say "CPU is high" — we tell the user exactly what to do. This is what gets marks in the Orchestrator section.
- **`cleanup_old_metrics()`** — Prevents the database from growing forever. After 7 days, old metrics are deleted automatically.

### Three Functions and When They're Used

| Function | Called By | Purpose |
|---|---|---|
| `record_metrics()` | Scheduler (every 30s) | Take snapshot, save to DB, check alarms |
| `latest_metrics()` | Dashboard API (every 5s) | Show current values on dashboard |
| `metrics_history(60)` | Dashboard chart | Draw the scrolling resource chart |

### Test Result ✅

```
Recording metrics...
CPU:     0.6%
RAM:     58.7%
Disk:    1.4%
Threads: 1
Alarms:  []

Latest from DB: {'cpu': 0.6, 'ram': 58.7, 'disk': 1.4, 'threads': 1, 'recorded_at': '2026-06-03 23:15:42.884781'}
```

All values saved to database correctly. No alarms triggered (Mac is healthy).

---

## 9. Base Agent

### Status: ✅ Completed

### What is an Abstract Base Class?

`ABC` (Abstract Base Class) is a Python concept that lets you define a **template** that other classes must follow. By marking `_run_logic()` as `@abstractmethod`, Python enforces that every agent MUST implement its own version — you literally cannot create an agent without it.

This is called **polymorphism** — each agent has the same interface (`run()`, `status()`) but different behaviour (`_run_logic()`).

### Key Features Built In

| Feature | How It Works |
|---|---|
| **Duplicate run prevention** | `_is_running` flag — scheduler won't start a second copy if one is already running |
| **Retry on crash** | Loops up to 3 times with 5 second delay between attempts |
| **Force restart** | `force_restart()` resets the stuck flag — called by the watchdog |
| **Database logging** | `_record()` saves every run (success or failure) to `agent_runs` table |
| **Status reporting** | `status()` returns a dict — read by dashboard every 5 seconds |

### Test Results ✅

**Normal run:**
```
Status before: never_run, last_run: None
Status after:  success, last_run: 2026-06-04T00:05:51, message: 'Test completed successfully'
```

**Crash recovery:**
```
[crashy_agent] attempt 1/3 failed: Simulated crash!
[crashy_agent] attempt 2/3 failed: Simulated crash!
[crashy_agent] attempt 3/3 failed: Simulated crash!
[crashy_agent] all 3 attempts failed. Crash count: 1
Status: error, crash_count: 1
```

Retried exactly 3 times, recorded the error, released the running flag — platform stayed alive.

---

## 10. Orchestrator & Scheduler

### Status: 🔲 Not Started Yet

---

## 11. Agent-1: AI-Times

### Status: ✅ Completed

### What It Does
Every day at 7:00am UTC it fetches two categories of YouTube videos separately, generates AI blurbs for each, saves to database, and emails a digest.

### Key Design Decisions

| Decision | Reason |
|---|---|
| Two separate YouTube queries | Assignment requires 5 news + 5 personality as distinct categories |
| 96 hour lookback window | Wider window ensures 5 results per category even on slow news days |
| `api_key` passed as parameter | Fixes module-level import timing issue — key read at runtime inside `_run_logic()` |
| `INSERT OR IGNORE` in DB | Prevents duplicate videos if agent runs twice in same day |

### Troubleshooting Fixed
- `YT_API_KEY` was being read at module import time before `load_dotenv()` ran
- Fixed by moving `os.getenv("YOUTUBE_API_KEY")` inside `_run_logic()` so it reads at runtime
- Missing comma in `_fetch_videos` method signature caused SyntaxError — fixed
- Indentation error in `_run_logic` — fixed

### Test Result ✅
```
[ai_times] success — Fetched 5 news + 5 personality videos, sent digest
Status: success, crash_count: 0
```
Email received with two sections: AI News Videos and AI Personality & Interview Videos, each with thumbnails, titles, channels, and Qwen3-generated blurbs.

---

## 12. Agent-2: Mailman

### Status: ✅ Completed

### What It Does
Every 15 minutes it scans Gmail for unread emails, classifies each one using Qwen3, applies labels, stars important emails, and sends a daily summary.

### Key Features Built
- ✅ **Gmail OAuth2** — secure token-based access, auto-refreshes when expired
- ✅ **7 categories** — URGENT, ACTION_REQUIRED, FOLLOW_UP, NEWSLETTER, NOTIFICATION, PERSONAL, OTHER
- ✅ **Auto-labelling** — creates Gmail labels if they don't exist, applies them automatically
- ✅ **Key people detection** — stars emails from configurable list in .env
- ✅ **AI summary** — Qwen3 writes one-sentence summary per email
- ✅ **Daily summary email** — category breakdown with visual bars, urgent list, key people section
- ✅ **Duplicate prevention** — gmail_id stored in DB, same email never classified twice

### How Gmail OAuth2 Works
1. `credentials.json` — downloaded from Google Cloud Console, identifies your app
2. `token.json` — created by running `gmail_auth.py` once, gives access to Gmail
3. Token auto-refreshes when expired — no manual re-authorisation needed
4. Both files are in `.gitignore` — never uploaded to GitHub

### Two LLM Calls Per Email
Each email triggers two Qwen3 calls through the LLM queue:
1. **Classification** — which of the 7 categories does this belong to?
2. **Summary** — one sentence describing what the email is about

### Test Result ✅
```
[Mailman] Classified 3 emails — 0 urgent, 1 from key people
Status: success, crash_count: 0
```
Labels applied in Gmail, key person email starred, summary email received.

---

## 13. Agent-3: Wallstreet Wolf

### Status: ✅ Completed

### What It Does
Every weekday at 6:30am UTC it fetches live market data, generates AI commentary, and emails a professional briefing.

### Data Sources
| Source | What We Fetch |
|---|---|
| Yahoo Finance (`yfinance`) | 22 stocks across Tech, Finance, Energy, Index sectors |
| Yahoo Finance | 5 currency pairs (USD/CAD, EUR, GBP, JPY, PKR) |
| Yahoo Finance | Gold and Silver futures prices |

### Key Features Built
- ✅ **Top 5 Gainers** — sorted by % change, best performers
- ✅ **Top 5 Losers** — sorted by % change, worst performers
- ✅ **Full Watchlist** — all 22 stocks with price and change
- ✅ **Currency Exchange** — 5 major USD pairs
- ✅ **Precious Metals** — Gold & Silver with daily change
- ✅ **LLM Commentary** — Qwen3 writes a 3-sentence professional market brief
- ✅ **HTML Email** — colour-coded (green/red), professional layout
- ✅ **SQLite storage** — every fetch saved for dashboard charts

### How the LLM Queue Showed Up
```
[LLM Queue] wallstreet_wolf waiting — queue depth: 1
[LLM Queue] wallstreet_wolf started (active=1, total=1)
[LLM Queue] wallstreet_wolf done (active=0)
```
This proves the semaphore is working — the agent waited for the key, used it, and released it.

### Test Result ✅
```
[wallstreet_wolf] success — Fetched 22 stocks, sent market brief
Status: success, crash_count: 0
```
Email received in Gmail with full market data, colour-coded tables, and Qwen3 commentary.

---

## 14. Agent-4: Quranic Arabic Word of the Day

### Status: ✅ Completed

### Concept Overview (150-word use-case proposal for README)

This agent helps users learn Quranic Arabic vocabulary through daily immersion. Each day, it selects a key Arabic word from a curated list of high-frequency Quranic terms, queries the AlQuran Cloud API (free, no key required) to fetch the actual verse containing that word, and passes everything to Qwen3 to generate:

- The 3-letter Arabic root and its morphological family
- Clear meaning in both English and Urdu
- A contextual explanation of the word's usage in the verse
- Related words derived from the same root

The daily digest is emailed as a beautifully formatted HTML email and displayed on a dedicated dashboard tab. A configurable word list lets users focus on specific Quranic chapters or themes. This agent is uniquely personal, culturally meaningful, and demonstrates the LLM's multilingual capability — making it a strong showcase of what local AI can do beyond typical use cases.

**External API used:** [api.alquran.cloud](https://alquran.cloud/api) — free, no API key needed.

---

## 15. FastAPI Backend (main.py)

### Status: 🔲 Not Started Yet

---

## 16. Dashboard Frontend

### Status: 🔲 Not Started Yet

---

## 17. Email Sender Utility

### Status: ✅ Completed

### What This Does

A shared helper used by all 3 email-sending agents (AI-Times, Wallstreet Wolf, Arabic Word of the Day). Instead of each agent writing SMTP code, they all call `send_html_email()`.

### Two Functions

| Function | Purpose |
|---|---|
| `send_html_email(subject, html, recipient)` | Connects to Gmail SMTP, sends the email, returns True/False |
| `build_email_wrapper(title, content, agent)` | Wraps any HTML in a professional branded email template |

### Key Concepts

- **SMTP** — Simple Mail Transfer Protocol. The standard for sending emails. Gmail's SMTP server is at `smtp.gmail.com` port 587
- **TLS (starttls)** — Encrypts the connection before sending your password. Without this, credentials would be sent in plain text
- **MIMEMultipart** — Email format that supports both plain text AND HTML. Email clients that can't render HTML fall back to plain text automatically
- **Returns True/False** — Never raises an exception. A failed email should not crash an agent run

### Test Result ✅
Email sent and received successfully in Gmail inbox with professional HTML formatting.

---

## 18. Tests

### Status: ✅ Completed

### Test Files Created

| File | Tests | What's Covered |
|---|---|---|
| `test_orchestrator.py` | 10 | LLM Queue semaphore, deadlock prevention, Base Agent retry logic |
| `test_wallstreet.py` | 11 | Ticker count, groups, FX pairs, metals, agent inheritance |
| `test_arabic_word.py` | 16 | Word lists, SRS intervals, difficulty settings, verse format |
| `test_email_sender.py` | 11 | HTML template, SMTP error handling, config validation |

### Result ✅
```
48 passed in 0.65s
```
All 48 tests passed. Zero failures.

### Key Testing Concepts Used

- **`unittest.mock.patch`** — replaces real functions (SMTP, database) with fake ones during tests so we don't send real emails or need a live database
- **`AsyncMock`** — mock version of async functions (needed for testing async code)
- **`pytest.mark.asyncio`** — tells pytest to run async test functions properly
- **`conftest.py`** — adds project root to Python path so all test files can import from `agents/`, `utils/`, etc.

---

## 19. GitHub Repository

### Status: ✅ Completed

### Requirements Checklist
- ✅ Repository created (private for now → make public before submission)
- ✅ README.md with full setup instructions
- ✅ .gitignore properly excluding .env, token.json, credentials.json, platform.db
- ✅ First commit includes Agent-4 use-case proposal (150 words in README)
- 🔲 Architecture diagram (PNG in repo) — add before submission
- 🔲 Make repository PUBLIC before submitting

### Repository
https://github.com/zaff3r-githubid/multi-agent-platform

### ⚠️ Before Submitting
1. Add architecture diagram PNG to repo
2. Go to Settings → Danger Zone → Change visibility → Make Public

---

## 20. Demo Video

### Status: 🔲 Not Started Yet

### Rules (Critical — Read Carefully)
- ✅ Max **10 minutes** — even 10:01 = **0 marks**
- ✅ Upload to **YouTube** — no other format accepted
- ✅ **Product demo only** — no slides, no architecture walkthrough
- ✅ All **5 agents must work live** — broken agent = full deduction for that agent (15 marks)
- ✅ Screen must be **readable** — avoid ultra-high resolution that makes text tiny

### Script (10 min)

| Time | What to Show |
|---|---|
| 0:00–1:00 | Dashboard overview — show all 5 agents listed, resource monitor live |
| 1:00–2:30 | Run Wallstreet Wolf — show terminal logs, email arriving in inbox |
| 2:30–4:00 | Run AI-Times — show 5 news + 5 personality video cards on dashboard |
| 4:00–5:30 | Run Mailman — show emails being classified and labelled in Gmail live |
| 5:30–7:00 | Run Researcher (Arabic Word) — show dashboard tab, email digest |
| 7:00–8:00 | Trigger 2 agents simultaneously — show LLM queue "active=1" preventing conflict |
| 8:00–9:00 | Trigger a 90% resource alarm (or simulate it) — show on-screen corrective alert |
| 9:00–10:00 | Show GitHub repo — README, folder structure, tests passing |

---

## Grading Checklist (100 Marks)

| # | Component | Marks | Status | Key Requirements |
|---|---|---|---|---|
| 1 | Orchestrator & Architecture | 15 | 🔲 | Resource monitor, 90% alarm, LLM semaphore, crash recovery |
| 2 | AI-Times | 15 | 🔲 | 5 news + 5 personality (separate), thumbnails, email, dashboard tab |
| 3 | Mailman | 15 | 🔲 | 7 categories, key-people alert, daily summary email, dashboard tab |
| 4 | Wallstreet Wolf | 15 | 🔲 | 20+ stocks, top 5 gainers/losers/watchlist, forex/metals, email |
| 5 | Agent-4 (Arabic Word) | 15 | 🔲 | AlQuran API, LLM explanation, email, dashboard tab, configurable |
| 6 | Code Quality & Creativity | 10 | 🔲 | Clean code, README, architecture diagram, tests |
| 7 | Demo Video | 15 | 🔲 | YouTube, max 10 min, all agents live |
| | **Total** | **100** | | |

---

*Last updated: Step 6 — LM Studio Client complete. Next: LLM Queue (Step 7)*
