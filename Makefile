.PHONY: install test test-mock run-mock demo-config

PYTHON ?= python3.11

install:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -U pip hatchling
	.venv/bin/pip install -e ".[dev]"

test:
	.venv/bin/pytest -q

test-mock:
	MAGNIFIC_MOCK_APIS=1 .venv/bin/pytest -q

demo-config:
	.venv/bin/python -m magnific generate-config \
		--idea "A loving couple navigating daily life" \
		-o workflow.yaml

run-mock:
	MAGNIFIC_MOCK_APIS=1 .venv/bin/python -m magnific run --config workflow.yaml --mock
