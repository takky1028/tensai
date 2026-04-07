from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class TopicConfig:
    target_id: str
    display_name: str
    keywords: list[str]
    enabled: bool
    poll_interval_minutes: int
    max_items: int
    x_search_enabled: bool
    news_enabled: bool
    analysis_profile: str
    discord_webhook_url: str


@dataclass(slots=True)
class AppSettings:
    config_path: str
    database_path: str
    x_bearer_token: str
    x_api_base_url: str
    x_request_timeout_sec: int
    x_api_tweet_fields: str
    x_api_max_page_size: int
    x_search_default_lang: str
    google_news_rss_base_url: str
    google_news_gl: str
    google_news_hl: str
    google_news_ceid: str
    news_request_timeout_sec: int
    xai_api_key: str
    grok_api_base_url: str
    grok_model: str
    grok_request_timeout_sec: int
    discord_request_timeout_sec: int
    log_level: str


@dataclass(slots=True)
class TargetState:
    target_id: str
    last_processed_post_id: str | None = None
    last_processed_post_at: datetime | None = None
    last_polled_at: datetime | None = None
    last_success_at: datetime | None = None


@dataclass(slots=True)
class ContentItem:
    post_id: str
    target_id: str
    source_type: str
    source_author: str
    title: str
    text: str
    created_at: datetime
    url: str
    raw_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisResult:
    target_id: str
    target_name: str
    analyzed_at: datetime
    source_posts: list[dict[str, Any]]
    summary: str
    usd_bias: str
    equity_bias: str
    risk_regime: str
    rate_bias: str
    inflation_bias: str
    trade_policy_bias: str
    geopolitical_risk: str
    confidence: int
    key_drivers: list[str]
    notable_quotes: list[str]
    raw_model_output: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_name": self.target_name,
            "analyzed_at": self.analyzed_at.isoformat(),
            "source_posts": self.source_posts,
            "summary": self.summary,
            "usd_bias": self.usd_bias,
            "equity_bias": self.equity_bias,
            "risk_regime": self.risk_regime,
            "rate_bias": self.rate_bias,
            "inflation_bias": self.inflation_bias,
            "trade_policy_bias": self.trade_policy_bias,
            "geopolitical_risk": self.geopolitical_risk,
            "confidence": self.confidence,
            "key_drivers": self.key_drivers,
            "notable_quotes": self.notable_quotes,
            "raw_model_output": self.raw_model_output,
        }
