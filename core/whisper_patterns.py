from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from jsonschema import Draft202012Validator, ValidationError

from ..defaults import WHISPER_REGISTRY_PATH

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "contracts" / "whisper_pattern.v1_3.schema.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_timestamp(timestamp: str | datetime | None) -> Optional[datetime]:
    if timestamp is None:
        return None
    if isinstance(timestamp, datetime):
        return _ensure_timezone(timestamp)
    value = timestamp.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    return _ensure_timezone(parsed)


@dataclass(frozen=True)
class DriftPredicate:
    gte: Optional[float] = None
    gt: Optional[float] = None
    lte: Optional[float] = None
    lt: Optional[float] = None
    abs_gte: Optional[float] = None
    abs_lte: Optional[float] = None

    def matches(self, drift: Optional[float]) -> bool:
        if drift is None:
            drift = 0.0
        if self.gte is not None and drift < self.gte:
            return False
        if self.gt is not None and drift <= self.gt:
            return False
        if self.lte is not None and drift > self.lte:
            return False
        if self.lt is not None and drift >= self.lt:
            return False
        absolute = abs(drift)
        if self.abs_gte is not None and absolute < self.abs_gte:
            return False
        if self.abs_lte is not None and absolute > self.abs_lte:
            return False
        return True


@dataclass(frozen=True)
class TagSelectors:
    tags_any: Set[str] = field(default_factory=set)
    tags_all: Set[str] = field(default_factory=set)
    tags_none: Set[str] = field(default_factory=set)

    def matches(self, tags: Iterable[str]) -> bool:
        tag_set: Set[str] = set()
        for tag in tags:
            if isinstance(tag, str):
                tag_set.add(tag)
            elif isinstance(tag, bytes):
                try:
                    tag_set.add(tag.decode("utf-8"))
                except UnicodeDecodeError:
                    continue
        if self.tags_all and not self.tags_all.issubset(tag_set):
            return False
        if self.tags_any and not (self.tags_any & tag_set):
            return False
        if self.tags_none and self.tags_none & tag_set:
            return False
        return True


@dataclass(frozen=True)
class CooldownSpec:
    counters: Optional[int] = None
    seconds: Optional[float] = None

    def is_idle(
        self,
        last_counter: Optional[int],
        last_timestamp: Optional[datetime],
        *,
        counter: Optional[int],
        timestamp: Optional[datetime],
    ) -> bool:
        if self.counters is not None and last_counter is not None and counter is not None:
            if counter - last_counter < self.counters:
                return False
        if self.seconds is not None and last_timestamp is not None and timestamp is not None:
            delta = (timestamp - last_timestamp).total_seconds()
            if delta < self.seconds:
                return False
        return True


@dataclass(frozen=True)
class WhisperPattern:
    id: str
    glyph_id: str
    pattern_path: str
    pattern_checksum: str
    loop: bool
    description: Optional[str] = None
    priority: int = 0
    selectors: TagSelectors = field(default_factory=TagSelectors)
    drift_predicate: Optional[DriftPredicate] = None
    cooldown: Optional[CooldownSpec] = None
    max_per_session: Optional[int] = None
    bindings: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "WhisperPattern":
        selectors_payload = payload.get("selectors") or {}
        drift_payload = selectors_payload.get("drift") or {}
        drift_predicate = None
        if drift_payload:
            drift_predicate = DriftPredicate(
                gte=drift_payload.get("gte"),
                gt=drift_payload.get("gt"),
                lte=drift_payload.get("lte"),
                lt=drift_payload.get("lt"),
                abs_gte=drift_payload.get("abs_gte"),
                abs_lte=drift_payload.get("abs_lte"),
            )
        selectors = TagSelectors(
            tags_any=set(selectors_payload.get("tags_any") or []),
            tags_all=set(selectors_payload.get("tags_all") or []),
            tags_none=set(selectors_payload.get("tags_none") or []),
        )

        cooldown_payload = payload.get("cooldown") or {}
        cooldown = None
        if cooldown_payload:
            cooldown = CooldownSpec(
                counters=cooldown_payload.get("counters"),
                seconds=cooldown_payload.get("seconds"),
            )

        bindings = payload.get("bindings")
        metadata = payload.get("metadata")

        return cls(
            id=str(payload["id"]),
            glyph_id=str(payload["glyph_id"]),
            pattern_path=str(payload["pattern_path"]),
            pattern_checksum=str(payload["pattern_checksum"]),
            loop=bool(payload["loop"]),
            description=payload.get("description"),
            priority=int(payload.get("priority", 0) or 0),
            selectors=selectors,
            drift_predicate=drift_predicate,
            cooldown=cooldown,
            max_per_session=payload.get("max_per_session"),
            bindings=bindings if isinstance(bindings, dict) else None,
            metadata=metadata if isinstance(metadata, dict) else None,
        )

    def matches(self, *, drift: Optional[float], tags: Iterable[str], glyph_id: Optional[str]) -> bool:
        if glyph_id is not None and glyph_id != self.glyph_id:
            return False
        if self.drift_predicate and not self.drift_predicate.matches(drift):
            return False
        if not self.selectors.matches(tags):
            return False
        return True

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "glyph_id": self.glyph_id,
            "pattern_path": self.pattern_path,
            "pattern_checksum": self.pattern_checksum,
            "loop": self.loop,
            "priority": self.priority,
        }
        if self.description:
            payload["description"] = self.description
        selectors_payload: Dict[str, Any] = {}
        if self.drift_predicate:
            drift_payload = {
                key: value
                for key, value in {
                    "gte": self.drift_predicate.gte,
                    "gt": self.drift_predicate.gt,
                    "lte": self.drift_predicate.lte,
                    "lt": self.drift_predicate.lt,
                    "abs_gte": self.drift_predicate.abs_gte,
                    "abs_lte": self.drift_predicate.abs_lte,
                }.items()
                if value is not None
            }
            if drift_payload:
                selectors_payload["drift"] = drift_payload
        if self.selectors.tags_any:
            selectors_payload["tags_any"] = sorted(self.selectors.tags_any)
        if self.selectors.tags_all:
            selectors_payload["tags_all"] = sorted(self.selectors.tags_all)
        if self.selectors.tags_none:
            selectors_payload["tags_none"] = sorted(self.selectors.tags_none)
        if selectors_payload:
            payload["selectors"] = selectors_payload
        if self.cooldown:
            cooldown_payload = {}
            if self.cooldown.counters is not None:
                cooldown_payload["counters"] = self.cooldown.counters
            if self.cooldown.seconds is not None:
                cooldown_payload["seconds"] = self.cooldown.seconds
            if cooldown_payload:
                payload["cooldown"] = cooldown_payload
        if self.max_per_session is not None:
            payload["max_per_session"] = self.max_per_session
        if self.bindings is not None:
            payload["bindings"] = self.bindings
        if self.metadata is not None:
            payload["metadata"] = self.metadata
        return payload


