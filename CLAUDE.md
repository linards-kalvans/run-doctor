# Run Doctor conventions

Experimental offline Python 3.11+ CLI for Hermes delegation live text transcripts.
Runtime is standard library only. No model calls, network calls, telemetry or automatic repairs.

## Commands
- `uv run python -m pytest -q`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `python3 run_doctor.py analyze tests/fixtures/timeout.log --format json`

## Development
Plan before implementation; use pytest RED/GREEN tests before behavior changes. Use uv and ruff.
New or changed behavior must be checked against native transcript structure, not just invented fixtures.
Tool requests use role `tool`, result wrappers use `result`, lifecycle terminal markers use `final`.
An `ok` wrapper is not proof that the tool or task succeeded.
Inter-event gaps are not LLM latency; repeat candidates may be truncated previews.
Numeric comparisons do not prove a fix worked unless workloads and conditions are controlled separately.
Do not add hosted services, dependencies or new formats without a concrete demonstrated need.

## Privacy
Never commit real raw transcripts or credentials. Use synthetic input fixtures only.
Public aggregate examples require review: fixed text, allowlisted statuses, numbers and line references only.
Never echo payloads, paths, tool names, custom exception messages or CLI argument values into default reports/errors.
Keep developer notes and private review output ignored. Stage files explicitly; review staged content before pushing.
