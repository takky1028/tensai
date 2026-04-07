from __future__ import annotations

from x_watch_monitor.models import utc_now
from x_watch_monitor.repositories.database import Database


class ErrorRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def log(self, stage: str, error_message: str, *, target_id: str | None = None, details: str | None = None) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO error_logs (target_id, stage, error_message, details, logged_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (target_id, stage, error_message, details, utc_now().isoformat()),
            )
