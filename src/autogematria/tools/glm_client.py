"""Minimal GLM chat-completions client with endpoint/model fallback."""

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


def _extract_error(data: dict[str, Any], fallback_text: str) -> tuple[str | None, str]:
    error = data.get("error")
    if isinstance(error, dict):
        code = str(error.get("code")) if error.get("code") is not None else None
        message = str(error.get("message", fallback_text))
        return code, message
    return None, fallback_text


def _candidate_endpoints(base_url: str | None) -> list[str]:
    if base_url:
        return [_normalize_base_url(base_url)]
    return [DEFAULT_GLM_BASE_URL, DEFAULT_GLM_CODING_BASE_URL]


def chat_completion(
    messages: list[dict[str, str]],
    model: str = "glm-5",
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 60.0,
    allow_model_fallback: bool = True,
) -> dict[str, Any]:
    """Call Z.AI-compatible chat completions endpoint.

    Reference: docs.z.ai `/paas/v4/chat/completions`
    """
    resolved_key = api_key or os.getenv("GLM_API_KEY")
    if not resolved_key:
        raise GLMClientError(
            "Missing GLM API key. Set GLM_API_KEY or pass --glm-api-key."
        )

    env_base = os.getenv("GLM_BASE_URL")
    endpoints = _candidate_endpoints(base_url or env_base)
    headers = {
        "Authorization": f"Bearer {resolved_key}",
        "Content-Type": "application/json",
        "Accept-Language": "en-US,en",
    }

    last_error = "Unknown GLM error"
    with httpx.Client(timeout=timeout_seconds) as client:
        model_candidates = [model]
        if allow_model_fallback and model.startswith("glm-5"):
            model_candidates.extend(["glm-4.7", "glm-4.7-coding-preview"])
        # Preserve order while removing duplicates.
        model_candidates = list(dict.fromkeys(model_candidates))

        for endpoint in endpoints:
            url = f"{endpoint}/chat/completions"
            for chosen_model in model_candidates:
                payload = {
                    "model": chosen_model,
                    "messages": messages,
                    "stream": False,
                    # Prevent blank `content` when the model returns only reasoning.
                    "thinking": {"type": "disabled"},
                }
                response = client.post(url, json=payload, headers=headers)

                # Parse response body once (JSON if possible) for better diagnostics.
                try:
                    body = response.json()
                except Exception:
                    body = {}
                code, msg = _extract_error(body, response.text[:400])

                if response.status_code >= 400:
                    # 1113 on general endpoint often means the key is for coding plan;
                    # try the coding endpoint automatically when base_url isn't forced.
                    if (
                        response.status_code == 429
                        and code == "1113"
                        and endpoint == DEFAULT_GLM_BASE_URL
                        and not (base_url or env_base)
                    ):
                        last_error = f"{response.status_code} {msg}"
                        break

                    # 1311 means the model is not in the subscription plan.
                    if (
                        response.status_code == 429
                        and code == "1311"
                        and chosen_model != model_candidates[-1]
                    ):
                        last_error = f"{response.status_code} {msg}"
                        continue

                    last_error = f"{response.status_code} {msg}"
                    continue

                choices = body.get("choices") or []
                if not choices:
                    last_error = f"Success without choices at {url}"
                    continue
                message = choices[0].get("message") or {}
                content = message.get("content")
                if not isinstance(content, str):
                    content = ""
                if not content.strip():
                    reasoning = message.get("reasoning_content")
                    if isinstance(reasoning, str):
                        content = reasoning
                if not isinstance(content, str) or not content.strip():
                    last_error = f"Response missing textual content at {url}"
                    continue

                return {
                    "model_requested": model,
                    "model": body.get("model", chosen_model),
                    "content": content,
                    "base_url": endpoint,
                    "raw": body,
                }

    raise GLMClientError(f"GLM request failed after fallbacks: {last_error}")
