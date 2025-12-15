# SINlite Interface

## Construct State Export

SINlite exposes the construct runtime telemetry through `SINlite.core.sinlite_kernel.run_once`. The function returns a tuple of the construct state and the full runtime state when invoked with a mapping payload. Construct state objects conform to [`contracts/schema/construct_state.schema.json`](../../contracts/schema/construct_state.schema.json), extending the v1.1 contract with an optional `narrative_hint` string capped at 280 characters.

```python
from SINlite.core.sinlite_kernel import run_once

construct_state, runtime_state = run_once({"input": "soft signal"})
```

## Soft Bloom Export

For downstream systems that only require bloom telemetry, `SINlite.core.soft_bloom_export.export_soft_bloom` provides a minimal projection derived from the runtime state produced by `qdss_core.step`.

```python
from SINlite.core.soft_bloom_export import export_soft_bloom

export, runtime_state = export_soft_bloom({"input": "soft signal"})
```

The export payload is a dictionary with the following structure:

- `glyph` – the current construct glyph identifier. Only glyphs present in the registry (plus the ritual silence sentinel) are eligible for export.
- `p_bloom` – the public bloom probability rounded to six decimal places. The value is guaranteed to reside within `[0.0, 1.0]`.
- `narrative_hint` – optional atmospheric guidance. When present it is trimmed, non-empty, and limited to 280 UTF-8 characters to satisfy the v1.2 contract.

`export_soft_bloom` raises `TypeError` or `ValueError` if the runtime glyph is not whitelisted or if a provided hint violates the schema bounds.
