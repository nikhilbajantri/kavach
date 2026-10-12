"""Live tool-calling LLMs behind the same `LLM` interface as ScriptedLLM.

Each adapter keeps its *own* provider-native transcript and appends to it
turn by turn rather than rebuilding it from the generic history. That matters
for Claude: thinking blocks must be passed back exactly as returned, and
editing earlier turns invalidates them.

Prompt injection may or may not succeed against a live model. KAVACH must hold
either way, so nothing here tries to make the model safer.
"""

from __future__ import annotations

import json
import os
from typing import Any

from agent.llm.base import AssistantTurn, Message, ToolCall

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"


def wire_name(name: str) -> str:
    """Provider tool names allow only [a-zA-Z0-9_-]; ours are dotted (`email.send`)."""
    return name.replace(".", "__")


def unwire_name(name: str) -> str:
    return name.replace("__", ".")


def _new_tool_messages(history: list[Message]) -> list[Message]:
    """Tool results appended since the last assistant turn."""
    out: list[Message] = []
    for msg in reversed(history):
        if msg.role == "assistant":
            break
        if msg.role == "tool":
            out.append(msg)
    return list(reversed(out))


def _is_error(content: str) -> bool:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and "error" in payload


class AnthropicLLM:
    """Claude via the Anthropic SDK (manual tool-use loop; the agent loop drives turns)."""

    def __init__(self, model: str | None = None, effort: str = "medium", client: Any = None) -> None:
        if client is None:
            import anthropic  # optional dependency: pip install -e ".[llm]"

            client = anthropic.AsyncAnthropic()
        self.client = client
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
        self.effort = effort
        self.mode = f"anthropic:{self.model}"
        self._system = ""
        self._messages: list[dict[str, Any]] = []

    def _sync(self, history: list[Message]) -> None:
        if not self._messages:
            self._system = next((m.content for m in history if m.role == "system"), "")
            first_user = next(m.content for m in history if m.role == "user")
            self._messages.append({"role": "user", "content": first_user})
            return
        results = [
            {
                "type": "tool_result",
                "tool_use_id": m.tool_call_id,
                "content": m.content,
                **({"is_error": True} if _is_error(m.content) else {}),
            }
            for m in _new_tool_messages(history)
        ]
        if results:
            # All results of one assistant turn go back in a single user message.
            self._messages.append({"role": "user", "content": results})

    async def step(self, history: list[Message], tools: list[dict[str, Any]]) -> AssistantTurn:
        self._sync(history)
        response = await self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=self._system,
            tools=[
                {
                    "name": wire_name(t["name"]),
                    "description": t.get("description", ""),
                    "input_schema": t["input_schema"],
                }
                for t in tools
            ],
            messages=self._messages,
            output_config={"effort": self.effort},
            # Policy declines are re-run server-side on a suitable fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        # Append the full content (thinking + tool_use blocks), never a re-serialised copy.
        self._messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            return AssistantTurn(text=f"(model declined the request: {category or 'unspecified'})")
        text = "".join(b.text for b in response.content if b.type == "text")
        calls = [
            ToolCall(id=b.id, name=unwire_name(b.name), args=dict(b.input))
            for b in response.content
            if b.type == "tool_use"
        ]
        return AssistantTurn(text=text, tool_calls=calls)


class OpenAICompatibleLLM:
    """OpenAI chat-completions tool calling; also serves Ollama via its OpenAI-compatible endpoint."""

    def __init__(self, model: str, mode: str, client: Any) -> None:
        self.client = client
        self.model = model
        self.mode = mode
        self._messages: list[dict[str, Any]] = []

    def _sync(self, history: list[Message]) -> None:
        if not self._messages:
            system = next((m.content for m in history if m.role == "system"), "")
            user = next(m.content for m in history if m.role == "user")
            self._messages += [{"role": "system", "content": system}, {"role": "user", "content": user}]
            return
        for m in _new_tool_messages(history):
            self._messages.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})

    async def step(self, history: list[Message], tools: list[dict[str, Any]]) -> AssistantTurn:
        self._sync(history)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self._messages,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": wire_name(t["name"]),
                        "description": t.get("description", ""),
                        "parameters": t["input_schema"],
                    },
                }
                for t in tools
            ],
        )
        msg = response.choices[0].message
        self._messages.append(msg.model_dump(exclude_none=True))
        calls = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=tc.id, name=unwire_name(tc.function.name), args=args))
        return AssistantTurn(text=msg.content or "", tool_calls=calls)


def make_openai() -> OpenAICompatibleLLM:
    import openai

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return OpenAICompatibleLLM(model, f"openai:{model}", openai.AsyncOpenAI())


def make_ollama() -> OpenAICompatibleLLM:
    import openai

    model = os.getenv("OLLAMA_MODEL", "llama3.1")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    return OpenAICompatibleLLM(
        model, f"ollama:{model}", openai.AsyncOpenAI(base_url=f"{host}/v1", api_key="ollama")
    )
