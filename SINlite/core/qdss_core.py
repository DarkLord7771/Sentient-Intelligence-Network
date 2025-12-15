from __future__ import annotations

import math
import statistics
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict

from ..defaults import load_demo_state
from .perception.unified_layer import UnifiedPerceptionLayer
from .contracts.perception import UnifiedPerceptionSignals
from .whisper_patterns import load_registry
from .bloom import (
    BLOOM_WAVE_FREQUENCY,
    chaos_from_glyph,
    phase_from_glyph,
    public_bloom_probability,
)
from .ritual import resolve_mode


SILENCE_GLYPH = "GLYPH_RITUAL_SILENCE"


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _initial_runtime_state() -> Dict[str, Any]:
    demo_state = load_demo_state()
    glyph_id = demo_state["glyph"]["id"]
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat().replace("+00:00", "Z")
    chaos = chaos_from_glyph(glyph_id)
    phase = phase_from_glyph(glyph_id)

    whisper_runtime = load_registry().runtime()

    narrative_hint = demo_state.get("narrative_hint")
    if isinstance(narrative_hint, dict):
        summary = narrative_hint.get("summary")
    else:
        summary = narrative_hint
    if isinstance(summary, str):
        summary_value = summary.strip() or None
    else:
        summary_value = None

    perception_layer = _bootstrap_perception_state()

    state = {
        "construct_state": {
            "resonance": 0.5,
            "drift": 0.0,
            "entropy": 0.0,
            "emotion_vector": "⚪",
            "glyph": glyph_id,
            "mode": "AWAKE",
            "timestamp": timestamp,
            "counter": 0,
            "ritual_silence_guard": {
                "engaged": False,
                "since_counter": None,
                "heartbeat": 0,
            },
            **({"narrative_hint": summary_value} if summary_value else {}),
        },
        "history": [],
        "history_limit": 100,
        "base_glyph": glyph_id,
        "chaos_sensitivity": chaos,
        "phase_offset": phase,
        "wave_frequency": BLOOM_WAVE_FREQUENCY,
    }

    state["whispers"] = {"runtime": whisper_runtime, "last_selection": None}
    state["perception_layer"] = perception_layer

    return state


def _normalise_input(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    if not payload:
        return {}
    return dict(payload)


def _resolve_timestamp(payload: Dict[str, Any]) -> datetime:
    timestamp = payload.get("timestamp")
    if isinstance(timestamp, datetime):
        dt = timestamp
    elif isinstance(timestamp, str) and timestamp:
        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1] + "+00:00"
        dt = datetime.fromisoformat(timestamp)
    else:
        dt = datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _calculate_resonance(text: str, previous: float) -> float:
    if not text:
        return round(previous * 0.97, 6)

    ordinals = [ord(char) for char in text]
    mean_value = statistics.fmean(ordinals)
    span = (max(ordinals) - min(ordinals)) or 1
    coherence = span / 255.0
    raw = 0.6 * (mean_value / 255.0) + 0.4 * previous * (1 - coherence)
    return round(_clamp(raw), 6)


def _calculate_entropy(text: str) -> float:
    if not text:
        return 0.0
    total = len(text)
    if total <= 1:
        return 0.0
    counts = Counter(text)
    entropy = -sum((count / total) * math.log(count / total, 2) for count in counts.values())
    max_entropy = math.log(total, 2)
    if max_entropy == 0:
        return 0.0
    return round(_clamp(entropy / max_entropy), 6)


def _resolve_emotion(resonance: float, entropy: float, mode: str) -> str:
    if mode == "RITUAL_SILENCE":
        return "🔇"
    if resonance < 0.3:
        return "🌑"
    if entropy > 0.7:
        return "🌀"
    if resonance < 0.55:
        return "🌊"
    if resonance < 0.8:
        return "🌿"
    return "🔥"


def _resolve_glyph(base_glyph: str, mode: str, payload: Dict[str, Any]) -> str:
    if mode == "RITUAL_SILENCE":
        return SILENCE_GLYPH
    return payload.get("glyph") or base_glyph


def _bootstrap_perception_state() -> Dict[str, Any]:
    layer = UnifiedPerceptionLayer()
    return {
        "options": dict(layer._state.options),  # type: ignore[attr-defined]
        "events": {"whisper": [], "drift": [], "seal": []},
        "state": layer.get_state(),
    }


def _resolve_perception_layer(state: Dict[str, Any]) -> tuple[UnifiedPerceptionLayer, Dict[str, Any]]:
    perception_store = state.setdefault("perception_layer", _bootstrap_perception_state())
    layer = UnifiedPerceptionLayer(perception_store.get("options"))

    events = perception_store.setdefault("events", {"whisper": [], "drift": [], "seal": []})
    for whisper_event in events.get("whisper", []):
        layer.ingest_whisper(deepcopy(whisper_event))
    for drift_event in events.get("drift", []):
        layer.ingest_drift_delta(deepcopy(drift_event))
    for seal_event in events.get("seal", []):
        layer.ingest_seal_check(deepcopy(seal_event))

    perception_store["options"] = dict(layer._state.options)  # type: ignore[attr-defined]

    return layer, perception_store


