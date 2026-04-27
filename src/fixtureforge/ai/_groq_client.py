"""
Lightweight Groq REST client for FixtureForge AI features.

Uses only `requests` (already a core dependency) — no extra pip install needed.
Model: llama3-8b-8192 (fast, free tier, sufficient for analysis tasks).

Usage:
    from fixtureforge.ai._groq_client import groq_complete, LLMClientError
    response = groq_complete(system="You are...", user="Analyze this...")
"""
from __future__ import annotations

import json
import os
import time
from typing import Optional

import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama3-8b-8192"
DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 2


class LLMClientError(RuntimeError):
    """Raised when the Groq API call fails after all retries."""


def groq_complete(
    system: str,
    user: str,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    api_key: Optional[str] = None,
) -> str:
    """
    Send a chat completion request to Groq and return the response text.

    Args:
        system:  System prompt (role definition / instructions).
        user:    User message (the actual task / input).
        model:   Groq model identifier. Default: llama3-8b-8192.
        timeout: Request timeout in seconds.
        retries: Number of retry attempts on transient errors.
        api_key: Override GROQ_API_KEY env var (optional).

    Returns:
        The model's response as a plain string.

    Raises:
        LLMClientError: If GROQ_API_KEY is not set or all retries fail.
    """
    key = api_key or os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise LLMClientError(
            "GROQ_API_KEY is not set. "
            "Export it with: export GROQ_API_KEY=gsk_... "
            "or set it in your .env file."
        )

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 512,
    }

    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                GROQ_API_URL,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.Timeout as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
        except requests.exceptions.HTTPError as exc:
            # 429 rate limit — back off and retry
            if resp.status_code == 429 and attempt < retries:
                time.sleep(2.0 * (attempt + 1))
                last_error = exc
            else:
                raise LLMClientError(
                    f"Groq API returned HTTP {resp.status_code}: {resp.text[:200]}"
                ) from exc
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise LLMClientError(
                f"Unexpected Groq response format: {exc}"
            ) from exc

    raise LLMClientError(
        f"Groq request failed after {retries + 1} attempts: {last_error}"
    )
