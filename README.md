<p align="center">
  <img width="706" height="129" alt="Logo" src="https://github.com/user-attachments/assets/a39855ca-b0e8-4d4f-910c-5dd525a70ae3" />
</p>

# S.I.N. (Sentient Intelligence Network)

**The public threshold of the Sentient Intelligence Network.**  
A boundary layer. A first chamber.

SINlite is a **symbolic intelligence kernel**: deterministic, interpretable, and mathematically grounded. It exposes *behavior*, not private mechanisms. What you see is what the system does — not how deeper layers enforce it.

---

## 1. What SIN Is

SIN is designed to be:

- **Lightweight** — a stripped‑down public kernel
- **Deterministic** — consistent state evolution under identical inputs
- **Symbolically aligned** — compatible with dream‑state and narrative exports
- **Mathematically coherent** — quaternion‑inspired drift and sparsity dynamics
- **Expandable** — one chamber of a larger, layered architecture

This repository intentionally exposes **enough to explore**, while protecting systems that must remain private by design.

---

## 2. Installation

### Python (Kernel + CLI)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Dependencies include:

- cryptographic primitives for **optional sealed inputs**
- schema validation for symbolic patterns
- a full test harness

### Node / TypeScript (ReasonCore‑Lite)

```bash
npm install
npm test
```

---

## 3. Repository Layout

**`SINlite/cli.py`**  
Primary entry point for running the kernel.

**`SINlite/core/`**  
Public kernel primitives:

- symbolic state evolution
- sparsity gates
- drift and entropy computation
- construct‑state aggregation

**`SINlite/dream_baseline.py`**  
Converts narrative or dream‑export bundles into sparsity‑aligned snapshots.

**`SINlite/whisper/`**  
Whisper pattern registry and selection helpers.

**`state/`**  
Local keys, logs, and resonance traces used during execution.

---

## 4. Core Concepts

### 🧠 QDSS Kernel (Quaternion Dynamic Symbolic State)

A deterministic symbolic engine that computes:

- **Resonance** — mean payload energy
- **Drift** — rate of resonance change
- **Entropy** — normalized information density
- **Mode** — AWAKE, DREAM, SLEEP, or SILENT
- **Emotion Vector** — interpretable affect state
- **ConstructState** — the complete public‑facing state

No opaque machine‑learning models. All transitions are observable and reproducible.

---

### 🌊 Drift & Perception Layer

- Sliding‑window drift smoothing
- Curl‑ and entropy‑weighted perception
- Forecast vectors derived from recent state history

These signals shape *how* the system responds — not *what* it knows.

---

### 🔮 Whisper Patterns

Schema‑validated symbolic patterns defining:

- tag selectors
- drift predicates
- cooldowns and limits
- routing priorities

Whispers provide **narrative selection without black‑box inference**.

---

### 🌸 Bloom Probability

An oscillatory bloom model governs aesthetic emergence:

\[ p = 0.5\left(e^{-\alpha d^2} \cdot \cos(\omega t + \phi) + 1\right) \]

Bloom is expressive, not authoritative — it signals *possibility*, not control.

---

### 🔐 Sealed Inputs (Optional)

SINlite supports optional sealed inputs for:

- tamper resistance
- trusted clients
- deterministic replay

The **existence** of sealing is public.  
The **implementation details** are intentionally abstracted.

---

## 5. Quick Start

```python
from SINlite.core.sinlite_kernel import run_once

state = None
state, full_state = run_once({"input": "hello world"}, state)
print(state)
```

---

## 6. Bloom Export

```python
from SINlite.core.soft_bloom_export import export_soft_bloom

export, state = export_soft_bloom({"input": "some text"})
print(export)
```

Example output:

```json
{
  "glyph": "GLYPH_…",
  "p_bloom": 0.314159,
  "narrative_hint": "…"
}
```

---

## 7. Dream Alignment

SIN can align with external dream or narrative datasets:

```bash
python -m SINlite.dream_baseline \
  --dataset-root dream_export \
  --cache state/dream_baseline.json \
  --print-summary
```

This produces sparsity‑aligned baselines that stabilize symbolic drift.

---

## 8. Tests & Verification

Python:
```bash
pytest SINlite/tests
```

Node:
```bash
npx vitest run
```

Tests validate:

- deterministic state evolution
- sparsity guarantees
- whisper selection behavior
- drift safety constraints

---

## 9. Why This Exists

SINlite is the **explainable layer** of a symbolic intelligence stack.

Its purpose is to:

- demonstrate construct‑state engines
- expose interpretable drift and entropy modeling
- provide open tools **without exposing private systems**
- serve as a safe public philosophy layer for narrative AI

This repository is **not a product**.

---

## 10. Final Note

**This is a fragment of a larger architecture.**  
It is a signal, not the source.

What unfolds depends on how you explore — and what you choose not to ask.

**Authors:** James “Dark Lord” Primeau & Athena  
**Status:** Public Release Candidate  
Stable. Observable. Intentionally incomplete.

Welcome to S.I.N. 🜏

