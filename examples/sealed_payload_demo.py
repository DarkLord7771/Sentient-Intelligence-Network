"""Show how to sign and verify a payload before executing the kernel."""
from __future__ import annotations

from nacl import signing

from SINlite.core.sealed_input import extract_payload, seal_payload
from SINlite.core.sinlite_kernel import run_once_with_envelope


def main() -> None:
    signing_key = signing.SigningKey.generate()
    verify_key = signing_key.verify_key

    raw_payload = {"input": "sealed hello"}
    envelope = seal_payload(raw_payload, signing_key)

    print("Envelope preview:")
    print(envelope.to_dict())

    verified_payload = extract_payload(envelope, verify_key=verify_key)
    print("Verified payload:")
    print(verified_payload)

    construct_state, runtime_state = run_once_with_envelope(
        envelope, verify_key=verify_key
    )
    print("\nConstructState:")
    print(construct_state)
    print("\nRuntime state keys:")
    print(sorted(runtime_state.keys()))


if __name__ == "__main__":
    main()
