import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "run_doctor.py"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_native_wrapper_without_duration_and_lifecycle_markers(tmp_path: Path) -> None:
    path = tmp_path / "native.log"
    path.write_text(
        "10:00:00 start | synthetic\n"
        "10:00:01 tool | -> synthetic_tool({})\n"
        "10:00:02 result | synthetic_tool ok: {}\n"
        "10:00:03 assistant | status=completed is only quoted content\n"
        "10:00:04 final | status=timeout duration=4s\n"
        "10:00:04 final | end status=timeout\n",
        encoding="utf-8",
    )
    report = json.loads(run_cli("analyze", str(path), "--format", "json").stdout)
    assert report["tool_ok_result_count"] == 1
    assert report["terminal_status"] == "timeout"
    assert report["terminal_status_lines"] == [5, 6]


def test_ok_wrapper_requires_native_colon_delimiter(tmp_path: Path) -> None:
    path = tmp_path / "ok-wrappers.log"
    path.write_text(
        "10:00:00 result | tool_without_duration ok: {}\n"
        "10:00:01 result | tool_with_duration ok 1.0s: {}\n"
        "10:00:02 result | malformed_tool ok {}\n",
        encoding="utf-8",
    )
    report = json.loads(run_cli("analyze", str(path), "--format", "json").stdout)
    assert report["tool_ok_result_count"] == 2


def test_cli_argument_errors_do_not_echo_private_values() -> None:
    result = run_cli("analyze", "CANARY_PATH", "--format", "CANARY_FORMAT")
    assert result.returncode == 2
    assert "CANARY" not in result.stderr


def test_analyze_timeout_json() -> None:
    result = run_cli("analyze", str(FIXTURES / "timeout.log"), "--format", "json")

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report == {
        "event_count": 4,
        "terminal_status": "timeout",
        "terminal_status_lines": [5],
        "tool_request_count": 1,
        "tool_result_count": 1,
        "tool_ok_result_count": 1,
        "duration_seconds": 9,
        "largest_gap_seconds": 6,
        "largest_gap_after_line": 4,
        "repeat_candidate_groups": [],
        "findings": [
            "The trace reports a timeout terminal status.",
            "The largest gap is observed time between logged events; it is not measured model latency or proof of a hang.",
        ],
        "caveats": [
            "Timestamps have one-second resolution; date and timezone may be absent.",
            "A tool result marked ok reports wrapper completion, not inner tool or business success.",
        ],
    }


def test_completed_trace_reports_repeat_candidates_without_payloads() -> None:
    result = run_cli("analyze", str(FIXTURES / "repeats_completed.log"), "--format", "json")

    assert result.returncode == 0
    assert "CANARY_REPEAT_PAYLOAD" not in result.stdout
    assert "private_tool" not in result.stdout
    report = json.loads(result.stdout)
    assert report["terminal_status"] == "completed"
    assert report["terminal_status_lines"] == [7]
    assert report["tool_request_count"] == 3
    assert report["tool_result_count"] == 2
    assert report["repeat_candidate_groups"] == [{"count": 2, "request_lines": [2, 4]}]
    assert report["findings"][0] == (
        "One repeated tool request payload is a repeat candidate; Hermes payloads may be truncated."
    )


def test_invalid_and_empty_inputs_fail_without_echoing_content(tmp_path: Path) -> None:
    for content in ("CANARY_NO_EVENTS\n", "25:00:00 user | CANARY_BAD_CLOCK\n"):
        path = tmp_path / "private-name.log"
        path.write_text(content, encoding="utf-8")
        result = run_cli("analyze", str(path), "--format", "json")
        assert result.returncode != 0
        assert "CANARY" not in result.stderr
        assert "private-name" not in result.stderr


def test_decreasing_clock_is_rejected_but_credible_midnight_rollover_is_allowed(
    tmp_path: Path,
) -> None:
    decreasing = tmp_path / "decreasing.log"
    decreasing.write_text("10:00:02 user | a\n10:00:01 assistant | b\n", encoding="utf-8")
    assert run_cli("analyze", str(decreasing), "--format", "json").returncode != 0

    result = run_cli("analyze", str(FIXTURES / "midnight.log"), "--format", "json")
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["duration_seconds"] == 4
    assert report["largest_gap_seconds"] == 4


