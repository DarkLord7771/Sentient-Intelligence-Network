"""Demonstrate deterministic state evolution across multiple inputs."""
from __future__ import annotations

from SINlite.core.sinlite_kernel import run_once


def main() -> None:
    state = None
    prompts = [
        {"input": "baseline ping"},
        {"input": "gentle wave", "tags": ["soft", "calm"]},
        {"input": "surge"},
    ]

    for index, payload in enumerate(prompts, start=1):
        construct_state, runtime_state = run_once(payload, state)
        state = runtime_state
        summary = {
            "counter": construct_state.get("counter"),
            "glyph": construct_state.get("glyph"),
            "mode": construct_state.get("mode"),
            "resonance": construct_state.get("resonance"),
            "drift": construct_state.get("drift"),
            "entropy": construct_state.get("entropy"),
        }
        print(f"Step {index}: {summary}")

    print("\nFinal ConstructState:")
    print(state["construct_state"])


if __name__ == "__main__":
    main()
