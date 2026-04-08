from datetime import datetime, timezone

from x_watch_monitor.models import AnalysisResult, ContentItem, TopicConfig
from x_watch_monitor.repositories import (
    AnalysisRepository,
    Database,
    ErrorRepository,
    NotificationRepository,
    PostRepository,
    StateRepository,
)
from x_watch_monitor.services import (
    AnalysisService,
    CollectionService,
    DiffService,
    MonitorOrchestrator,
    NotificationService,
)


class FakeCollectionService(CollectionService):
    def __init__(self, posts: list[ContentItem]) -> None:
        self.posts = posts

    def collect(self, target: TopicConfig, since_time: datetime | None) -> list[ContentItem]:
        if since_time:
            return [post for post in self.posts if post.created_at > since_time]
        return list(self.posts)


class FakeAnalysisService(AnalysisService):
    def __init__(self) -> None:
        pass

    def analyze(self, target: TopicConfig, posts: list[ContentItem], previous_analysis=None) -> AnalysisResult:
        return AnalysisResult(
            target_id=target.target_id,
            target_name=target.display_name,
            analyzed_at=datetime.now(timezone.utc),
            source_posts=[
                {
                    "post_id": post.post_id,
                    "created_at": post.created_at.isoformat(),
                    "text": post.text,
                    "url": post.url,
                }
                for post in posts
            ],
            summary="summary",
            why_now="why now",
            change_summary="initial snapshot",
            market_triggers=["trigger"],
            next_watch_events=["event"],
            usd_bias="neutral",
            equity_bias="neutral",
            risk_regime="neutral",
            rate_bias="neutral",
            inflation_bias="neutral",
            trade_policy_bias="neutral",
            geopolitical_risk="medium",
            overall_tone="neutral",
            confidence=50,
            key_drivers=["driver"],
            notable_quotes=[],
            signal_assessment={"usd": {"strength": "medium", "horizon": "short_term", "rationale": "test"}},
            raw_model_output={"ok": True},
        )


class FakeNotificationService(NotificationService):
    def __init__(self) -> None:
        self.calls = 0

    def notify(self, target: TopicConfig, analysis: AnalysisResult) -> dict:
        self.calls += 1
        return {"ok": True}


def build_post(post_id: str, hour: int) -> ContentItem:
    return ContentItem(
        post_id=post_id,
        target_id="macro-watch",
        source_type="news_rss",
        source_author="Google News",
        title=f"title {post_id}",
        text=f"post {post_id}",
        created_at=datetime(2026, 4, 7, hour, 0, tzinfo=timezone.utc),
        url=f"https://example.com/{post_id}",
        raw_json={},
    )


def test_orchestrator_updates_state_and_avoids_duplicate_notification(tmp_path) -> None:
    db = Database(str(tmp_path / "monitor.db"))
    db.initialize()

    state_repo = StateRepository(db)
    notification_repo = NotificationRepository(db)
    notification_service = FakeNotificationService()
    posts = [build_post("200", 0), build_post("201", 1)]
    target = TopicConfig(
        target_id="macro-watch",
        display_name="Macro Watch",
        keywords=["FRB", "Trump"],
        enabled=True,
        poll_interval_minutes=0,
        max_items=10,
        x_search_enabled=True,
        news_enabled=True,
        analysis_profile="default",
        discord_webhook_url="https://discord.example/webhook",
    )

    orchestrator = MonitorOrchestrator(
        state_repository=state_repo,
        post_repository=PostRepository(db),
        analysis_repository=AnalysisRepository(db),
        notification_repository=notification_repo,
        error_repository=ErrorRepository(db),
        collection_service=FakeCollectionService(posts),
        diff_service=DiffService(notification_repo),
        analysis_service=FakeAnalysisService(),
        notification_service=notification_service,
    )

    orchestrator.run([target])
    first_state = state_repo.get("macro-watch")

    assert first_state.last_processed_post_id == "201"
    assert notification_service.calls == 1

    orchestrator.run([target])
    second_state = state_repo.get("macro-watch")

    assert second_state.last_processed_post_id == "201"
    assert notification_service.calls == 1
