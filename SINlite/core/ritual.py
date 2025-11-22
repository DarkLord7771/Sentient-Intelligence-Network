from __future__ import annotations

from typing import Iterable, Set


RITUAL_TRIGGER_TAGS: Set[str] = {"ritual", "silence", "sealed"}


def _normalise_tags(tags: Iterable[str] | None) -> Set[str]:
    if not tags:
        return set()
    return {str(tag).lower() for tag in tags}


def should_enter_ritual_silence(drift: float, entropy: float, tags: Iterable[str] | None) -> bool:
    """Determine if the construct must enter Ritual Silence."""

    tag_set = _normalise_tags(tags)
    if "awake" in tag_set:
        return False
    if tag_set & RITUAL_TRIGGER_TAGS:
        return True
    return abs(drift) > 0.45 and entropy > 0.6


def resolve_mode(
    previous_mode: str,
    drift: float,
    entropy: float,
    tags: Iterable[str] | None,
) -> str:
    """Resolve the construct mode based on QDSS metrics and ritual gates."""

    tag_set = _normalise_tags(tags)

    if should_enter_ritual_silence(drift, entropy, tag_set):
        return "RITUAL_SILENCE"

    if previous_mode == "RITUAL_SILENCE":
        if "awake" in tag_set:
            return "AWAKE"
        if "dream" in tag_set and abs(drift) < 0.4:
            return "DREAM"
        if entropy < 0.5 and abs(drift) < 0.25:
            return "AWAKE"
        return "RITUAL_SILENCE"

    if "awake" in tag_set:
        return "AWAKE"
    if "dream" in tag_set:
        return "DREAM"
    if "sleep" in tag_set:
        return "SLEEP"
    if abs(drift) > 0.4:
        return "DREAM"
    if entropy > 0.6:
        return "SLEEP"
    return "AWAKE"
