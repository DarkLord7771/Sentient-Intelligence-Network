from __future__ import annotations

import json

from SINlite.contracts import validate_construct_state
from SINlite.core.sinlite_kernel import run_once
from SINlite.defaults import DEMO_FIXTURE_ROOT


FIXTURE_ROOT = DEMO_FIXTURE_ROOT


def load_payloads() -> dict:
    return json.loads((FIXTURE_ROOT / "kernel_inputs.json").read_text())


def test_io_matches_contract():
    payloads = load_payloads()

    construct_state, _ = run_once(payloads["baseline"])
    construct_state = validate_construct_state(construct_state)

    assert construct_state["mode"] == "AWAKE"
    assert construct_state["glyph"]
    assert construct_state["counter"] >= 1
    assert "narrative_hint" in construct_state
    assert 0 < len(construct_state["narrative_hint"]) <= 280
    guard = construct_state["ritual_silence_guard"]
    assert guard["engaged"] is False
    assert guard["heartbeat"] == 0
    assert guard["since_counter"] is None
