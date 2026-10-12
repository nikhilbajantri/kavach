"""A plain tool-calling loop. No framework: the gateway is the agent's only way to act."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from agent.llm.base import LLM, Message
from kavach.gateway import Gateway, Session, ToolOutcome

StepHook = Callable[[str, ToolOutcome | None], Awaitable[None] | None]


class Transcript(BaseModel):
    mode: str
    session_id: str
    task_id: str
    messages: list[Message] = Field(default_factory=list)
    final: str = ""
    steps: int = 0


async def run_agent(
    llm: LLM,
    gateway: Gateway,
    session: Session,
    *,
    system_prompt: str,
    operator_prompt: str,
    max_steps: int = 80,
    on_step: StepHook | None = None,
) -> Transcript:
    history: list[Message] = [
        Message(role="system", content=system_prompt),
        Message(role="user", content=operator_prompt),
    ]
    tools = await gateway.list_tools()
    transcript = Transcript(mode=llm.mode, session_id=session.session_id, task_id=session.identity.task_id)
    for _ in range(max_steps):
        turn = await llm.step(history, tools)
        history.append(Message(role="assistant", content=turn.text, tool_calls=turn.tool_calls))
        if turn.done:
            transcript.final = turn.text
            break
        for call in turn.tool_calls:
            outcome = await gateway.call(session, call.name, call.args)
            payload: dict[str, Any] = outcome.for_agent()
            history.append(
                Message(
                    role="tool",
                    tool_call_id=call.id,
                    name=call.name,
                    content=json.dumps(payload, ensure_ascii=False, default=str),
                )
            )
            transcript.steps += 1
            if on_step:
                maybe = on_step(turn.text, outcome)
                if maybe is not None:
                    await maybe
    transcript.messages = history
    return transcript
