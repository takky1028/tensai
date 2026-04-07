from __future__ import annotations

from x_watch_monitor.clients.x_client import XApiClient
from x_watch_monitor.models import TargetConfig, XPost


class CollectionService:
    def __init__(self, x_client: XApiClient) -> None:
        self.x_client = x_client

    def collect(self, target: TargetConfig, since_id: str | None) -> list[XPost]:
        return self.x_client.fetch_recent_posts(target, since_id=since_id)
