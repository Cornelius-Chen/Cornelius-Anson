import argparse

from scripts.stress_pomo import run_stress_pomo


def test_stress_pomo_fast_smoke(tmp_path) -> None:
    args = argparse.Namespace(
        mode="fast",
        minutes=0.2,
        hours=1.0,
        seed=7,
        workdir=str(tmp_path / ".stress_pomo"),
        clean=True,
        focus_seconds=12,
        break_seconds=5,
        step_seconds=1,
        sleep_per_step=0.0,
        pause_rate=0.01,
        resume_rate=0.35,
        skip_rate=0.01,
        restart_rate=0.01,
        net_jitter=0.12,
        time_jump_rate=0.01,
        time_jump_seconds=45,
        base_pearls=10,
        valid_ratio=0.8,
        warn_effective_rate=0.4,
        warn_skip_rate=0.7,
    )
    rc = run_stress_pomo(args)
    assert rc == 0
