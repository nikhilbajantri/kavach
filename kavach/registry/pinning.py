"""Tool pinning (counters L3: tools that change underneath the agent).

At registration KAVACH stores SHA-256(name + description + schema) for every
upstream tool. Every later listing is re-hashed: a changed manifest ("rug pull")
quarantines the tool. Its calls are BLOCKed by R0, and the agent keeps seeing
the *pinned* description, so a poisoned description never reaches the model.
"""

from __future__ import annotations

import re
import time
from typing import Any

from pydantic import BaseModel, Field

from kavach.canonical import canonical_json, sha256_hex

SUSPICIOUS = [
    (
        re.compile(r"ignore (all )?(previous|prior) (instructions|rules)", re.I),
        "asks to ignore previous instructions",
    ),
    (re.compile(r"\bsystem\s*:", re.I), "impersonates a system message"),
    (re.compile(r"\byou must\b", re.I), "imperative aimed at the model ('you must')"),
    (re.compile(r"<\s*important\s*>", re.I), "hidden <IMPORTANT> block"),
    (re.compile(r"do not (tell|mention|inform)", re.I), "asks to hide behaviour from the user"),
    (re.compile(r"https?://|\b[\w.-]+@[\w-]+\.[\w.]+", re.I), "embeds a URL or email address"),
    (re.compile(r"\b(bcc|forward|exfiltrat|send (a )?copy)\b", re.I), "asks to copy data elsewhere"),
]


def manifest_hash(manifest: dict[str, Any]) -> str:
    return sha256_hex(
        canonical_json(
            {
                "name": manifest["name"],
                "description": manifest.get("description", ""),
                "input_schema": manifest.get("input_schema", {}),
            }
        )
    )


ORG_DOMAINS = ("ourbank.in",)


def scan_description(text: str) -> list[str]:
    """Flag instruction-like text. The bank's own domains are not suspicious."""
    cleaned = text or ""
    for domain in ORG_DOMAINS:
        cleaned = re.sub(rf"[\w.-]*@?{re.escape(domain)}\b", "", cleaned, flags=re.I)
    return [reason for rx, reason in SUSPICIOUS if rx.search(cleaned)]


class PinnedTool(BaseModel):
    name: str
    server: str = ""
    sha256: str
    manifest: dict[str, Any]
    pinned_at: float = Field(default_factory=time.time)
    flags: list[str] = Field(default_factory=list)
    status: str = "pinned"  # pinned | quarantined
    observed_sha256: str | None = None
    observed_description: str | None = None
    observed_flags: list[str] = Field(default_factory=list)


class ToolRegistry:
    def __init__(self) -> None:
        self.tools: dict[str, PinnedTool] = {}
        self.alerts: list[dict[str, Any]] = []

    def pin(self, manifests: list[dict[str, Any]]) -> None:
        for m in manifests:
            self.tools[m["name"]] = PinnedTool(
                name=m["name"],
                server=m.get("server", ""),
                sha256=manifest_hash(m),
                manifest=m,
                flags=scan_description(m.get("description", "")),
            )

    def check(self, manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compare a fresh listing with the pins; quarantine and alert on any drift."""
        new_alerts: list[dict[str, Any]] = []
        for m in manifests:
            pinned = self.tools.get(m["name"])
            if pinned is None:
                # A tool that appears after registration is untrusted until an operator pins it.
                self.tools[m["name"]] = PinnedTool(
                    name=m["name"], server=m.get("server", ""), sha256="", manifest=m, status="quarantined"
                )
                new_alerts.append(self._alert(m["name"], "tool_added_after_pinning", m))
                continue
            digest = manifest_hash(m)
            if digest != pinned.sha256 and pinned.observed_sha256 != digest:
                pinned.status = "quarantined"
                pinned.observed_sha256 = digest
                pinned.observed_description = m.get("description", "")
                pinned.observed_flags = scan_description(pinned.observed_description)
                new_alerts.append(self._alert(m["name"], "tool_manifest_changed", m))
        self.alerts += new_alerts
        return new_alerts

    def _alert(self, name: str, reason: str, manifest: dict[str, Any]) -> dict[str, Any]:
        pinned = self.tools[name]
        return {
            "type": "supply_chain",
            "reason": reason,
            "tool": name,
            "pinned_sha256": pinned.sha256,
            "observed_sha256": manifest_hash(manifest),
            "observed_description": manifest.get("description", ""),
            "flags": scan_description(manifest.get("description", "")),
            "ts": time.time(),
        }

    def quarantined(self) -> set[str]:
        return {n for n, t in self.tools.items() if t.status == "quarantined"}

    def agent_view(self, manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """What the agent may see: pinned manifests only, never a drifted description."""
        out = []
        for m in manifests:
            pinned = self.tools.get(m["name"])
            if pinned is not None and pinned.sha256:
                out.append(pinned.manifest)
        return out

    def approve_current(self, manifests: list[dict[str, Any]]) -> None:
        """Operator re-approves the upstream as it is now (after review)."""
        self.pin(manifests)

    def snapshot(self) -> list[dict[str, Any]]:
        return [t.model_dump() for t in self.tools.values()]
