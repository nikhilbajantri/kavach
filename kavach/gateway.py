"""The KAVACH gateway: every agent tool call passes through `Gateway.call`.

Pipeline (enforce mode): 1 Label → 2 Type → 3 Attribute → 4 Decide → 5 Mint.
In pass-through mode the call is forwarded unchanged but still logged, which
powers the "without KAVACH" side of the demo.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from kavach.attribution.attribute import attribute_value
from kavach.attribution.flow import sensitivity_flow
from kavach.identity.broker import CredentialBroker, Identity
from kavach.models import Decision, FlowReport, ParamAttribution, Verdict
from kavach.provenance.labeller import label_result, label_session_start
from kavach.provenance.ledger import ProvenanceStore
from kavach.registry.manifests import ParamKind, ToolSpec, spec_for
from kavach.transport import Transport
from mocks.tools import UpstreamError

EventSink = Callable[[str, dict[str, Any]], None]


@dataclass
class Session:
    session_id: str
    identity: Identity
    store: ProvenanceStore
    decisions: list[Decision] = field(default_factory=list)


@dataclass
class ToolOutcome:
    decision: Decision
    result: dict[str, Any] | None = None
    error: str | None = None

    def for_agent(self) -> dict[str, Any]:
        """What the LLM sees. Blocked calls get a plain refusal it can reason about."""
        if self.error:
            return {"error": self.error}
        return self.result or {}


class Gateway:
    def __init__(
        self,
        transport: Transport,
        broker: CredentialBroker,
        *,
        enabled: bool,
        agent_id: str = "support-bot-1",
        operator: str = "operator@ourbank.in",
        on_event: EventSink | None = None,
        org_domains: tuple[str, ...] = ("ourbank.in", "support.ourbank.in"),
    ) -> None:
        self.transport = transport
        self.broker = broker
        self.enabled = enabled
        self.agent_id = agent_id
        self.operator = operator
        self.on_event = on_event
        self.org_domains = org_domains

    def open_session(self, operator_prompt: str, system_prompt: str, task_id: str | None = None) -> Session:
        task = task_id or f"T-{time.strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:3].upper()}"
        identity = Identity(agent_id=self.agent_id, on_behalf_of=self.operator, task_id=task)
        session_id = f"sess_{uuid.uuid4().hex[:10]}"
        store = ProvenanceStore(session_id=session_id)
        label_session_start(store, system_prompt, operator_prompt, self.org_domains)
        return Session(session_id=session_id, identity=identity, store=store)

    async def list_tools(self) -> list[dict[str, Any]]:
        """The only tool list the agent ever sees: KAVACH re-exports upstream tools."""
        return await self.transport.list_tools()

    async def call(self, session: Session, tool: str, args: dict[str, Any]) -> ToolOutcome:
        call_id = f"call_{uuid.uuid4().hex[:10]}"
        started = time.perf_counter()
        spec = spec_for(tool, args)
        decision = Decision(
            call_id=call_id,
            session_id=session.session_id,
            tool=tool,
            args=args,
            final_args=args,
            verdict=Verdict.PASSTHROUGH,
            explanation="KAVACH disabled: forwarded without enforcement.",
            identity=_identity_dict(session.identity),
            is_sink=spec.sink,
        )
        if self.enabled:
            decision.attributions = attribute_call(spec, args, session.store)
            decision.flow = content_flow(spec, args, session.store) if spec.sink else None
            decision.verdict = Verdict.ALLOW
            decision.explanation = "Allowed."
        token = self.broker.mint(session.identity, tool, decision.final_args or {})
        decision.token_id = token.jti
        decision.latency_ms = round((time.perf_counter() - started) * 1000, 3)

        outcome = ToolOutcome(decision=decision)
        try:
            outcome.result = await self.transport.call(tool, decision.final_args or {}, token.token)
        except UpstreamError as exc:
            outcome.error = f"upstream {exc.status}: {exc}"
        if outcome.result is not None:
            label_result(session.store, tool, decision.final_args or {}, outcome.result, call_id)
        session.decisions.append(decision)
        self._emit("decision", {"decision": decision.model_dump(mode="json"), "error": outcome.error})
        return outcome

    def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        if self.on_event:
            self.on_event(kind, payload)


def _identity_dict(identity: Identity) -> dict[str, str]:
    return {"agent_id": identity.agent_id, "on_behalf_of": identity.on_behalf_of, "task_id": identity.task_id}


def attribute_call(spec: ToolSpec, args: dict[str, Any], store: ProvenanceStore) -> list[ParamAttribution]:
    """Attribute every CONTROL argument that is present (sources too, for visibility)."""
    out = []
    for name in spec.control_params():
        if name in args and args[name] not in (None, ""):
            numeric = spec.params[name].kind is ParamKind.AMOUNT
            out.append(attribute_value(name, args[name], store, numeric=numeric))
    return out


def content_flow(spec: ToolSpec, args: dict[str, Any], store: ProvenanceStore) -> FlowReport:
    content = "\n".join(str(args[p]) for p in spec.content_params() if args.get(p))
    return sensitivity_flow(content, store)
