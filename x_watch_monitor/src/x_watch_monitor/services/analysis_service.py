from __future__ import annotations

import json
from datetime import timezone
from typing import Any

from x_watch_monitor.clients.grok_client import GrokClient
from x_watch_monitor.models import AnalysisResult, ContentItem, TopicConfig, utc_now

PROFILE_HINTS = {
    "default": "日本語で簡潔かつ実務的に要約し、不確実性は明示してください。",
    "macro_policy": "為替、株式、金利、インフレ、関税、地政学への波及を優先して整理してください。",
    "rates_focus": "金利見通し、景気減速、インフレ圧力のバランスを重視してください。",
}


class AnalysisService:
    def __init__(self, grok_client: GrokClient) -> None:
        self.grok_client = grok_client

    def analyze(self, target: TopicConfig, posts: list[ContentItem]) -> AnalysisResult:
        analyzed_at = utc_now()
        system_prompt = self._build_system_prompt(target.analysis_profile)
        user_prompt = self._build_user_prompt(target, posts, analyzed_at.isoformat())
        parsed, raw_response = self.grok_client.analyze_posts(system_prompt, user_prompt)
        return self._normalize_result(target, posts, analyzed_at, parsed, raw_response)

    def _build_system_prompt(self, analysis_profile: str) -> str:
        hint = PROFILE_HINTS.get(analysis_profile, PROFILE_HINTS["default"])
        schema = {
            "summary": "日本語の短い要約",
            "usd_bias": "ドル高|ドル安|中立",
            "equity_bias": "株高|株安|中立",
            "risk_regime": "リスクオン|リスクオフ|中立",
            "rate_bias": "金利上昇圧力|金利低下圧力|中立",
            "inflation_bias": "インフレ懸念|景気減速懸念|中立",
            "trade_policy_bias": "関税・貿易摩擦リスク|中立",
            "geopolitical_risk": "高い|中程度|低い",
            "overall_tone": "強気|弱気|警戒|中立",
            "confidence": "0-100 の整数",
            "key_drivers": ["50文字以内の日本語箇条書き", "50文字以内の日本語箇条書き", "50文字以内の日本語箇条書き"],
            "notable_quotes": ["日本語の引用または見出し"],
        }
        return (
            "あなたは金融市場向けのニュース監視アナリストです。"
            "与えられたX検索結果とニュース見出しだけを根拠に分析してください。"
            "出力はMarkdownではなくJSONのみで返してください。"
            "必ず日本語で記述してください。"
            "key_drivers は必ず3件に固定し、各項目は50文字以内にしてください。"
            "通知では key_drivers と各バイアスだけを使うため、簡潔で断定的な表現を優先してください。"
            "判断が割れる場合は中立を選び、confidenceを下げてください。"
            f"{hint}"
            f"必須JSON形式: {json.dumps(schema, ensure_ascii=False)}"
        )

    def _build_user_prompt(self, target: TopicConfig, posts: list[ContentItem], analyzed_at: str) -> str:
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
        return (
            f"target_id={target.target_id}\n"
            f"target_name={target.display_name}\n"
            f"keywords={json.dumps(target.keywords, ensure_ascii=False)}\n"
            f"analysis_profile={target.analysis_profile}\n"
            f"analyzed_at={analyzed_at}\n"
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
            usd_bias=self._enum_value(parsed.get("usd_bias"), "中立"),
            equity_bias=self._enum_value(parsed.get("equity_bias"), "中立"),
            risk_regime=self._enum_value(parsed.get("risk_regime"), "中立"),
            rate_bias=self._enum_value(parsed.get("rate_bias"), "中立"),
            inflation_bias=self._enum_value(parsed.get("inflation_bias"), "中立"),
            trade_policy_bias=self._enum_value(parsed.get("trade_policy_bias"), "中立"),
            geopolitical_risk=self._enum_value(parsed.get("geopolitical_risk"), "中程度"),
            overall_tone=self._enum_value(parsed.get("overall_tone"), "中立"),
            confidence=self._confidence_value(parsed.get("confidence")),
            key_drivers=self._key_drivers(parsed.get("key_drivers")),
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

    @staticmethod
    def _key_drivers(value: Any) -> list[str]:
        items = AnalysisService._string_list(value)[:3]
        trimmed = [item[:50] for item in items]
        while len(trimmed) < 3:
            trimmed.append("情報整理中")
        return trimmed
