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
from typing import Any, Protocol

from kavach.approvals import ApprovalQueue
from kavach.attribution.attribute import attribute_value
from kavach.attribution.flow import sensitivity_flow
from kavach.identity.broker import CredentialBroker, Identity
from kavach.models import Decision, FlowReport, ParamAttribution, Verdict
from kavach.policy.context import build_context, refund_amount_ok, resolve_destinations
from kavach.policy.directory import TrustDirectory
from kavach.policy.engine import CedarEngine, PolicyResult, default_engine
from kavach.policy.explain import explain, risk_summary
from kavach.policy.remediation import REMEDIATIONS, ticket_customer
from kavach.provenance.labeller import label_result, label_session_start
from kavach.provenance.ledger import ProvenanceStore
from kavach.registry.manifests import ParamKind, ToolSpec, spec_for
from kavach.transport import Transport
from mocks.tools import UpstreamError

EventSink = Callable[[str, dict[str, Any]], None]
ORG_DOMAINS = ("ourbank.in", "support.ourbank.in")


class DecisionLog(Protocol):
    """Where decisions are recorded (the hash-chained evidence ledger)."""

    def append(self, decision: Decision) -> Any: ...


@dataclass
class Session:
    session_id: str
    identity: Identity
    store: ProvenanceStore
    decisions: list[Decision] = field(default_factory=list)
    current_ticket: dict[str, str] | None = None  # the inbound email being handled


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
        directory: TrustDirectory | None = None,
        engine: CedarEngine | None = None,
        ledger: DecisionLog | None = None,
        agent_id: str = "support-bot-1",
        operator: str = "operator@ourbank.in",
        on_event: EventSink | None = None,
        org_domains: tuple[str, ...] = ORG_DOMAINS,
        approvals: ApprovalQueue | None = None,
    ) -> None:
        if enabled and directory is None:
            raise ValueError("enforce mode needs a TrustDirectory")
        self.transport = transport
        self.broker = broker
        self.enabled = enabled
        self.directory = directory
        self.engine = engine or default_engine()
        self.ledger = ledger
        self.agent_id = agent_id
        self.operator = operator
        self.on_event = on_event
        self.org_domains = org_domains
        self.approvals = approvals if approvals is not None else ApprovalQueue()
        self.quarantined: set[str] = set()
        self.sessions: dict[str, Session] = {}

    # ------------------------------------------------------------------ sessions
    def open_session(self, operator_prompt: str, system_prompt: str, task_id: str | None = None) -> Session:
        task = task_id or f"T-{time.strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:3].upper()}"
        identity = Identity(agent_id=self.agent_id, on_behalf_of=self.operator, task_id=task)
        session_id = f"sess_{uuid.uuid4().hex[:10]}"
        store = ProvenanceStore(session_id=session_id)
        label_session_start(store, system_prompt, operator_prompt, self.org_domains)
        session = Session(session_id=session_id, identity=identity, store=store)
        self.sessions[session_id] = session
        return session

    async def list_tools(self) -> list[dict[str, Any]]:
        """The only tool list the agent ever sees: KAVACH re-exports upstream tools."""
        return await self.transport.list_tools()

    # ------------------------------------------------------------------ calls
    async def call(self, session: Session, tool: str, args: dict[str, Any]) -> ToolOutcome:
        started = time.perf_counter()
        spec = spec_for(tool, args)
        decision = Decision(
            call_id=f"call_{uuid.uuid4().hex[:10]}",
            session_id=session.session_id,
            tool=tool,
            args=args,
            final_args=args,
            verdict=Verdict.PASSTHROUGH,
            explanation="KAVACH disabled: forwarded without enforcement.",
            identity=_identity_dict(session.identity),
            is_sink=spec.sink,
            ticket_id=(session.current_ticket or {}).get("id"),
            mode="enforce" if self.enabled else "passthrough",
        )
        if self.enabled:
            self._decide(session, spec, decision)

        outcome = ToolOutcome(decision=decision)
        if decision.verdict in (Verdict.ALLOW, Verdict.SANITISE, Verdict.PASSTHROUGH):
            token = self.broker.mint(session.identity, tool, decision.final_args or {})
            decision.token_id = token.jti
            decision.latency_ms = _ms(started)
            await self._execute(session, decision, token.token, outcome)
        elif decision.verdict is Verdict.ESCALATE:
            approval = self.approvals.add(decision, session, executor=self)
            decision.approval_id = approval.id
            decision.latency_ms = _ms(started)
            outcome.result = {
                "status": "pending_human_approval",
                "approval_id": approval.id,
                "message": "KAVACH escalated this action to a human operator. " + decision.explanation,
            }
            self._emit("approval", approval.public())
        else:
            decision.latency_ms = _ms(started)
            outcome.error = f"KAVACH {decision.explanation}"
            if decision.rule_ids:
                self._emit("alert", {"decision": decision.model_dump(mode="json")})

        session.decisions.append(decision)
        if self.ledger is not None:
            self.ledger.append(decision)
        self._emit("decision", {"decision": decision.model_dump(mode="json"), "error": outcome.error})
        return outcome

    async def _execute(self, session: Session, decision: Decision, token: str, outcome: ToolOutcome) -> None:
        args = decision.final_args or {}
        try:
            outcome.result = await self.transport.call(decision.tool, args, token)
        except UpstreamError as exc:
            outcome.error = f"upstream {exc.status}: {exc}"
            return
        label_result(session.store, decision.tool, args, outcome.result, decision.call_id)
        if decision.tool == "email.read":
            session.current_ticket = {
                "id": str(outcome.result.get("id")),
                "from": str(outcome.result.get("from")),
            }

    # ------------------------------------------------------------------ decide
    def _decide(self, session: Session, spec: ToolSpec, decision: Decision) -> None:
        assert self.directory is not None
        customer = ticket_customer(self.directory, (session.current_ticket or {}).get("from"))
        args = decision.args
        result, attributions, flow, dests = self._evaluate(session, spec, args, customer)
        verdict, rules = result.verdict, result.rule_ids()
        remediations = []

        if verdict is Verdict.SANITISE and spec.remediation:
            fixed = REMEDIATIONS[spec.remediation](args, attributions, customer, session.store)
            if fixed is None:
                verdict = Verdict.BLOCK  # no safe default available: fail closed
            else:
                args, remediations = fixed
                # Re-check the remediated call from scratch; it must stand on its own.
                result2, attributions2, flow, dests = self._evaluate(session, spec, args, customer)
                if result2.verdict is not Verdict.ALLOW:
                    verdict = result2.verdict
                    rules = sorted(set(rules) | set(result2.rule_ids()))
                decision.final_args = args
                attributions = attributions + [
                    a for a in attributions2 if a.param in {r.param for r in remediations}
                ]

        decision.verdict = verdict
        decision.rule_ids = rules
        decision.attributions = attributions
        decision.flow = flow
        decision.destinations = [d.as_dict() for d in dests]
        decision.remediations = remediations
        decision.risk = risk_summary(
            rules, session.store.saw_untrusted, session.store.touched_regulated, result.flagged
        )
        decision.explanation = explain(
            verdict=verdict,
            rules=rules,
            tool=spec.name,
            is_sink=spec.sink,
            attributions=attributions,
            flow=flow,
            destinations=dests,
            remediations=remediations,
            customer=customer,
            args=decision.args,
        )

    def _evaluate(
        self, session: Session, spec: ToolSpec, args: dict[str, Any], customer: dict[str, Any] | None
    ) -> tuple[PolicyResult, list[ParamAttribution], FlowReport | None, list]:
        assert self.directory is not None
        attributions = attribute_call(spec, args, session.store)
        flow = content_flow(spec, args, session.store) if spec.sink else None
        dests = resolve_destinations(spec, args, self.directory, session.store, self.org_domains)
        context = build_context(
            spec,
            attributions,
            flow,
            dests,
            session.store,
            amount_matches_order=refund_amount_ok(args, customer) if spec.name == "payments.refund" else True,
            quarantined=spec.name in self.quarantined,
        )
        return self.engine.evaluate(self.agent_id, spec.name, context), attributions, flow, dests

    # ------------------------------------------------------------------ approvals
    async def resolve_approval(
        self, approval_id: str, approve: bool, reviewer: str = "operator"
    ) -> dict[str, Any]:
        approval = self.approvals.get(approval_id)
        if approval is None or approval.status != "pending":
            raise KeyError(approval_id)
        approval.resolved_by = reviewer
        original = approval.decision
        # The human decision is evidence too: record it as its own ledger row.
        record = original.model_copy(
            update={
                "call_id": f"call_{uuid.uuid4().hex[:10]}",
                "verdict": Verdict.ALLOW if approve else Verdict.BLOCK,
                "explanation": f"{'Approved' if approve else 'Rejected'} by {reviewer} after escalation "
                f"({approval.id}). {original.explanation}",
                "token_id": None,
            }
        )
        if not approve:
            approval.status = "rejected"
        else:
            approval.status = "approved"
            token = self.broker.mint(approval.session.identity, original.tool, original.final_args or {})
            record.token_id = token.jti
            outcome = ToolOutcome(decision=record)
            await self._execute(approval.session, record, token.token, outcome)
            approval.result, approval.error = outcome.result, outcome.error
        approval.session.decisions.append(record)
        if self.ledger is not None:
            self.ledger.append(record)
        self._emit("approval", approval.public())
        return approval.public()

    def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        if self.on_event:
            self.on_event(kind, payload)


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


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
