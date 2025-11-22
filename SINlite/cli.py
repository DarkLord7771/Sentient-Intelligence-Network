"""Command line helpers for the SINlite kernel."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from nacl import encoding, signing

from .core.sealed_input import seal_payload
from .core.sinlite_kernel import run_once_with_envelope
from .core.whisper_patterns import load_registry

STATE_DIR = Path("state")
DEFAULT_SIGNING_KEY = STATE_DIR / "signing_key.ed25519"
DEFAULT_VERIFY_KEY = STATE_DIR / "verify_key.ed25519"
DEFAULT_RUN_LOG = STATE_DIR / "construct_state.jsonl"


def _derive_verify_key_path(signing_path: Path) -> Path:
    if signing_path == DEFAULT_SIGNING_KEY:
        return DEFAULT_VERIFY_KEY
    return signing_path.with_name(signing_path.name + ".pub")


def _load_signing_key(path: Path) -> signing.SigningKey:
    if path.exists():
        data = path.read_text(encoding="utf-8").strip()
        if not data:
            raise RuntimeError(f"Signing key file {path} is empty")
        try:
            key_bytes = bytes.fromhex(data)
        except ValueError:
            key_bytes = encoding.Base64Encoder.decode(data.encode("ascii"))
        return signing.SigningKey(key_bytes)

    path.parent.mkdir(parents=True, exist_ok=True)
    signing_key = signing.SigningKey.generate()
    path.write_text(
        signing_key.encode(encoder=encoding.HexEncoder).decode("ascii"),
        encoding="utf-8",
    )
    verify_key_path = _derive_verify_key_path(path)
    verify_key_path.parent.mkdir(parents=True, exist_ok=True)
    verify_key_path.write_text(
        signing_key.verify_key.encode(encoder=encoding.HexEncoder).decode("ascii"),
        encoding="utf-8",
    )
    return signing_key


def _load_verify_key(path: Path) -> signing.VerifyKey:
    data = path.read_text(encoding="utf-8").strip()
    if not data:
        raise RuntimeError(f"Verification key file {path} is empty")
    try:
        key_bytes = bytes.fromhex(data)
    except ValueError:
        key_bytes = encoding.Base64Encoder.decode(data.encode("ascii"))
    return signing.VerifyKey(key_bytes)


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True))
        fh.write("\n")


def _handle_seal(args: argparse.Namespace) -> int:
    signing_key = _load_signing_key(args.signing_key)
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    envelope = seal_payload(payload, signing_key)
    output = json.dumps(envelope.to_dict(), sort_keys=True)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


def _handle_run(args: argparse.Namespace) -> int:
    if sum(bool(opt) for opt in (args.demo, args.payload, args.envelope)) > 1:
        raise SystemExit("Choose exactly one of --demo, --payload, or --envelope")

    payload_source: Any
    verify_key: signing.VerifyKey | None = None
    require_signature = False

    if args.demo:
        payload_source = {"input": "demo resonance"}
    elif args.payload:
        payload_source = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    elif args.envelope:
        payload_source = json.loads(Path(args.envelope).read_text(encoding="utf-8"))
        verify_key_path = Path(args.verify_key) if args.verify_key else DEFAULT_VERIFY_KEY
        verify_key = _load_verify_key(verify_key_path)
        require_signature = True
    else:
        payload_source = None

    construct_state, _runtime_state = run_once_with_envelope(
        payload_source,
        verify_key=verify_key,
        require_signature=require_signature,
    )

    _append_jsonl(Path(args.log), construct_state)

    if args.as_json:
        print(json.dumps(construct_state, sort_keys=True))
    else:
        print(json.dumps(construct_state, indent=2, sort_keys=True))

    return 0


def _handle_whisper_list(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry) if args.registry else None
    registry = load_registry(registry_path, validate=not args.skip_validation)
    patterns = [pattern.to_payload() for pattern in registry.patterns]

    if args.as_json:
        json_kwargs = {"indent": 2} if args.pretty else {}
        print(json.dumps(patterns, sort_keys=args.sort_keys, **json_kwargs))
        return 0

    for pattern in patterns:
        summary = f"{pattern['id']} ({pattern['glyph_id']})"
        description = pattern.get("description")
        if description:
            summary += f": {description}"
        print(summary)
    return 0


def _iter_jsonl(path: Path) -> list[dict]:
    payloads: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            candidate = line.strip()
            if not candidate:
                continue
            payloads.append(json.loads(candidate))
    return payloads


def _resolve_counter(candidate: Any, fallback: int) -> int:
    if candidate is None:
        return fallback
    if isinstance(candidate, (int, float)):
        return int(candidate)
    if isinstance(candidate, str) and candidate.strip():
        return int(float(candidate))
    raise TypeError("Counter value must be an integer or numeric string.")


def _handle_whisper_demo(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry) if args.registry else None
    registry = load_registry(registry_path, validate=not args.skip_validation)
    runtime = registry.runtime()

    input_path = Path(args.inputs)
    payloads = _iter_jsonl(input_path)

    output_path = Path(args.output) if args.output else None
    writer = None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        writer = output_path.open("w", encoding="utf-8")

    try:
        for index, payload in enumerate(payloads):
            drift = payload.get("drift")
            drift_value = float(drift) if drift is not None else None

            glyph_id = payload.get("glyph_id") or args.glyph
            counter = _resolve_counter(payload.get("counter"), index)

            selection = runtime.select(
                drift=drift_value,
                tags=payload.get("tags") or (),
                glyph_id=glyph_id,
                counter=counter,
                timestamp=payload.get("timestamp"),
                consume=True,
            )

            trace = {
                "index": index,
                "input": payload,
                "glyph_id": glyph_id,
                "selected": None,
            }

            if selection:
                trace["selected"] = {
                    "pattern": selection.to_payload(),
                    "state": runtime.status(selection.id),
                }

            encoded = json.dumps(trace, sort_keys=args.sort_keys)
            if writer:
                writer.write(encoded + "\n")
            else:
                print(encoded)
    finally:
        if writer:
            writer.close()

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sinlite", description="SINlite CLI helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seal_parser = subparsers.add_parser("seal", help="Seal a payload JSON file")
    seal_parser.add_argument("input", type=Path, help="Path to the JSON payload to seal")
    seal_parser.add_argument(
        "--signing-key",
        type=Path,
        default=DEFAULT_SIGNING_KEY,
        help="Path to an Ed25519 signing key (generated if missing)",
    )
    seal_parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path for the sealed envelope (defaults to stdout)",
    )
    seal_parser.set_defaults(func=_handle_seal)

    run_parser = subparsers.add_parser("run", help="Execute the SINlite kernel")
    run_group = run_parser.add_mutually_exclusive_group()
    run_group.add_argument("--demo", action="store_true", help="Execute a demo run")
    run_group.add_argument("--payload", type=Path, help="Path to a raw JSON payload")
    run_group.add_argument(
        "--envelope",
        type=Path,
        help="Path to a sealed envelope JSON payload",
    )
    run_parser.add_argument(
        "--verify-key",
        type=Path,
        default=DEFAULT_VERIFY_KEY,
        help="Verification key used for sealed envelopes",
    )
    run_parser.add_argument(
        "--log",
        type=Path,
        default=DEFAULT_RUN_LOG,
        help="Destination JSONL log file (default: state/construct_state.jsonl)",
    )
    run_parser.add_argument(
        "--as-json",
        action="store_true",
        help="Emit compact JSON instead of pretty output",
    )
    run_parser.set_defaults(func=_handle_run)

    whisper_parser = subparsers.add_parser("whisper", help="Inspect and demo whisper patterns")
    whisper_parser.add_argument(
        "--registry",
        type=Path,
        help="Optional override path to the whisper pattern registry JSON file",
    )
    whisper_parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Disable JSON schema validation when loading the registry",
    )
    whisper_subparsers = whisper_parser.add_subparsers(dest="whisper_command", required=True)

    whisper_list = whisper_subparsers.add_parser("list", help="List whisper patterns in the registry")
    whisper_list.add_argument(
        "--as-json",
        action="store_true",
        help="Emit JSON array instead of human-readable text",
    )
    whisper_list.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output when combined with --as-json",
    )
    whisper_list.add_argument(
        "--sort-keys",
        action="store_true",
        help="Sort keys when emitting JSON output",
    )
    whisper_list.set_defaults(func=_handle_whisper_list)

    whisper_demo = whisper_subparsers.add_parser(
        "demo",
        help="Replay pattern selection across a JSONL stream of learned drift inputs",
    )
    whisper_demo.add_argument(
        "inputs",
        type=Path,
        help="Path to the JSONL file containing drift predictions and tags",
    )
    whisper_demo.add_argument(
        "--glyph",
        help="Explicit glyph id for selection (defaults to entry-provided glyph or registry default)",
    )
    whisper_demo.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the resulting JSONL trace (defaults to stdout)",
    )
    whisper_demo.add_argument(
        "--sort-keys",
        action="store_true",
        help="Sort keys in the emitted JSONL output",
    )
    whisper_demo.set_defaults(func=_handle_whisper_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
