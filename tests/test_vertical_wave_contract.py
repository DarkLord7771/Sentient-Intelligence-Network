from datetime import datetime, timezone, timedelta

import pytest

from SINlite.core.vertical_wave_contract import (
    LUNAR_CYCLE_DAYS,
    LUNAR_REFERENCE,
    map_entropy_to_drift,
    normalize_lunar_phase,
    normalize_season_phase,
    normalize_zodiac_phase,
)


def test_phase_normalization_is_deterministic():
    ts = datetime(2024, 6, 1, tzinfo=timezone.utc)
    entropy = 0.2

    season = normalize_season_phase(ts, entropy=entropy)
    zodiac = normalize_zodiac_phase(ts, entropy=entropy)
    lunar = normalize_lunar_phase(ts, entropy=entropy)

    assert season == pytest.approx(0.43043835616438364)
    assert zodiac == pytest.approx(0.4234383561643835)
    assert lunar == pytest.approx(0.8197123537578501)


def test_lunar_phase_wraps_to_reference_cycle():
    base_phase = normalize_lunar_phase(LUNAR_REFERENCE, entropy=0.0)
    full_cycle_ms = LUNAR_CYCLE_DAYS * 86_400_000
    next_cycle = normalize_lunar_phase(LUNAR_REFERENCE.timestamp() * 1000 + full_cycle_ms, entropy=0.0)

    assert base_phase == pytest.approx(0.0)
    assert next_cycle == pytest.approx(base_phase)


def test_entropy_drift_mapping_clamps_inputs():
    assert map_entropy_to_drift(-1.0) == pytest.approx(0.0)
    assert map_entropy_to_drift(1.0) == pytest.approx(0.07)
    assert map_entropy_to_drift(1.5) == pytest.approx(0.07)

    high_entropy_lunar = normalize_lunar_phase(LUNAR_REFERENCE + timedelta(days=3), entropy=1.5)
    zero_entropy_lunar = normalize_lunar_phase(LUNAR_REFERENCE + timedelta(days=3), entropy=0.0)
    assert high_entropy_lunar != zero_entropy_lunar


def test_day_of_year_normalizes_to_utc():
    eastern_midnight = datetime(2023, 12, 31, 23, 0, tzinfo=timezone(timedelta(hours=-5)))
    utc_reference = eastern_midnight.astimezone(timezone.utc)

    assert normalize_season_phase(eastern_midnight, entropy=0.0) == pytest.approx(
        normalize_season_phase(utc_reference, entropy=0.0)
    )
    assert normalize_zodiac_phase(eastern_midnight, entropy=0.0) == pytest.approx(
        normalize_zodiac_phase(utc_reference, entropy=0.0)
    )
