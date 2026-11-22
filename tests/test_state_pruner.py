from src.observability.state_pruner import prune, prune_state


def test_large_payload_is_bounded():
    result = prune({"payload": "x" * 10000}, max_chars=512)
    assert result["truncated"] is True
    assert len(result["preview"]) < 512


def test_small_payload_is_preserved():
    value = {"count": 3}
    assert prune_state({"tool": value}) == {"tool": value}
