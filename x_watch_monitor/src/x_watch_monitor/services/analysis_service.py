from __future__ import annotations

import json
from datetime import timezone
from typing import Any

from x_watch_monitor.clients.grok_client import GrokClient
from x_watch_monitor.models import AnalysisResult, ContentItem, TopicConfig, utc_now

PROFILE_HINTS = {
    "default": "Focus on why the topic matters now, what changed versus the prior snapshot, and what would move markets next.",
    "macro_policy": "Emphasize FX, equities, rates, inflation, trade policy, and macro spillover effects.",
    "rates_focus": "Weight rate-path implications and inflation-growth tradeoffs more heavily than equity narratives.",
}


class AnalysisService:
    def __init__(self, grok_client: GrokClient) -> None:
        self.grok_client = grok_client

    def analyze(
        self,
        target: TopicConfig,
        posts: list[ContentItem],
        previous_analysis: dict[str, Any] | None = None,
    ) -> AnalysisResult:
        analyzed_at = utc_now()
        system_prompt = self._build_system_prompt(target.analysis_profile)
        user_prompt = self._build_user_prompt(target, posts, analyzed_at.isoformat(), previous_analysis)
        parsed, raw_response = self.grok_client.analyze_posts(system_prompt, user_prompt)
        return self._normalize_result(target, posts, analyzed_at, parsed, raw_response)

    def _build_system_prompt(self, analysis_profile: str) -> str:
        hint = PROFILE_HINTS.get(analysis_profile, PROFILE_HINTS["default"])
        schema = {
            "summary": "short Japanese summary",
            "why_now": "why this matters now in 1-3 sentences",
            "change_summary": "what changed versus the previous analysis, or say initial snapshot if none",
            "market_triggers": ["specific trigger events or conditions to watch next"],
            "next_watch_events": [
                "next events or deadlines explicitly mentioned or strongly implied by the source items; otherwise []"
            ],
            "usd_bias": "usd_bullish|usd_bearish|neutral",
            "equity_bias": "equity_bullish|equity_bearish|neutral",
            "risk_regime": "risk_on|risk_off|neutral",
            "rate_bias": "upward_pressure|downward_pressure|neutral",
            "inflation_bias": "inflation_concern|growth_slowdown_concern|neutral",
            "trade_policy_bias": "trade_friction_risk_high|trade_friction_risk_low|neutral",
            "geopolitical_risk": "high|medium|low",
            "overall_tone": "bullish|bearish|mixed|neutral",
            "confidence": "0-100 integer",
            "key_drivers": ["string"],
            "notable_quotes": ["string"],
            "signal_assessment": {
                "usd": {"strength": "strong|medium|weak", "horizon": "short_term|medium_term|long_term", "rationale": "string"},
                "equities": {
                    "strength": "strong|medium|weak",
                    "horizon": "short_term|medium_term|long_term",
                    "rationale": "string",
                },
                "rates": {"strength": "strong|medium|weak", "horizon": "short_term|medium_term|long_term", "rationale": "string"},
                "inflation": {
                    "strength": "strong|medium|weak",
                    "horizon": "short_term|medium_term|long_term",
                    "rationale": "string",
                },
                "trade_policy": {
                    "strength": "strong|medium|weak",
                    "horizon": "short_term|medium_term|long_term",
                    "rationale": "string",
                },
                "geopolitics": {
                    "strength": "strong|medium|weak",
                    "horizon": "short_term|medium_term|long_term",
                    "rationale": "string",
                },
            },
        }
        return (
            "You are a Japanese market surveillance analyst. "
            "Read the provided X search results and news items and return JSON only. "
            "Do not wrap the response in markdown. "
            "Base the analysis only on the provided items. "
            "Keep uncertainty explicit and avoid overclaiming. "
            "Do not invent precise calendar events that are not mentioned or strongly implied by the provided items. "
            "If the source items do not support a specific next event or deadline, return an empty list for next_watch_events. "
            "Write natural Japanese text for summary, why_now, change_summary, rationale, and notable_quotes. "
            f"{hint} "
            f"Required JSON shape: {json.dumps(schema, ensure_ascii=False)}"
        )

    def _build_user_prompt(
        self,
        target: TopicConfig,
        posts: list[ContentItem],
        analyzed_at: str,
        previous_analysis: dict[str, Any] | None,
    ) -> str:
        post_lines = [
            json.dumps(
                {
                    "post_id": post.post_id,
                    "source_type": post.source_type,
                    "source_author": post.source_author,
                    "title": post.title,
                    "created_at": post.created_at.astimezone(timezone.utc).isoformat(),
                    "text": post.text,
                    "url": post.url,
                },
                ensure_ascii=False,
            )
            for post in posts
        ]
        previous_block = json.dumps(previous_analysis, ensure_ascii=False) if previous_analysis else "null"
        return (
            f"target_id={target.target_id}\n"
            f"target_name={target.display_name}\n"
            f"keywords={json.dumps(target.keywords, ensure_ascii=False)}\n"
            f"analysis_profile={target.analysis_profile}\n"
            f"analyzed_at={analyzed_at}\n"
            f"previous_analysis={previous_block}\n"
            "source_items=\n"
            + "\n".join(post_lines)
        )

    def _normalize_result(
        self,
        target: TopicConfig,
        posts: list[ContentItem],
        analyzed_at,
        parsed: dict[str, Any],
        raw_response: dict[str, Any],
    ) -> AnalysisResult:
        return AnalysisResult(
            target_id=target.target_id,
            target_name=target.display_name,
            analyzed_at=analyzed_at,
            source_posts=[
                {
                    "post_id": post.post_id,
                    "source_type": post.source_type,
                    "source_author": post.source_author,
                    "title": post.title,
                    "created_at": post.created_at.isoformat(),
                    "text": post.text,
                    "url": post.url,
                }
                for post in posts
            ],
            summary=str(parsed.get("summary", "")).strip(),
            why_now=str(parsed.get("why_now", "")).strip(),
            change_summary=str(parsed.get("change_summary", "")).strip(),
            market_triggers=self._string_list(parsed.get("market_triggers")),
            next_watch_events=self._string_list(parsed.get("next_watch_events")),
            usd_bias=self._enum_value(parsed.get("usd_bias"), "neutral"),
            equity_bias=self._enum_value(parsed.get("equity_bias"), "neutral"),
            risk_regime=self._enum_value(parsed.get("risk_regime"), "neutral"),
            rate_bias=self._enum_value(parsed.get("rate_bias"), "neutral"),
            inflation_bias=self._enum_value(parsed.get("inflation_bias"), "neutral"),
            trade_policy_bias=self._enum_value(parsed.get("trade_policy_bias"), "neutral"),
            geopolitical_risk=self._enum_value(parsed.get("geopolitical_risk"), "medium"),
            overall_tone=self._enum_value(parsed.get("overall_tone"), "neutral"),
            confidence=self._confidence_value(parsed.get("confidence")),
            key_drivers=self._key_drivers(parsed.get("key_drivers")),
            notable_quotes=self._string_list(parsed.get("notable_quotes")),
            signal_assessment=self._signal_assessment(parsed.get("signal_assessment")),
            raw_model_output={"parsed_json": parsed, "api_response": raw_response},
        )

    @staticmethod
    def _enum_value(value: Any, default: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return default

    @staticmethod
    def _confidence_value(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, min(number, 100))

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _key_drivers(value: Any) -> list[str]:
        items = AnalysisService._string_list(value)[:3]
        trimmed = [item[:50] for item in items]
        while len(trimmed) < 3:
            trimmed.append("情報不足")
        return trimmed

    @staticmethod
    def _signal_assessment(value: Any) -> dict[str, dict[str, str]]:
        if not isinstance(value, dict):
            return {}

        result: dict[str, dict[str, str]] = {}
        for key, item in value.items():
            if not isinstance(item, dict):
                continue
            result[str(key).strip()] = {
                "strength": str(item.get("strength", "")).strip() or "weak",
                "horizon": str(item.get("horizon", "")).strip() or "short_term",
                "rationale": str(item.get("rationale", "")).strip(),
            }
        return result
