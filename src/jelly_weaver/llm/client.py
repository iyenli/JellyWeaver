"""OpenAI-compatible API client for media directory renaming."""

import json
import logging
import time

from openai import OpenAI, APIError, APITimeoutError

from jelly_weaver.core.tree import TreeNode
from .prompts import RENAME_SYSTEM_PROMPT, build_rename_prompt

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_TIMEOUT = 30
_HEALTH_TIMEOUT = 10


class LLMClient:
    def __init__(self, api_base: str, api_key: str, model: str):
        self._client = OpenAI(base_url=api_base, api_key=api_key, timeout=_TIMEOUT)
        self._api_base = api_base
        self._api_key = api_key
        self._model = model

    def _create(self, **kwargs):
        """Call chat.completions.create with fallbacks for picky models.

        Some models (o1, o3, Gemini via proxy, etc.) reject 'temperature' or
        'response_format'. On a 400 mentioning the unsupported param, retry once
        without it.
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

    def rename_tree(self, root: TreeNode) -> tuple[dict[str, str], str | None]:
        """Rename all directories in one LLM call with full tree context.

        Passes the complete directory tree so the LLM can see root name,
        all siblings, children, and sample files simultaneously — avoiding
        the ambiguity of naming a Season folder without knowing the parent type.

        Returns:
            (names, media_type) where names is {node_key: suggested_name} for
            every directory in the tree, and media_type is "tv" or "movie"
            (None on failure).
        """
        prompt_text, keys = build_rename_prompt(root)
        messages = [
            {"role": "system", "content": RENAME_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ]
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = self._create(
                    model=self._model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                content = resp.choices[0].message.content or ""
                result = self._parse_rename_response(content, keys)
                if result is not None:
                    return result
            except (APIError, APITimeoutError) as e:
                logger.warning("rename_tree attempt %d failed: %s", attempt + 1, e)
                if attempt < _MAX_RETRIES:
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.error("rename_tree unexpected error: %s", e)
                return {}, None
        return {}, None

    def health_check(self) -> bool:
        """Test connectivity with a minimal API call."""
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
    def _parse_rename_response(content: str, keys: list[str]) -> tuple[dict[str, str], str | None] | None:
        try:
            text = content.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
                text = text.rstrip("`").strip()
            data = json.loads(text)
            # Support both {"renames":[...]} and bare [...] (fallback for models
            # that ignore response_format and return an array directly)
            items = data.get("renames", data) if isinstance(data, dict) else data
            if not isinstance(items, list):
                return None
            media_type: str | None = data.get("media_type") if isinstance(data, dict) else None
            if media_type not in ("tv", "movie"):
                media_type = None
            result: dict[str, str] = {}
            for item in items:
                idx = int(item["id"])
                if 0 <= idx < len(keys):
                    result[keys[idx]] = str(item["name"])
            return result, media_type
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.error("Failed to parse rename response: %s | content: %s", e, content[:200])
            return None
