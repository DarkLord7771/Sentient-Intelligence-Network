from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Union

TimestampLike = Union[str, datetime]


BLOOM_ALPHA = 0.45
BLOOM_WAVE_FREQUENCY = 0.85


def normalise_timestamp(value: TimestampLike | None) -> datetime:
    """Return an aware UTC ``datetime`` from diverse timestamp inputs."""

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value:
        # ``datetime.fromisoformat`` cannot parse the trailing ``Z`` marker
        # so we normalise before parsing.
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
    else:
        dt = datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def time_cursor(value: TimestampLike | None) -> float:
    """Map a timestamp onto a minute-resolution VerticalWave cursor."""

    dt = normalise_timestamp(value)
    midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return (dt - midnight).total_seconds() / 60.0


def chaos_from_glyph(glyph: str) -> float:
    """Derive a deterministic chaos sensitivity (α) from a glyph id."""

    if not glyph:
        return BLOOM_ALPHA
    glyph_value = sum(ord(char) for char in glyph)
    normalised = (glyph_value % 1000) / 1000.0
    return 0.3 + 0.4 * normalised


def phase_from_glyph(glyph: str) -> float:
    """Derive a deterministic VerticalWave phase offset from a glyph id."""

    if not glyph:
        return 0.0
    glyph_value = sum(ord(char) for char in glyph)
    return math.radians(glyph_value % 360)


def public_bloom_probability(
    drift: float,
    timestamp: TimestampLike | None,
    *,
    chaos_sensitivity: float = BLOOM_ALPHA,
    wave_frequency: float = BLOOM_WAVE_FREQUENCY,
    phase: float = 0.0,
) -> float:
    """Compute the public-facing bloom probability."""

    cursor = time_cursor(timestamp)
    damping = math.exp(-chaos_sensitivity * float(drift) ** 2)
    oscillation = math.cos(wave_frequency * cursor + phase)
    probability = 0.5 * (damping * oscillation + 1.0)
    return max(0.0, min(1.0, probability))
