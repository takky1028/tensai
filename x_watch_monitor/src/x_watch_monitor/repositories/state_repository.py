from __future__ import annotations

from datetime import datetime

from x_watch_monitor.models import TargetState, utc_now
from x_watch_monitor.repositories.database import Database


class StateRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self, target_id: str) -> TargetState:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT target_id, last_processed_post_id, last_processed_post_at, last_polled_at, last_success_at
                FROM target_state
                WHERE target_id = ?
                """,
                (target_id,),
            ).fetchone()
        if not row:
            return TargetState(target_id=target_id)
        return TargetState(
            target_id=row["target_id"],
            last_processed_post_id=row["last_processed_post_id"],
            last_processed_post_at=_parse_dt(row["last_processed_post_at"]),
            last_polled_at=_parse_dt(row["last_polled_at"]),
            last_success_at=_parse_dt(row["last_success_at"]),
        )

    def upsert(
        self,
        target_id: str,
        *,
        last_processed_post_id: str | None,
        last_processed_post_at: datetime | None,
        last_polled_at: datetime | None,
        last_success_at: datetime | None,
    ) -> None:
        now = utc_now().isoformat()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO target_state (
                    target_id, last_processed_post_id, last_processed_post_at, last_polled_at, last_success_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(target_id) DO UPDATE SET
                    last_processed_post_id = excluded.last_processed_post_id,
                    last_processed_post_at = excluded.last_processed_post_at,
                    last_polled_at = excluded.last_polled_at,
                    last_success_at = excluded.last_success_at,
                    updated_at = excluded.updated_at
                """,
                (
                    target_id,
                    last_processed_post_id,
                    _fmt_dt(last_processed_post_at),
                    _fmt_dt(last_polled_at),
                    _fmt_dt(last_success_at),
                    now,
                ),
            )


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _fmt_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
