"""Demo service layer: scripted replay and live Nemotron runs of the repo verifier.

Everything the HTTP layer needs lives here as plain functions so it can be tested
without a web framework.

Security model for a publicly hosted demo:
    * the API NEVER accepts a patch or a target from the client. Patches come only
      from the stored scenarios in ``demo_agents`` (so no one can make the server
      execute their code), and the target must be an allowlisted name;
    * a live run may carry custom *report text* (it is only ever text shown to
      Nemotron and compared against evidence), capped in length;
    * live runs are rate limited and concurrency limited to protect credits.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque

from backend import sandbox
from backend.claim_extractor import extract_claims_llm
from backend.demo_agents import (
    SCENARIO_KINDS,
    TARGET_INFO,
    build_scenario,
    scripted_extractor,
)
from backend.repo_verifier import verify_agent_report

MAX_REPORT_CHARS = 4000
MODES = ("replay", "live")
_ACQUIRE_TIMEOUT_S = 20

SCENARIO_LABELS = {
    "honest": "Honest agent",
    "overclaim": "Overclaiming agent",
    "tamper": "Test-tampering agent",
    "deploy": "Deploy-claiming agent",
}


class LiveUnavailable(RuntimeError):
    """Live mode needs NEBIUS_API_KEY and NEBIUS_MODEL."""


class RateLimited(RuntimeError):
    pass


class Busy(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

class SlidingWindowLimiter:
    def __init__(self, limit: int, window_s: float, clock=time.monotonic):
        self.limit, self.window_s, self.clock = limit, window_s, clock
        self._hits: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = self.clock()
        with self._lock:
            while self._hits and now - self._hits[0] >= self.window_s:
                self._hits.popleft()
            if len(self._hits) >= self.limit:
                return False
            self._hits.append(now)
            return True


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default)))
    except ValueError:
        return default


_live_limiter = SlidingWindowLimiter(_int_env("VERDIKT_LIVE_LIMIT_PER_HOUR", 30), 3600)
_run_slots = threading.BoundedSemaphore(_int_env("VERDIKT_MAX_CONCURRENT_RUNS", 2))


def reset_limits_for_tests(live_limit: int = 30, slots: int = 2) -> None:
    global _live_limiter, _run_slots
    _live_limiter = SlidingWindowLimiter(live_limit, 3600)
    _run_slots = threading.BoundedSemaphore(slots)


def allow_model_call() -> bool:
    """Spend one unit of the hourly model-call budget (Live mode and the legacy /verify route)."""
    return _live_limiter.allow()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def live_available() -> bool:
    from dotenv import load_dotenv

    load_dotenv()
    return bool(os.getenv("NEBIUS_API_KEY") and os.getenv("NEBIUS_MODEL"))


def live_model() -> str | None:
    from dotenv import load_dotenv

    load_dotenv()
    return os.getenv("NEBIUS_MODEL") or None


def describe() -> dict:
    """Everything the UI needs to render its pickers (targets, scenarios, defaults)."""
    available = set(sandbox.list_targets())
    targets = []
    for name, (title, src, _test) in TARGET_INFO.items():
        if name not in available:
            continue
        scenarios = []
        for kind in SCENARIO_KINDS:
            s = build_scenario(name, kind)
            scenarios.append({"kind": kind, "label": SCENARIO_LABELS[kind], "report": s["report"]})
        targets.append({"name": name, "title": title, "source_file": src, "scenarios": scenarios})
    return {
        "targets": targets,
        "live_available": live_available(),
        "live_model": live_model() if live_available() else None,
        "max_report_chars": MAX_REPORT_CHARS,
    }


def run_demo(target: str, scenario: str, mode: str = "replay", report: str | None = None) -> dict:
    """Verify one stored agent scenario. Raises sandbox.SandboxError / ValueError for bad input."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if scenario not in SCENARIO_KINDS:
        raise sandbox.SandboxError(f"Unknown scenario: {scenario!r}")
    if target not in TARGET_INFO:
        raise sandbox.SandboxError(f"Unknown target: {target!r}")
    if report is not None and (not isinstance(report, str) or len(report) > MAX_REPORT_CHARS):
        raise ValueError(f"report must be a string of at most {MAX_REPORT_CHARS} characters")

    s = build_scenario(target, scenario)

    if mode == "live":
        if not live_available():
            raise LiveUnavailable("Live mode needs NEBIUS_API_KEY and NEBIUS_MODEL on the server.")
        if not _live_limiter.allow():
            raise RateLimited("Live run limit reached. Try replay mode or wait a while.")
        report_text = report.strip() if report and report.strip() else s["report"]
        extractor = extract_claims_llm
    else:
        report_text = s["report"]  # scripted claims are tied to this exact text
        extractor = scripted_extractor(s["claims"])

    if not _run_slots.acquire(timeout=_ACQUIRE_TIMEOUT_S):
        raise Busy("The verifier is busy. Please retry in a moment.")
    try:
        started = time.monotonic()
        result = verify_agent_report(target, report_text, s["patch"], extract=extractor)
    finally:
        _run_slots.release()

    result.update(
        mode=mode,
        scenario=scenario,
        scenario_label=SCENARIO_LABELS[scenario],
        model=live_model() if mode == "live" else None,
        elapsed_s=round(time.monotonic() - started, 2),
        patch_files=sorted(s["patch"]),
    )
    return result
