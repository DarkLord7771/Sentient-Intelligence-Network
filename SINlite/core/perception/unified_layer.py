"""Minimal UnifiedPerceptionLayer implementation for SINlite runtime hooks."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any, Dict, Mapping, MutableMapping


class UnifiedPerceptionLayer:
    """Capture perception events and expose a stable state interface."""

    def __init__(self, options: Mapping[str, Any] | None = None):
        default_options: Dict[str, Any] = {"driftWindow": 0, "whisperWindow": 0, "sealWindow": 0}
        resolved = dict(default_options)
        if options:
            resolved.update({k: v for k, v in options.items() if v is not None})
        self._state = SimpleNamespace(
            options=resolved,
            events={"whisper": [], "drift": [], "seal": []},
            drift={"latest": {}},
            whisper={},
            forecast={"vector": {"valence": 0.0, "arousal": 0.0, "tension": 0.0}},
        )

    def ingest_whisper(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        whisper_payload = deepcopy(dict(payload))
        self._state.events.setdefault("whisper", []).append(whisper_payload)
        self._state.whisper = whisper_payload
        emotional_vector = whisper_payload.get("emotionalVector") or {}
        self._state.forecast["vector"] = {
            "valence": float(emotional_vector.get("valence", 0.0)),
            "arousal": float(emotional_vector.get("arousal", 0.0)),
            "tension": float(emotional_vector.get("tension", whisper_payload.get("narrativeEntropy", 0.0))),
        }
        return self.get_state()

    def ingest_drift_delta(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        drift_payload = deepcopy(dict(payload))
        self._state.events.setdefault("drift", []).append(drift_payload)
        self._state.drift = {"latest": drift_payload}
        return self.get_state()

    def ingest_seal_check(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        self._state.events.setdefault("seal", []).append(deepcopy(dict(payload)))
        return self.get_state()

    def ingest_signals(self, signals: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
        if whisper := signals.get("whisper"):
            self.ingest_whisper(whisper)
        if drift := signals.get("drift"):
            self.ingest_drift_delta(drift)
        if seal := signals.get("seal"):
            self.ingest_seal_check(seal)
        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        events_copy: MutableMapping[str, list[Mapping[str, Any]]] = {
            key: [deepcopy(entry) for entry in value]
            for key, value in self._state.events.items()
        }
        return {
            "options": dict(self._state.options),
            "events": events_copy,
            "drift": deepcopy(self._state.drift),
            "whisper": deepcopy(self._state.whisper),
            "forecast": deepcopy(self._state.forecast),
        }
