from scripts.demo_v2 import build_demo_steps


def test_demo_v2_timeline_has_end_marker() -> None:
    steps = build_demo_steps(include_cofocus=True)
    assert steps
    assert steps[-1].at_sec == 300
    assert "结束" in steps[-1].action
