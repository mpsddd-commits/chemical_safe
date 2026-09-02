"""N4 PromptRepository - BR-93, NFR-22, CP-2.

Prompts are files, not string literals, for two reasons. They change on a
different rhythm than code and want a different kind of review; and the version
must be recordable, because `llm_call.prompt_version` is what lets u4 line a
quality regression up against a prompt change.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.errors import ConfigurationError

_ROOT = Path(__file__).resolve().parents[2] / "prompts"


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    text: str


class PromptRepository:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or _ROOT

    def _index(self) -> dict[str, str]:
        index_path = self._root / "index.yaml"
        if not index_path.exists():
            raise ConfigurationError(f"prompt index missing: {index_path}")
        data = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
        return {str(k): str(v) for k, v in data.items()}

    def get(self, name: str) -> Prompt:
        version = self._index().get(name)
        if not version:
            raise ConfigurationError(f"no active version for prompt {name!r}")
        path = self._root / name / f"{version}.md"
        if not path.exists():
            # The index and the files disagreeing is a deployment error, not a
            # runtime condition to paper over: silently falling back to another
            # version would make `prompt_version` a lie.
            raise ConfigurationError(f"prompt file missing: {path}")
        return Prompt(name=name, version=version, text=path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def shared_repository() -> PromptRepository:
    return PromptRepository()
