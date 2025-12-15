from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

from SINlite import defaults

from .qdss_core import SILENCE_GLYPH, step


_HINT_MIN_LENGTH = 1
_HINT_MAX_LENGTH = 280


def _coerce_payload(payload: Any) -> Mapping[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, Mapping):
        return payload
    if isinstance(payload, str):
        return json.loads(payload)
    raise TypeError(
        "export_soft_bloom payload must be a mapping, a JSON string, or None."
    )


def _registry_path() -> Path:
    return defaults.GLYPH_REGISTRY_PATH


def _load_allowed_glyphs() -> set[str]:
    try:
        with _registry_path().open("r", encoding="utf-8") as handle:
            registry = json.load(handle)
    except FileNotFoundError:
        registry = {}

    glyphs = {
        str(entry["id"])
        for entry in registry.get("glyphs", [])
        if isinstance(entry, Mapping) and isinstance(entry.get("id"), str)
    }
    glyphs.add(SILENCE_GLYPH)
    return glyphs


_ALLOWED_GLYPHS = _load_allowed_glyphs()


def _validate_glyph(glyph: Any) -> str:
    if not isinstance(glyph, str):
        raise TypeError("Construct glyph must be a string.")
    glyph_id = glyph.strip()
    if not glyph_id:
        raise ValueError("Construct glyph cannot be empty.")
    if glyph_id not in _ALLOWED_GLYPHS:
        raise ValueError(f"Glyph '{glyph_id}' is not exportable.")
    return glyph_id


def _validate_probability(probability: Any) -> float:
    if not isinstance(probability, (int, float)):
        raise TypeError("Bloom probability must be numeric.")
    value = float(probability)
    if not (0.0 <= value <= 1.0):
        raise ValueError("Bloom probability must be between 0.0 and 1.0.")
    return round(value, 6)


def _validate_hint(hint: Any) -> str | None:
    if hint is None:
        return None
    if not isinstance(hint, str):
        raise TypeError("Narrative hint must be a string when provided.")
    trimmed = hint.strip()
    if len(trimmed) < _HINT_MIN_LENGTH:
        raise ValueError("Narrative hint cannot be empty.")
    if len(trimmed) > _HINT_MAX_LENGTH:
        raise ValueError(
            f"Narrative hint exceeds {_HINT_MAX_LENGTH} characters (got {len(trimmed)})."
        )
    return trimmed


def export_soft_bloom(
    payload: Any = None,
    state: Dict[str, Any] | None = None,
    *,
    include_narrative_hint: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    payload_mapping = _coerce_payload(payload)
    runtime_state = step(payload_mapping, state)

    construct = runtime_state["construct_state"]
    glyph_id = _validate_glyph(construct.get("glyph"))
    probability = _validate_probability(runtime_state.get("bloom_probability"))

    export: Dict[str, Any] = {"glyph": glyph_id, "p_bloom": probability}

    hint = construct.get("narrative_hint") if include_narrative_hint else None
    validated_hint = _validate_hint(hint)
    if validated_hint is not None:
        export["narrative_hint"] = validated_hint
        construct["narrative_hint"] = validated_hint
    else:
        construct.pop("narrative_hint", None)

    return export, runtime_state
