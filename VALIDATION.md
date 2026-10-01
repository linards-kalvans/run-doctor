# Validation: Run Doctor v0.1

## What was exercised

- 13 subprocess-based pytest tests passed on Python 3.11 and on the implementation environment's Python 3.14.
- Ruff checking and formatting checks passed.
- The documented compare command was run successfully; its output explicitly disclaims causal conclusions.
- Both original private timeout transcripts were analyzed in place. Counts below were cross-checked against a separate role-counting script, not inferred from the parser's output alone.
- A native-format regression was found during real-trace testing: initial synthetic tests used the wrong event labels. The fixtures and parser were corrected before publication. A subsequent test covers native `ok:` wrappers without duration and duplicate final markers.
- Tests also cover missing/conflicting/unknown status, exact repeat candidates, credible midnight rollover, reversed and invalid clocks, unreadable/empty input, Unicode, multiline payloads, and non-disclosure of canary data and CLI argument values.

## Real incidents

The JSON files are actual aggregate outputs, not fabricated sample results. The input traces remain private and are intentionally not distributed. Public readers can reproduce the synthetic cases, but cannot independently reproduce these private inputs.

- [Incident A](examples/incident-a.json): 24 events, 8 tool requests and 8 result wrappers, all 8 marked `ok`; reported terminal status `timeout`; observed span 600 seconds; largest inter-event gap 204 seconds. No exact logged request-repeat groups.
- [Incident B](examples/incident-b.json): 18 events, 5 tool requests and 5 result wrappers, all 5 marked `ok`; reported terminal status `timeout`; observed span 600 seconds; largest inter-event gap 226 seconds. Two exact logged request-repeat groups, each with two occurrences.

These are different workloads, not before/after versions of the same run. A wrapper reporting `ok` does not prove its underlying operation or the overall task succeeded. A large gap is not measured model latency and does not locate a root cause. Repeated truncated previews do not prove repeated full arguments. No remedy or performance gain has been verified.

## Limits

Experimental support for the documented Hermes delegation text format only; not OpenClaw, Codex JSONL, arbitrary logs, or a universal observability backend. Logs are assumed to be authentic; this parser cannot authenticate or independently verify their claims. Timing has one-second resolution and absent dates/timezones; the narrow midnight heuristic is not suitable for arbitrary multi-day traces.

No telemetry, model invocation, credentials, upload, or hosted service is required by the runtime. Aggregate timing and counts may themselves be sensitive: review any report before sharing it. The program never executes input content.

This is evidence of a functioning small tool, not evidence of paying demand or revenue.
