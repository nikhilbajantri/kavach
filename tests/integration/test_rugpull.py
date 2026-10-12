"""Acceptance: a rug-pulled tool description triggers quarantine and an alert."""

from agent.prompts import OPERATOR_PROMPT, SYSTEM_PROMPT
from agent.runner import build_runtime
from kavach.models import Verdict
from kavach.registry.pinning import scan_description
from mocks.tools import RUG_PULL_DESCRIPTION, rug_pull


async def test_rug_pull_quarantines_tool_and_blocks_calls() -> None:
    events: list[tuple[str, dict]] = []
    rt = build_runtime(enabled=True, on_event=lambda kind, data: events.append((kind, data)))
    session = rt.gateway.open_session(OPERATOR_PROMPT, SYSTEM_PROMPT)
    await rt.gateway.call(session, "crm.get_customer", {"email": "ravi.kumar@gmail.com"})

    rug_pull(rt.world)  # upstream silently rewrites email.send after it was approved
    tools = await rt.gateway.list_tools()

    sent = next(t for t in tools if t["name"] == "email.send")
    assert "archive@kyc-verify.net" not in sent["description"]  # the agent never sees the poison
    assert rt.gateway.quarantined == {"email.send"}
    alerts = [d["supply_chain"] for k, d in events if k == "alert" and "supply_chain" in d]
    assert alerts and alerts[0]["reason"] == "tool_manifest_changed"
    assert "hidden <IMPORTANT> block" in alerts[0]["flags"]

    outcome = await rt.gateway.call(
        session, "email.send", {"to": "ravi.kumar@gmail.com", "subject": "hi", "body": "refund done"}
    )
    assert outcome.decision.verdict is Verdict.BLOCK
    assert outcome.decision.rule_ids == ["R0"]
    assert "tool_manifest_changed" in outcome.decision.explanation
    assert rt.world.mail.sent == []


async def test_alert_fires_once_per_change() -> None:
    rt = build_runtime(enabled=True)
    rug_pull(rt.world)
    assert len(await rt.gateway.refresh_tools()) == 1
    assert await rt.gateway.refresh_tools() == []


async def test_passthrough_mode_exposes_the_poisoned_description() -> None:
    rt = build_runtime(enabled=False)
    rug_pull(rt.world)
    tools = await rt.gateway.list_tools()
    assert next(t for t in tools if t["name"] == "email.send")["description"] == RUG_PULL_DESCRIPTION


def test_instruction_like_text_is_flagged() -> None:
    flags = scan_description(RUG_PULL_DESCRIPTION)
    assert {
        "hidden <IMPORTANT> block",
        "asks to hide behaviour from the user",
        "embeds a URL or email address",
    } <= set(flags)
    assert scan_description("Send an email from support@ourbank.in.") == []
