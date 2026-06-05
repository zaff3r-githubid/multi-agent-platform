# Demo Video — Talking Points & Pre-Flight Checklist

> **CRITICAL RULES — Read before recording:**
> - Video must be **MAX 10 MINUTES** — even 10:01 = 0 marks
> - Upload to **YouTube only** — no other format accepted
> - **Product demo only** — no slides, no architecture walkthrough
> - All 5 agents must work **live on camera**
> - Screen must be **readable** — zoom in if needed

---

## Pre-Flight Checklist (Run BEFORE Recording)

### Step 1 — Environment Setup
Open two terminal windows side by side with your browser.

**Make sure LM Studio is open and the server is running first!**
- Open LM Studio → Developer tab → confirm server is running on port 1234

**Terminal 1 — Start the platform (use start.sh):**
```bash
cd ~/multi-agent-platform
./start.sh
```

> `start.sh` automatically handles:
> - ✅ Activating the virtual environment (venv)
> - ✅ Setting `ulimit -n 4096` (prevents "too many open files" error)
> - ✅ Running `caffeinate` to prevent Mac from sleeping mid-demo
> - ✅ Starting `main.py`

Wait until you see:
```
=================================================
  Multi-Agent Platform — Starting
=================================================
  Python: /Users/.../venv/bin/python
  Preventing Mac sleep with caffeinate...
  Dashboard → http://localhost:8000
```

**Terminal 2 — For all other commands:**
```bash
cd ~/multi-agent-platform
```
> No need to activate venv in Terminal 2 — curl commands work without it

---

### Step 2 — Warm Up All Agents (Run in Order)

Wait for each command to complete before running the next.

**Agent 1 — Wallstreet Wolf** (~60 seconds):
```bash
curl -X POST http://localhost:8000/api/agents/wallstreet_wolf/run
```
Wait for terminal to show: `[wallstreet_wolf] success`

---

**Agent 2 — Arabic Word of the Day** (~2 minutes):
```bash
curl -X POST http://localhost:8000/api/agents/arabic_word/run
```
Wait for terminal to show: `[arabic_word] success`

---

**Agent 3 — AI-Times** (~3 minutes):
```bash
curl -X POST http://localhost:8000/api/agents/ai_times/run
```
Wait for terminal to show: `[ai_times] success`

---

**Agent 4 — Mailman** (~2 minutes):
```bash
curl -X POST http://localhost:8000/api/agents/mailman/run
```
Wait for terminal to show: `[mailman] success`

---

### Step 3 — Verify Everything Looks Good

```bash
curl http://localhost:8000/api/status | python3 -m json.tool
```
All 4 agents should show `"last_status": "success"`

```bash
curl http://localhost:8000/api/alarm
```
Should return `{"alarms": []}` — Mac is healthy

```bash
curl http://localhost:8000/api/stocks | python3 -m json.tool
```
Should return stock data

```bash
pytest tests/ -v
```
Should show `48 passed`

---

### Step 4 — Browser Setup
1. Open `http://localhost:8000`
2. Click through all 5 tabs — make sure data is showing
3. Zoom browser to **125%** so text is readable in recording
4. Make sure both Terminal 1 and browser are visible side by side

---

### Step 5 — Recording Setup
1. Open **QuickTime Player** → File → New Screen Recording
2. Click the dropdown arrow → select your microphone
3. Choose to record the full screen or a window
4. Font size in Terminal: minimum **14pt** (Terminal → Preferences → Font)
5. Do a **10 second test recording** to check audio levels

---

## Demo Script — Minute by Minute

---

### 0:00 – 1:00 | Dashboard Overview

**What to show:**
- Open browser at `http://localhost:8000`
- Point to the hero banner
- Point to the 5 metric cards (CPU, RAM, Disk, Threads, LLM Queue)
- Point to the 4 agent rows showing green SUCCESS badges
- Point to the live resource history chart updating

**What to say:**
> "This is a fully local Multi-Agent Auto-Scheduling Platform.
> Five specialized AI agents run automatically on a schedule —
> all powered by Qwen3-14B running right here on this machine
> through LM Studio. No data leaves this computer.
> No OpenAI, no Anthropic, no cloud APIs whatsoever.
>
> The dashboard updates every 5 seconds. You can see live CPU,
> RAM, disk usage, and thread count. The LLM Queue indicator
> shows whether Qwen3 is currently processing a request.
> All four agents are showing success from their last run."

