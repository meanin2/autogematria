"""Tests for GLM client helpers."""

import pytest

from autogematria.tools.glm_client import GLMClientError, chat_completion


def test_glm_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    with pytest.raises(GLMClientError):
        chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="glm-5",
            api_key=None,
        )
