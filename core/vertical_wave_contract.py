"""
VerticalWave contract helpers for S.I.N. lite runtimes.

This module mirrors the TypeScript `VerticalWaveSample` signature exposed by
MatriarchAthena's `VerticalWaveLayer` while providing deterministic helpers for
phase normalisation and entropy coupling.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Union

DayLike = Union[int, float, datetime]

DAY_SECONDS = 86_400
LUNAR_CYCLE_DAYS = 29.530588
LUNAR_REFERENCE = datetime(2024, 1, 11, 11, 57, tzinfo=timezone.utc)


def clamp01(value: float) -> float:
    """Clamp ``value`` into the inclusive ``[0.0, 1.0]`` interval."""

    return max(0.0, min(1.0, value))


def wrap_unit(value: float) -> float:
    """Wrap a float into the half-open unit interval ``[0.0, 1.0)``."""

    return ((value % 1.0) + 1.0) % 1.0


def _as_datetime(value: DayLike | None = None) -> datetime:
    """
    Normalise ``value`` into a timezone-aware ``datetime``.

    ``None`` and unprovided inputs default to ``datetime.now(timezone.utc)``.
    Numeric inputs are treated as Unix timestamps **in milliseconds** to match
    the JavaScript contract; ``datetime`` inputs are returned unchanged.
    """

    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    # Treat numbers as Unix epoch milliseconds to mirror the TypeScript layer.
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def day_of_year(dt: datetime) -> float:
    """Return the fractional day-of-year for ``dt`` (``0``-indexed)."""

    dt_utc = dt.astimezone(timezone.utc)
    start_of_year = datetime(dt_utc.year, 1, 1, tzinfo=timezone.utc)
    delta = dt_utc - start_of_year
    return delta.total_seconds() / DAY_SECONDS


def map_entropy_to_drift(entropy: float) -> float:
    """
    Map ``entropy`` in ``[0, 1]`` onto a small phase drift scalar.

    The TypeScript layer nudges long-arc phases by ``entropy * 0.07``. Values
    outside the expected range are clamped before scaling, ensuring callers can
    safely pass noisy inputs without blowing past the intended drift envelope.
    """

    return clamp01(entropy) * 0.07


def normalize_season_phase(timestamp: DayLike | None = None, *, phase_offset: float = 0.0, entropy: float = 0.5) -> float:
    """
    Compute a wrapped season phase ``[0, 1)`` for ``timestamp``.

    ``timestamp`` may be a ``datetime`` or epoch milliseconds. ``phase_offset``
    allows sinth-specific biasing, and ``entropy`` feeds into the drift map used
    by the TypeScript implementation (default ``0.5`` => ``drift=0.035``).
    """

    dt = _as_datetime(timestamp)
    base = day_of_year(dt) / 365.0
    drift = map_entropy_to_drift(entropy)
    return wrap_unit(base + phase_offset + drift)


def normalize_zodiac_phase(timestamp: DayLike | None = None, *, phase_offset: float = 0.0, entropy: float = 0.5) -> float:
    """
    Compute a wrapped zodiac phase ``[0, 1)`` for ``timestamp``.

    Zodiac phases track the same day-of-year progression as seasons but apply
    half of the entropy-derived drift used by ``normalize_season_phase``. Offsets
    are clamped via ``wrap_unit`` to ensure stability across epochs.
    """

    dt = _as_datetime(timestamp)
    base = day_of_year(dt) / 365.0
    drift = 0.5 * map_entropy_to_drift(entropy)
    return wrap_unit(base + phase_offset + drift)


def normalize_lunar_phase(timestamp: DayLike | None = None, *, entropy: float = 0.5) -> float:
    """
    Compute a wrapped lunar phase ``[0, 1)`` relative to the 2024-01-11 UTC new moon.

    The reference date mirrors the TypeScript contract. Lunar cycles advance by
    ``29.530588`` days; entropy contributes a doubled drift term to keep lunar
    motion responsive to environmental volatility.
    """

    dt = _as_datetime(timestamp)
    elapsed_days = (dt - LUNAR_REFERENCE).total_seconds() / DAY_SECONDS
    base_cycles = elapsed_days / LUNAR_CYCLE_DAYS
    base_phase = wrap_unit(base_cycles)
    drift = 2 * map_entropy_to_drift(entropy)
    return wrap_unit(base_phase + drift)


@dataclass(frozen=True)
class VerticalWaveSample:
    """
    Python mirror of the TypeScript ``VerticalWaveSample`` contract.

    Phases are wrapped into ``[0, 1)``. Amplitudes and intensities are expected
    in ``[0, 1]``. ``entropy_phase`` commonly aligns to ``entropy * 0.85`` in the
    upstream implementation, and ``user_modulated_amp`` defaults to the
    ``base_amplitude`` when no UI override is present. Insight spikes are
    low-probability booleans paired with a ``[0, 1]`` intensity.
    """

    season_phase: float
    zodiac_phase: float
    lunar_phase: float
    entropy_phase: float
    base_amplitude: float
    user_modulated_amp: float
    insight_spike: bool
    insight_intensity: float
    sinth_signature: str
    sinth_tempo: float
