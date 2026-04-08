from datetime import datetime, timezone

from x_watch_monitor.models import AnalysisResult, TopicConfig
from x_watch_monitor.services.notification_service import NotificationService


class StubDiscordClient:
    def __init__(self) -> None:
        self.contents: list[str] = []

    def send_message(self, webhook_url: str, content: str) -> dict:
        self.contents.append(content)
        return {"webhook_url": webhook_url, "content": content}

    def send_messages(self, webhook_url: str, contents: list[str]) -> dict:
        responses = []
        for content in contents:
            responses.append(self.send_message(webhook_url, content))
        return {"messages_sent": len(responses), "responses": responses}


def test_notification_message_includes_new_context_fields() -> None:
    client = StubDiscordClient()
    service = NotificationService(client)
    target = TopicConfig(
        target_id="macro-watch",
        display_name="Macro Watch",
        keywords=["FRB", "Trump"],
        enabled=True,
        poll_interval_minutes=120,
        max_items=10,
        x_search_enabled=True,
        news_enabled=True,
        analysis_profile="default",
        discord_webhook_url="https://discord.example/webhook",
    )
    analysis = AnalysisResult(
        target_id="macro-watch",
        target_name="Macro Watch",
        analyzed_at=datetime(2026, 4, 8, 0, 0, tzinfo=timezone.utc),
        source_posts=[
            {
                "post_id": "200",
                "created_at": "2026-04-08T00:00:00+00:00",
                "text": "sample",
                "url": "https://x.com/example/status/200",
            }
        ],
        summary="summary",
        why_now="liquidity is thin and policy sensitivity is elevated",
        change_summary="more hawkish than the previous snapshot",
        market_triggers=["tariff escalation", "rate-path repricing"],
        next_watch_events=["CPI release", "Fed speaker remarks"],
        usd_bias="neutral",
        equity_bias="neutral",
        risk_regime="neutral",
        rate_bias="neutral",
        inflation_bias="neutral",
        trade_policy_bias="neutral",
        geopolitical_risk="medium",
        overall_tone="neutral",
        confidence=55,
        key_drivers=["driver"],
        notable_quotes=["quote"],
        signal_assessment={
            "usd": {"strength": "strong", "horizon": "short_term", "rationale": "policy shock sensitivity"}
        },
        raw_model_output={"ok": True},
    )

    result = service.notify(target, analysis)
    content = client.contents[0]

    assert "Why now:" in content
    assert "Change vs previous:" in content
    assert "Market triggers:" in content
    assert "Next watch events:" in content
    assert "strength=strong" in content
    assert result["messages_sent"] == 1


def test_notification_splits_long_messages_under_discord_limit() -> None:
    client = StubDiscordClient()
    service = NotificationService(client)
    target = TopicConfig(
        target_id="macro-watch",
        display_name="Macro Watch",
        keywords=["FRB", "Trump"],
        enabled=True,
        poll_interval_minutes=120,
        max_items=10,
        x_search_enabled=True,
        news_enabled=True,
        analysis_profile="default",
        discord_webhook_url="https://discord.example/webhook",
    )
    analysis = AnalysisResult(
        target_id="macro-watch",
        target_name="Macro Watch",
        analyzed_at=datetime(2026, 4, 8, 0, 0, tzinfo=timezone.utc),
        source_posts=[
            {
                "post_id": str(idx),
                "created_at": "2026-04-08T00:00:00+00:00",
                "text": "sample",
                "url": f"https://example.com/{idx}",
            }
            for idx in range(10)
        ],
        summary="S" * 900,
        why_now="W" * 900,
        change_summary="C" * 900,
        market_triggers=["T" * 300, "U" * 300],
        next_watch_events=["E" * 300, "F" * 300],
        usd_bias="neutral",
        equity_bias="neutral",
        risk_regime="neutral",
        rate_bias="neutral",
        inflation_bias="neutral",
        trade_policy_bias="neutral",
        geopolitical_risk="medium",
        overall_tone="neutral",
        confidence=55,
        key_drivers=["driver1", "driver2", "driver3"],
        notable_quotes=["quote1", "quote2", "quote3"],
        signal_assessment={
            "usd": {"strength": "strong", "horizon": "short_term", "rationale": "R" * 500},
            "rates": {"strength": "medium", "horizon": "medium_term", "rationale": "Q" * 500},
        },
        raw_model_output={"ok": True},
    )

    result = service.notify(target, analysis)

    assert result["messages_sent"] >= 2
    assert all(len(content) <= service.discord_limit for content in client.contents)
