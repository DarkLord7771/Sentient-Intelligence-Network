from __future__ import annotations

import pytest
from jsonschema import ValidationError

from SINlite.core.whisper_patterns import WhisperPatternRegistry, load_registry


def test_default_registry_satisfies_schema() -> None:
    registry = load_registry()
    assert registry.patterns
    ids = {pattern.id for pattern in registry.patterns}
    assert "s1_demo_whisper" in ids


def test_invalid_pattern_payload_raises_validation_error() -> None:
    payload = {
        "patterns": [
            {
                "id": "invalid",
                "glyph_id": "s1_demo_glyph",
                "pattern_path": "fixtures/s1_demo/audio_reference.json",
                "loop": True,
                "pattern_checksum": "sha256:3f7f4a1c72b4d45160d98d0b8ab09f9c7dd27e98b452edca2697b32f9bfd6d9a",
                "cooldown": {},
            }
        ]
    }

    with pytest.raises(ValidationError):
        WhisperPatternRegistry.from_payload(payload)


def test_registry_can_skip_validation() -> None:
    payload = {
        "patterns": [
            {
                "id": "invalid",
                "glyph_id": "s1_demo_glyph",
                "pattern_path": "fixtures/s1_demo/audio_reference.json",
                "loop": True,
                "pattern_checksum": "not-a-valid-digest",
            }
        ]
    }

    registry = WhisperPatternRegistry.from_payload(payload, validate=False)
    assert registry.patterns[0].id == "invalid"
