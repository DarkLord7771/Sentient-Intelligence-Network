"""Dream-pack sparsity baseline loader and cache helper."""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence

_STATE_DIR = Path("state")
_DEFAULT_DATASET_ROOT = Path("dream_export")
_DEFAULT_CACHE_PATH = _STATE_DIR / "dream_baseline.json"


@dataclass(frozen=True)
class DreamBaselineSample:
    """Single dream-pack sparsity observation."""

    tick: int
    density: float
    active_indices: tuple[int, ...]
    scene_tags: tuple[str, ...]
    glyph: Optional[str] = None

    def to_payload(self) -> Mapping[str, object]:
        payload = {
            "tick": self.tick,
            "density": self.density,
            "activeIndices": list(self.active_indices),
            "sceneTags": list(self.scene_tags),
        }
        if self.glyph:
            payload["glyph"] = self.glyph
        return payload


class DreamBaseline:
    """In-memory index of dream-pack sparsity samples."""

    def __init__(self, source: Path, samples: Sequence[DreamBaselineSample]):
        self.source = source
        self._by_tick: Dict[int, DreamBaselineSample] = {sample.tick: sample for sample in samples}
        self._scene_index: Dict[str, List[DreamBaselineSample]] = {}
        for sample in samples:
            for tag in sample.scene_tags:
                self._scene_index.setdefault(tag, []).append(sample)

    def ticks(self) -> List[int]:
        return sorted(self._by_tick.keys())

    def scenes(self) -> List[str]:
        return sorted(self._scene_index.keys())

    def get(self, tick: int) -> Optional[DreamBaselineSample]:
        return self._by_tick.get(int(tick))

    def by_scene(self, scene_tag: str) -> Sequence[DreamBaselineSample]:
        return list(self._scene_index.get(scene_tag, ()))

    def to_cache_payload(self) -> Mapping[str, object]:
        refreshed_at = datetime.now(timezone.utc).isoformat()
        return {
            "source": str(self.source),
            "refreshedAt": refreshed_at,
            "ticks": len(self._by_tick),
            "scenes": self.scenes(),
            "samples": [sample.to_payload() for sample in sorted(self._by_tick.values(), key=lambda item: item.tick)],
        }

    def write_cache(self, path: Path) -> Path:
        payload = self.to_cache_payload()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path


@dataclass
class _BaselineCacheEntry:
    symbolic_path: Path
    mtime: float
    baseline: DreamBaseline


_BASELINE_CACHE: MutableMapping[Path, _BaselineCacheEntry] = {}


