from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@dataclass(frozen=True)
class DemoStep:
    at_sec: int
    actor: str
    action: str
    expected: str


def _fmt_mmss(seconds: int) -> str:
    mm = seconds // 60
    ss = seconds % 60
    return f"{mm:02d}:{ss:02d}"


def build_demo_steps(include_cofocus: bool) -> list[DemoStep]:
    steps = [
        DemoStep(0, "A+B", "启动 app", "两端显示 source/skin"),
        DemoStep(30, "A", "点击 ping", "B 出现 A ping 气泡"),
        DemoStep(60, "A", "点击 pomo 开始 FOCUS", "A 显示 FOCUS 倒计时"),
        DemoStep(100, "A", "等待 focus 完成", "A +pearls，B 看到完成反射"),
        DemoStep(120, "B", "点击 pomo 开始 FOCUS", "A 看到 B 的 focus 反射"),
        DemoStep(160, "B", "等待 focus 完成", "B +pearls，A 看到 B 完成反射"),
    ]
    if include_cofocus:
        steps.extend(
            [
                DemoStep(180, "A+B", "同时点击 pomo", "两端进入重叠 FOCUS"),
                DemoStep(270, "A+B", "打开 debug", "展示 debug pomo / debug health"),
            ]
        )
    else:
        steps.append(DemoStep(270, "A+B", "打开 debug", "展示 debug pomo / debug health"))
    steps.append(DemoStep(300, "A+B", "结束", "完成 5 分钟演示"))
    return steps


def print_env_block(role: str, transport: str, repo: str, branch: str, folder: str, source_id: str) -> None:
    print(f"[{role}] demo env (PowerShell)")
    print(f'$env:DUGONG_SOURCE_ID="{source_id}"')
    print(f'$env:DUGONG_TRANSPORT="{transport}"')
    if transport == "github":
        print(f'$env:DUGONG_GITHUB_REPO="{repo}"')
        print('$env:DUGONG_GITHUB_TOKEN="<YOUR_TOKEN>"')
        print(f'$env:DUGONG_GITHUB_BRANCH="{branch}"')
        print(f'$env:DUGONG_GITHUB_FOLDER="{folder}"')
    else:
        shared = str((ROOT_DIR / ".demo_transport_shared").resolve())
        print(f'$env:DUGONG_FILE_TRANSPORT_DIR="{shared}"')
    print('$env:DUGONG_SYNC_INTERVAL_SECONDS="5"')
    print('$env:DUGONG_POMO_FOCUS_MINUTES="1"')
    print('$env:DUGONG_POMO_BREAK_MINUTES="1"')
    print("python -m dugong_app.main")
    print("")


def run_countdown(steps: list[DemoStep]) -> int:
    start = time.monotonic()
    idx = 0
    print("V2 demo running... (Ctrl+C to stop)")
    try:
        while idx < len(steps):
            elapsed = int(time.monotonic() - start)
            while idx < len(steps) and elapsed >= steps[idx].at_sec:
                s = steps[idx]
                print(f"[{_fmt_mmss(s.at_sec)}] {s.actor:>3s} | {s.action} -> {s.expected}")
                idx += 1
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    return 0


def print_plan(steps: list[DemoStep]) -> None:
    print("V2 demo script (5 min)")
    for s in steps:
        print(f"[{_fmt_mmss(s.at_sec)}] {s.actor:>3s} | {s.action} -> {s.expected}")
    print("")
    print("debug commands:")
    print("python -m dugong_app.debug pomo")
    print("python -m dugong_app.debug health")
    print("")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dugong V2 5-minute demo script")
    parser.add_argument("--transport", choices=["github", "file"], default="github")
    parser.add_argument("--repo", default=os.getenv("DUGONG_GITHUB_REPO", "owner/repo"))
    parser.add_argument("--branch", default=os.getenv("DUGONG_GITHUB_BRANCH", "main"))
    parser.add_argument("--folder", default=os.getenv("DUGONG_GITHUB_FOLDER", "dugong_sync"))
    parser.add_argument("--a-source", default="cornelius")
    parser.add_argument("--b-source", default="anson")
    parser.add_argument("--include-cofocus", action="store_true")
    parser.add_argument("--run", action="store_true", help="Run timeline countdown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    steps = build_demo_steps(include_cofocus=args.include_cofocus)
    print_plan(steps)
    print_env_block("A", args.transport, args.repo, args.branch, args.folder, args.a_source)
    print_env_block("B", args.transport, args.repo, args.branch, args.folder, args.b_source)
    if args.run:
        return run_countdown(steps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
