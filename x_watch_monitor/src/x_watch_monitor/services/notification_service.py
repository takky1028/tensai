from __future__ import annotations

import json

from x_watch_monitor.clients.discord_client import DiscordWebhookClient
from x_watch_monitor.models import AnalysisResult, TopicConfig


class NotificationService:
    discord_limit = 1900

    def __init__(self, discord_client: DiscordWebhookClient) -> None:
        self.discord_client = discord_client

    def notify(self, target: TopicConfig, analysis: AnalysisResult) -> dict:
        contents = self._render_messages(target, analysis)
        return self.discord_client.send_messages(target.discord_webhook_url, contents)

    def _render_messages(self, target: TopicConfig, analysis: AnalysisResult) -> list[str]:
        highlights = {
            "usd_bias": analysis.usd_bias,
            "equity_bias": analysis.equity_bias,
            "risk_regime": analysis.risk_regime,
            "rate_bias": analysis.rate_bias,
            "inflation_bias": analysis.inflation_bias,
            "trade_policy_bias": analysis.trade_policy_bias,
            "geopolitical_risk": analysis.geopolitical_risk,
            "overall_tone": analysis.overall_tone,
            "confidence": analysis.confidence,
        }
        signal_lines = self._format_signal_assessment(analysis.signal_assessment)
        sections = [
            f"**Topic Monitor Alert | {target.display_name}**\n"
            f"Analyzed at: {analysis.analyzed_at.isoformat()}\n"
            f"Processed items: {len(analysis.source_posts)}",
            f"Summary: {analysis.summary}",
            f"Why now: {analysis.why_now or 'n/a'}",
            f"Change vs previous: {analysis.change_summary or 'Initial snapshot'}",
            f"Market triggers: {', '.join(analysis.market_triggers) if analysis.market_triggers else 'n/a'}",
            f"Next watch events: {', '.join(analysis.next_watch_events) if analysis.next_watch_events else 'n/a'}",
            "Signals:\n" + f"```json\n{json.dumps(highlights, ensure_ascii=False, indent=2)}\n```",
            f"Signal assessment:\n{signal_lines}",
            f"Key drivers: {', '.join(analysis.key_drivers) if analysis.key_drivers else 'n/a'}",
            f"Notable quotes: {', '.join(analysis.notable_quotes[:3]) if analysis.notable_quotes else 'n/a'}",
            "Source items:",
        ]
        sections.extend(f"- {item['url']}" for item in analysis.source_posts[:5])
        return self._chunk_sections(sections)

    @staticmethod
    def _format_signal_assessment(signal_assessment: dict[str, dict[str, str]]) -> str:
        if not signal_assessment:
            return "- n/a"

        lines = []
        for key, item in signal_assessment.items():
            strength = item.get("strength", "weak")
            horizon = item.get("horizon", "short_term")
            rationale = item.get("rationale", "")
            line = f"- {key}: strength={strength}, horizon={horizon}"
            if rationale:
                line += f", rationale={rationale}"
            lines.append(line)
        return "\n".join(lines)

    def _chunk_sections(self, sections: list[str]) -> list[str]:
        messages: list[str] = []
        current_parts: list[str] = []

        for section in sections:
            safe_section = self._truncate_section(section)
            candidate_parts = current_parts + [safe_section]
            candidate = "\n\n".join(candidate_parts)
            if current_parts and len(candidate) > self.discord_limit:
                messages.append("\n\n".join(current_parts))
                current_parts = [safe_section]
            else:
                current_parts = candidate_parts

        if current_parts:
            messages.append("\n\n".join(current_parts))

        return messages

    def _truncate_section(self, section: str) -> str:
        if len(section) <= self.discord_limit:
            return section
        return section[: self.discord_limit - 3] + "..."
