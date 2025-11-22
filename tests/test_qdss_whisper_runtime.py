from __future__ import annotations

from datetime import datetime, timedelta, timezone

from SINlite.core import qdss_core
from SINlite.core.whisper_patterns import WhisperPatternRegistry


def _demo_registry() -> WhisperPatternRegistry:
    payload = {
        "patterns": [
            {
                "id": "demo_guard",
                "glyph_id": "s1_demo_glyph",
                "pattern_path": "fixtures/s1_demo/audio_reference.json",
                "pattern_checksum": "sha256:3f7f4a1c72b4d45160d98d0b8ab09f9c7dd27e98b452edca2697b32f9bfd6d9a",
                "loop": False,
                "selectors": {"tags_any": ["demo"]},
                "cooldown": {"counters": 2},
            }
        ]
    }
    return WhisperPatternRegistry.from_payload(payload)


def test_step_records_whisper_selection_and_cooldown(monkeypatch) -> None:
    registry = _demo_registry()
    monkeypatch.setattr(qdss_core, "load_registry", lambda: registry)

    base_timestamp = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    first_state = qdss_core.step(
        {"input": "awaken", "tags": ["demo"], "timestamp": base_timestamp.isoformat()},
        None,
    )

    whispers = first_state["whispers"]
    runtime = whispers["runtime"]
    assert whispers["last_selection"]["pattern"]["id"] == "demo_guard"
    status = whispers["last_selection"]["status"]
    assert status["session_count"] == 1
    assert status["last_counter"] == first_state["construct_state"]["counter"]

    second_state = qdss_core.step(
        {
            "input": "awaken again",
            "tags": ["demo"],
            "timestamp": (base_timestamp + timedelta(seconds=1)).isoformat(),
        },
        first_state,
    )

    follow_up_whispers = second_state["whispers"]
    assert follow_up_whispers["runtime"] is runtime
    assert follow_up_whispers["last_selection"]["pattern"] is None
    assert follow_up_whispers["last_selection"]["status"] is None
    assert runtime.status("demo_guard")["session_count"] == 1
