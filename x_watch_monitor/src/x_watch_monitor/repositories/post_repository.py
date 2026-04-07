from __future__ import annotations

import json

from x_watch_monitor.models import XPost, utc_now
from x_watch_monitor.repositories.database import Database


class PostRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_many(self, posts: list[XPost]) -> None:
        if not posts:
            return
        with self.db.connect() as conn:
            conn.executemany(
                """
                INSERT INTO posts (
                    post_id, target_id, x_user, author_id, text, created_at, conversation_id, is_reply, is_thread, raw_json, inserted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                    text = excluded.text,
                    raw_json = excluded.raw_json
                """,
                [
                    (
                        post.post_id,
                        post.target_id,
                        post.x_user,
                        post.author_id,
                        post.text,
                        post.created_at.isoformat(),
                        post.conversation_id,
                        int(post.is_reply),
                        int(post.is_thread_post),
                        json.dumps(post.raw_json, ensure_ascii=False),
                        utc_now().isoformat(),
                    )
                    for post in posts
                ],
            )
