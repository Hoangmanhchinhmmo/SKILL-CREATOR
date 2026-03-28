"""
SQLite database connection and schema initialization.
DB file stored in %APPDATA%/NPB-Podcast-Writer/ (persistent across exe runs).
"""

import sqlite3
import os
import sys

DB_NAME = "npb_podcast.db"
APP_DATA_DIR = "NPB-Podcast-Writer"
_db_path = None


def get_db_path() -> str:
    """Get absolute path to database file in persistent user data folder."""
    global _db_path
    if _db_path is None:
        # Use %APPDATA% on Windows — survives PyInstaller onefile temp extraction
        appdata = os.environ.get("APPDATA")
        if appdata:
            data_dir = os.path.join(appdata, APP_DATA_DIR)
        else:
            # Fallback: user home
            data_dir = os.path.join(os.path.expanduser("~"), f".{APP_DATA_DIR}")
        os.makedirs(data_dir, exist_ok=True)
        _db_path = os.path.join(data_dir, DB_NAME)
    return _db_path


def get_connection() -> sqlite3.Connection:
    """Get a new SQLite connection with WAL mode and foreign keys."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                topic       TEXT NOT NULL,
                format      TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME
            );

            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id  INTEGER REFERENCES articles(id) ON DELETE SET NULL,
                status      TEXT NOT NULL DEFAULT 'running',
                started_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                finished_at DATETIME,
                total_time  REAL
            );

            CREATE TABLE IF NOT EXISTS agent_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id      INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
                agent_name  TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'waiting',
                attempt     INTEGER DEFAULT 1,
                started_at  DATETIME,
                finished_at DATETIME,
                error_msg   TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                encrypted   INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS license_cache (
                id           INTEGER PRIMARY KEY DEFAULT 1,
                license_key  TEXT NOT NULL,
                machine_code TEXT NOT NULL,
                status       TEXT NOT NULL,
                product      TEXT,
                plan         TEXT,
                expires_at   DATETIME,
                verified_at  DATETIME,
                token_data   TEXT
            );

            CREATE TABLE IF NOT EXISTS translations (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                title               TEXT,
                source_text         TEXT NOT NULL,
                source_lang         TEXT DEFAULT 'vi',
                source_type         TEXT,
                source_url          TEXT,
                result_text         TEXT,
                config_json         TEXT,
                mapping_json        TEXT,
                status              TEXT DEFAULT 'draft',
                total_segments      INTEGER DEFAULT 0,
                completed_segments  INTEGER DEFAULT 0,
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS translation_segments (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                translation_id      INTEGER NOT NULL REFERENCES translations(id) ON DELETE CASCADE,
                segment_index       INTEGER NOT NULL,
                source_text         TEXT NOT NULL,
                result_text         TEXT,
                status              TEXT DEFAULT 'pending',
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
            CREATE INDEX IF NOT EXISTS idx_agent_logs_run ON agent_logs(run_id);
            CREATE INDEX IF NOT EXISTS idx_translations_created ON translations(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_translations_status ON translations(status);
            CREATE INDEX IF NOT EXISTS idx_translation_segments_tid ON translation_segments(translation_id);
        """)
        # Migration: add titles column if missing
        try:
            conn.execute("SELECT titles FROM articles LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE articles ADD COLUMN titles TEXT DEFAULT ''")

        conn.commit()
    finally:
        conn.close()


def get_db_size() -> int:
    """Get database file size in bytes."""
    path = get_db_path()
    if os.path.exists(path):
        return os.path.getsize(path)
    return 0
