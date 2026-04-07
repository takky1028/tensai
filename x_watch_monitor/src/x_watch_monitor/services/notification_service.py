from __future__ import annotations

import json

from x_watch_monitor.clients.discord_client import DiscordWebhookClient
from x_watch_monitor.models import AnalysisResult, TargetConfig


class NotificationService:
    def __init__(self, discord_client: DiscordWebhookClient) -> None:
        self.discord_client = discord_client

    def notify(self, target: TargetConfig, analysis: AnalysisResult) -> dict:
        content = self._render_message(target, analysis)
        return self.discord_client.send_message(target.discord_webhook_url, content)

    def _render_message(self, target: TargetConfig, analysis: AnalysisResult) -> str:
        highlights = {
            "usd_bias": analysis.usd_bias,
            "equity_bias": analysis.equity_bias,
            "risk_regime": analysis.risk_regime,
            "rate_bias": analysis.rate_bias,
            "inflation_bias": analysis.inflation_bias,
            "trade_policy_bias": analysis.trade_policy_bias,
            "geopolitical_risk": analysis.geopolitical_risk,
            "confidence": analysis.confidence,
        }
        post_links = "\n".join(f"- {item['url']}" for item in analysis.source_posts[:5])
        return (
            f"**X Monitor Alert | {target.display_name} (@{target.x_user})**\n"
            f"Analyzed at: {analysis.analyzed_at.isoformat()}\n"
            f"Processed posts: {len(analysis.source_posts)}\n"
            f"Summary: {analysis.summary}\n"
            "Signals:\n"
            f"```json\n{json.dumps(highlights, ensure_ascii=False, indent=2)}\n```\n"
            f"Key drivers: {', '.join(analysis.key_drivers) if analysis.key_drivers else 'n/a'}\n"
            f"Notable quotes: {', '.join(analysis.notable_quotes[:3]) if analysis.notable_quotes else 'n/a'}\n"
            f"Posts:\n{post_links}"
        )
