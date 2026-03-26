"""Minimal GLM chat-completions client (global Z.AI API)."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_GLM_BASE_URL = "https://api.z.ai/api/paas/v4"
DEFAULT_GLM_CODING_BASE_URL = "https://api.z.ai/api/coding/paas/v4"


class GLMClientError(RuntimeError):
    """Raised when a GLM API call cannot be completed."""


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def chat_completion(
    messages: list[dict[str, str]],
    model: str = "glm-5",
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    """Call Z.AI-compatible chat completions endpoint.

    Reference: docs.z.ai `/paas/v4/chat/completions`
    """
    resolved_key = api_key or os.getenv("GLM_API_KEY")
    if not resolved_key:
        raise GLMClientError(
            "Missing GLM API key. Set GLM_API_KEY or pass --glm-api-key."
        )

    resolved_base = _normalize_base_url(
        base_url or os.getenv("GLM_BASE_URL", DEFAULT_GLM_BASE_URL)
    )
    url = f"{resolved_base}/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {resolved_key}",
        "Content-Type": "application/json",
        "Accept-Language": "en-US,en",
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, json=payload, headers=headers)

    if response.status_code >= 400:
        snippet = response.text[:400]
        raise GLMClientError(
            f"GLM request failed ({response.status_code}) at {url}: {snippet}"
        )

    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise GLMClientError("GLM response missing choices.")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        raise GLMClientError("GLM response missing textual message content.")

    return {
        "model": data.get("model", model),
        "content": content,
        "raw": data,
    }
