# Shortcuts. Each target is one uv command; run `make help` to list them.
.PHONY: help install data test smoke bench report

help:
	@echo "make install  - create the Python environment (uv sync)"
	@echo "make data     - download datasets into data/ (~2.1 GB)"
	@echo "make test     - run unit tests"
	@echo "make smoke    - 5-utterance end-to-end run (target: under 5 minutes)"
	@echo "make bench    - full benchmark run"
	@echo "make report   - build results/report.md and charts"

install:
	uv sync

test:
	uv run pytest

smoke:
	uv run asr-bench run --smoke

bench:
	uv run asr-bench run

report:
	uv run asr-bench report

data:
	uv run asr-bench download
