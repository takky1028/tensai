from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from x_watch_monitor.models import AppSettings

logger = logging.getLogger(__name__)

JSON_BLOCK_PATTERN = re.compile(r"```json\s*(\{.*\})\s*```", re.DOTALL)


class GrokClient:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def analyze_posts(self, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if not self.settings.xai_api_key:
            raise RuntimeError("XAI_API_KEY is not set")

        payload = {
            "model": self.settings.grok_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        response = self.session.post(
            f"{self.settings.grok_api_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.xai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.settings.grok_request_timeout_sec,
        )
        response.raise_for_status()
        body = response.json()
        content = self._extract_content(body)
        parsed = self._parse_json_content(content)
        return parsed, body

    @staticmethod
    def _extract_content(body: dict[str, Any]) -> str:
        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError("Grok response did not include choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if isinstance(item, dict)]
            return "\n".join(part for part in text_parts if part)
        raise RuntimeError("Grok response content format was not recognized")

    @staticmethod
    def _parse_json_content(content: str) -> dict[str, Any]:
        candidate = content.strip()
        block_match = JSON_BLOCK_PATTERN.search(candidate)
        if block_match:
            candidate = block_match.group(1)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            logger.error("failed to parse Grok JSON content=%s", content)
            raise RuntimeError("Grok response was not valid JSON") from exc
