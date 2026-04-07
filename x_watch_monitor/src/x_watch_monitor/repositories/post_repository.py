from __future__ import annotations

import json

from x_watch_monitor.models import ContentItem, utc_now
from x_watch_monitor.repositories.database import Database


class PostRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_many(self, posts: list[ContentItem]) -> None:
        if not posts:
            return
        with self.db.connect() as conn:
            conn.executemany(
                """
                INSERT INTO posts (
                    post_id, target_id, source_type, source_author, title, text, created_at, url, raw_json, inserted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                    title = excluded.title,
                    text = excluded.text,
                    url = excluded.url,
                    raw_json = excluded.raw_json
                """,
                [
                    (
                        post.post_id,
                        post.target_id,
                        post.source_type,
                        post.source_author,
                        post.title,
                        post.text,
                        post.created_at.isoformat(),
                        post.url,
                        json.dumps(post.raw_json, ensure_ascii=False),
                        utc_now().isoformat(),
                    )
                    for post in posts
                ],
            )
