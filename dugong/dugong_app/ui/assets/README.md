# UI Assets (PySide6)

Dugong UI will auto-load these PNG assets from this folder.

## Required
- `bg_ocean.png` (background)
- Character frames (at least one group):
  - `Swim_loop1.png` ... `Swim_loopN.png` (preferred)
  - or legacy fallback: `seal_1.png`, `seal_2.png`, `seal_3.png`

## Optional (used when present)
- `Idle_loop1.png` ... `Idle_loopN.png`
- `Turn1.png` ... `TurnN.png`
- `React_happy.png` (or `React_happy1..N`)
- `React_chill.png` (or `React_chill1..N`)
- `React_dumb.png` (or `React_dumb1..N`)
- `React_shock.png` (or `React_shock1..N`)

## Direction Rule
- Put only right-facing frames in assets.
- Left-facing frames are generated automatically by runtime mirror.
