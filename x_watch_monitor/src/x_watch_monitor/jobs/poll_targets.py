from __future__ import annotations

import argparse

from x_watch_monitor.clients.discord_client import DiscordWebhookClient
from x_watch_monitor.clients.grok_client import GrokClient
from x_watch_monitor.clients.x_client import XApiClient
from x_watch_monitor.config import load_settings, load_targets
from x_watch_monitor.logging_utils import configure_logging
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll configured X targets, analyze with Grok, and notify Discord.")
    parser.add_argument("--config", help="Path to targets yaml. Defaults to CONFIG_PATH env or config/targets.yaml.")
    parser.add_argument("--db", help="Path to SQLite database. Defaults to DATABASE_PATH env or data/monitor.db.")
    args = parser.parse_args()

    settings = load_settings()
    if args.config:
        settings.config_path = args.config
    if args.db:
        settings.database_path = args.db

    configure_logging(settings.log_level)
    targets = load_targets(settings.config_path)

    db = Database(settings.database_path)
    db.initialize()

    orchestrator = MonitorOrchestrator(
        state_repository=StateRepository(db),
        post_repository=PostRepository(db),
        analysis_repository=AnalysisRepository(db),
        notification_repository=NotificationRepository(db),
        error_repository=ErrorRepository(db),
        collection_service=CollectionService(XApiClient(settings)),
        diff_service=DiffService(NotificationRepository(db)),
        analysis_service=AnalysisService(GrokClient(settings)),
        notification_service=NotificationService(DiscordWebhookClient(settings)),
    )
    orchestrator.run(targets)


if __name__ == "__main__":
    main()
