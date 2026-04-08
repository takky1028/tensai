from __future__ import annotations

import requests

from x_watch_monitor.models import AppSettings


class DiscordWebhookClient:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def send_message(self, webhook_url: str, content: str) -> dict:
        if not webhook_url:
            raise RuntimeError("discord_webhook_url is not set for target")
        response = self.session.post(
            webhook_url,
            json={"content": content},
            timeout=self.settings.discord_request_timeout_sec,
        )
        if response.status_code >= 300:
            raise RuntimeError(f"Discord webhook failed: {response.status_code} {response.text}")
        if not response.text:
            return {"status_code": response.status_code}
        try:
            return response.json()
        except ValueError:
            return {"status_code": response.status_code, "body": response.text}

    def send_messages(self, webhook_url: str, contents: list[str]) -> dict:
        responses = []
        for content in contents:
            responses.append(self.send_message(webhook_url, content))
        return {"messages_sent": len(responses), "responses": responses}
