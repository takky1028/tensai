from __future__ import annotations

from x_watch_monitor.clients.discord_client import DiscordWebhookClient
from x_watch_monitor.models import AnalysisResult, TopicConfig


class NotificationService:
    def __init__(self, discord_client: DiscordWebhookClient) -> None:
        self.discord_client = discord_client

    def notify(self, target: TopicConfig, analysis: AnalysisResult) -> dict:
        content = self._render_message(target, analysis)
        return self.discord_client.send_message(target.discord_webhook_url, content)

    def _render_message(self, target: TopicConfig, analysis: AnalysisResult) -> str:
        key_points = "\n".join(f"- {self._truncate(point, 50)}" for point in analysis.key_drivers[:3])
        return (
            f"【{target.display_name}】\n"
            "要点:\n"
            f"{key_points}\n"
            f"ドル: {analysis.usd_bias}\n"
            f"株: {analysis.equity_bias}\n"
            f"リスク: {analysis.risk_regime}\n"
            f"金利: {analysis.rate_bias}\n"
            f"物価・景気: {analysis.inflation_bias}\n"
            f"関税・貿易摩擦: {analysis.trade_policy_bias}\n"
            f"地政学: {analysis.geopolitical_risk}\n"
            f"総合トーン: {analysis.overall_tone}\n"
            f"確信度: {analysis.confidence}"
        )

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit]
