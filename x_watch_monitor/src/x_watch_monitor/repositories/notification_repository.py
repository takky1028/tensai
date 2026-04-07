from __future__ import annotations

import json

from x_watch_monitor.models import utc_now
from x_watch_monitor.repositories.database import Database


class NotificationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def was_sent(self, target_id: str, post_id: str) -> bool:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM notifications
                WHERE target_id = ? AND post_id = ? AND status = 'sent'
                """,
                (target_id, post_id),
            ).fetchone()
        return bool(row)

    def mark_sent(self, target_id: str, post_ids: list[str], analysis_id: int, webhook_url: str, response_body: dict) -> None:
        with self.db.connect() as conn:
            conn.executemany(
                """
                INSERT INTO notifications (
                    target_id, post_id, analysis_id, webhook_url, status, sent_at, response_body, error_message
                )
                VALUES (?, ?, ?, ?, 'sent', ?, ?, NULL)
                ON CONFLICT(target_id, post_id) DO UPDATE SET
                    analysis_id = excluded.analysis_id,
                    webhook_url = excluded.webhook_url,
                    status = excluded.status,
                    sent_at = excluded.sent_at,
                    response_body = excluded.response_body,
                    error_message = NULL
                """,
                [
                    (
                        target_id,
                        post_id,
                        analysis_id,
                        webhook_url,
                        utc_now().isoformat(),
                        json.dumps(response_body, ensure_ascii=False),
                    )
                    for post_id in post_ids
                ],
            )

    def mark_failed(self, target_id: str, post_ids: list[str], analysis_id: int, webhook_url: str, error_message: str) -> None:
        with self.db.connect() as conn:
            conn.executemany(
                """
                INSERT INTO notifications (
                    target_id, post_id, analysis_id, webhook_url, status, sent_at, response_body, error_message
                )
                VALUES (?, ?, ?, ?, 'failed', ?, NULL, ?)
                ON CONFLICT(target_id, post_id) DO UPDATE SET
                    analysis_id = excluded.analysis_id,
                    webhook_url = excluded.webhook_url,
                    status = excluded.status,
                    sent_at = excluded.sent_at,
                    error_message = excluded.error_message
                """,
                [
                    (
                        target_id,
                        post_id,
                        analysis_id,
                        webhook_url,
                        utc_now().isoformat(),
                        error_message,
                    )
                    for post_id in post_ids
                ],
            )
