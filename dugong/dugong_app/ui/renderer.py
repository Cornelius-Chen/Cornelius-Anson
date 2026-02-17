from __future__ import annotations

from dugong_app.core.state import DugongState


class Renderer:
    def sprite_for(self, state: DugongState) -> str:
        # Cute companion emoji skin (V1 placeholder)
        base = "🦭"

        if state.energy < 30:
            return f"💤{base}"     # sleepy
        if state.focus > 75:
            return f"🤓{base}"     # focused
        if state.mood > 75:
            return f"✨{base}"     # happy
        return base                # neutral

    def bubble_for_click(self, state: DugongState) -> str:
        if state.mode == "study":
            return "📚 专注...咕噜..."
        if state.mode == "rest":
            return "🔋 深海静默模式"
        return "🌿 吃口海草，继续。"
