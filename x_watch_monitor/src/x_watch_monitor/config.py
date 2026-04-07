from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from x_watch_monitor.models import AppSettings, TopicConfig

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            default = match.group(2) or ""
            return os.getenv(key, default)

        return ENV_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def load_settings() -> AppSettings:
    load_dotenv()
    return AppSettings(
        config_path=os.getenv("CONFIG_PATH", "config/targets.yaml"),
        database_path=os.getenv("DATABASE_PATH", "data/monitor.db"),
        x_bearer_token=os.getenv("X_BEARER_TOKEN", "").strip(),
        x_api_base_url=os.getenv("X_API_BASE_URL", "https://api.x.com/2").rstrip("/"),
        x_request_timeout_sec=int(os.getenv("X_REQUEST_TIMEOUT_SEC", "30")),
        x_api_tweet_fields=os.getenv(
            "X_API_TWEET_FIELDS",
            "author_id,created_at,lang,public_metrics,text",
        ),
        x_api_max_page_size=int(os.getenv("X_API_MAX_PAGE_SIZE", "100")),
        x_search_default_lang=os.getenv("X_SEARCH_DEFAULT_LANG", "ja"),
        google_news_rss_base_url=os.getenv("GOOGLE_NEWS_RSS_BASE_URL", "https://news.google.com/rss/search"),
        google_news_gl=os.getenv("GOOGLE_NEWS_GL", "JP"),
        google_news_hl=os.getenv("GOOGLE_NEWS_HL", "ja"),
        google_news_ceid=os.getenv("GOOGLE_NEWS_CEID", "JP:ja"),
        news_request_timeout_sec=int(os.getenv("NEWS_REQUEST_TIMEOUT_SEC", "30")),
        xai_api_key=os.getenv("XAI_API_KEY", "").strip(),
        grok_api_base_url=os.getenv("GROK_API_BASE_URL", "https://api.x.ai/v1").rstrip("/"),
        grok_model=os.getenv("GROK_MODEL", "grok-4.20-beta-latest-non-reasoning"),
        grok_request_timeout_sec=int(os.getenv("GROK_REQUEST_TIMEOUT_SEC", "60")),
        discord_request_timeout_sec=int(os.getenv("DISCORD_REQUEST_TIMEOUT_SEC", "20")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


def load_targets(config_path: str) -> list[TopicConfig]:
    path = Path(config_path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    expanded = _expand_env(payload)
    targets = expanded.get("targets", [])
    result: list[TopicConfig] = []
    for item in targets:
        result.append(
            TopicConfig(
                target_id=item["target_id"],
                display_name=item["display_name"],
                keywords=[str(keyword).strip() for keyword in item.get("keywords", []) if str(keyword).strip()],
                enabled=bool(item.get("enabled", True)),
                poll_interval_minutes=int(item.get("poll_interval_minutes", 120)),
                max_items=int(item.get("max_items", 10)),
                x_search_enabled=bool(item.get("x_search_enabled", True)),
                news_enabled=bool(item.get("news_enabled", True)),
                analysis_profile=item.get("analysis_profile", "default"),
                discord_webhook_url=item.get("discord_webhook_url", "").strip(),
            )
        )
    return result
