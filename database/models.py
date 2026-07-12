# database/models.py
SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name  TEXT NOT NULL,
    status      TEXT NOT NULL,
    started_at  DATETIME NOT NULL,
    finished_at DATETIME,
    message     TEXT
);

CREATE TABLE IF NOT EXISTS resource_metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cpu_pct     REAL,
    ram_pct     REAL,
    disk_pct    REAL,
    threads     INTEGER,
    recorded_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS stocks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL,
    price       REAL,
    change_pct  REAL,
    volume      INTEGER,
    fetched_at  DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_id    TEXT UNIQUE,
    title       TEXT,
    authors     TEXT,
    abstract    TEXT,
    summary     TEXT,
    url         TEXT,
    fetched_at  DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS email_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_id        TEXT UNIQUE,
    sender          TEXT,
    subject         TEXT,
    snippet         TEXT,
    classification  TEXT,
    ai_summary      TEXT,
    classified_at   DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS videos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id    TEXT UNIQUE,
    title       TEXT,
    channel     TEXT,
    thumbnail   TEXT,
    url         TEXT,
    category    TEXT,
    blurb       TEXT,
    fetched_at  DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS arabic_words (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    word                TEXT,
    transliteration     TEXT,
    root                TEXT,
    root_transliteration TEXT,
    difficulty          TEXT DEFAULT 'beginner',
    meaning_en          TEXT,
    meaning_ur          TEXT,
    verb_form           TEXT,
    root_family         TEXT,
    contextual_explanation TEXT,
    verse_ref           TEXT,
    verse_ar            TEXT,
    verse_en            TEXT,
    verse_ur            TEXT,
    audio_url           TEXT,
    quiz_question       TEXT,
    srs_box             INTEGER DEFAULT 1,
    next_review         DATE,
    fetched_at          DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS srs_feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id     INTEGER NOT NULL,
    knew_it     INTEGER NOT NULL,
    reviewed_at DATETIME NOT NULL,
    FOREIGN KEY (word_id) REFERENCES arabic_words(id)
);

CREATE TABLE IF NOT EXISTS llm_usage (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name        TEXT NOT NULL,
    prompt_tokens     INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens      INTEGER DEFAULT 0,
    response_time_ms  INTEGER DEFAULT 0,
    tokens_per_sec    REAL DEFAULT 0,
    called_at         DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_schedule_state (
    agent_name  TEXT PRIMARY KEY,
    paused      INTEGER NOT NULL DEFAULT 0,
    updated_at  DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS leverage_videos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id    TEXT UNIQUE,
    title       TEXT,
    channel     TEXT,
    thumbnail   TEXT,
    url         TEXT,
    category    TEXT,
    views       INTEGER DEFAULT 0,
    blurb       TEXT,
    fetched_at  DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_builder_videos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id    TEXT UNIQUE,
    title       TEXT,
    channel     TEXT,
    thumbnail   TEXT,
    url         TEXT,
    views       INTEGER DEFAULT 0,
    blurb       TEXT,
    fetched_at  DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS woodworking_videos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id    TEXT UNIQUE,
    title       TEXT,
    channel     TEXT,
    thumbnail   TEXT,
    url         TEXT,
    views       INTEGER DEFAULT 0,
    blurb       TEXT,
    fetched_at  DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS inbox_cleaner_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date     DATE NOT NULL,
    sender       TEXT NOT NULL,
    sender_email TEXT NOT NULL,
    subject      TEXT,
    gmail_id     TEXT UNIQUE,
    action       TEXT NOT NULL,  -- 'trashed' or 'whitelisted'
    cleaned_at   DATETIME NOT NULL
);
"""
