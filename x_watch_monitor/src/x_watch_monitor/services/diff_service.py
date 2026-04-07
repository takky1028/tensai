from __future__ import annotations

from datetime import datetime

from x_watch_monitor.models import ContentItem
from x_watch_monitor.repositories.notification_repository import NotificationRepository


class DiffService:
    def __init__(self, notification_repository: NotificationRepository) -> None:
        self.notification_repository = notification_repository

    def select_unprocessed(
        self,
        posts: list[ContentItem],
        target_id: str,
        last_processed_post_at: datetime | None,
    ) -> list[ContentItem]:
        results: list[ContentItem] = []
        for post in posts:
            if last_processed_post_at and post.created_at <= last_processed_post_at:
                continue
            if self.notification_repository.was_sent(target_id, post.post_id):
                continue
            results.append(post)
        return results
