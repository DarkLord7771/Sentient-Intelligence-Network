"""Helpers for sealing and verifying kernel payloads."""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping

from nacl import encoding, exceptions, signing


class SealedInputError(ValueError):
    """Base class for sealed input related exceptions."""


class SignatureMissingError(SealedInputError):
    """Raised when a signature is required but missing."""


class SignatureVerificationError(SealedInputError):
    """Raised when signature verification fails."""


def _ensure_json_serialisable(payload: Any) -> Any:
    """Return a JSON compatible copy of *payload*."""

    try:
        return json.loads(
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    except (TypeError, ValueError) as exc:
        raise SealedInputError("Payload must be JSON serialisable") from exc


def _serialise_message(payload: Any, monotonic: int, nonce: str | None) -> bytes:
    body: dict[str, Any] = {
        "monotonic": monotonic,
        "payload": payload,
    }
    if nonce is not None:
        body["nonce"] = nonce
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class SealedEnvelope:
    """Representation of a signed payload envelope."""

    payload: Any
    monotonic: int
    sig: str
    nonce: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {"payload": self.payload, "monotonic": self.monotonic, "sig": self.sig}
        if self.nonce is not None:
            data["nonce"] = self.nonce
        return data

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "SealedEnvelope":
        try:
            payload = mapping["payload"]
            monotonic_raw = mapping["monotonic"]
        except KeyError as exc:
            raise SealedInputError("Envelope missing required fields") from exc

        sig = mapping.get("sig")
        nonce = mapping.get("nonce")

        if sig is None:
            raise SignatureMissingError("Envelope does not include a signature")

        try:
            monotonic = int(monotonic_raw)
        except (TypeError, ValueError) as exc:
            raise SealedInputError("Envelope monotonic value must be an integer") from exc

        return cls(payload=_ensure_json_serialisable(payload), monotonic=monotonic, sig=str(sig), nonce=nonce)


def seal_payload(
    payload: Any,
    signing_key: signing.SigningKey,
    *,
    monotonic: int | None = None,
    nonce: str | None = None,
) -> SealedEnvelope:
    """Wrap *payload* in a signed envelope."""

    monotonic_value = monotonic if monotonic is not None else time.monotonic_ns()
    nonce_value = nonce if nonce is not None else secrets.token_hex(16)

    payload_copy = _ensure_json_serialisable(payload)
    message = _serialise_message(payload_copy, monotonic_value, nonce_value)
    signature = signing_key.sign(message).signature
    signature_b64 = encoding.Base64Encoder.encode(signature).decode("ascii")

    return SealedEnvelope(
        payload=payload_copy,
        monotonic=monotonic_value,
        sig=signature_b64,
        nonce=nonce_value,
    )


def verify_envelope(envelope: SealedEnvelope | Mapping[str, Any], verify_key: signing.VerifyKey) -> Any:
    """Validate *envelope* and return its payload."""

    if not isinstance(envelope, SealedEnvelope):
        envelope = SealedEnvelope.from_mapping(envelope)

    try:
        signature = encoding.Base64Encoder.decode(envelope.sig.encode("ascii"))
    except Exception as exc:  # pragma: no cover - defensive guard
        raise SignatureVerificationError("Unable to decode signature") from exc

    message = _serialise_message(envelope.payload, envelope.monotonic, envelope.nonce)

    try:
        verify_key.verify(message, signature)
    except exceptions.BadSignatureError as exc:
        raise SignatureVerificationError("Envelope signature is invalid") from exc

    payload = envelope.payload
    if isinstance(payload, MutableMapping):
        return dict(payload)
    return payload


def extract_payload(
    candidate: Any,
    *,
    verify_key: signing.VerifyKey | None = None,
    require_signature: bool = False,
) -> Any:
    """Return the payload from *candidate*, verifying sealed envelopes when present."""

    if isinstance(candidate, SealedEnvelope):
        if verify_key is None and require_signature:
            raise SignatureMissingError("Verification key required for sealed envelope")
        if verify_key is None:
            return candidate.payload
        return verify_envelope(candidate, verify_key)

    if isinstance(candidate, Mapping) and "payload" in candidate and "monotonic" in candidate:
        if "sig" not in candidate:
            if require_signature:
                raise SignatureMissingError("Signature is required for envelope payloads")
            payload = candidate["payload"]
            return _ensure_json_serialisable(payload)
        if verify_key is None:
            if require_signature:
                raise SignatureMissingError("Verification key required for sealed envelope")
            return _ensure_json_serialisable(candidate["payload"])
        return verify_envelope(candidate, verify_key)

    if require_signature:
        raise SignatureMissingError("Signed envelope expected")

    return candidate
