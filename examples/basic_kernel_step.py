"""Minimal single-step run of the SINlite kernel."""
from __future__ import annotations

from SINlite.core.sinlite_kernel import run_once


def describe_construct(construct_state: dict[str, object]) -> str:
    glyph = construct_state.get("glyph")
    mode = construct_state.get("mode")
    resonance = construct_state.get("resonance")
    drift = construct_state.get("drift")
    return f"glyph={glyph}, mode={mode}, resonance={resonance}, drift={drift}"


def main() -> None:
    construct_state, runtime_state = run_once({"input": "hello sin"})

    print("ConstructState snapshot:")
    print("  " + describe_construct(construct_state))

    bloom_probability = runtime_state.get("bloom_probability")
    print("Bloom probability:")
    print(f"  {bloom_probability}")


if __name__ == "__main__":
    main()
