"""Thin Nebius Token Factory chat helper (OpenAI-compatible endpoint).

The OpenAI SDK is imported lazily so modules that only need the sandbox or the
scripted replay path can be imported and tested without it.
"""
from __future__ import annotations

import os
import re

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

# Reasoning models may wrap chain-of-thought in <think>…</think>; never parse it.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    text = _THINK_BLOCK.sub("", text or "")
    # An unterminated <think> (truncated output) means there is no usable answer after it.
    if re.search(r"<think>", text, re.IGNORECASE):
        text = re.split(r"<think>", text, flags=re.IGNORECASE)[0]
    return text.strip()


def chat(system: str, user: str, model: str | None = None, max_tokens: int = 6000) -> str:
    """Single chat completion on Token Factory. Returns the answer text."""
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()
    model = model or os.getenv("NEBIUS_MODEL")
    if not model:
        raise ValueError("NEBIUS_MODEL is missing from your .env file")
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise ValueError("NEBIUS_API_KEY is missing from your .env file")

    client = OpenAI(
        base_url=os.getenv("NEBIUS_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key,
        timeout=90.0,
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
        max_tokens=max_tokens,
    )
    content = strip_reasoning(response.choices[0].message.content or "")
    if not content:
        raise ValueError("Model returned an empty response")
    return content