def _read_json(path: Path) -> Mapping[str, object] | Sequence[Mapping[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _scene_windows(narrative_payload: Mapping[str, object] | Sequence[Mapping[str, object]]) -> List[tuple[int, int, List[str]]]:
    scenes: Iterable[Mapping[str, object]]
    if isinstance(narrative_payload, Mapping):
        raw = narrative_payload.get("scenes") or narrative_payload.get("timeline") or []
        if isinstance(raw, Mapping):
            scenes = raw.get("scenes", [])  # type: ignore[assignment]
        else:
            scenes = raw  # type: ignore[assignment]
    else:
        scenes = narrative_payload

    windows: List[tuple[int, int, List[str]]] = []
    for scene in scenes:
        if not isinstance(scene, Mapping):
            continue
        try:
            start = int(scene.get("startTick") or scene.get("start") or scene.get("tick") or 0)
            end = int(scene.get("endTick") or scene.get("end") or start)
        except Exception:  # pragma: no cover - defensive
            continue
        tags: List[str] = []
        label = scene.get("label") or scene.get("name")
        if isinstance(label, str) and label.strip():
            tags.append(label.strip())
        for key in ("tags", "sceneTags"):
            value = scene.get(key)
            if isinstance(value, Sequence):
                for tag in value:
                    if isinstance(tag, str) and tag.strip():
                        tags.append(tag.strip())
        windows.append((start, end, sorted({*tags})))
    return windows


def _scene_tags_for_tick(windows: Sequence[tuple[int, int, Sequence[str]]], tick: int) -> List[str]:
    tags: List[str] = []
    for start, end, scene_tags in windows:
        if start <= tick <= end:
            tags.extend(scene_tags)
    return sorted({*tags})


def _extract_density(entry: Mapping[str, object]) -> Optional[float]:
    density_candidate = entry.get("density")
    if isinstance(density_candidate, (int, float)):
        return float(density_candidate)
    sparsity = entry.get("sparsity")
    if isinstance(sparsity, Mapping):
        density = sparsity.get("density")
        if isinstance(density, (int, float)):
            return float(density)
    return None


def _extract_indices(entry: Mapping[str, object]) -> List[int]:
    candidates = entry.get("activeIndices") or entry.get("active_indices")
    if not isinstance(candidates, Sequence):
        sparsity = entry.get("sparsity")
        if isinstance(sparsity, Mapping):
            candidates = sparsity.get("activeIndices") or sparsity.get("active_indices")
    if not isinstance(candidates, Sequence):
        return []
    result: List[int] = []
    for candidate in candidates:
        try:
            value = int(candidate)
        except Exception:
            continue
        if value < 0:
            continue
        result.append(value)
    return sorted({*result})


def _latest_symbolic_path(dataset_root: Path) -> tuple[Path, Path]:
    candidates: List[tuple[float, Path, Path]] = []
    search_roots = [dataset_root]
    if dataset_root.is_dir():
        for entry in dataset_root.iterdir():
            if entry.is_dir():
                search_roots.append(entry)
    for root in search_roots:
        symbolic = root / "json_meta" / "symbolic_drift.json"
        narrative = root / "json_meta" / "narrative.json"
        if symbolic.exists():
            candidates.append((symbolic.stat().st_mtime, symbolic, narrative))
    if not candidates:
        raise FileNotFoundError(
            f"No symbolic_drift.json found under {dataset_root}. Run dream_export first."
        )
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, symbolic_path, narrative_path = candidates[0]
    return symbolic_path, narrative_path


def _load_baseline_samples(symbolic_path: Path, narrative_path: Path) -> List[DreamBaselineSample]:
    payload = _read_json(symbolic_path)
    if not isinstance(payload, Sequence):
        raise RuntimeError(f"symbolic_drift.json must contain an array: {symbolic_path}")

    windows: Sequence[tuple[int, int, Sequence[str]]] = []
    if narrative_path.exists():
        narrative_payload = _read_json(narrative_path)
        if isinstance(narrative_payload, (Mapping, Sequence)):
            windows = _scene_windows(narrative_payload)  # type: ignore[arg-type]

    samples: List[DreamBaselineSample] = []
    for entry in payload:
        if not isinstance(entry, Mapping):
            continue
        tick_raw = entry.get("tick") or entry.get("frame")
        try:
            tick = int(tick_raw)
        except Exception:
            continue
        density = _extract_density(entry)
        if density is None:
            continue
        active_indices = tuple(_extract_indices(entry))
        scene_tags: List[str] = []
        entry_scene_tags = entry.get("sceneTags")
        if isinstance(entry_scene_tags, Sequence):
            for tag in entry_scene_tags:
                if isinstance(tag, str) and tag.strip():
                    scene_tags.append(tag.strip())
        scene_tags.extend(_scene_tags_for_tick(windows, tick))
        sample = DreamBaselineSample(
            tick=tick,
            density=float(max(0.0, min(1.0, density))),
            active_indices=active_indices,
            scene_tags=tuple(sorted({*scene_tags})),
            glyph=str(entry.get("glyph")) if entry.get("glyph") else None,
        )
        samples.append(sample)
    return sorted(samples, key=lambda sample: sample.tick)


def load_latest_baseline(dataset_root: Path | str = _DEFAULT_DATASET_ROOT) -> DreamBaseline:
    """Load (and cache) the most recent dream-pack sparsity baseline."""

    dataset_root = Path(dataset_root).resolve()
    symbolic_path, narrative_path = _latest_symbolic_path(dataset_root)
    key = dataset_root
    cached = _BASELINE_CACHE.get(key)
    current_mtime = symbolic_path.stat().st_mtime
    if cached and cached.symbolic_path == symbolic_path and cached.mtime == current_mtime:
        return cached.baseline

    samples = _load_baseline_samples(symbolic_path, narrative_path)
    baseline = DreamBaseline(symbolic_path.parent.parent, samples)
    _BASELINE_CACHE[key] = _BaselineCacheEntry(symbolic_path=symbolic_path, mtime=current_mtime, baseline=baseline)
    return baseline


def refresh_baseline_cache(dataset_root: Path | str, cache_path: Path | str = _DEFAULT_CACHE_PATH) -> Path:
    baseline = load_latest_baseline(dataset_root)
    cache = Path(cache_path)
    return baseline.write_cache(cache)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load dream sparsity baselines and persist them to disk.")
    parser.add_argument(
        "--dataset-root",
        default=str(_DEFAULT_DATASET_ROOT),
        help="Path containing dream_export outputs (json_meta/symbolic_drift.json)",
    )
    parser.add_argument(
        "--cache",
        default=str(_DEFAULT_CACHE_PATH),
        help="Destination file for the cached baseline payload",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print a short summary after refreshing the cache",
    )
    return parser


def _main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    cache_path = refresh_baseline_cache(Path(args.dataset_root), Path(args.cache))
    if args.print_summary:
        baseline = load_latest_baseline(Path(args.dataset_root))
        summary = {
            "ticks": len(baseline.ticks()),
            "scenes": baseline.scenes(),
            "cache": str(cache_path),
        }
        print(json.dumps(summary, indent=2))
    else:
        print(str(cache_path))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(_main())
