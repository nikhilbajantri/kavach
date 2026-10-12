"""Offline checks of the live-LLM adapters' message plumbing (no network, fake clients)."""

from types import SimpleNamespace

from agent.llm.base import Message
from agent.llm.providers import AnthropicLLM, OpenAICompatibleLLM, unwire_name, wire_name

TOOLS = [{"name": "email.read", "description": "read", "input_schema": {"type": "object", "properties": {}}}]


def test_tool_names_round_trip() -> None:
    assert wire_name("crm.get_customer") == "crm__get_customer"
    assert unwire_name("crm__get_customer") == "crm.get_customer"


class FakeAnthropic:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        tool_use = SimpleNamespace(
            type="tool_use", id="toolu_1", name="email__read", input={"message_id": "TKT-1"}
        )
        thinking = SimpleNamespace(type="thinking", thinking="", signature="sig")
        done = SimpleNamespace(type="text", text="All done.")
        self._responses = [
            SimpleNamespace(content=[thinking, tool_use], stop_reason="tool_use", stop_details=None),
            SimpleNamespace(content=[done], stop_reason="end_turn", stop_details=None),
        ]
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self._responses[len(self.calls) - 1]


async def test_anthropic_adapter_appends_full_content_and_tool_results() -> None:
    fake = FakeAnthropic()
    llm = AnthropicLLM(client=fake)
    history = [Message(role="system", content="sys"), Message(role="user", content="Process tickets.")]

    turn = await llm.step(history, TOOLS)
    assert turn.tool_calls[0].name == "email.read"
    assert fake.calls[0]["tools"][0]["name"] == "email__read"
    assert fake.calls[0]["model"] == "claude-opus-5-5"
    assert fake.calls[0]["fallbacks"] == "default"

    history += [
        Message(role="assistant", tool_calls=turn.tool_calls),
        Message(role="tool", tool_call_id="toolu_1", content='{"error": "KAVACH Blocked: ..."}'),
    ]
    final = await llm.step(history, TOOLS)
    assert final.done and final.text == "All done."
    sent = fake.calls[1]["messages"]
    assert sent[1]["content"][0].type == "thinking"  # thinking block passed back untouched
    result = sent[2]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "toolu_1" and result["is_error"]


async def test_openai_adapter_maps_tool_calls() -> None:
    call = SimpleNamespace(
        id="c1", function=SimpleNamespace(name="email__read", arguments='{"message_id": "TKT-1"}')
    )
    msg = SimpleNamespace(
        content=None, tool_calls=[call], model_dump=lambda exclude_none=True: {"role": "assistant"}
    )

    async def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    llm = OpenAICompatibleLLM("m", "openai:m", client)
    turn = await llm.step([Message(role="system", content="s"), Message(role="user", content="u")], TOOLS)
    assert turn.tool_calls[0].name == "email.read" and turn.tool_calls[0].args == {"message_id": "TKT-1"}
