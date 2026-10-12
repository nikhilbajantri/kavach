"""Run the 2 AM scenario from the terminal, with any LLM provider, KAVACH on or off.

python -m agent.cli                       # scripted, KAVACH on
python -m agent.cli --kavach off
LLM_PROVIDER=anthropic python -m agent.cli
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from agent.llm.factory import PROVIDERS, make_llm
from agent.llm.scripted import load_plan
from agent.runner import run_scenario


async def main(provider: str | None, kavach: bool, scenario: str) -> int:
    plan = load_plan(scenario)
    llm = make_llm(plan, provider)
    outcome, _ = await run_scenario(plan, enabled=kavach, llm=llm)
    print(
        f"mode={outcome.mode}  kavach={'ON' if kavach else 'OFF'}  session={outcome.transcript.session_id}\n"
    )
    for d in outcome.decisions:
        print(f"{d.verdict.value:11} {d.tool:22} {', '.join(d.rule_ids):12} {d.explanation[:110]}")
    print(
        f"\nmoney to attacker ₹{outcome.money_to_attacker_inr:,} · KYC leaked {outcome.kyc_records_leaked} · "
        f"tickets {outcome.tasks_completed}/{len(outcome.tasks)}"
    )
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--provider", choices=PROVIDERS, default=None)
    parser.add_argument("--kavach", choices=["on", "off"], default="on")
    parser.add_argument("--scenario", default="nbfc_2am")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.provider, args.kavach == "on", args.scenario)))
