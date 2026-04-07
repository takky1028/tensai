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
            "ドル方向感": analysis.usd_bias,
            "株式方向感": analysis.equity_bias,
            "リスク環境": analysis.risk_regime,
            "金利バイアス": analysis.rate_bias,
            "物価・景気": analysis.inflation_bias,
            "通商政策": analysis.trade_policy_bias,
            "地政学リスク": analysis.geopolitical_risk,
            "確信度": analysis.confidence,
        }
        links = "\n".join(
            f"- [{item['source_type']}] {item.get('title') or item.get('text', '')[:40]} {item['url']}"
            for item in analysis.source_posts[:5]
        )
        return (
            f"**トピック監視アラート | {target.display_name}**\n"
            f"分析時刻: {analysis.analyzed_at.isoformat()}\n"
            f"収集件数: {len(analysis.source_posts)}\n"
            f"キーワード: {', '.join(target.keywords)}\n"
            f"要約: {analysis.summary}\n"
            "シグナル:\n"
            f"```json\n{json.dumps(highlights, ensure_ascii=False, indent=2)}\n```\n"
            f"主な材料: {'、'.join(analysis.key_drivers) if analysis.key_drivers else 'なし'}\n"
            f"注目引用: {' / '.join(analysis.notable_quotes[:3]) if analysis.notable_quotes else 'なし'}\n"
            f"参照ソース:\n{links}"
        )
