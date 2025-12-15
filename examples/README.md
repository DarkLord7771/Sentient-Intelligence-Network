# SINlite Examples

Small, self contained scripts that exercise the public S.I.N. kernel. Each
example sticks to the public surface area: no private weights, no hidden
keys.

## Usage

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=.
```

Then run any example with Python:

```bash
python examples/basic_kernel_step.py
```

## Included scripts

- **basic_kernel_step.py** – single step through the kernel, showing the
  construct glyph, mode, and resonance.
- **stateful_loop.py** – feeds a series of inputs through `run_once`, carrying
  state forward to demonstrate deterministic evolution.
- **sealed_payload_demo.py** – signs a payload with a throwaway key, verifies
  it, and executes `run_once_with_envelope`.
- **soft_bloom_projection.py** – emits the minimal bloom export for a payload
  alongside the underlying runtime state.
