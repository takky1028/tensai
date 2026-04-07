from __future__ import annotations

from x_watch_monitor.models import XPost
from x_watch_monitor.repositories.notification_repository import NotificationRepository


class DiffService:
    def __init__(self, notification_repository: NotificationRepository) -> None:
        self.notification_repository = notification_repository

    def select_unprocessed(self, posts: list[XPost], target_id: str, last_processed_post_id: str | None) -> list[XPost]:
        results: list[XPost] = []
        last_processed_num = int(last_processed_post_id) if last_processed_post_id else None
        for post in posts:
            if last_processed_num is not None and int(post.post_id) <= last_processed_num:
                continue
            if self.notification_repository.was_sent(target_id, post.post_id):
                continue
            results.append(post)
        return results
