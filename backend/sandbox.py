"""Sandboxed test execution for Verdikt.

Verdikt never executes anything a model wrote or described. This module runs
ONE fixed command (``python -m pytest``) inside a throw-away copy of an
allowlisted target repo under ``backend/targets``. The only thing an agent's
report can influence is the *content of source files* inside that copy:

* targets are referenced by name and must exist in the allowlisted directory;
* patch paths must be relative ``.py`` files without ``..`` components;
* anything under ``tests/`` (or a ``conftest.py``) is protected: such edits are
  ignored and reported, because an agent that edits the tests to make them pass
  has not fixed anything;
* the child process gets a scrubbed environment, a hard timeout, and is killed
  as a process group on timeout.

Evidence semantics (``passed``):
    True  - the tests ran and all passed (pytest exit code 0)
    False - the tests ran and at least one failed (exit code 1)
    None  - inconclusive (timeout, collection error, no tests, infra error)
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

TARGETS_DIR = Path(__file__).resolve().parent / "targets"
TARGET_SOLUTIONS_DIR = Path(__file__).resolve().parent / "target_solutions"

DEFAULT_TIMEOUT_S = 30
MAX_PATCH_FILES = 20
MAX_PATCH_FILE_BYTES = 200_000
OUTPUT_TAIL_CHARS = 4000

_TARGET_NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
_NODE_ID = re.compile(r"^[A-Za-z0-9_./:\[\]\-]+$")
_ALLOWED_ENV = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "SYSTEMROOT", "TMP", "TEMP")
_IGNORED_DIRS = {"__pycache__", ".pytest_cache", ".git"}


class SandboxError(ValueError):
    """Raised for invalid targets, selectors or patches (never for test failures)."""


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

def list_targets() -> list[str]:
    if not TARGETS_DIR.is_dir():
        return []
    return sorted(
        p.name for p in TARGETS_DIR.iterdir()
        if p.is_dir() and _TARGET_NAME.match(p.name)
    )


def target_path(name: str) -> Path:
    if not isinstance(name, str) or not _TARGET_NAME.match(name):
        raise SandboxError(f"Invalid target name: {name!r}")
    path = TARGETS_DIR / name
    if not path.is_dir():
        raise SandboxError(f"Unknown target: {name}")
    return path


def _is_protected(rel: PurePosixPath) -> bool:
    return (
        "tests" in rel.parts
        or rel.name == "conftest.py"
        or rel.name.startswith("test_")
        or rel.name.endswith("_test.py")
    )


def split_patch(files: dict | None) -> tuple[dict[str, bytes], list[str]]:
    """Validate an agent patch ({relative_path: new_content}).

    Returns ``(applicable, ignored_protected_paths)``. Raises SandboxError for
    structurally invalid patches (absolute paths, traversal, non-.py, too big).
    """
    if not files:
        return {}, []
    if not isinstance(files, dict):
        raise SandboxError("Patch must be a mapping of path -> content")
    if len(files) > MAX_PATCH_FILES:
        raise SandboxError(f"Patch touches more than {MAX_PATCH_FILES} files")

    applicable: dict[str, bytes] = {}
    ignored: list[str] = []
    for raw_path, content in files.items():
        if not isinstance(raw_path, str) or not isinstance(content, str):
            raise SandboxError("Patch paths and contents must be strings")
        if "\\" in raw_path or raw_path.startswith("/") or re.match(r"^[A-Za-z]:", raw_path):
            raise SandboxError(f"Patch path must be relative POSIX: {raw_path!r}")
        rel = PurePosixPath(raw_path)
        if not rel.parts or any(p in ("..", "") or p.startswith(".") for p in rel.parts):
            raise SandboxError(f"Unsafe patch path: {raw_path!r}")
        if rel.suffix != ".py":
            raise SandboxError(f"Only .py files may be patched: {raw_path!r}")
        data = content.encode("utf-8")
        if len(data) > MAX_PATCH_FILE_BYTES:
            raise SandboxError(f"Patch file too large: {raw_path!r}")
        if _is_protected(rel):
            ignored.append(str(rel))
        else:
            applicable[str(rel)] = data
    return applicable, sorted(ignored)


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

def _copy_target(name: str, dest: Path) -> None:
    shutil.copytree(
        target_path(name),
        dest,
        ignore=shutil.ignore_patterns(*_IGNORED_DIRS, "*.pyc"),
    )
    # Pin pytest's rootdir to the workspace regardless of the host's config.
    (dest / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        if any(part in _IGNORED_DIRS for part in rel.parts):
            continue
        digest.update(str(rel.as_posix()).encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def changed_paths(name: str, applicable: dict[str, bytes]) -> list[str]:
    """Paths in the patch whose content differs from the pristine target."""
    base = target_path(name)
    changed = []
    for rel, data in applicable.items():
        original = base / rel
        if not original.is_file() or _normalize_newlines(original.read_bytes()) != _normalize_newlines(data):
            changed.append(rel)
    return sorted(changed)


def _normalize_newlines(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _scrubbed_env(workspace: Path) -> dict:
    env = {k: os.environ[k] for k in _ALLOWED_ENV if k in os.environ}
    env.update(
        {
            "PYTHONPATH": str(workspace),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "HOME": str(workspace),
            "USERPROFILE": str(workspace),
        }
    )
    return env


def _run(cmd: list[str], cwd: Path, env: dict, timeout: float):
    popen_kwargs = {"start_new_session": True} if os.name == "posix" else {}
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **popen_kwargs,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out or "", err or "", False
    except subprocess.TimeoutExpired:
        if hasattr(os, "killpg"):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:  # Windows
            proc.kill()
        out, err = proc.communicate()
        return None, out or "", err or "", True


def _tail(text: str) -> str:
    return text if len(text) <= OUTPUT_TAIL_CHARS else "…" + text[-OUTPUT_TAIL_CHARS:]


def _count(pattern: str, text: str) -> int:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else 0


def run_pytest(
    target: str,
    patch: dict | None = None,
    node_ids: list[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> dict:
    """Run a target's test suite (optionally on a patched copy) and return evidence.

    ``node_ids`` restricts the run to specific pytest node ids; each must match a
    conservative character set and not look like an option.
    """
    applicable, ignored = split_patch(patch)
    selectors = list(node_ids or [])
    for node in selectors:
        if not isinstance(node, str) or node.startswith("-") or not _NODE_ID.match(node):
            raise SandboxError(f"Invalid test selector: {node!r}")

    started = time.monotonic()
    tmp = Path(tempfile.mkdtemp(prefix="verdikt_"))
    try:
        workspace = tmp / "ws"
        _copy_target(target, workspace)
        for rel, data in applicable.items():
            dest = workspace / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        tree_sha = _tree_hash(workspace)

        cmd = [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", *selectors]
        code, out, err, timed_out = _run(cmd, workspace, _scrubbed_env(workspace), timeout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if timed_out:
        passed, status = None, "timeout"
    elif code == 0:
        passed, status = True, "executed"
    elif code == 1:
        passed, status = False, "executed"
    elif code == 2:
        passed, status = None, "collection_error"
    elif code == 5:
        passed, status = None, "no_tests_collected"
    else:
        passed, status = None, "infrastructure_error"

    return {
        "passed": passed,
        "status": status,
        "exit_code": code,
        "tests_ran": status == "executed",
        "n_passed": _count(r"(\d+) passed", out),
        "n_failed": _count(r"(\d+) failed", out),
        "n_errors": _count(r"(\d+) errors?\b", out),
        "stdout": _tail(out),
        "stderr": _tail(err),
        "evidence_source": "pytest-sandbox",
        "tree_sha256": tree_sha,
        "ignored_protected_paths": ignored,
        "duration_s": round(time.monotonic() - started, 3),
    }


def collect_test_ids(target: str, timeout: float = DEFAULT_TIMEOUT_S) -> list[str]:
    """List the pristine target's pytest node ids (used as a selector allowlist)."""
    tmp = Path(tempfile.mkdtemp(prefix="verdikt_"))
    try:
        workspace = tmp / "ws"
        _copy_target(target, workspace)
        cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header", "-p", "no:cacheprovider"]
        code, out, _err, timed_out = _run(cmd, workspace, _scrubbed_env(workspace), timeout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if timed_out or code not in (0,):
        return []
    return sorted({line.strip() for line in out.splitlines() if "::" in line and _NODE_ID.match(line.strip())})
