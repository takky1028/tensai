from datetime import datetime, timezone

from x_watch_monitor.models import ContentItem
from x_watch_monitor.services.diff_service import DiffService


class StubNotificationRepository:
    def __init__(self, sent_ids: set[str] | None = None) -> None:
        self.sent_ids = sent_ids or set()

    def was_sent(self, target_id: str, post_id: str) -> bool:
        return post_id in self.sent_ids


def build_post(post_id: str, hour: int) -> ContentItem:
    return ContentItem(
        post_id=post_id,
        target_id="t1",
        source_type="news_rss",
        source_author="Google News",
        title=f"title {post_id}",
        text=f"post {post_id}",
        created_at=datetime(2026, 4, 7, hour, 0, tzinfo=timezone.utc),
        url=f"https://example.com/{post_id}",
        raw_json={},
    )


def test_select_unprocessed_filters_last_processed_and_sent_items() -> None:
    posts = [build_post("100", 0), build_post("101", 1), build_post("102", 2)]
    service = DiffService(StubNotificationRepository(sent_ids={"102"}))

    result = service.select_unprocessed(posts, "t1", last_processed_post_at=datetime(2026, 4, 7, 0, 30, tzinfo=timezone.utc))

    assert [item.post_id for item in result] == ["101"]
