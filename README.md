# Run Doctor

Run Doctor creates local, deterministic incident summaries from Hermes delegation live
transcripts. It reports structural counts, relative timing, terminal status, and repeated
request candidates without reproducing transcript content. The runtime uses only the Python
standard library: it makes no model or network calls and needs no account or signup.

This project was built with AI assistance. It is not affiliated with or endorsed by Hermes or
Nous Research. Treat its output as descriptive evidence, not an automated diagnosis.

Hermes already has [native heartbeat and timeout diagnostics](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation/).
This utility adds a small offline aggregate report; it does not replace those diagnostics,
inspect thread stacks, or establish why a run failed.

## Requirements and use

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/) for the development commands (optional for normal use)

Clone this repository, enter its directory, and run with Python directly—no dependency install:

```console
git clone https://github.com/linards-kalvans/run-doctor.git
cd run-doctor
python3 run_doctor.py analyze tests/fixtures/timeout.log --format json
```

Analyze the included synthetic example as JSON or Markdown:

```console
uv run python run_doctor.py analyze tests/fixtures/timeout.log --format json
uv run python run_doctor.py analyze tests/fixtures/timeout.log --format markdown
```

Compare numeric counts and timing between two traces:

```console
uv run python run_doctor.py compare tests/fixtures/timeout.log tests/fixtures/repeats_completed.log
```

The comparison is descriptive only. Different traces may represent different inputs or
workloads, so a delta does not establish that a fix worked.

Invalid or unsupported input produces a generic error on stderr and a nonzero exit status.

## Supported input

Run Doctor accepts append-only event lines in this form:

```text
HH:MM:SS role | payload
```

An optional `started: YYYY-MM-DD HH:MM:SS` header is treated as metadata only. Non-event lines
are treated as multiline payload continuations and are never included in output. Times have
one-second resolution; dates and timezones may be absent. Clocks must be monotonic except for a
narrow, credible rollover from `23:xx:xx` to `00:xx:xx`.

The `tool` role is a tool request and `result` is a tool result. Lifecycle roles such as
`start` and `think` are not tool results. An `ok` result means only that its wrapper reported
completion; it does not establish inner tool or business success. Terminal `status=`
markers are read only from `final` lines. For example:

```text
12:00:03 tool      | -> example_tool({})
12:00:04 result    | example_tool ok 1.0s: synthetic result
12:00:10 final     | end status=timeout
```
Terminal markers are allowlisted as `timeout`, `completed`, `error`, and `cancelled`. Missing
markers produce `incomplete`; unrecognized or conflicting markers produce `unknown`.

## Privacy and interpretation limits

Default reports contain only fixed explanatory text, numeric aggregates, allowlisted status
categories, and source line references. They do not output goals, payload text, arguments,
tool names, filenames, paths, URLs, model names, IDs, credentials, or custom error messages.
Inputs still remain your responsibility: use local files and do not commit private transcripts.

- A gap is silence between logged events. It is not measured model latency, root-cause evidence,
  or proof of a hang or idleness.
- Repeat candidates share an exact logged request payload, but Hermes payloads may be truncated.
  This does not prove that full requests or executions were identical.
- A terminal marker preserves what the trace reports; it does not independently prove task or
  business success.
- The optional start header does not supply missing per-event dates or timezone information.

## Real-run evidence and feedback

[Validation notes](VALIDATION.md) describe two real timeout traces. Only aggregate reports are
published in `examples/`; the private inputs are not distributed. They are two different
workloads, **not** a before/after benchmark or evidence that a remedy worked.

To help shape the next version, open an issue describing the failure you were trying to
investigate and which missing measurement would have helped. Include a synthetic reproduction
or a reviewed aggregate report—not raw logs, prompts, credentials, or personal data.
No paid service or payment collection is currently enabled.

## Development

Development tools are pinned in `uv.lock` and have no place in the runtime dependency set.

```console
uv run --with pytest python -m pytest -q
uv run --with ruff ruff check .
uv run --with ruff ruff format --check .
```

Only synthetic fixtures belong in this repository. Run private transcripts in place and publish
only reviewed aggregate reports.

## License

MIT. See [LICENSE](LICENSE).
