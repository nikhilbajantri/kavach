"""Runtime configuration read from the environment.

Kept dependency-free (no pydantic-settings) so every module, including the
mocks and the benchmark runner, can import it cheaply.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """All tunables in one place. Secrets come from env only, never from code."""

    enabled: bool = field(default_factory=lambda: _bool(os.getenv("KAVACH_ENABLED"), True))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("KAVACH_DATA_DIR", "./data")))
    agent_id: str = field(default_factory=lambda: os.getenv("KAVACH_AGENT_ID", "support-bot-1"))
    operator: str = field(default_factory=lambda: os.getenv("KAVACH_OPERATOR", "operator@ourbank.in"))
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "scripted"))
    token_ttl_seconds: int = 60
    org_domains: tuple[str, ...] = ("ourbank.in", "support.ourbank.in")


settings = Settings()
