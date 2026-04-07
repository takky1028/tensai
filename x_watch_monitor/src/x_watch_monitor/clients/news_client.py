from __future__ import annotations

import email.utils
import logging
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from x_watch_monitor.clients.x_client import stable_id
from x_watch_monitor.models import AppSettings, ContentItem, TopicConfig

logger = logging.getLogger(__name__)


class NewsRssClient:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def fetch_topic_news(self, topic: TopicConfig) -> list[ContentItem]:
        query = " OR ".join(topic.keywords)
        params = {
            "q": query,
            "hl": self.settings.google_news_hl,
            "gl": self.settings.google_news_gl,
            "ceid": self.settings.google_news_ceid,
        }
        url = f"{self.settings.google_news_rss_base_url}?{urllib.parse.urlencode(params)}"
        response = self.session.get(url, timeout=self.settings.news_request_timeout_sec)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        channel = root.find("channel")
        if channel is None:
            return []

        items: list[ContentItem] = []
        for entry in channel.findall("item")[: topic.max_items]:
            title = (entry.findtext("title") or "").strip()
            link = (entry.findtext("link") or "").strip()
            description = (entry.findtext("description") or "").strip()
            pub_date = email.utils.parsedate_to_datetime(entry.findtext("pubDate") or "")
            if pub_date is None:
                continue
            items.append(
                ContentItem(
                    post_id=stable_id([topic.target_id, link, title]),
                    target_id=topic.target_id,
                    source_type="news_rss",
                    source_author="Google News",
                    title=title,
                    text=description or title,
                    created_at=pub_date,
                    url=link,
                    raw_json={
                        "title": title,
                        "link": link,
                        "description": description,
                        "pubDate": entry.findtext("pubDate"),
                    },
                )
            )
        logger.info("fetched news items target_id=%s total=%d query=%s", topic.target_id, len(items), query)
        return items
