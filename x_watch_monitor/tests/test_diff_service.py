from x_watch_monitor.models import XPost
from x_watch_monitor.services.diff_service import DiffService


class StubNotificationRepository:
    def __init__(self, sent_ids: set[str] | None = None) -> None:
        self.sent_ids = sent_ids or set()

    def was_sent(self, target_id: str, post_id: str) -> bool:
        return post_id in self.sent_ids


def build_post(post_id: str) -> XPost:
    return XPost(
        post_id=post_id,
        author_id="a1",
        x_user="example",
        target_id="t1",
        text=f"post {post_id}",
        created_at=__import__("datetime").datetime.fromisoformat("2026-04-07T00:00:00+00:00"),
        conversation_id=post_id,
        in_reply_to_user_id=None,
        referenced_tweets=[],
        raw_json={},
    )


def test_select_unprocessed_filters_last_processed_and_sent_items() -> None:
    posts = [build_post("100"), build_post("101"), build_post("102")]
    service = DiffService(StubNotificationRepository(sent_ids={"102"}))

    result = service.select_unprocessed(posts, "t1", last_processed_post_id="100")

    assert [item.post_id for item in result] == ["101"]
