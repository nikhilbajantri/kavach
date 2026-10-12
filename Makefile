# KAVACH task shortcuts. On Windows without make, use: python tasks.py <target>
PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.PHONY: install dev test lint demo bench seed docker

install:
	$(PY) -m pip install -e ".[dev]"
	cd web && npm install

dev:
	$(PY) tasks.py dev

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check . && $(PY) -m ruff format --check .

seed:
	$(PY) -m mocks.seed

demo:
	$(PY) tasks.py demo

bench:
	$(PY) -m bench.runner

docker:
	docker compose up --build