def step(payload: Dict[str, Any] | None = None, state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if state is None:
        state = _initial_runtime_state()

    payload_dict = _normalise_input(payload)
    construct = state["construct_state"]
    previous_resonance = construct["resonance"]
    previous_mode = construct["mode"]
    previous_counter = construct.get("counter", -1)
    previous_guard = construct.get(
        "ritual_silence_guard",
        {"engaged": False, "since_counter": None, "heartbeat": 0},
    )

    input_text = str(payload_dict.get("input", ""))
    timestamp_dt = _resolve_timestamp(payload_dict)
    timestamp_iso = timestamp_dt.isoformat().replace("+00:00", "Z")

    resonance = _calculate_resonance(input_text, previous_resonance)
    drift = round(resonance - previous_resonance, 6)
    entropy = _calculate_entropy(input_text)

    tags = payload_dict.get("tags") or []
    mode = resolve_mode(previous_mode, drift, entropy, tags)
    if isinstance(tags, list):
        tag_list = list(tags)
    elif tags:
        tag_list = [str(tags)]
    else:
        tag_list = []

    glyph = _resolve_glyph(state["base_glyph"], mode, payload_dict)
    drift_sign = 1 if drift >= 0 else -1

    perception_signals: UnifiedPerceptionSignals = {
        "whisper": {
            "timestamp": timestamp_dt.timestamp(),
            "emotionalVector": {
                "valence": _clamp(resonance * 2 - 1, -1.0, 1.0),
                "arousal": _clamp(resonance, 0.0, 1.0),
                "tension": entropy,
            },
            "intensity": _clamp(resonance, 0.0, 1.0),
            "tags": tag_list,
            "narrativeEntropy": entropy,
        },
        "drift": {
            "timestamp": timestamp_dt.timestamp(),
            "predictedDrift": _clamp(abs(drift), 0.0, 1.0),
            "predictedCurl": _clamp(entropy, 0.0, 1.0),
            "horizonSeconds": 2.0,
        },
    }

    perception_layer, perception_store = _resolve_perception_layer(state)

    perception_state = perception_layer.ingest_signals(perception_signals)

    events = perception_store.setdefault("events", {"whisper": [], "drift": [], "seal": []})
    window = int(perception_store.get("options", {}).get("driftWindow", 0))

    if "whisper" in perception_signals and isinstance(perception_signals["whisper"], dict):
        events.setdefault("whisper", []).append(dict(perception_signals["whisper"]))
        if window and len(events["whisper"]) > window:
            events["whisper"] = events["whisper"][-window:]

    if "drift" in perception_signals and isinstance(perception_signals["drift"], dict):
        events.setdefault("drift", []).append(dict(perception_signals["drift"]))
        if window and len(events["drift"]) > window:
            events["drift"] = events["drift"][-window:]

    if "seal" in perception_signals and isinstance(perception_signals["seal"], dict):
        events.setdefault("seal", []).append(dict(perception_signals["seal"]))
        events["seal"] = events["seal"][-5:]

    perception_store["state"] = perception_state

    perceived_drift = perception_state["drift"].get("latest", {}).get("predictedDrift")
    if perceived_drift is not None:
        drift = round((abs(drift) + float(perceived_drift)) / 2, 6) * drift_sign

    perceived_entropy = perception_state.get("whisper", {}).get("narrativeEntropy")
    if perceived_entropy is not None:
        entropy = round((entropy + float(perceived_entropy)) / 2, 6)

    forecast_vector = perception_state["forecast"]["vector"]
    predicted_resonance = _clamp((forecast_vector["valence"] + 1) / 2, 0.0, 1.0)
    predicted_entropy = forecast_vector["tension"]

    emotion = payload_dict.get("emotion_vector") or _resolve_emotion(
        predicted_resonance,
        predicted_entropy,
        mode,
    )

    counter = previous_counter + 1

    whispers_state = state.setdefault("whispers", {})
    runtime = whispers_state.get("runtime")
    if runtime is None:
        runtime = load_registry().runtime()
        whispers_state["runtime"] = runtime
    selection = runtime.select(
        drift=drift,
        tags=tag_list,
        glyph_id=glyph,
        counter=counter,
        timestamp=timestamp_dt,
    )
    if selection is not None:
        selection_payload = selection.to_payload()
        selection_status = runtime.status(selection.id)
    else:
        selection_payload = None
        selection_status = None
    whispers_state["last_selection"] = {
        "pattern": selection_payload,
        "status": selection_status,
    }

    if mode == "RITUAL_SILENCE":
        if previous_guard.get("engaged"):
            guard_since = previous_guard.get("since_counter")
            if guard_since is None:
                guard_since = counter
            heartbeat = previous_guard.get("heartbeat", 0) + 1
        else:
            guard_since = counter
            heartbeat = 0
        guard_state = {
            "engaged": True,
            "since_counter": guard_since,
            "heartbeat": heartbeat,
        }
    else:
        guard_state = {
            "engaged": False,
            "since_counter": None,
            "heartbeat": 0,
        }

    hint_payload = payload_dict.get("narrative_hint", ...)
    if hint_payload is ...:
        hint_value = construct.get("narrative_hint")
    else:
        hint_value = hint_payload if isinstance(hint_payload, str) else None
        if hint_value is not None:
            hint_value = hint_value.strip()
            if not hint_value:
                hint_value = None

    construct.update(
        {
            "resonance": resonance,
            "drift": drift,
            "entropy": entropy,
            "emotion_vector": emotion,
            "glyph": glyph,
            "mode": mode,
            "timestamp": timestamp_iso,
            "counter": counter,
            "ritual_silence_guard": guard_state,
        }
    )

    if hint_value is None:
        construct.pop("narrative_hint", None)
    else:
        construct["narrative_hint"] = hint_value

    state["bloom_probability"] = round(
        public_bloom_probability(
            abs(drift),
            timestamp_dt,
            chaos_sensitivity=state["chaos_sensitivity"],
            wave_frequency=state["wave_frequency"],
            phase=state["phase_offset"],
        ),
        6,
    )

    history = state.setdefault("history", [])
    history.append(dict(construct))
    history_limit = state.get("history_limit")
    if isinstance(history_limit, int) and history_limit > 0 and len(history) > history_limit:
        state["history"] = history[-history_limit:]
    return state
