from schemas.dream_bridge_model import validate_dream_bridge_model
from SINlite.core import qdss_core


def test_step_can_emit_dream_bridge_envelope():
    result = qdss_core.step({"input": "signal"}, withDreamBridge=True)

    assert isinstance(result, dict)
    assert "state" in result
    assert "dream_bridge_envelope" in result

    envelope = result["dream_bridge_envelope"]
    assert envelope is not None

    valid, errors = validate_dream_bridge_model(envelope)
    assert valid, errors

    # Ensure state can continue to be reused without the envelope mutating it
    follow_up = qdss_core.step({"input": "next"}, state=result["state"], withDreamBridge=True)
    assert "state" in follow_up
    assert "dream_bridge_envelope" in follow_up
