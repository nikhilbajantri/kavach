"""Provider-agnostic LLM interface for the tool-calling loop."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    id: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


class AssistantTurn(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)

    @property
    def done(self) -> bool:
        return not self.tool_calls


class LLM(Protocol):
    mode: str

    async def step(self, history: list[Message], tools: list[dict[str, Any]]) -> AssistantTurn: ...
