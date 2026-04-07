from __future__ import annotations

import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS target_state (
                    target_id TEXT PRIMARY KEY,
                    last_processed_post_id TEXT,
                    last_processed_post_at TEXT,
                    last_polled_at TEXT,
                    last_success_at TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS posts (
                    post_id TEXT PRIMARY KEY,
                    target_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_author TEXT,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    url TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    inserted_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analyses (
                    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL,
                    source_post_ids TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id TEXT NOT NULL,
                    post_id TEXT NOT NULL,
                    analysis_id INTEGER NOT NULL,
                    webhook_url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    response_body TEXT,
                    error_message TEXT,
                    UNIQUE(target_id, post_id),
                    FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id)
                );

                CREATE TABLE IF NOT EXISTS error_logs (
                    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id TEXT,
                    stage TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    details TEXT,
                    logged_at TEXT NOT NULL
                );
                """
            )
            self._migrate_posts_table(conn)

    def _migrate_posts_table(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(posts)").fetchall()}
        required = {"post_id", "target_id", "source_type", "source_author", "title", "text", "created_at", "url", "raw_json", "inserted_at"}
        if not columns or required.issubset(columns):
            return

        conn.execute("DROP TABLE IF EXISTS posts_legacy")
        conn.execute("ALTER TABLE posts RENAME TO posts_legacy")
        conn.executescript(
            """
            CREATE TABLE posts (
                post_id TEXT PRIMARY KEY,
                target_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_author TEXT,
                title TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                url TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                inserted_at TEXT NOT NULL
            );
            """
        )
