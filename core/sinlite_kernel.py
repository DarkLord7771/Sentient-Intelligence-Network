from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from nacl import signing

from SINlite.contracts import validate_construct_state
from .qdss_core import step
from .sealed_input import extract_payload


def _coerce_payload(payload: Any) -> Dict[str, Any]:
    """Normalise caller supplied input into a dictionary payload."""

    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        return json.loads(payload)
    raise TypeError(
        "run_once payload must be a mapping, a JSON string, or None."
    )


def run_once(
    payload: Any = None,
    state: Dict[str, Any] | None = None,
    *,
    as_json: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]] | str:
    """Execute a single kernel step and emit the ConstructState JSON."""

    payload_dict = _coerce_payload(payload)
    runtime_state = step(payload_dict, state)
    construct_state: Dict[str, Any] = validate_construct_state(runtime_state["construct_state"])

    if as_json:
        return json.dumps(construct_state)
    return construct_state, runtime_state


def run_once_with_envelope(
    payload_or_envelope: Any = None,
    state: Dict[str, Any] | None = None,
    *,
    verify_key: signing.VerifyKey | None = None,
    require_signature: bool = False,
    as_json: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]] | str:
    """Execute a kernel step using either a raw payload or a sealed envelope."""

    payload_candidate = extract_payload(
        payload_or_envelope,
        verify_key=verify_key,
        require_signature=require_signature,
    )
    payload_dict = _coerce_payload(payload_candidate)
    runtime_state = step(payload_dict, state)
    construct_state: Dict[str, Any] = validate_construct_state(runtime_state["construct_state"])

    if as_json:
        return json.dumps(construct_state)
    return construct_state, runtime_state
