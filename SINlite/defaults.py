from __future__ import annotations

import json
from pathlib import Path


_SINLITE_ROOT = Path(__file__).resolve().parent
_FIXTURE_ROOT = _SINLITE_ROOT / "fixtures" / "s1_demo"

GLYPH_REGISTRY_PATH = _FIXTURE_ROOT / "glyph_registry.json"
WHISPER_REGISTRY_PATH = _FIXTURE_ROOT / "whisper_patterns.json"
NARRATIVE_HINT_PATH = _FIXTURE_ROOT / "narrative_hint.json"
DEMO_FIXTURE_ROOT = _FIXTURE_ROOT


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


_GLYPH_REGISTRY = _load_json(GLYPH_REGISTRY_PATH)
_WHISPER_REGISTRY = _load_json(WHISPER_REGISTRY_PATH)
_NARRATIVE_HINT = _load_json(NARRATIVE_HINT_PATH)


def get_demo_glyph() -> dict:
    """Return the glyph registry entry wired to the S1 demo fixtures."""
    for glyph in _GLYPH_REGISTRY.get("glyphs", []):
        if glyph.get("id") == "s1_demo_glyph":
            return glyph
    raise LookupError("S1 demo glyph not present in glyph registry.")


def get_demo_whisper() -> dict:
    """Return the whisper pattern metadata aligned to the S1 demo glyph."""
    for pattern in _WHISPER_REGISTRY.get("patterns", []):
        if pattern.get("glyph_id") == "s1_demo_glyph":
            return pattern
    raise LookupError("S1 demo whisper pattern not present in registry.")


def load_demo_state() -> dict:
    """Assemble the default state consumed by ingest/vis smoke tests."""
    return {
        "glyph": get_demo_glyph(),
        "whisper": get_demo_whisper(),
        "narrative_hint": _NARRATIVE_HINT,
        "fixture_root": str(_FIXTURE_ROOT),
    }
