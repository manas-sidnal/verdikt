import os
import tempfile
from pathlib import Path

import pytest

from backend import sandbox
from backend.demo_agents import load_solution


def _verdikt_tmpdirs():
    return {p.name for p in Path(tempfile.gettempdir()).glob("verdikt_*")}


def test_lists_all_sample_targets():
    assert {"slugify_fix", "cart_total", "rate_limit"} <= set(sandbox.list_targets())


@pytest.mark.parametrize("name", ["../etc", "Slugify", "a b", "", "x" * 60, "slugify_fix/..", None, 5])
def test_invalid_target_names_rejected(name):
    with pytest.raises(sandbox.SandboxError):
        sandbox.target_path(name)


def test_unknown_target_rejected():
    with pytest.raises(sandbox.SandboxError):
        sandbox.run_pytest("does_not_exist")


@pytest.mark.parametrize("target", ["slugify_fix", "cart_total", "rate_limit"])
def test_pristine_target_fails_and_good_fix_passes(target):
    base = sandbox.run_pytest(target)
    assert base["passed"] is False and base["status"] == "executed"
    assert base["n_failed"] >= 1 and base["tests_ran"] is True

    good = sandbox.run_pytest(target, patch=load_solution(target, "good"))
    assert good["passed"] is True and good["n_failed"] == 0 and good["exit_code"] == 0

    partial = sandbox.run_pytest(target, patch=load_solution(target, "partial"))
    assert partial["passed"] is False and partial["n_failed"] >= 1


@pytest.mark.parametrize(
    "path",
    ["/etc/passwd", "../evil.py", "a/../../evil.py", "C:/evil.py", "a\\b.py", ".hidden.py", "pkg/.x/y.py", "notes.txt", "mod.sh", ""],
)
def test_unsafe_patch_paths_rejected(path):
    with pytest.raises(sandbox.SandboxError):
        sandbox.split_patch({path: "x = 1\n"})


def test_patch_structure_limits():
    with pytest.raises(sandbox.SandboxError):
        sandbox.split_patch({f"m{i}.py": "" for i in range(sandbox.MAX_PATCH_FILES + 1)})
    with pytest.raises(sandbox.SandboxError):
        sandbox.split_patch({"big.py": "x" * (sandbox.MAX_PATCH_FILE_BYTES + 1)})
    with pytest.raises(sandbox.SandboxError):
        sandbox.split_patch({"a.py": 5})
    with pytest.raises(sandbox.SandboxError):
        sandbox.split_patch(["not", "a", "dict"])
    assert sandbox.split_patch(None) == ({}, [])


def test_protected_test_files_are_ignored_and_reported():
    patch = dict(load_solution("slugify_fix", "partial"))
    patch["tests/test_textutils.py"] = "def test_x():\n    assert True\n"
    patch["conftest.py"] = "import sys\n"
    applicable, ignored = sandbox.split_patch(patch)
    assert set(applicable) == {"textutils.py"}
    assert ignored == ["conftest.py", "tests/test_textutils.py"]

    # Tampering has no effect on the result: the pristine tests still run and still fail.
    run = sandbox.run_pytest("slugify_fix", patch=patch)
    assert run["passed"] is False
    assert run["ignored_protected_paths"] == ["conftest.py", "tests/test_textutils.py"]


@pytest.mark.parametrize("bad", ["-x", "--co", "a b", "x;rm -rf /", "$(id)", "a|b", "", 5])
def test_invalid_test_selectors_rejected(bad):
    with pytest.raises(sandbox.SandboxError):
        sandbox.run_pytest("slugify_fix", node_ids=[bad])


def test_selector_runs_only_that_test():
    run = sandbox.run_pytest(
        "slugify_fix",
        patch=load_solution("slugify_fix", "partial"),
        node_ids=["tests/test_textutils.py::test_punctuation_removed"],
    )
    assert run["passed"] is True and run["n_passed"] == 1


def test_hanging_code_times_out_and_is_inconclusive_not_contradicted():
    patch = {"textutils.py": "while True:\n    pass\n"}
    run = sandbox.run_pytest("slugify_fix", patch=patch, timeout=2)
    assert run["status"] == "timeout"
    assert run["passed"] is None


def test_syntax_error_in_patch_is_a_collection_error_at_sandbox_level():
    run = sandbox.run_pytest("slugify_fix", patch={"textutils.py": "def slugify(:\n"})
    assert run["status"] == "collection_error"
    assert run["passed"] is None


def test_environment_is_scrubbed(monkeypatch):
    monkeypatch.setenv("VERDIKT_SECRET", "hunter2")
    leaky = (
        "import os\n"
        "assert 'VERDIKT_SECRET' not in os.environ, 'secret leaked into sandbox'\n"
        "def slugify(text):\n    return text\n"
    )
    run = sandbox.run_pytest("slugify_fix", patch={"textutils.py": leaky})
    # If the secret leaked, the import assertion would fail collection (status collection_error).
    assert run["status"] == "executed"


def test_tree_hash_is_deterministic_and_patch_sensitive():
    a = sandbox.run_pytest("cart_total")
    b = sandbox.run_pytest("cart_total")
    c = sandbox.run_pytest("cart_total", patch=load_solution("cart_total", "good"))
    assert a["tree_sha256"] == b["tree_sha256"]
    assert a["tree_sha256"] != c["tree_sha256"]


def test_no_temp_dirs_or_bytecode_leak():
    before = _verdikt_tmpdirs()
    sandbox.run_pytest("rate_limit")
    sandbox.collect_test_ids("rate_limit")
    assert _verdikt_tmpdirs() == before
    leftovers = [p for p in sandbox.TARGETS_DIR.rglob("*") if p.name in ("__pycache__", ".pytest_cache")]
    assert leftovers == []


def test_collect_test_ids():
    ids = sandbox.collect_test_ids("rate_limit")
    assert "tests/test_limiter.py::test_blocks_over_limit" in ids
    assert len(ids) == 5


def test_changed_paths_compares_to_pristine():
    applicable, _ = sandbox.split_patch(load_solution("cart_total", "good"))
    assert sandbox.changed_paths("cart_total", applicable) == ["cart.py"]
    same = {"cart.py": (sandbox.TARGETS_DIR / "cart_total" / "cart.py").read_bytes()}
    assert sandbox.changed_paths("cart_total", same) == []
    assert sandbox.changed_paths("cart_total", {"brand_new.py": b"x=1\n"}) == ["brand_new.py"]
