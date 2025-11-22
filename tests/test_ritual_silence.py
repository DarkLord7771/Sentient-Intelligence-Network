from __future__ import annotations

import json

from SINlite.core.sinlite_kernel import run_once
from SINlite.defaults import DEMO_FIXTURE_ROOT


FIXTURE_ROOT = DEMO_FIXTURE_ROOT


def load_payloads() -> dict:
    return json.loads((FIXTURE_ROOT / "kernel_inputs.json").read_text())


def test_mode_transitions_through_ritual_silence():
    payloads = load_payloads()

    construct_state, runtime_state = run_once(payloads["baseline"])
    assert construct_state["mode"] == "AWAKE"
    baseline_counter = construct_state["counter"]

    construct_state, runtime_state = run_once(payloads["noisy"], runtime_state)
    assert construct_state["mode"] == "RITUAL_SILENCE"
    assert construct_state["glyph"] == "GLYPH_RITUAL_SILENCE"
    silence_counter = construct_state["counter"]
    assert silence_counter == baseline_counter + 1
    guard = construct_state["ritual_silence_guard"]
    assert guard["engaged"] is True
    assert guard["since_counter"] == silence_counter
    assert guard["heartbeat"] == 0

    construct_state, runtime_state = run_once(payloads["noisy"], runtime_state)
    assert construct_state["mode"] == "RITUAL_SILENCE"
    guard_repeat = construct_state["ritual_silence_guard"]
    assert guard_repeat["engaged"] is True
    assert guard_repeat["since_counter"] == silence_counter
    assert guard_repeat["heartbeat"] == guard["heartbeat"] + 1

    construct_state, runtime_state = run_once(payloads["recovery"], runtime_state)
    assert construct_state["mode"] == "AWAKE"
    assert construct_state["glyph"] != "GLYPH_RITUAL_SILENCE"
    assert construct_state["counter"] == guard_repeat["since_counter"] + 2
    guard_released = construct_state["ritual_silence_guard"]
    assert guard_released["engaged"] is False
    assert guard_released["heartbeat"] == 0
    assert guard_released["since_counter"] is None
