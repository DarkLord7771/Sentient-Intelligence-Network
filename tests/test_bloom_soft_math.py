from __future__ import annotations

import json
import math

import pytest

from SINlite.core import bloom
from SINlite.core import qdss_core
from SINlite.defaults import DEMO_FIXTURE_ROOT


FIXTURE_ROOT = DEMO_FIXTURE_ROOT


def load_payloads() -> dict:
    return json.loads((FIXTURE_ROOT / "kernel_inputs.json").read_text())


def _expected_probability(state: dict) -> float:
    construct = state["construct_state"]
    drift = abs(construct["drift"])
    timestamp = construct["timestamp"]
    chaos = state["chaos_sensitivity"]
    omega = state["wave_frequency"]
    phase = state["phase_offset"]

    cursor = bloom.time_cursor(timestamp)
    raw = math.exp(-chaos * drift ** 2) * math.cos(omega * cursor + phase)
    probability = 0.5 * (raw + 1.0)
    return round(max(0.0, min(1.0, probability)), 6)


def test_public_bloom_probability_tracks_soft_math():
    payloads = load_payloads()

    state = qdss_core.step(payloads["baseline"])
    assert state["bloom_probability"] == pytest.approx(
        _expected_probability(state), rel=1e-6
    )

    state = qdss_core.step(payloads["dreamlike"], state)
    assert state["bloom_probability"] == pytest.approx(
        _expected_probability(state), rel=1e-6
    )
    assert 0.0 <= state["bloom_probability"] <= 1.0
