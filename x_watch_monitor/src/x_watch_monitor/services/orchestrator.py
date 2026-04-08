from __future__ import annotations

import logging
from datetime import timedelta

from x_watch_monitor.models import TopicConfig, utc_now
from x_watch_monitor.repositories import (
    AnalysisRepository,
    ErrorRepository,
    NotificationRepository,
    PostRepository,
    StateRepository,
)
from x_watch_monitor.services.analysis_service import AnalysisService
from x_watch_monitor.services.collection_service import CollectionService
from x_watch_monitor.services.diff_service import DiffService
from x_watch_monitor.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class MonitorOrchestrator:
    def __init__(
        self,
        *,
        state_repository: StateRepository,
        post_repository: PostRepository,
        analysis_repository: AnalysisRepository,
        notification_repository: NotificationRepository,
        error_repository: ErrorRepository,
        collection_service: CollectionService,
        diff_service: DiffService,
        analysis_service: AnalysisService,
        notification_service: NotificationService,
    ) -> None:
        self.state_repository = state_repository
        self.post_repository = post_repository
        self.analysis_repository = analysis_repository
        self.notification_repository = notification_repository
        self.error_repository = error_repository
        self.collection_service = collection_service
        self.diff_service = diff_service
        self.analysis_service = analysis_service
        self.notification_service = notification_service

    def run(self, targets: list[TopicConfig]) -> None:
        for target in targets:
            if not target.enabled:
                logger.info("skip disabled target target_id=%s", target.target_id)
                continue
            self._run_target(target)

    def _run_target(self, target: TopicConfig) -> None:
        state = self.state_repository.get(target.target_id)
        now = utc_now()
        if state.last_polled_at and now - state.last_polled_at < timedelta(minutes=target.poll_interval_minutes):
            logger.info(
                "skip target because interval not elapsed target_id=%s interval_minutes=%d",
                target.target_id,
                target.poll_interval_minutes,
            )
            return

        logger.info("start target target_id=%s keywords=%s", target.target_id, ",".join(target.keywords))
        try:
            posts = self.collection_service.collect(target, since_time=state.last_processed_post_at)
            self.post_repository.save_many(posts)
            new_posts = self.diff_service.select_unprocessed(posts, target.target_id, state.last_processed_post_at)
            if not new_posts:
                logger.info("no new posts target_id=%s", target.target_id)
                self.state_repository.upsert(
                    target.target_id,
                    last_processed_post_id=state.last_processed_post_id,
                    last_processed_post_at=state.last_processed_post_at,
                    last_polled_at=now,
                    last_success_at=now,
                )
                return

            previous_analysis = self.analysis_repository.get_latest_payload(target.target_id)
            analysis = self.analysis_service.analyze(target, new_posts, previous_analysis=previous_analysis)
            analysis_id = self.analysis_repository.save(analysis)
            try:
                response_body = self.notification_service.notify(target, analysis)
            except Exception as exc:
                self.notification_repository.mark_failed(
                    target.target_id,
                    [post.post_id for post in new_posts],
                    analysis_id,
                    target.discord_webhook_url,
                    str(exc),
                )
                raise

            max_post = max(new_posts, key=lambda item: (item.created_at, item.post_id))
            self.notification_repository.mark_sent(
                target.target_id,
                [post.post_id for post in new_posts],
                analysis_id,
                target.discord_webhook_url,
                response_body,
            )
            self.state_repository.upsert(
                target.target_id,
                last_processed_post_id=max_post.post_id,
                last_processed_post_at=max_post.created_at,
                last_polled_at=now,
                last_success_at=now,
            )
            logger.info(
                "completed target target_id=%s new_posts=%d analysis_id=%d",
                target.target_id,
                len(new_posts),
                analysis_id,
            )
        except Exception as exc:
            logger.exception("target failed target_id=%s", target.target_id)
            self.error_repository.log("target_run", str(exc), target_id=target.target_id)
            self.state_repository.upsert(
                target.target_id,
                last_processed_post_id=state.last_processed_post_id,
                last_processed_post_at=state.last_processed_post_at,
                last_polled_at=now,
                last_success_at=state.last_success_at,
            )
