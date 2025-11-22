"""Integration tests for the SINlite CLI flows."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI_MODULE = "SINlite.cli"
WHISPER_REGISTRY = PROJECT_ROOT / "SINlite" / "whisper" / "whisper_patterns.json"


def _run_cli_command(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    pythonpath_parts = [str(PROJECT_ROOT)]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    return subprocess.run(
        [sys.executable, "-m", CLI_MODULE, *args],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_seal_generates_keys_and_envelope(tmp_path: Path) -> None:
    payload_path = tmp_path / "payload.json"
    payload_data = {"input": "cli sealing", "tags": ["test", "cli"]}
    payload_path.write_text(json.dumps(payload_data, sort_keys=True), encoding="utf-8")
    sealed_path = tmp_path / "payload.sealed.json"

    _run_cli_command(tmp_path, "seal", str(payload_path), "--output", str(sealed_path))

    assert sealed_path.exists()
    envelope = json.loads(sealed_path.read_text(encoding="utf-8"))
    assert envelope["payload"] == payload_data
    assert isinstance(envelope["sig"], str)
    assert isinstance(envelope["monotonic"], int)

    signing_key_path = tmp_path / "state" / "signing_key.ed25519"
    verify_key_path = tmp_path / "state" / "verify_key.ed25519"
    assert signing_key_path.exists()
    assert verify_key_path.exists()
    assert signing_key_path.read_text(encoding="utf-8").strip()
    assert verify_key_path.read_text(encoding="utf-8").strip()


def test_cli_run_demo_persists_construct_state(tmp_path: Path) -> None:
    result = _run_cli_command(tmp_path, "run", "--demo", "--as-json")
    construct_state = json.loads(result.stdout)
    assert construct_state["counter"] == 1

    log_path = tmp_path / "state" / "construct_state.jsonl"
    assert log_path.exists()
    log_lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert log_lines
    log_state = json.loads(log_lines[-1])
    assert log_state["counter"] == construct_state["counter"]
    assert log_state["mode"] == construct_state["mode"]


def test_cli_run_envelope_verifies_payload(tmp_path: Path) -> None:
    payload_path = tmp_path / "demo.json"
    payload_data = {"input": "sealed demo"}
    payload_path.write_text(json.dumps(payload_data, sort_keys=True), encoding="utf-8")
    envelope_path = tmp_path / "demo.sealed.json"
    _run_cli_command(tmp_path, "seal", str(payload_path), "--output", str(envelope_path))

    verify_key_path = tmp_path / "state" / "verify_key.ed25519"
    result = _run_cli_command(
        tmp_path,
        "run",
        "--envelope",
        str(envelope_path),
        "--verify-key",
        str(verify_key_path),
        "--as-json",
    )
    construct_state = json.loads(result.stdout)
    assert construct_state["counter"] == 1

    log_path = tmp_path / "state" / "construct_state.jsonl"
    log_lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(log_lines) == 1
    log_state = json.loads(log_lines[0])
    assert log_state == construct_state


def test_cli_whisper_list_outputs_json(tmp_path: Path) -> None:
    result = _run_cli_command(
        tmp_path,
        "whisper",
        "--registry",
        str(WHISPER_REGISTRY),
        "list",
        "--as-json",
        "--sort-keys",
    )

    patterns = json.loads(result.stdout)
    assert isinstance(patterns, list)
    assert [pattern["id"] for pattern in patterns] == ["s1_demo_whisper", "s1_demo_whisper_stable"]


def test_cli_whisper_list_human_output(tmp_path: Path) -> None:
    result = _run_cli_command(
        tmp_path,
        "whisper",
        "--registry",
        str(WHISPER_REGISTRY),
        "list",
    )

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert lines
    assert lines[0].startswith("s1_demo_whisper")
    assert any("s1_demo_whisper_stable" in line for line in lines)


def test_cli_whisper_demo_records_selection(tmp_path: Path) -> None:
    inputs_path = tmp_path / "whisper_inputs.jsonl"
    inputs = [
        {"drift": 0.1, "tags": ["demo"], "glyph_id": "s1_demo_glyph", "counter": 0},
        {"drift": 0.01, "tags": ["calibrate"], "glyph_id": "s1_demo_glyph", "counter": 1},
    ]
    inputs_path.write_text("\n".join(json.dumps(line) for line in inputs), encoding="utf-8")

    result = _run_cli_command(
        tmp_path,
        "whisper",
        "--registry",
        str(WHISPER_REGISTRY),
        "demo",
        str(inputs_path),
        "--sort-keys",
    )

    traces = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert len(traces) == len(inputs)

    first_selection = traces[0]["selected"]
    assert first_selection["pattern"]["id"] == "s1_demo_whisper"
    assert first_selection["state"]["session_count"] == 1
    assert first_selection["state"]["last_counter"] == 0

    second_selection = traces[1]["selected"]
    assert second_selection["pattern"]["id"] == "s1_demo_whisper_stable"
    assert second_selection["state"]["session_count"] == 1
