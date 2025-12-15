from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, RefResolver


_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONTRACT_ROOT = _REPO_ROOT / "contracts"
_SCHEMA_ROOT = _CONTRACT_ROOT / "schema"


@lru_cache(maxsize=None)
def _load_schema(name: str) -> Dict[str, Any]:
    schema_path = _SCHEMA_ROOT / name
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return schema


@lru_cache(maxsize=None)
def _construct_validator() -> Draft202012Validator:
    schema = _load_schema("construct_state.schema.json")
    construct_schema_path = _CONTRACT_ROOT / "construct_state.v1_2.schema.json"
    construct_schema = json.loads(construct_schema_path.read_text(encoding="utf-8"))
    store = {
        "../construct_state.v1_2.schema.json": construct_schema,
        "construct_state.v1_2.schema.json": construct_schema,
        str(construct_schema_path): construct_schema,
        construct_schema_path.as_uri(): construct_schema,
        "https://schemas.sin.dev/construct_state.v1_2.schema.json": construct_schema,
        "https://schemas.sin.dev/contracts/construct_state.v1_2.schema.json": construct_schema,
    }
    schema_id = schema.get("$id")
    if schema_id:
        store[schema_id] = schema
    resolver = RefResolver(base_uri=f"{_SCHEMA_ROOT.as_uri()}/", referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


@lru_cache(maxsize=None)
def _sin_event_validator() -> Draft202012Validator:
    schema = _load_schema("sin_event.schema.json")
    events_schema_path = _REPO_ROOT / "SINphony" / "schema" / "events.json"
    construct_schema_path = _CONTRACT_ROOT / "construct_state.v1_2.schema.json"
    events_schema = json.loads(events_schema_path.read_text(encoding="utf-8"))
    construct_schema = json.loads(construct_schema_path.read_text(encoding="utf-8"))
    store = {
        "../../SINphony/schema/events.json": events_schema,
        str(events_schema_path): events_schema,
        events_schema_path.as_uri(): events_schema,
        "https://schemas.sin.dev/SINphony/schema/events.json": events_schema,
        "../construct_state.v1_2.schema.json": construct_schema,
        "construct_state.v1_2.schema.json": construct_schema,
        str(construct_schema_path): construct_schema,
        construct_schema_path.as_uri(): construct_schema,
        "https://schemas.sin.dev/contracts/construct_state.v1_2.schema.json": construct_schema,
    }
    schema_id = schema.get("$id")
    if schema_id:
        store[schema_id] = schema
    resolver = RefResolver(base_uri=f"{_SCHEMA_ROOT.as_uri()}/", referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


@lru_cache(maxsize=None)
def _visual_manifest_validator() -> Draft202012Validator:
    schema = _load_schema("visual_manifest.schema.json")
    visual_schema_path = _CONTRACT_ROOT / "visual_manifest.schema.json"
    visual_schema = json.loads(visual_schema_path.read_text(encoding="utf-8"))
    store = {
        "../visual_manifest.schema.json": visual_schema,
        "visual_manifest.schema.json": visual_schema,
        str(visual_schema_path): visual_schema,
        visual_schema_path.as_uri(): visual_schema,
        "https://schemas.sin.dev/visual_manifest.schema.json": visual_schema,
        "https://schemas.sin.dev/contracts/visual_manifest.schema.json": visual_schema,
    }
    schema_id = schema.get("$id")
    if schema_id:
        store[schema_id] = schema
    resolver = RefResolver(base_uri=f"{_SCHEMA_ROOT.as_uri()}/", referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def _strip_meta(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = dict(payload)
    sanitized.pop("$schema", None)
    return sanitized


def validate_construct_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    validator = _construct_validator()
    sanitized = _strip_meta(payload)
    validator.validate(sanitized)
    return sanitized


def validate_sin_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    validator = _sin_event_validator()
    sanitized = _strip_meta(payload)
    validator.validate(sanitized)
    return sanitized


def validate_visual_manifest(payload: Dict[str, Any]) -> Dict[str, Any]:
    validator = _visual_manifest_validator()
    sanitized = _strip_meta(payload)
    validator.validate(sanitized)
    return sanitized


def serialize_roundtrip(payload: Dict[str, Any], validator) -> Dict[str, Any]:
    validator(payload)
    serialized = json.dumps(payload, ensure_ascii=False)
    decoded = json.loads(serialized)
    validator(decoded)
    return decoded


def serialize_construct_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    return serialize_roundtrip(payload, validate_construct_state)


def serialize_sin_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    return serialize_roundtrip(payload, validate_sin_event)


def serialize_visual_manifest(payload: Dict[str, Any]) -> Dict[str, Any]:
    return serialize_roundtrip(payload, validate_visual_manifest)


_ROADMAP_REDACT = {"quat_state", "face_profile", "actor_rig"}


def apply_roadmap_redaction(event: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = dict(event)
    for field in _ROADMAP_REDACT:
        sanitized.pop(field, None)
    return sanitized