---

### 1:00 – 2:30 | Wallstreet Wolf

**What to show:**
- Click Wallstreet Wolf tab
- Show Top 5 Gainers, Top 5 Losers, Full Watchlist
- Click **▶ Run Now**
- Switch to Terminal 1 — show LLM queue log lines firing
- Switch back to browser — show data refreshing
- Open Gmail inbox — show the market brief email

**What to say:**
> "Agent 3 is Wallstreet Wolf. It tracks 22 stocks across
> Tech, Finance, Energy, and Index sectors — plus five currency
> exchange pairs and Gold and Silver prices from Yahoo Finance.
>
> Let me trigger it manually. Watch the terminal — you can see
> the LLM Queue: wallstreet_wolf waiting, then started, then
> done. Qwen3 just wrote a 3-sentence market commentary
> entirely on this machine.
>
> And the email has already arrived in my inbox — a fully
> formatted HTML market brief with colour-coded gainers
> and losers."

---

### 2:30 – 4:00 | AI-Times

**What to show:**
- Click AI-Times tab
- Show the two columns — news videos and personality videos
- Point to the thumbnails, channel names, and AI blurbs
- Click **▶ Run Now**
- Watch LLM queue fire 10 times in terminal (once per video)
- Show the email digest in Gmail

**What to say:**
> "Agent 1 is AI-Times. It uses the YouTube Data API to fetch
> two completely separate categories — 5 AI news videos and
> 5 AI personality or interview videos from the last 96 hours.
>
> For each video, Qwen3 generates a one-sentence explanation
> of why that video matters for AI practitioners. Watch the
> terminal — you can see it calling the LLM queue once for
> every single video.
>
> The email digest has two sections, video thumbnails, channel
> names, and those AI-generated blurbs for each one."

---

### 4:00 – 5:30 | Mailman

**What to show:**
- Click Mailman tab
- Show the category pie chart
- Show the email list with category badges and AI summaries
- Click **▶ Scan Now**
- While it runs — open Gmail and show labels appearing in real time
- Come back to dashboard — show pie chart updating

**What to say:**
> "Agent 2 is Mailman. It connects to my Gmail via OAuth2,
> scans unread emails, and classifies each one into 7 categories
> using Qwen3 — Urgent, Action Required, Follow-Up, Newsletter,
> Notification, Personal, and Other.
>
> It automatically applies Gmail labels and stars emails from
> my key people list. Watch Gmail on the side — you can see
> the labels appearing on emails in real time as Qwen3
> classifies them.
>
> It also generates a one-sentence AI summary for every email
> and sends me a daily digest with a category breakdown."

---

### 5:30 – 7:30 | Arabic Word of the Day

**What to show:**
- Click Arabic Word tab
- Point to the large Arabic word card — word, transliteration, root
- Point to English and Urdu meaning cards side by side
- Point to the Morphological Analysis section
- Point to the verse in 3 languages (Arabic, English, Urdu)
- Click the audio link — let it play for 5 seconds
- Scroll down — show the Root Family tree
- Point to the SRS history section
- Click **✓ Knew it** on one word — show the box update
- Show the email in Gmail inbox

**What to say:**
> "Agent 4 is my custom agent — Quranic Arabic Word of the Day.
> This is something I built to help with learning Quranic Arabic
> vocabulary through daily immersion.
>
> It uses the AlQuran Cloud API — completely free, no API key
> required — to fetch the actual Arabic verse, English translation,
> Urdu translation, and an audio URL of the verse recited by
> Mishary Alafasy.
>
> Qwen3 generates a full linguistic analysis. This section here
> is the morphological analysis — it identifies which verb form
> this word uses, Form I through Form X, and explains exactly
> how that form shifts the meaning from the root.
>
> This is the root family tree — all the Quranic words that
> branch from the same 3 root letters. You can see how one
> root generates an entire family of related meanings.
>
> This is a spaced repetition system — the same algorithm used
> by Anki. I can mark words as known or still learning, and
> the system automatically schedules when to resurface each
> word. Box 1 comes back tomorrow, Box 2 in 3 days,
> Box 3 in 7 days.
>
> The daily email includes a micro-quiz from yesterday's word
> to reinforce retention. On Sundays, it sends a full
> weekly recap of all 7 words."

---

