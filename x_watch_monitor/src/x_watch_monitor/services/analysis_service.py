from __future__ import annotations

import json
from datetime import timezone
from typing import Any

from x_watch_monitor.clients.grok_client import GrokClient
from x_watch_monitor.models import AnalysisResult, TargetConfig, XPost, utc_now

PROFILE_HINTS = {
    "default": "Focus on market-moving macro implications, avoid overclaiming, and keep uncertainty explicit.",
    "macro_policy": "Emphasize FX, equities, rates, inflation, trade policy, and macro spillover effects.",
    "rates_focus": "Weight rate-path implications and inflation-growth tradeoffs more heavily than equity narratives.",
}


class AnalysisService:
    def __init__(self, grok_client: GrokClient) -> None:
        self.grok_client = grok_client

    def analyze(self, target: TargetConfig, posts: list[XPost]) -> AnalysisResult:
        analyzed_at = utc_now()
        system_prompt = self._build_system_prompt(target.analysis_profile)
        user_prompt = self._build_user_prompt(target, posts, analyzed_at.isoformat())
        parsed, raw_response = self.grok_client.analyze_posts(system_prompt, user_prompt)
        return self._normalize_result(target, posts, analyzed_at, parsed, raw_response)

    def _build_system_prompt(self, analysis_profile: str) -> str:
        hint = PROFILE_HINTS.get(analysis_profile, PROFILE_HINTS["default"])
        schema = {
            "summary": "short summary",
            "usd_bias": "usd_bullish|usd_bearish|neutral",
            "equity_bias": "equity_bullish|equity_bearish|neutral",
            "risk_regime": "risk_on|risk_off|neutral",
            "rate_bias": "upward_pressure|downward_pressure|neutral",
            "inflation_bias": "inflation_concern|growth_slowdown_concern|neutral",
            "trade_policy_bias": "trade_friction_risk_high|trade_friction_risk_low|neutral",
            "geopolitical_risk": "high|medium|low",
            "confidence": "0-100 integer",
            "key_drivers": ["string"],
            "notable_quotes": ["string"],
        }
        return (
            "You are a market surveillance analyst. "
            "Read the provided X posts and return JSON only. "
            "Do not wrap the response in markdown. "
            "Base the analysis only on the provided posts. "
            "If signal is mixed or unclear, use neutral/medium and lower confidence. "
            f"{hint} "
            f"Required JSON shape: {json.dumps(schema, ensure_ascii=False)}"
        )

    def _build_user_prompt(self, target: TargetConfig, posts: list[XPost], analyzed_at: str) -> str:
        post_lines = [
            json.dumps(
                {
                    "post_id": post.post_id,
                    "created_at": post.created_at.astimezone(timezone.utc).isoformat(),
                    "text": post.text,
                    "url": post.url,
                },
                ensure_ascii=False,
            )
            for post in posts
        ]
        return (
            f"target_id={target.target_id}\n"
            f"target_name={target.display_name}\n"
            f"analysis_profile={target.analysis_profile}\n"
            f"analyzed_at={analyzed_at}\n"
            "posts=\n"
            + "\n".join(post_lines)
        )

    def _normalize_result(
        self,
        target: TargetConfig,
        posts: list[XPost],
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
                    "created_at": post.created_at.isoformat(),
                    "text": post.text,
                    "url": post.url,
                }
                for post in posts
            ],
            summary=str(parsed.get("summary", "")).strip(),
            usd_bias=self._enum_value(parsed.get("usd_bias"), "neutral"),
            equity_bias=self._enum_value(parsed.get("equity_bias"), "neutral"),
            risk_regime=self._enum_value(parsed.get("risk_regime"), "neutral"),
            rate_bias=self._enum_value(parsed.get("rate_bias"), "neutral"),
            inflation_bias=self._enum_value(parsed.get("inflation_bias"), "neutral"),
            trade_policy_bias=self._enum_value(parsed.get("trade_policy_bias"), "neutral"),
            geopolitical_risk=self._enum_value(parsed.get("geopolitical_risk"), "medium"),
            confidence=self._confidence_value(parsed.get("confidence")),
            key_drivers=self._string_list(parsed.get("key_drivers")),
            notable_quotes=self._string_list(parsed.get("notable_quotes")),
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
