from __future__ import annotations

from datetime import datetime, timedelta, timezone

from SINlite.core.whisper_patterns import WhisperPatternRegistry


def _counter_registry() -> WhisperPatternRegistry:
    payload = {
        "patterns": [
            {
                "id": "counter_guard",
                "glyph_id": "s1_demo_glyph",
                "pattern_path": "fixtures/s1_demo/audio_reference.json",
                "pattern_checksum": "sha256:3f7f4a1c72b4d45160d98d0b8ab09f9c7dd27e98b452edca2697b32f9bfd6d9a",
                "loop": False,
                "selectors": {"tags_any": ["demo"]},
                "cooldown": {"counters": 2},
                "max_per_session": 3,
            }
        ]
    }
    return WhisperPatternRegistry.from_payload(payload)


def _seconds_registry() -> WhisperPatternRegistry:
    payload = {
        "patterns": [
            {
                "id": "temporal_guard",
                "glyph_id": "s1_demo_glyph",
                "pattern_path": "fixtures/s1_demo/audio_reference.json",
                "pattern_checksum": "sha256:3f7f4a1c72b4d45160d98d0b8ab09f9c7dd27e98b452edca2697b32f9bfd6d9a",
                "loop": True,
                "selectors": {"tags_any": ["calibrate"]},
                "cooldown": {"seconds": 5.0},
                "max_per_session": 2,
            }
        ]
    }
    return WhisperPatternRegistry.from_payload(payload)


def test_counter_cooldown_enforces_gap() -> None:
    registry = _counter_registry()
    runtime = registry.runtime()

    first = runtime.select(
        drift=0.1,
        tags=["demo"],
        glyph_id="s1_demo_glyph",
        counter=10,
        timestamp=None,
    )
    assert first is not None

    second = runtime.select(
        drift=0.1,
        tags=["demo"],
        glyph_id="s1_demo_glyph",
        counter=11,
        timestamp=None,
    )
    assert second is None

    third = runtime.select(
        drift=0.1,
        tags=["demo"],
        glyph_id="s1_demo_glyph",
        counter=12,
        timestamp=None,
    )
    assert third is not None
    assert third.id == first.id


def test_seconds_cooldown_requires_delay() -> None:
    registry = _seconds_registry()
    runtime = registry.runtime()

    base = datetime(2024, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

    first = runtime.select(
        drift=0.0,
        tags=["calibrate"],
        glyph_id="s1_demo_glyph",
        counter=0,
        timestamp=base,
    )
    assert first is not None

    blocked = runtime.select(
        drift=0.0,
        tags=["calibrate"],
        glyph_id="s1_demo_glyph",
        counter=1,
        timestamp=base + timedelta(seconds=2),
    )
    assert blocked is None

    released = runtime.select(
        drift=0.0,
        tags=["calibrate"],
        glyph_id="s1_demo_glyph",
        counter=2,
        timestamp=base + timedelta(seconds=5),
    )
    assert released is not None
    assert released.id == first.id


def test_max_per_session_caps_usage() -> None:
    registry = _counter_registry()
    runtime = registry.runtime()

    assert runtime.select(drift=0.2, tags=["demo"], glyph_id="s1_demo_glyph", counter=0, timestamp=None)
    assert runtime.select(drift=0.2, tags=["demo"], glyph_id="s1_demo_glyph", counter=2, timestamp=None)
    assert runtime.select(drift=0.2, tags=["demo"], glyph_id="s1_demo_glyph", counter=4, timestamp=None)

    capped = runtime.select(
        drift=0.2,
        tags=["demo"],
        glyph_id="s1_demo_glyph",
        counter=6,
        timestamp=None,
    )
    assert capped is None

    runtime.reset()
    recovered = runtime.select(
        drift=0.2,
        tags=["demo"],
        glyph_id="s1_demo_glyph",
        counter=0,
        timestamp=None,
    )
    assert recovered is not None
