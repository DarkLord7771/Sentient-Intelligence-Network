"""Emit the soft bloom export for a payload."""
from __future__ import annotations

from SINlite.core.soft_bloom_export import export_soft_bloom


def main() -> None:
    export, runtime_state = export_soft_bloom({"input": "soft bloom demo"})

    print("Bloom export (safe for downstream systems):")
    print(export)

    construct = runtime_state.get("construct_state", {})
    print("\nConstructState essentials:")
    essentials = {
        "glyph": construct.get("glyph"),
        "mode": construct.get("mode"),
        "resonance": construct.get("resonance"),
        "drift": construct.get("drift"),
        "entropy": construct.get("entropy"),
        "narrative_hint": construct.get("narrative_hint"),
    }
    print(essentials)


if __name__ == "__main__":
    main()
