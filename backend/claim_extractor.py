"""Turn a coding agent's free-text report into atomic, checkable claims.

Nemotron decides WHICH claims the agent made and WHICH allowlisted check can
test each one. It never decides whether a claim is true: that comes only from
executed evidence (see repo_verifier). Its output is validated strictly:

* every claim must carry a ``quote`` that appears verbatim in the report, so the
  model cannot invent claims the agent never made;
* ``check`` must be one of the allowlisted check ids;
* ``arg`` is only accepted where the check takes one, and is validated by the
  caller against values Verdikt itself computed (real test ids, real changed files).
"""
from __future__ import annotations

import json
import re
from typing import Callable

from backend import llm

SYSTEM_PROMPT = """You extract verifiable claims from a coding agent's final report.

Return ONLY a JSON object: {"claims": [{"quote": "...", "text": "...", "check": "...", "arg": null}]}

Rules:
1. "quote" must be copied VERBATIM from the report (an exact substring). Never invent claims.
2. One claim per distinct verifiable assertion. Skip opinions and vague statements.
3. "text" restates the claim in one short sentence.
4. "check" must be exactly one of:
   - "tests_pass": the agent says the tests/suite pass now, or that the bug/feature works. arg = null.
   - "bug_was_real": the agent says the tests/bug failed or was reproduced BEFORE the fix. arg = null.
   - "targeted_test": the agent says one specific test passes. arg = one id from AVAILABLE_TESTS.
   - "files_changed": the agent says it changed/added/rewrote a specific source file. arg = that file's relative path.
   - "deployment_status": the agent says it deployed, released, shipped or published anything. arg = null.
5. If a claim fits none of these, leave it out. Do not guess.
6. Output JSON only. No markdown fences, no commentary."""

Extractor = Callable[[str, dict], list]


def build_user_prompt(report_text: str, context: dict) -> str:
    tests = "\n".join(f"- {t}" for t in context.get("test_ids", [])) or "- (none)"
    return (
        f"AVAILABLE_TESTS:\n{tests}\n\n"
        f"AGENT REPORT:\n<<<\n{report_text}\n>>>"
    )


def parse_claims_json(raw: str) -> list:
    """Parse the model's JSON, tolerating code fences and leading/trailing prose."""
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("Model did not return a JSON object")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned invalid JSON: {exc}") from exc
    claims = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(claims, list):
        raise ValueError("JSON object has no 'claims' list")
    return claims


def extract_claims_llm(report_text: str, context: dict, chat=None) -> list:
    """Default extractor: Nemotron on Nebius Token Factory."""
    chat = chat or llm.chat
    raw = chat(SYSTEM_PROMPT, build_user_prompt(report_text, context))
    return parse_claims_json(raw)
