"""OpenAI-compatible API client for media name parsing."""

import json
import logging
import time

from openai import OpenAI, APIError, APITimeoutError

from jelly_weaver.core.models import LLMResult, MediaType, LinkPlan, PlanItem, StructureType
from .prompts import (
    SYSTEM_PROMPT, build_user_prompt,
    STRUCTURE_SYSTEM_PROMPT, build_structure_prompt,
    RENAME_SYSTEM_PROMPT, build_rename_prompt,
)

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_TIMEOUT = 30
_HEALTH_TIMEOUT = 10


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
        self._api_base = api_base
        self._api_key = api_key
        self._model = model

    def _create(self, **kwargs):
        """Call chat.completions.create with automatic fallbacks for picky models.

        Some models (o1, o3, etc.) reject 'temperature' or 'response_format'.
        On a 400 that mentions the unsupported parameter, retry once without it.
        """
        try:
            return self._client.chat.completions.create(**kwargs)
        except APIError as e:
            err = str(e)
            retried = False
            if "temperature" in err:
                kwargs.pop("temperature", None)
                retried = True
            if "response_format" in err:
                kwargs.pop("response_format", None)
                retried = True
            if retried:
                return self._client.chat.completions.create(**kwargs)
            raise

    def parse_folder_name(
        self,
        name: str,
        hint: str | None = None,
    ) -> LLMResult | None:
        """Parse a raw folder name into structured media info."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(name, hint)},
        ]
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = self._create(
                    model=self._model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                content = resp.choices[0].message.content
                return self._parse_response(content)
            except (APIError, APITimeoutError) as e:
                logger.warning("LLM attempt %d failed: %s", attempt + 1, e)
                if attempt < _MAX_RETRIES:
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.error("LLM unexpected error: %s", e)
                return None
        return None

    def health_check(self) -> bool:
        """Test connectivity with a minimal API call."""
        # Use 16 as the minimum token count — some models (e.g. Gemini via proxy)
        # reject values below 16 for max_output_tokens.
        _MIN_TOKENS = 16
        try:
            health_client = OpenAI(
                base_url=self._api_base,
                api_key=self._api_key,
                timeout=_HEALTH_TIMEOUT,
            )
            kwargs: dict = dict(
                model=self._model,
                messages=[{"role": "user", "content": "hi"}],
            )
            try:
                resp = health_client.chat.completions.create(**kwargs, max_tokens=_MIN_TOKENS)
            except APIError as e:
                err = str(e)
                if "max_tokens" in err:
                    try:
                        resp = health_client.chat.completions.create(**kwargs, max_completion_tokens=_MIN_TOKENS)
                    except APIError as e2:
                        err2 = str(e2)
                        if "max_completion_tokens" in err2 or "max_output_tokens" in err2:
                            resp = health_client.chat.completions.create(**kwargs, max_output_tokens=_MIN_TOKENS)
                        else:
                            raise
                else:
                    raise
            return bool(resp.choices)
        except Exception as e:
            logger.warning("LLM health check failed: %s", e)
            raise

    @staticmethod
    def _parse_response(content: str) -> LLMResult | None:
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

    def analyze_structure(
        self,
        folder_name: str,
        tree: dict,
    ) -> LinkPlan | None:
        """Analyze source directory structure and generate a link plan."""
        messages = [
            {"role": "system", "content": STRUCTURE_SYSTEM_PROMPT},
            {"role": "user", "content": build_structure_prompt(folder_name, tree)},
        ]
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = self._create(
                    model=self._model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                content = resp.choices[0].message.content
                return self._parse_structure_response(content)
            except (APIError, APITimeoutError) as e:
                logger.warning("LLM structure analysis attempt %d failed: %s", attempt + 1, e)
                if attempt < _MAX_RETRIES:
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.error("LLM structure analysis unexpected error: %s", e)
                return None
        return None

    @staticmethod
    def _parse_structure_response(content: str) -> LinkPlan | None:
        try:
            data = json.loads(content)
            structure_type = StructureType(data["structure_type"])
            items = []
            for item in data.get("items", []):
                items.append(PlanItem(
                    source_subdir=item.get("source_subdir", ""),
                    target_subdir=item.get("target_subdir", ""),
                    title_en=item.get("title_en", ""),
                    year=int(item.get("year", 0)),
                ))
            return LinkPlan(structure_type=structure_type, items=items)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Failed to parse LLM structure response: %s", e)
            return None

    def rename_batch(
        self,
        siblings: list[dict],
        parent_context: str,
        depth: int = 0,
    ) -> list[str | None]:
        """Batch-rename a group of sibling directories."""
        if not siblings:
            return []
        messages = [
            {"role": "system", "content": RENAME_SYSTEM_PROMPT},
            {"role": "user", "content": build_rename_prompt(siblings, parent_context)},
        ]
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = self._create(
                    model=self._model,
                    messages=messages,
                    temperature=0.1,
                )
                content = resp.choices[0].message.content or ""
                names = self._parse_rename_response(content, len(siblings))
                if names is not None:
                    return names
            except (APIError, APITimeoutError) as e:
                logger.warning("rename_batch attempt %d failed: %s", attempt + 1, e)
                if attempt < _MAX_RETRIES:
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.error("rename_batch unexpected error: %s", e)
                return [None] * len(siblings)
        return [None] * len(siblings)

    @staticmethod
    def _parse_rename_response(content: str, expected: int) -> list[str | None] | None:
        try:
            text = content.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
                text = text.rstrip("`").strip()
            data = json.loads(text)
            if not isinstance(data, list):
                return None
            result: list[str | None] = [None] * expected
            for item in data:
                idx = int(item["index"])
                if 0 <= idx < expected:
                    result[idx] = str(item["name"])
            return result
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.error("Failed to parse rename response: %s | content: %s", e, content[:200])
            return None
