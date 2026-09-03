"""Small dependency-free client for OpenAI's Responses API."""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any


class OpenAIError(RuntimeError):
    """Raised when the Responses API cannot produce a usable result."""


Requester = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]


def _default_requester(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("error", {}).get("message", body)
        except json.JSONDecodeError:
            detail = body
        error = OpenAIError(f"OpenAI API returned HTTP {exc.code}: {detail}")
        error.status_code = exc.code  # type: ignore[attr-defined]
        error.retry_after = exc.headers.get("retry-after")  # type: ignore[attr-defined]
        raise error from exc
    except urllib.error.URLError as exc:
        raise OpenAIError(f"OpenAI API request failed: {exc.reason}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise OpenAIError("OpenAI API returned non-JSON data") from exc
    if not isinstance(parsed, dict):
        raise OpenAIError("OpenAI API returned an unexpected response shape")
    return parsed


def extract_output_text(response: dict[str, Any]) -> str:
    """Extract assistant text without assuming it is the first output item."""

    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct

    texts: list[str] = []
    refusals: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                texts.append(content["text"])
            elif content.get("type") == "refusal" and isinstance(content.get("refusal"), str):
                refusals.append(content["refusal"])

    if texts:
        return "\n".join(texts)
    if refusals:
        raise OpenAIError(f"Model refused the request: {'; '.join(refusals)}")
    raise OpenAIError("OpenAI API response did not contain output text")


class OpenAIClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4.1",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 180.0,
        max_retries: int = 3,
        requester: Requester | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.requester = requester or _default_requester
        self.sleeper = sleeper

    def create_json(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        schema_name: str,
        instructions: str | None = None,
        use_web_search: bool = False,
        max_output_tokens: int = 12_000,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": instructions
            or "Follow the task exactly. Return only data matching the supplied JSON Schema.",
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
        if use_web_search:
            # web_search_preview preserves compatibility with the original gpt-4.1 workflow.
            payload["tools"] = [{"type": "web_search_preview", "search_context_size": "high"}]
            payload["tool_choice"] = "auto"
            payload["include"] = ["web_search_call.action.sources"]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response: dict[str, Any] | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.requester(
                    f"{self.base_url}/responses", payload, headers, self.timeout
                )
                break
            except OpenAIError as exc:
                retryable = getattr(exc, "status_code", None) in {408, 409, 429, 500, 502, 503, 504}
                if attempt >= self.max_retries or not retryable:
                    raise
                retry_after = getattr(exc, "retry_after", None)
                try:
                    delay = float(retry_after) if retry_after else 2**attempt + random.random()
                except (TypeError, ValueError):
                    delay = 2**attempt + random.random()
                self.sleeper(min(delay, 30.0))

        if response is None:  # pragma: no cover - defensive invariant
            raise OpenAIError("OpenAI API request failed without a response")
        if response.get("status") in {"failed", "cancelled", "incomplete"}:
            detail = response.get("error") or response.get("incomplete_details") or response["status"]
            raise OpenAIError(f"OpenAI response was not completed: {detail}")

        raw = extract_output_text(response)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OpenAIError(f"Structured output was not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise OpenAIError("Structured output must be a JSON object")
        return data