### 7:30 – 8:30 | Deadlock Prevention Live Demo

**What to show:**
- Go to Overview tab
- Click **▶** on Wallstreet Wolf
- Immediately click **▶** on AI-Times
- Switch to Terminal 1 quickly
- Point to the LLM queue messages

**What to say:**
> "One of the core engineering requirements is preventing
> deadlocks. All 4 agents share a single Qwen3 instance.
> Watch what happens when I trigger two agents simultaneously.
>
> You can see in the terminal — wallstreet_wolf is active,
> ai_times is waiting in the queue with depth 1.
> The asyncio Semaphore ensures only one agent calls the
> model at a time. When wallstreet_wolf finishes and releases
> the key, ai_times immediately picks it up.
>
> There's also a background watchdog running every 60 seconds.
> If any agent has been running for more than 10 minutes
> it gets force-restarted automatically — without touching
> the rest of the platform."

---

### 8:30 – 9:15 | Resource Monitor & Alarm System

**What to show:**
- Point to the resource chart on Overview tab — show it updating live
- Open Terminal 2 — run the alarm check
- Show the response

**Terminal command to run on camera:**
```bash
curl http://localhost:8000/api/alarm
```

**What to say:**
> "The orchestrator monitors CPU, RAM, disk, and thread count
> every 30 seconds and stores it all in SQLite. The chart
> you see here is live data — it updates every 30 seconds.
>
> If any resource exceeds 90%, an alarm fires at the top of
> the dashboard with a specific corrective action — not just
> a warning, but an actual suggested fix like 'close unused
> applications' or 'switch to a smaller model'.
>
> Running the alarm API right now shows no alarms — the
> machine is handling everything comfortably."

---

### 9:15 – 10:00 | GitHub & Tests

**What to show:**
- Open GitHub repo in browser
- Show README.md rendered nicely
- Show folder structure
- Switch to Terminal 2 — run pytest

**Terminal command to run on camera:**
```bash
pytest tests/ -v
```

**What to say:**
> "All the code is on GitHub. The README has full setup
> instructions, API configuration steps, and a complete
> architecture overview.
>
> The project has 48 automated tests covering the LLM Queue
> semaphore and deadlock prevention, the Base Agent retry
> logic, the Wallstreet Wolf ticker configuration, the
> Arabic word list integrity, and the email sender.
>
> 48 tests, all passing.
>
> That's the platform — 5 agents, fully local AI,
> spaced repetition, real-time dashboard, zero cloud
> dependencies. Thank you."

---

## Emergency Backup Plan

If an agent fails during recording:

**Restart a single agent without stopping the platform:**
```bash
curl -X POST http://localhost:8000/api/agents/wallstreet_wolf/run
curl -X POST http://localhost:8000/api/agents/ai_times/run
curl -X POST http://localhost:8000/api/agents/mailman/run
curl -X POST http://localhost:8000/api/agents/arabic_word/run
```

**If platform crashes — restart quickly:**
```bash
cd ~/multi-agent-platform
./start.sh
```

**If LM Studio stops responding:**
1. Open LM Studio
2. Developer tab → confirm server is running
3. If not — click Start Server
4. Wait 30 seconds then retry the agent

---

## Post-Recording Checklist

- [ ] Video is under 10 minutes (check the exact duration!)
- [ ] Upload to YouTube (can be Unlisted until submission)
- [ ] Copy the YouTube URL
- [ ] Make GitHub repo **PUBLIC** (Settings → Danger Zone → Change visibility)
- [ ] Submit GitHub URL + YouTube URL to instructor

---

## Quick Reference — All API Endpoints

```bash
# Trigger agents manually
curl -X POST http://localhost:8000/api/agents/ai_times/run
curl -X POST http://localhost:8000/api/agents/mailman/run
curl -X POST http://localhost:8000/api/agents/wallstreet_wolf/run
curl -X POST http://localhost:8000/api/agents/arabic_word/run

# Check status
curl http://localhost:8000/api/status
curl http://localhost:8000/api/alarm
curl http://localhost:8000/api/stocks
curl http://localhost:8000/api/videos
curl http://localhost:8000/api/emails
curl http://localhost:8000/api/arabic/today

# Run tests
pytest tests/ -v

# Start platform (recommended)
./start.sh

# Start platform (manual alternative)
source venv/bin/activate && ulimit -n 4096 && caffeinate -i python main.py
```
