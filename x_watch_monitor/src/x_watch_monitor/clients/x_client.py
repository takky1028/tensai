from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests

from x_watch_monitor.models import AppSettings, TargetConfig, XPost

logger = logging.getLogger(__name__)


class XApiClient:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self._user_cache: dict[str, str] = {}

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
        response.raise_for_status()
        return response.json()

    def resolve_user_id(self, username: str) -> str:
        cached = self._user_cache.get(username.lower())
        if cached:
            return cached

        payload = self._request(
            "users/by",
            {
                "usernames": username,
                "user.fields": self.settings.x_api_user_fields,
            },
        )
        data = payload.get("data") or []
        if not data:
            raise RuntimeError(f"user lookup returned no data for @{username}")
        user_id = data[0]["id"]
        self._user_cache[username.lower()] = user_id
        return user_id

    def fetch_recent_posts(self, target: TargetConfig, since_id: str | None = None) -> list[XPost]:
        user_id = self.resolve_user_id(target.x_user)
        params: dict[str, Any] = {
            "max_results": min(max(target.max_posts, 5), self.settings.x_api_max_page_size),
            "tweet.fields": self.settings.x_api_tweet_fields,
        }
        if since_id:
            params["since_id"] = since_id
        if not target.include_replies:
            params["exclude"] = "replies,retweets"
        else:
            params["exclude"] = "retweets"

        payload = self._request(f"users/{user_id}/tweets", params)
        raw_posts = payload.get("data") or []
        posts = [self._to_post(item, target) for item in raw_posts]

        filtered = [
            post
            for post in posts
            if (target.include_threads or not post.is_thread_post)
            and (target.include_replies or not post.is_reply)
        ]
        filtered.sort(key=lambda item: (item.created_at, int(item.post_id)))
        logger.info(
            "fetched posts target_id=%s x_user=%s total=%d filtered=%d",
            target.target_id,
            target.x_user,
            len(posts),
            len(filtered),
        )
        return filtered

    @staticmethod
    def _to_post(raw: dict[str, Any], target: TargetConfig) -> XPost:
        return XPost(
            post_id=raw["id"],
            author_id=raw.get("author_id", ""),
            x_user=target.x_user,
            target_id=target.target_id,
            text=raw.get("text", "").strip(),
            created_at=datetime.fromisoformat(raw["created_at"].replace("Z", "+00:00")),
            conversation_id=raw.get("conversation_id"),
            in_reply_to_user_id=raw.get("in_reply_to_user_id"),
            referenced_tweets=raw.get("referenced_tweets", []),
            raw_json=raw,
        )
