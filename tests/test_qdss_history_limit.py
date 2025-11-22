from __future__ import annotations

from SINlite.core.qdss_core import _initial_runtime_state, step


def test_history_respects_default_limit():
    state = _initial_runtime_state()
    history_limit = state["history_limit"]

    assert history_limit > 0

    total_steps = history_limit + 5
    for idx in range(total_steps):
        step({"input": f"entry {idx}"}, state)

    assert len(state["history"]) == history_limit

    expected_start = total_steps - history_limit + 1
    counters = [entry["counter"] for entry in state["history"]]
    assert counters[0] == expected_start
    assert counters[-1] == total_steps


def test_history_respects_custom_limit():
    state = _initial_runtime_state()
    state["history_limit"] = 3

    for idx in range(5):
        step({"input": f"entry {idx}"}, state)

    history = state["history"]
    assert len(history) == 3
    assert [entry["counter"] for entry in history] == [3, 4, 5]
