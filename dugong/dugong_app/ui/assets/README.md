# UI Assets (PySide6)

Skin-based layout is supported.

Recommended structure:
- `assets/dugong_skin/default/...` (default skin)
- `assets/dugong_skin/<your_skin_id>/...` (other skins)

Choose skin by env var:
- `DUGONG_SKIN_ID=auto` (recommended, resolve by source_id using `skin_map.json`)
- `DUGONG_SKIN_ID=default`
- `DUGONG_SKIN_ID=<your_skin_id>`

Auto mapping file:
- `assets/dugong_skin/skin_map.json`
- Example:
  - `cornelius -> horse`
  - `anson -> default`

Loader priority:
1. `assets/dugong_skin/<DUGONG_SKIN_ID>/`
2. `assets/dugong_skin/default/`
3. `assets/default/` (legacy)
4. `assets/` (legacy flat layout)

## Required
- `bg_ocean.png` (background)
- Character frames (at least one group):
  - `Swim_loop1.png` ... `Swim_loopN.png` (preferred)
  - or legacy fallback: `seal_1.png`, `seal_2.png`, `seal_3.png`

## Optional (used when present)
- `Idle_loop1.png` ... `Idle_loopN.png`
- `Turn1.png` ... `TurnN.png`
- `React_study.png` (or `React_study1..N`)
- `React_chill.png` (or `React_chill1..N`)
- `React_rest.png` (or `React_rest1..N`)

Legacy names are still supported:
- `React_happy*`, `React_dumb*`, `React_shock*`

## Direction Rule
- Put only right-facing frames in assets.
- Left-facing frames are generated automatically by runtime mirror.