def test_missing_and_conflicting_terminal_statuses_are_not_success(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete.log"
    incomplete.write_text("10:00:00 user | a\n", encoding="utf-8")
    assert (
        json.loads(run_cli("analyze", str(incomplete), "--format", "json").stdout)[
            "terminal_status"
        ]
        == "incomplete"
    )

    conflicting = tmp_path / "conflicting.log"
    conflicting.write_text(
        "10:00:00 final | status=completed\n10:00:01 final | status=error\n",
        encoding="utf-8",
    )
    report = json.loads(run_cli("analyze", str(conflicting), "--format", "json").stdout)
    assert report["terminal_status"] == "unknown"
    assert report["terminal_status_lines"] == [1, 2]


def test_markdown_is_readable_and_multiline_payloads_do_not_leak(tmp_path: Path) -> None:
    path = tmp_path / "multiline.log"
    path.write_text(
        "09:00:00 user | CANARY_GOAL\n"
        "continuation with https://secret.invalid and TOKEN_CANARY\n"
        '09:00:02 tool | -> CANARY_TOOL {"path":"CANARY_PATH"}\n'
        "continued CANARY_ARGUMENT\n"
        "09:00:03 result | CANARY_TOOL ok 1.0s: CANARY_RESULT\n"
        "09:00:04 final | status=cancelled\n",
        encoding="utf-8",
    )
    result = run_cli("analyze", str(path), "--format", "markdown")

    assert result.returncode == 0
    assert result.stdout.startswith("# Run Doctor report\n")
    assert "Terminal status | cancelled" in result.stdout
    assert "Largest observed gap (seconds) | 2" in result.stdout
    for canary in ("CANARY", "secret.invalid", str(path)):
        assert canary not in result.stdout


def test_compare_reports_only_numeric_deltas() -> None:
    result = run_cli(
        "compare", str(FIXTURES / "timeout.log"), str(FIXTURES / "repeats_completed.log")
    )

    assert result.returncode == 0
    assert result.stdout.startswith("# Run Doctor comparison\n")
    assert "| Metric | Before | After | Delta |" in result.stdout
    assert "| Event count | 4 | 7 | +3 |" in result.stdout
    assert "timeout" not in result.stdout
    assert "completed" not in result.stdout
    assert "works" not in result.stdout
    assert "synthetic" not in result.stdout


def test_compare_invalid_input_fails_with_safe_error(tmp_path: Path) -> None:
    invalid = tmp_path / "CANARY_PRIVATE.log"
    invalid.write_text("CANARY_CONTENT", encoding="utf-8")
    result = run_cli("compare", str(invalid), str(FIXTURES / "timeout.log"))
    assert result.returncode != 0
    assert "CANARY" not in result.stderr


def test_custom_tool_name_is_counted_but_not_disclosed(tmp_path: Path) -> None:
    path = tmp_path / "custom.log"
    path.write_text(
        "11:00:00 tool | -> CANARY_REQUEST_TOOL({})\n11:00:01 result | CANARY_RESULT_TOOL ok 0.1s: {}\n",
        encoding="utf-8",
    )
    result = run_cli("analyze", str(path), "--format", "json")
    report = json.loads(result.stdout)
    assert report["tool_request_count"] == 1
    assert report["tool_result_count"] == 1
    assert report["tool_ok_result_count"] == 1
    assert "CANARY" not in result.stdout


def test_unrecognized_terminal_marker_is_unknown(tmp_path: Path) -> None:
    path = tmp_path / "unknown.log"
    path.write_text("11:00:00 final | status=CANARY_PRIVATE_STATUS\n", encoding="utf-8")
    result = run_cli("analyze", str(path), "--format", "json")
    report = json.loads(result.stdout)
    assert report["terminal_status"] == "unknown"
    assert report["terminal_status_lines"] == [1]
    assert "CANARY" not in result.stdout