class WhisperPatternRegistry:
    """Collection of whisper patterns backed by the JSON registry."""

    def __init__(self, patterns: Sequence[WhisperPattern], metadata: Optional[Dict[str, Any]] = None):
        self._patterns = list(sorted(patterns, key=lambda pattern: pattern.priority * -1))
        self.metadata = metadata or {}

    @property
    def patterns(self) -> List[WhisperPattern]:
        return list(self._patterns)

    @classmethod
    def from_payload(cls, payload: Any, *, validate: bool = True) -> "WhisperPatternRegistry":
        if isinstance(payload, dict) and "patterns" in payload:
            patterns_payload = payload["patterns"]
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None
        elif isinstance(payload, list):
            patterns_payload = payload
            metadata = None
        else:
            raise TypeError("Whisper pattern payload must be a sequence or mapping with 'patterns'.")

        if not isinstance(patterns_payload, list):
            raise TypeError("Registry payload 'patterns' must be a list.")

        if validate:
            validator = _schema_validator()
            for fragment in patterns_payload:
                validator.validate(fragment)

        patterns = [WhisperPattern.from_dict(fragment) for fragment in patterns_payload]
        return cls(patterns, metadata=metadata)

    @classmethod
    def from_path(cls, path: Optional[Path] = None, *, validate: bool = True) -> "WhisperPatternRegistry":
        registry_path = path or WHISPER_REGISTRY_PATH
        payload = _load_json(registry_path)
        return cls.from_payload(payload, validate=validate)

    def runtime(self) -> "WhisperPatternRuntime":
        return WhisperPatternRuntime(self)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "patterns": [pattern.to_payload() for pattern in self._patterns],
            **({"metadata": self.metadata} if self.metadata else {}),
        }


class WhisperPatternRuntime:
    """Session oriented helper that enforces cooldown and session counters."""

    def __init__(self, registry: WhisperPatternRegistry):
        self.registry = registry
        self._state: Dict[str, Dict[str, Any]] = {
            pattern.id: {"last_counter": None, "last_timestamp": None, "session_count": 0}
            for pattern in registry.patterns
        }

    def reset(self) -> None:
        for payload in self._state.values():
            payload.update(last_counter=None, last_timestamp=None, session_count=0)

    def status(self, pattern_id: str) -> Dict[str, Any]:
        if pattern_id not in self._state:
            raise KeyError(f"Unknown pattern '{pattern_id}'.")
        return dict(self._state[pattern_id])

    def select(
        self,
        *,
        drift: Optional[float],
        tags: Iterable[str],
        glyph_id: Optional[str],
        counter: Optional[int] = None,
        timestamp: str | datetime | None = None,
        consume: bool = True,
    ) -> Optional[WhisperPattern]:
        resolved_timestamp = _parse_timestamp(timestamp)
        for pattern in self.registry.patterns:
            if not pattern.matches(drift=drift, tags=tags, glyph_id=glyph_id):
                continue
            state = self._state[pattern.id]
            if pattern.max_per_session is not None and state["session_count"] >= pattern.max_per_session:
                continue
            cooldown = pattern.cooldown
            if cooldown and not cooldown.is_idle(
                state.get("last_counter"),
                state.get("last_timestamp"),
                counter=counter,
                timestamp=resolved_timestamp,
            ):
                continue
            if consume:
                state["session_count"] += 1
                if counter is not None:
                    state["last_counter"] = counter
                if resolved_timestamp is not None:
                    state["last_timestamp"] = resolved_timestamp
            return pattern
        return None


def _schema_validator() -> Draft202012Validator:
    schema = _load_json(_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def load_registry(path: Optional[Path] = None, *, validate: bool = True) -> WhisperPatternRegistry:
    """Load the whisper pattern registry from disk."""
    return WhisperPatternRegistry.from_path(path, validate=validate)


__all__ = [
    "CooldownSpec",
    "DriftPredicate",
    "TagSelectors",
    "WhisperPattern",
    "WhisperPatternRegistry",
    "WhisperPatternRuntime",
    "load_registry",
]
