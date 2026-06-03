"""Load workflow configuration from YAML, JSON, or TOML."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from magnific.models import WorkflowConfig

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


def _load_raw(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    elif suffix == ".json":
        data = json.loads(text)
    elif suffix == ".toml":
        if tomllib is None:
            raise ValueError("TOML support requires Python 3.11+")
        data = tomllib.loads(text)
    else:
        raise ValueError(f"Unsupported config format: {suffix}")
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")
    return data


def load_prompt_template(path: str | Path, base_dir: Path | None = None) -> str:
    """Resolve prompt template path relative to config file directory or cwd."""
    p = Path(path)
    if not p.is_absolute():
        if base_dir is not None:
            candidate = base_dir / p
            if candidate.exists():
                p = candidate
            else:
                p = Path.cwd() / p
        else:
            p = Path.cwd() / p
    return p.read_text(encoding="utf-8").strip()


def load_workflow_config(path: str | Path) -> WorkflowConfig:
    """Parse and validate workflow configuration from disk."""
    config_path = Path(path).resolve()
    raw = _load_raw(config_path)
    return WorkflowConfig.model_validate(raw)


def save_workflow_config(config: WorkflowConfig, path: str | Path) -> Path:
    """Serialize workflow config to YAML."""
    out = Path(path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump(mode="json")
    out.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return out
