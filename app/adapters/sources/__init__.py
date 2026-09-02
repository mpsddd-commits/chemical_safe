"""Source adapter registry.

The orchestrator asks for an adapter by `source_id` and never learns which class
answers (DD-2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.adapters.sources.api_sources import (
    IncidentDataAdapter,
    LawApiAdapter,
    SubstanceApiAdapter,
)
from app.adapters.sources.msds_pdf import MsdsPdfAdapter
from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError
from app.ports.source import SourceAdapter

_ADAPTERS = {
    "ncis_substance": SubstanceApiAdapter,
    "law_api": LawApiAdapter,
    "incident_data": IncidentDataAdapter,
    "msds_pdf": MsdsPdfAdapter,
}

DEFAULT_CONFIG_PATH = Path("config/sources.yaml")


def load_source_specs(path: Path | None = None) -> list[dict[str, Any]]:
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise ConfigurationError(f"source config not found: {config_path}")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    specs = data.get("sources", [])
    if not isinstance(specs, list) or not specs:
        raise ConfigurationError(f"no sources declared in {config_path}")
    return specs


def build_adapter(spec: dict[str, Any], settings: Settings | None = None) -> SourceAdapter:
    source_id = spec.get("source_id")
    adapter_cls = _ADAPTERS.get(str(source_id))
    if adapter_cls is None:
        raise ConfigurationError(f"no adapter registered for source_id={source_id!r}")
    return adapter_cls(settings or get_settings(), spec)  # type: ignore[return-value]


def build_all(
    path: Path | None = None, settings: Settings | None = None
) -> dict[str, SourceAdapter]:
    return {
        str(spec["source_id"]): build_adapter(spec, settings)
        for spec in load_source_specs(path)
    }


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "IncidentDataAdapter",
    "LawApiAdapter",
    "MsdsPdfAdapter",
    "SubstanceApiAdapter",
    "build_adapter",
    "build_all",
    "load_source_specs",
]
