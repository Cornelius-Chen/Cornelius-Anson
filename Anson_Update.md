# Anson Update Log

## Template
- Time: YYYY-MM-DD HH:MM:SS
- Scope:
- Files:
  - path/to/file
- Changes:
  - ...
- Validation:
  - command -> result

## 2026-02-17 04:26:00
- Scope: UI implementation TODO from Cornelius handoff.
- Please Implement:
  - Keep changes inside `dugong/dugong_app/ui/*` when possible.
  - Add sprite/assets rendering (not title-text only).
  - Improve bubble expression by `mode` + stat ranges.
  - Keep cross-platform context menu support (`Button-2/3`, `Control-Button-1`).
- Contract to Keep:
  - `DugongShell(on_mode_change, on_click)`
  - `update_view(sprite, state_text, bubble)`
  - `Renderer.sprite_for(state)`
  - `Renderer.bubble_for_click(state)`
- Done Criteria:
  - `python -m pytest` passes.
  - `python -m dugong_app.main` shows visible sprite changes by state.
