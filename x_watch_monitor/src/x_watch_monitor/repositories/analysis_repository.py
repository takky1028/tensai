from __future__ import annotations

import json

from x_watch_monitor.models import AnalysisResult
from x_watch_monitor.repositories.database import Database


class AnalysisRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, analysis: AnalysisResult) -> int:
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analyses (target_id, analyzed_at, source_post_ids, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    analysis.target_id,
                    analysis.analyzed_at.isoformat(),
                    json.dumps([item["post_id"] for item in analysis.source_posts]),
                    json.dumps(analysis.to_payload(), ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)
