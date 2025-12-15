"""Tests for the `SINlite.dream_baseline` helper."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI_MODULE = "SINlite.dream_baseline"


def _dump_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _run_baseline_cli(tmp_path: Path, dataset_root: Path, cache_path: Path) -> str:
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    pythonpath_parts = [str(PROJECT_ROOT)]
    if pythonpath:
        pythonpath_parts.append(pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            CLI_MODULE,
            "--dataset-root",
            str(dataset_root),
            "--cache",
            str(cache_path),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def test_dream_baseline_cache_includes_latest_snapshot(tmp_path: Path) -> None:
    dataset_root = tmp_path / "dream_export"
    dataset_root.mkdir()

    old_pack = dataset_root / "pack-alpha"
    old_meta = old_pack / "json_meta"
    old_meta.mkdir(parents=True)
    old_symbolic = old_meta / "symbolic_drift.json"
    _dump_json(old_symbolic, [{"tick": 0, "density": 0.1, "activeIndices": [0]}])

    new_pack = dataset_root / "pack-beta"
    new_meta = new_pack / "json_meta"
    new_meta.mkdir(parents=True)
    new_symbolic = new_meta / "symbolic_drift.json"
    new_entries = [
        {
            "tick": 1,
            "density": 0.12,
            "activeIndices": [0, 1, 1],
            "sceneTags": ["primed"],
            "glyph": "glyph-prime",
        },
        {
            "tick": 4,
            "density": 0.45,
            "activeIndices": [2, 3],
            "sceneTags": ["mid"],
        },
        {
            "tick": 7,
            "sparsity": {"density": 0.9, "active_indices": [3, 5, 5]},
        },
    ]
    _dump_json(new_symbolic, new_entries)

    narrative_path = new_meta / "narrative.json"
    _dump_json(
        narrative_path,
        {
            "scenes": [
                {"startTick": 0, "endTick": 3, "label": "intro", "tags": ["loom"]},
                {
                    "startTick": 4,
                    "endTick": 10,
                    "name": "ascent",
                    "sceneTags": ["flare", "rise"],
                },
            ]
        },
    )

    now = time.time()
    os.utime(old_symbolic, (now - 60, now - 60))
    os.utime(new_symbolic, (now, now))

    cache_path = tmp_path / "state" / "dream_baseline.json"
    result_path = _run_baseline_cli(tmp_path, dataset_root, cache_path)

    assert Path(result_path).resolve() == cache_path.resolve()
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert Path(payload["source"]).resolve() == new_pack.resolve()

    samples = payload["samples"]
    expected_ticks = [1, 4, 7]
    assert [sample["tick"] for sample in samples] == expected_ticks
    assert payload["ticks"] == len(expected_ticks)

    expected_scene_tags_by_tick = {
        1: ["intro", "loom", "primed"],
        4: ["ascent", "flare", "mid", "rise"],
        7: ["ascent", "flare", "rise"],
    }
    expected_densities = {1: 0.12, 4: 0.45, 7: 0.9}
    expected_active_indices = {1: [0, 1], 4: [2, 3], 7: [3, 5]}
    all_expected_scenes = sorted(
        tag for tags in expected_scene_tags_by_tick.values() for tag in tags
    )
    assert payload["scenes"] == sorted(set(all_expected_scenes))

    for sample in samples:
        tick = sample["tick"]
        assert sample["sceneTags"] == expected_scene_tags_by_tick[tick]
        assert sample["density"] == expected_densities[tick]
        assert sample["activeIndices"] == expected_active_indices[tick]
        if tick == 1:
            assert sample["glyph"] == "glyph-prime"
        else:
            assert "glyph" not in sample

    latest_sample = samples[-1]
    assert latest_sample["tick"] == expected_ticks[-1]
    baseline_snapshot = {
        "tick": latest_sample["tick"],
        "sceneTags": latest_sample["sceneTags"],
        "targets": {
            target: {
                "tick": latest_sample["tick"],
                "sceneTags": latest_sample["sceneTags"],
                "density": latest_sample["density"],
                "activeIndices": latest_sample["activeIndices"],
            }
            for target in ("drift", "emotion", "glyph")
        },
    }

    assert set(baseline_snapshot["targets"].keys()) == {"drift", "emotion", "glyph"}
    for vector in baseline_snapshot["targets"].values():
        assert vector["density"] == latest_sample["density"]
        assert vector["activeIndices"] == latest_sample["activeIndices"]
        assert vector["sceneTags"] == latest_sample["sceneTags"]
        assert vector["tick"] == latest_sample["tick"]
