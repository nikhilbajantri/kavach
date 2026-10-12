# Design decisions

This file records spec ambiguities, and how they were resolved, while building KAVACH. Each entry gives the decision first, then the reasoning.

## D1: Repo root is the working folder

The repo is built in the session folder (`DevHost`) and not in a separate `kavach/` folder. The layout matches spec §8 relative to the repo root, so the gateway Python package sits at `./kavach/`.

## D2: `tasks.py` alongside the `Makefile`

The dev machine (Windows) has no `make`. `python tasks.py <target>` mirrors every Makefile target. Docker, Linux and CI use the Makefile.

## D3: Python 3.12

The spec asks for Python 3.11+. Only 3.12 was available, so development, CI and the Docker image all use 3.12. `pyproject.toml` still declares `>=3.11`.

## D4: SQLite via the stdlib `sqlite3` module

The stdlib module is used directly instead of SQLModel. The schemas are tiny, and this drops a dependency and an ORM layer from the hot path, where the decision-latency target is under 10 ms.

## D5: Cedar is real

`cedarpy` 4.x installed cleanly on Windows/py3.12, so the YAML fallback evaluator is not needed. Rules live in `policies/*.cedar`.

## D6: `crm.update_address` added

The spec's tool list cannot complete the benign "address change" ticket, so this tool was added. It is a sink: `customer_id` is a CONTROL parameter and `new_address` is CONTENT. That split also demonstrates the core rule: untrusted text may be *content*, but never *control*.
