"""OpenAI-compatible API client for media name parsing."""

import json
import logging
import time

from openai import OpenAI, APIError, APITimeoutError

from jelly_weaver.core.models import LLMResult, MediaType
from .prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_TIMEOUT = 30


class LLMClient:
    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
    ):
        self._client = OpenAI(
            base_url=api_base,
            api_key=api_key,
            timeout=_TIMEOUT,
        )
        self._model = model

    def parse_folder_name(
        self,
        name: str,
        hint: str | None = None,
    ) -> LLMResult | None:
        """Parse a raw folder name into structured media info.

        Returns None if parsing fails after retries.
        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(name, hint)},
        ]

        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                content = resp.choices[0].message.content
                return self._parse_response(content)
            except (APIError, APITimeoutError) as e:
                logger.warning(
                    "LLM attempt %d failed: %s", attempt + 1, e,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.error("LLM unexpected error: %s", e)
                return None
        return None

    @staticmethod
    def _parse_response(content: str) -> LLMResult | None:
        """Parse JSON response into LLMResult."""
        try:
            data = json.loads(content)
            return LLMResult(
                media_type=MediaType(data["media_type"]),
                title_en=data["title_en"],
                title_zh=data.get("title_zh", ""),
                year=int(data["year"]),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Failed to parse LLM response: %s", e)
            return None
