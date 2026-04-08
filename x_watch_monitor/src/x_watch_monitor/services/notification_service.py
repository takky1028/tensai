from __future__ import annotations

import json

from x_watch_monitor.clients.discord_client import DiscordWebhookClient
from x_watch_monitor.models import AnalysisResult, TopicConfig


class NotificationService:
    def __init__(self, discord_client: DiscordWebhookClient) -> None:
        self.discord_client = discord_client

    def notify(self, target: TopicConfig, analysis: AnalysisResult) -> dict:
        content = self._render_message(target, analysis)
        return self.discord_client.send_message(target.discord_webhook_url, content)

    def _render_message(self, target: TopicConfig, analysis: AnalysisResult) -> str:
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
        source_links = "\n".join(f"- {item['url']}" for item in analysis.source_posts[:5])
        signal_lines = self._format_signal_assessment(analysis.signal_assessment)
        return (
            f"**Topic Monitor Alert | {target.display_name}**\n"
            f"Analyzed at: {analysis.analyzed_at.isoformat()}\n"
            f"Processed items: {len(analysis.source_posts)}\n"
            f"Summary: {analysis.summary}\n"
            f"Why now: {analysis.why_now or 'n/a'}\n"
            f"Change vs previous: {analysis.change_summary or 'Initial snapshot'}\n"
            f"Market triggers: {', '.join(analysis.market_triggers) if analysis.market_triggers else 'n/a'}\n"
            f"Next watch events: {', '.join(analysis.next_watch_events) if analysis.next_watch_events else 'n/a'}\n"
            "Signals:\n"
            f"```json\n{json.dumps(highlights, ensure_ascii=False, indent=2)}\n```\n"
            f"Signal assessment:\n{signal_lines}\n"
            f"Key drivers: {', '.join(analysis.key_drivers) if analysis.key_drivers else 'n/a'}\n"
            f"Notable quotes: {', '.join(analysis.notable_quotes[:3]) if analysis.notable_quotes else 'n/a'}\n"
            f"Source items:\n{source_links}"
        )

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
