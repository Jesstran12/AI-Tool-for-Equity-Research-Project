"""F4.3 prompt files, lock and run record."""

import hashlib
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from orebody.llm.prompts import (
    LOCK_FILE,
    PROMPTS_DIR,
    check_lock,
    load_prompt,
    load_prompts,
    run_record,
    write_lock,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _write(d: Path, name: str, text: str) -> Path:
    p = d / f"{name}.md"
    p.write_text(text)
    return p


def test_load_prompt(tmp_path: Path) -> None:
    p = load_prompt(_write(tmp_path, "agent", "version: 2\n\n  You are an analyst.\n\n"))
    assert (p.name, p.version) == ("agent", "2")
    assert p.body == "You are an analyst.\n"  # stripped, one trailing newline
    assert p.sha256 == _sha("You are an analyst.\n")


@pytest.mark.parametrize(
    ("header", "version"), [("version: 1", "1"), ("version: 1.2", "1.2"), ("version:3", "3")]
)
def test_valid_versions(tmp_path: Path, header: str, version: str) -> None:
    assert load_prompt(_write(tmp_path, "a", f"{header}\nbody")).version == version


@pytest.mark.parametrize(
    "header", ["Version 1", "version: v1", "version: one", "version:", "body only"]
)
def test_bad_header_names_the_file(tmp_path: Path, header: str) -> None:
    with pytest.raises(ValueError, match=r"bad\.md"):
        load_prompt(_write(tmp_path, "bad", f"{header}\nbody"))


def test_load_prompts_reads_md_files_only(tmp_path: Path) -> None:
    _write(tmp_path, "a", "version: 1\nA")
    _write(tmp_path, "b", "version: 1\nB")
    (tmp_path / "versions.lock").write_text("{}")
    assert sorted(load_prompts(tmp_path)) == ["a", "b"]


# --- lock -------------------------------------------------------------------------------------


@pytest.fixture
def locked(tmp_path: Path) -> tuple[Path, Path]:
    _write(tmp_path, "a", "version: 1\nAlpha prompt")
    lock = tmp_path / "versions.lock"
    write_lock(load_prompts(tmp_path), lock)
    return tmp_path, lock


def test_write_then_check_is_clean(locked) -> None:
    d, lock = locked
    entry = yaml.safe_load(lock.read_text())["a"]
    assert entry == {"version": "1", "sha256": _sha("Alpha prompt\n")}
    assert check_lock(load_prompts(d), lock) == []


def test_text_changed_without_version_bump_is_reported(locked) -> None:
    d, lock = locked
    _write(d, "a", "version: 1\nAlpha prompt, edited")
    assert check_lock(load_prompts(d), lock) == [
        "a: text changed but version is still 1; bump the version, then run `orebody prompts lock`"
    ]


def test_version_bump_without_relock_is_reported(locked) -> None:
    d, lock = locked
    _write(d, "a", "version: 2\nAlpha prompt, edited")
    assert check_lock(load_prompts(d), lock) == [
        "a: version 2 is not in the lock (locked: 1); run `orebody prompts lock`"
    ]


def test_new_prompt_and_stale_entry_are_reported(locked) -> None:
    d, lock = locked
    _write(d, "b", "version: 1\nBeta")
    (d / "a.md").unlink()
    assert sorted(check_lock(load_prompts(d), lock)) == [
        "a: in the lock but no prompts/a.md",
        "b: not in the lock; run `orebody prompts lock`",
    ]


def test_run_record(locked) -> None:
    d, _ = locked
    assert run_record(load_prompts(d)) == {"a": {"version": "1", "sha256": _sha("Alpha prompt\n")}}


# --- the repo's own prompts ---------------------------------------------------------------------


def test_repo_prompts_match_their_lock() -> None:
    # Fails whenever a prompt in prompts/ is edited without bumping its version (ground rule 6)
    assert check_lock(load_prompts(PROMPTS_DIR), LOCK_FILE) == []


def test_financial_analyst_is_version_1() -> None:
    assert load_prompts(PROMPTS_DIR)["financial_analyst"].version == "1"


# --- CLI ----------------------------------------------------------------------------------------


def test_prompts_check_cli(locked) -> None:
    from orebody.cli import app

    d, lock = locked
    args = ["prompts", "check", "--dir", str(d), "--lock", str(lock)]
    ok = CliRunner().invoke(app, args)
    assert ok.exit_code == 0 and "1 prompt(s) match the lock" in ok.output
    _write(d, "a", "version: 1\nchanged")
    bad = CliRunner().invoke(app, args)
    assert bad.exit_code == 1 and "text changed but version is still 1" in bad.output


def test_prompts_lock_cli(tmp_path: Path) -> None:
    from orebody.cli import app

    _write(tmp_path, "a", "version: 3\nGamma")
    lock = tmp_path / "versions.lock"
    r = CliRunner().invoke(app, ["prompts", "lock", "--dir", str(tmp_path), "--lock", str(lock)])
    assert r.exit_code == 0 and "locked 1 prompt(s)" in r.output
    assert yaml.safe_load(lock.read_text())["a"]["version"] == "3"
