from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

import requests

from x_watch_monitor.models import AppSettings, ContentItem, TopicConfig

logger = logging.getLogger(__name__)


class XApiClient:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.session = requests.Session()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.x_bearer_token}",
            "Accept": "application/json",
        }

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.x_bearer_token:
            raise RuntimeError("X_BEARER_TOKEN is not set")
        response = self.session.get(
            f"{self.settings.x_api_base_url}/{path.lstrip('/')}",
            headers=self._headers,
            params=params,
            timeout=self.settings.x_request_timeout_sec,
        )
        if response.status_code == 402:
            raise RuntimeError("X API の契約プラン不足、または読み取り権限不足で検索 API を利用できません")
        response.raise_for_status()
        return response.json()

    def search_recent_posts(self, topic: TopicConfig, since_time: datetime | None = None) -> list[ContentItem]:
        query = self._build_query(topic.keywords)
        params: dict[str, Any] = {
            "query": query,
            "max_results": min(max(topic.max_items, 10), self.settings.x_api_max_page_size),
            "tweet.fields": self.settings.x_api_tweet_fields,
        }
        if since_time:
            params["start_time"] = since_time.isoformat().replace("+00:00", "Z")

        payload = self._request("tweets/search/recent", params)
        raw_items = payload.get("data") or []
        results = [self._to_content_item(item, topic) for item in raw_items]
        results.sort(key=lambda item: (item.created_at, item.post_id))
        logger.info("fetched x search items target_id=%s total=%d query=%s", topic.target_id, len(results), query)
        return results

    def _build_query(self, keywords: list[str]) -> str:
        joined = " OR ".join(f'"{keyword}"' if " " in keyword else keyword for keyword in keywords)
        if self.settings.x_search_default_lang:
            return f"({joined}) lang:{self.settings.x_search_default_lang} -is:retweet"
        return f"({joined}) -is:retweet"

    @staticmethod
    def _to_content_item(raw: dict[str, Any], topic: TopicConfig) -> ContentItem:
        text = raw.get("text", "").strip()
        post_id = raw["id"]
        author_id = raw.get("author_id", "")
        return ContentItem(
            post_id=post_id,
            target_id=topic.target_id,
            source_type="x_search",
            source_author=author_id or "X",
            title=text[:80] if text else "X投稿",
            text=text,
            created_at=datetime.fromisoformat(raw["created_at"].replace("Z", "+00:00")),
            url=f"https://x.com/i/web/status/{post_id}",
            raw_json=raw,
        )


def stable_id(parts: list[str]) -> str:
    return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()[:24]
