"""Local, deterministic analysis of supported Hermes live transcripts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

EVENT_RE = re.compile(r"^(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}) (?P<role>[^|]+)\|(?P<payload>.*)$")
STATUS_RE = re.compile(r"(?:^|\s)status=(?P<status>[A-Za-z_-]+)(?:\s|$)")
TERMINAL_STATUSES = frozenset({"timeout", "completed", "error", "cancelled"})
COMPARE_METRICS = (
    ("Event count", "event_count"),
    ("Tool request count", "tool_request_count"),
    ("Tool result count", "tool_result_count"),
    ("Tool ok result count", "tool_ok_result_count"),
    ("Duration (seconds)", "duration_seconds"),
    ("Largest observed gap (seconds)", "largest_gap_seconds"),
)


class InputError(ValueError):
    """An input is not a supported transcript."""


@dataclass(frozen=True)
class Event:
    line: int
    second_of_day: int
    absolute_second: int
    role: str
    payload: str


def _read_events(path: Path) -> list[Event]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise InputError("input could not be read") from exc

    events: list[Event] = []
    day_offset = 0
    previous_value: int | None = None
    for line_number, line in enumerate(lines, 1):
        match = EVENT_RE.fullmatch(line)
        if not match:
            continue
        hour, minute, second = (int(match.group(key)) for key in ("h", "m", "s"))
        if hour > 23 or minute > 59 or second > 59:
            raise InputError("invalid timestamp")
        value = hour * 3600 + minute * 60 + second
        if previous_value is not None and value < previous_value:
            if previous_value >= 23 * 3600 and value < 3600:
                day_offset += 24 * 3600
            else:
                raise InputError("non-monotonic timestamp")
        events.append(
            Event(
                line=line_number,
                second_of_day=value,
                absolute_second=value + day_offset,
                role=match.group("role").strip(),
                payload=match.group("payload").strip(),
            )
        )
        previous_value = value
    if not events:
        raise InputError("no supported events")
    return events


def analyze(path: Path) -> dict[str, object]:
    events = _read_events(path)
    gaps = [b.absolute_second - a.absolute_second for a, b in pairwise(events)]
    largest_gap = max(gaps, default=0)
    gap_index = gaps.index(largest_gap) if gaps else None

    requests = [event for event in events if event.role == "tool"]
    results = [event for event in events if event.role == "result"]
    request_lines_by_payload: dict[str, list[int]] = defaultdict(list)
    for event in requests:
        request_lines_by_payload[event.payload].append(event.line)
    repeat_groups = [
        {"count": len(lines), "request_lines": lines}
        for lines in request_lines_by_payload.values()
        if len(lines) > 1
    ]
    repeat_groups.sort(key=lambda group: group["request_lines"][0])  # type: ignore[index]
    statuses: list[tuple[str, int]] = []
    for event in events:
        match = STATUS_RE.search(event.payload)
        if match and event.role == "final":
            status = match.group("status")
            statuses.append((status if status in TERMINAL_STATUSES else "unknown", event.line))
    distinct_statuses = {status for status, _ in statuses}
    terminal_status = statuses[-1][0] if len(distinct_statuses) == 1 else "unknown"
    status_lines = [line for _, line in statuses]
    findings = []
    if terminal_status == "timeout":
        findings.append("The trace reports a timeout terminal status.")
    if repeat_groups:
        count_word = "One" if len(repeat_groups) == 1 else "Multiple"
        noun = "payload is" if len(repeat_groups) == 1 else "payloads are"
        findings.append(
            f"{count_word} repeated tool request {noun} a repeat candidate; "
            "Hermes payloads may be truncated."
        )
    findings.append(
        "The largest gap is observed time between logged events; it is not measured model latency or proof of a hang."
    )

    return {
        "event_count": len(events),
        "terminal_status": terminal_status if statuses else "incomplete",
        "terminal_status_lines": status_lines,
        "tool_request_count": len(requests),
        "tool_result_count": len(results),
        "tool_ok_result_count": sum(
            bool(re.match(r"^\S+ ok(?: \d+(?:\.\d+)?s)?:", event.payload)) for event in results
        ),
        "duration_seconds": events[-1].absolute_second - events[0].absolute_second,
        "largest_gap_seconds": largest_gap,
        "largest_gap_after_line": events[gap_index].line if gap_index is not None else None,
        "repeat_candidate_groups": repeat_groups,
        "findings": findings,
        "caveats": [
            "Timestamps have one-second resolution; date and timezone may be absent.",
            "A tool result marked ok reports wrapper completion, not inner tool or business success.",
        ],
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Run Doctor report",
        "",
        "| Measure | Value |",
        "| --- | ---: |",
        f"| Event count | {report['event_count']} |",
        f"| Terminal status | {report['terminal_status']} |",
        f"| Tool requests | {report['tool_request_count']} |",
        f"| Tool results | {report['tool_result_count']} |",
        f"| Tool results marked ok | {report['tool_ok_result_count']} |",
        f"| Duration (seconds) | {report['duration_seconds']} |",
        f"| Largest observed gap (seconds) | {report['largest_gap_seconds']} |",
        f"| Largest gap after source line | {report['largest_gap_after_line']} |",
        f"| Repeat-candidate groups | {len(report['repeat_candidate_groups'])} |",  # type: ignore[arg-type]
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {finding}" for finding in report["findings"])  # type: ignore[union-attr]
    lines.extend(("", "## Caveats", ""))
    lines.extend(f"- {caveat}" for caveat in report["caveats"])  # type: ignore[union-attr]
    return "\n".join(lines) + "\n"


def render_comparison(before: dict[str, object], after: dict[str, object]) -> str:
    lines = [
        "# Run Doctor comparison",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label, key in COMPARE_METRICS:
        before_value = int(before[key])  # type: ignore[arg-type]
        after_value = int(after[key])  # type: ignore[arg-type]
        lines.append(
            f"| {label} | {before_value} | {after_value} | {after_value - before_value:+d} |"
        )
    lines.extend(
        (
            "",
            "Values are descriptive only; traces may represent different workloads and do not prove a remedy effective.",
        )
    )
    return "\n".join(lines) + "\n"


class SafeParser(argparse.ArgumentParser):
    """Do not echo potentially sensitive argument values in errors."""

    def error(self, message):
        self.exit(2, "run-doctor: invalid arguments; use --help\n")


def main(argv: list[str] | None = None) -> int:
    parser = SafeParser(prog="run-doctor")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("path", type=Path)
    analyze_parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("before", type=Path)
    compare_parser.add_argument("after", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            report = analyze(args.path)
        else:
            before = analyze(args.before)
            after = analyze(args.after)
    except InputError:
        print("run-doctor: unsupported or invalid input", file=sys.stderr)
        return 2
    if args.command == "compare":
        sys.stdout.write(render_comparison(before, after))
    elif args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
