from __future__ import annotations

import json
from pathlib import Path

from SINlite.contracts import (
    apply_roadmap_redaction,
    serialize_construct_state,
    serialize_sin_event,
    serialize_visual_manifest,
)
from SINlite.core.sinlite_kernel import run_once
from SINlite.defaults import DEMO_FIXTURE_ROOT


_SAMPLE_ROOT = Path(__file__).resolve().parents[2] / "contracts" / "samples"


def _load_sample(name: str) -> dict:
    return json.loads((_SAMPLE_ROOT / name).read_text())


def test_kernel_output_validates_against_contract():
    payloads = json.loads((DEMO_FIXTURE_ROOT / "kernel_inputs.json").read_text())

    construct_state, _ = run_once(payloads["baseline"])
    validated = serialize_construct_state(construct_state)

    assert validated["mode"] == "AWAKE"
    assert validated["glyph"]


def test_sample_sin_event_roundtrip_and_redaction():
    sample = _load_sample("sample_sin_event.json")

    validated = serialize_sin_event(sample)
    redacted = apply_roadmap_redaction(validated)

    assert "quat_state" in validated
    assert "quat_state" not in redacted
    assert "face_profile" not in redacted
    assert redacted["event_id"] == sample["event_id"]


def test_visual_manifest_roundtrip_matches_contract():
    manifest = _load_sample("sample_visual_manifest.json")

    validated = serialize_visual_manifest(manifest)

    assert validated["scene_id"] == manifest["scene_id"]
    assert validated["facial_clip"]["profile"] == manifest["facial_clip"]["profile"]
