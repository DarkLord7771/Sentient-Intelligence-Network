from __future__ import annotations

import json

import pytest

from SINlite.core.soft_bloom_export import export_soft_bloom
from SINlite.defaults import DEMO_FIXTURE_ROOT


FIXTURE_ROOT = DEMO_FIXTURE_ROOT


def load_payloads() -> dict:
    return json.loads((FIXTURE_ROOT / "kernel_inputs.json").read_text())


def test_soft_bloom_export_includes_hint_and_probability() -> None:
    payloads = load_payloads()

    export, state = export_soft_bloom(payloads["baseline"])

    assert export["glyph"] == state["construct_state"]["glyph"]
    assert export["p_bloom"] == state["bloom_probability"]
    assert 0.0 <= export["p_bloom"] <= 1.0
    assert export["narrative_hint"]
    assert len(export["narrative_hint"]) <= 280


def test_soft_bloom_export_rejects_unlisted_glyph() -> None:
    payloads = load_payloads()
    tampered = dict(payloads["baseline"], glyph="intruder_glyph")

    with pytest.raises(ValueError):
        export_soft_bloom(tampered)


def test_soft_bloom_export_rejects_hint_out_of_bounds() -> None:
    payloads = load_payloads()
    long_hint = "a" * 400

    with pytest.raises(ValueError):
        export_soft_bloom(dict(payloads["baseline"], narrative_hint=long_hint))
