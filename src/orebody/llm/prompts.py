"""F4.3 prompt files: one `prompts/<name>.md` per agent, first line `version: N` (or `N.M`).

A run records each prompt's name, version and text sha256 (SPEC §5.5). `prompts/versions.lock`
pins version + sha256 per prompt; `check_lock` reports any prompt whose text changed while its
version did not (ground rule 6), any prompt missing from the lock, and any lock entry without a
prompt. `write_lock` rewrites the lock from the current files after a deliberate version bump.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml
from pydantic import BaseModel

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
LOCK_FILE = PROMPTS_DIR / "versions.lock"
_HEADER = re.compile(r"version:\s*(\d+(?:\.\d+)?)\s*")
_LOCK_HEADER = """\
# F4.3 prompt lock (ground rule 6): each prompt's version and the sha256 of its text (the file
# after the "version:" line, stripped, plus one newline). Edit a prompt -> bump its version ->
# run `orebody prompts lock`. `orebody prompts check` and the test suite fail if a prompt's text
# changed while its version did not.
"""


class Prompt(BaseModel):
    name: str  # file stem, e.g. "financial_analyst"
    version: str
    body: str  # text after the version line, stripped, plus one newline (what the model sees)
    sha256: str  # of body


def load_prompt(path: Path) -> Prompt:
    """Parse one prompt file. ValueError naming the file when the first line is not
    'version: N' or 'version: N.M'."""
    path = Path(path)
    first, _, rest = path.read_text().partition("\n")
    m = _HEADER.fullmatch(first.strip())
    if not m:
        raise ValueError(f"{path.name}: first line must be 'version: N', got {first!r}")
    body = rest.strip() + "\n"
    return Prompt(
        name=path.stem,
        version=m.group(1),
        body=body,
        sha256=hashlib.sha256(body.encode()).hexdigest(),
    )


def load_prompts(prompts_dir: Path = PROMPTS_DIR) -> dict[str, Prompt]:
    """Every *.md in the directory, by name."""
    return {p.stem: load_prompt(p) for p in sorted(Path(prompts_dir).glob("*.md"))}


def check_lock(prompts: dict[str, Prompt], lock_path: Path = LOCK_FILE) -> list[str]:
    """Problems as sentences; empty list when every prompt matches its lock entry."""
    lock_path = Path(lock_path)
    lock = (yaml.safe_load(lock_path.read_text()) or {}) if lock_path.exists() else {}
    problems: list[str] = []
    for name, p in sorted(prompts.items()):
        entry = lock.get(name)
        if entry is None:
            problems.append(f"{name}: not in the lock; run `orebody prompts lock`")
        elif str(entry.get("version")) != p.version:
            problems.append(
                f"{name}: version {p.version} is not in the lock "
                f"(locked: {entry.get('version')}); run `orebody prompts lock`"
            )
        elif entry.get("sha256") != p.sha256:
            problems.append(
                f"{name}: text changed but version is still {p.version}; "
                "bump the version, then run `orebody prompts lock`"
            )
    for name in sorted(set(lock) - set(prompts)):
        problems.append(f"{name}: in the lock but no prompts/{name}.md")
    return problems


def write_lock(prompts: dict[str, Prompt], lock_path: Path = LOCK_FILE) -> None:
    entries = "".join(
        f'{name}:\n  version: "{p.version}"\n  sha256: "{p.sha256}"\n'
        for name, p in sorted(prompts.items())
    )
    Path(lock_path).write_text(_LOCK_HEADER + entries)


def run_record(prompts: dict[str, Prompt]) -> dict[str, dict[str, str]]:
    """{name: {"version": ..., "sha256": ...}} for the runs.prompt_versions column."""
    return {name: {"version": p.version, "sha256": p.sha256} for name, p in sorted(prompts.items())}
