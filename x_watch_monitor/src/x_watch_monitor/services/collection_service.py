from __future__ import annotations

import logging
from datetime import datetime

from x_watch_monitor.clients.news_client import NewsRssClient
from x_watch_monitor.clients.x_client import XApiClient
from x_watch_monitor.models import ContentItem, TopicConfig

logger = logging.getLogger(__name__)


class CollectionService:
    def __init__(self, x_client: XApiClient, news_client: NewsRssClient) -> None:
        self.x_client = x_client
        self.news_client = news_client

    def collect(self, target: TopicConfig, since_time: datetime | None) -> list[ContentItem]:
        items: dict[str, ContentItem] = {}
        errors: list[str] = []

        if target.x_search_enabled:
            try:
                for item in self.x_client.search_recent_posts(target, since_time=since_time):
                    items[item.post_id] = item
            except Exception as exc:
                logger.warning("x search collection failed target_id=%s err=%s", target.target_id, exc)
                errors.append(f"x_search: {exc}")

        if target.news_enabled:
            try:
                for item in self.news_client.fetch_topic_news(target):
                    if since_time and item.created_at <= since_time:
                        continue
                    items[item.post_id] = item
            except Exception as exc:
                logger.warning("news collection failed target_id=%s err=%s", target.target_id, exc)
                errors.append(f"news: {exc}")

        if not items and errors:
            raise RuntimeError(" / ".join(errors))

        results = sorted(items.values(), key=lambda item: (item.created_at, item.post_id))
        return results[: target.max_items]
