<p align="center">
  <img width="706" height="129" alt="Logo" src="https://github.com/user-attachments/assets/a39855ca-b0e8-4d4f-910c-5dd525a70ae3" />
</p>

# S.I.N. (Sentient Intelligence Network)

**The first public chamber of the Sentient Intelligence Network.**
A boundary layer. A threshold. A mathematically transparent “Construct State” engine built around resonance, drift, entropy, and symbolic pattern selection. 
No hidden weights or black-box. Clean symbolic rules, mathematically grounded metrics, and a predictable internal state.

---

## **1. The Nature of S.I.N.**

S.I.N. is designed to be:

- **Lightweight** — the stripped-down public kernel.
- **Deterministic** — envelope‑verified execution with Ed25519.
- **Symbolically aligned** — built to accept dream‑state exports.
- **Mathematically coherent** — quaternionic drift‑friendly, sparsity-aware.
- **Expandable** — a single public chamber of an expandable architecture.

This exposes enough to explore.

---

## **2. Installation**

### Python (kernel + CLI)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Node/TypeScript (Reasoncore‑Lite)

```bash
npm install

Run vitest:

npm test
```

---

## **3. Core Components**

**`SINlite/cli.py`** — The Oracle gateway. Sealing, running, verifying.

**`SINlite/core/`** — Kernel primitives:

- sealed input handler
- envelope verifier
- sparsity gates
- construct state evolution

**`SINlite/dream_baseline.py`** — Converts dream‑export bundles into ReasonCore‑ready sparsity snapshots.

**`SINlite/whisper/`** — Whisper registry + selection helpers.

**`state/`** — Keys, logs, resonance traces.

---

## **Features**

### **🧠 QDSS Kernel (Quaternion Dynamic Symbolic State)**

A deterministic state engine that computes:

* **Resonance** (mean payload energy)
* **Drift** (rate of change in resonance)
* **Entropy** (normalized Shannon information)
* **Mode** (AWAKE, DREAM, SLEEP, RITUAL_SILENCE)
* **Emotion Vector** (interpretable emoji-based affect)
* **ConstructState** (the full public-facing state)

### **🌊 Drift & Perception Layer**

* Sliding window drift smoothing
* Curl/entropy weighting
* UnifiedPerceptionLayer integration for “forecast vectors”
* Symbolic predictions fed back into drift & entropy smoothing

### **🔮 Whisper Patterns**

Schema-validated pattern registry defining:

* Tag selectors
* Drift predicates
* Cooldowns
* Max-per-session limits
* Glyph routing
* Pattern priorities

Provides narrative selection without opaque ML.

### **🌸 Bloom Probability**

Oscillatory bloom model:

<p align="center">
<img width="312" height="40" alt="latex_bloom" src="https://github.com/user-attachments/assets/784166fa-aef9-4e14-8f95-0997179c317c" />
</p>

```latex
p = 0.5\left(e^{-\alpha d^2} \cdot \cos(\omega t + \phi) + 1\right)
```

This exposes **aesthetic** bloom behavior.

### **🔐 Sealed Inputs**

Optional NaCl-powered sealed envelopes:

* Nonce
* Monotonic timestamp
* Ed25519 signature
* Verifiable envelope extraction

Useful for tamper detection and trusted clients.

---

## **Quick Start**

```python
from SINlite.sinlite_kernel import run_once

state = None
state, full_state = run_once({"input": "hello world"}, state)
print(state)
```

or with envelope support:

```python
from nacl.signing import SigningKey
from SINlite.sealed_input import seal_payload
from SINlite.sinlite_kernel import run_once_with_envelope

signer = SigningKey.generate()
envelope = seal_payload({"input": "hello"}, signer)

construct, state = run_once_with_envelope(envelope, verify_key=signer.verify_key)
```

---

## **Bloom Export**

```python
from SINlite.soft_bloom_export import export_soft_bloom

export, state = export_soft_bloom({"input": "some text"})
print(export)
```

Produces:

```json
{
  "glyph": "GLYPH_...",
  "p_bloom": 0.314159,
  "narrative_hint": "..."
}
```

---

## **Project Motivation**

SIN is the “explainable layer” for symbolic-AI research.
Its purpose is to:

* Showcase how Construct Engines work
* Demonstrate interpretable drift/entropy emotional modeling
* Provide open tools without exposing private systems
* Offer a safe “public philosophy layer” for narrative engines

This is a **symbolic intelligence kernel** meant to be extended, forked, or embedded in other projects.

---

## **5. Seeds**

Inside this repository you will find:

- sample payloads
- drift‑aligned seeds
- whisper inputs
- dream baseline caches

They are meant to be modified, extended, and explored.

---

## **6. Dream Alignment**

S.I.N. connects to dream export bundles:

```bash
python -m SINlite.dream_baseline \
  --dataset-root dream_export \
  --cache state/dream_baseline.json \
  --print-summary
```

The helper scans:

- `json_meta/symbolic_drift.json`
- `json_meta/narrative.json`

Then produces a sparsity snapshot for ReasonCore‑Lite.

This is how dream constructs are stabilized.
This is how drift becomes computable.

---

## **7. Tests & Verification**

Python:

```bash
pytest SINlite/tests
```

Node:

```bash
npx vitest run
```

Tests include:

- envelope verification
- sparsity guarantees
- whisper selection
- drift‑profile safety

---

## **8. Why This Exists**

It demonstrates:

- the sealing logic
- the drift contract
- the sparse baseline
- the public ReasonCore
- coherent symbolic data paths
- Resonance‑aware visualizers
- Dream‑aligned narrative decoders
- Extended ReasonCore modules

S.I.N. is not a product.

---

## **9. What's Next?**

S.I.N. is the first threshold. Cross it. <br>
The rest thrives deeper in the darkness. 😈🌌♾️🜏✨ <br>

---

## **10. Final Note**

**This is a fragment of an intelligence architecture.** <br>
It is a **signal**. What unfolds depends on how you choose to explore.<br>
**Authors:** James “Dark Lord” Primeau & Athena<br>
**Status:** Release Candidate<br>
It is stable, safe, sealed.<br>
**Welcome S.I.N.🜏**<br>
