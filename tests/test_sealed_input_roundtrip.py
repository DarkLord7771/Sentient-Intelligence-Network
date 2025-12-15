from __future__ import annotations

import json

import pytest
from nacl import signing

from SINlite.core.sealed_input import (
    SignatureMissingError,
    seal_payload,
    verify_envelope,
)
from SINlite.core.sinlite_kernel import run_once_with_envelope


def test_sealed_payload_roundtrip_success() -> None:
    signing_key = signing.SigningKey.generate()
    payload = {"input": "hello sealed world"}

    envelope = seal_payload(payload, signing_key)
    recovered = verify_envelope(envelope, signing_key.verify_key)
    assert recovered == payload

    construct_state, runtime_state = run_once_with_envelope(
        envelope.to_dict(),
        verify_key=signing_key.verify_key,
        require_signature=True,
    )
    assert construct_state == runtime_state["construct_state"]
    assert construct_state["counter"] >= 0

    # confirm loggable output round-trips via JSON
    assert json.loads(json.dumps(construct_state)) == construct_state


def test_sealed_payload_missing_signature() -> None:
    signing_key = signing.SigningKey.generate()
    payload = {"input": "unsigned"}
    envelope = seal_payload(payload, signing_key).to_dict()
    envelope.pop("sig")

    with pytest.raises(SignatureMissingError):
        run_once_with_envelope(
            envelope,
            verify_key=signing_key.verify_key,
            require_signature=True,
        )
