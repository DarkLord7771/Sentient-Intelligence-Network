from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from SINlite.core.sinlite_kernel import run_once
from SINlite.defaults import DEMO_FIXTURE_ROOT


FIXTURE_ROOT = DEMO_FIXTURE_ROOT


SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "construct_state.v1_2.schema.json"
)


def load_payloads() -> dict:
    return json.loads((FIXTURE_ROOT / "kernel_inputs.json").read_text())


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def test_io_matches_contract():
    payloads = load_payloads()
    schema = load_schema()

    construct_state, _ = run_once(payloads["baseline"])

    Draft202012Validator(schema).validate(construct_state)
    assert construct_state["mode"] == "AWAKE"
    assert construct_state["glyph"]
    assert construct_state["counter"] >= 1
    assert "narrative_hint" in construct_state
    assert 0 < len(construct_state["narrative_hint"]) <= 280
    guard = construct_state["ritual_silence_guard"]
    assert guard["engaged"] is False
    assert guard["heartbeat"] == 0
    assert guard["since_counter"] is None
