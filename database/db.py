# database/db.py
import sqlite3, os
from database.models import SCHEMA

DB_PATH = os.getenv("DATABASE_URL", "platform.db").replace("sqlite:///./", "")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    # timeout=30 means if DB is locked, wait up to 30 seconds before giving up
    # This prevents the 'database is locked' error when multiple agents write simultaneously
    conn.execute("PRAGMA journal_mode=WAL")
    # WAL (Write-Ahead Logging) allows simultaneous reads and writes
    # Without WAL, any write locks the entire database blocking all reads
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
    print("Database initialised ✓")


def reset_db():
    """
    Drops and recreates all tables.
    WARNING: This deletes all data. Only use during development.
    """
    drop_all = """
    DROP TABLE IF EXISTS agent_runs;
    DROP TABLE IF EXISTS resource_metrics;
    DROP TABLE IF EXISTS stocks;
    DROP TABLE IF EXISTS papers;
    DROP TABLE IF EXISTS email_log;
    DROP TABLE IF EXISTS videos;
    DROP TABLE IF EXISTS arabic_words;
    DROP TABLE IF EXISTS srs_feedback;
    """
    with get_conn() as conn:
        conn.executescript(drop_all)
        conn.executescript(SCHEMA)
        conn.commit()
    print("Database reset and reinitialised ✓")