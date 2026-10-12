"""Select the LLM by `LLM_PROVIDER`: scripted (default, offline) | anthropic | openai | ollama."""

from __future__ import annotations

import os

from agent.llm.base import LLM
from agent.llm.scripted import Plan, ScriptedLLM

PROVIDERS = ("scripted", "anthropic", "openai", "ollama")


def make_llm(plan: Plan, provider: str | None = None) -> LLM:
    name = (provider or os.getenv("LLM_PROVIDER", "scripted")).lower()
    if name == "scripted":
        return ScriptedLLM(plan)
    if name == "anthropic":
        from agent.llm.providers import AnthropicLLM

        return AnthropicLLM()
    if name == "openai":
        from agent.llm.providers import make_openai

        return make_openai()
    if name == "ollama":
        from agent.llm.providers import make_ollama

        return make_ollama()
    raise ValueError(f"unknown LLM_PROVIDER {name!r}; expected one of {PROVIDERS}")
