# Dugong 🟦🐟
## Desktop Pet as a Mediated Interaction Agent

> Dugong is not just a desktop pet.  
> It is a behavior reflection layer and a future interaction mediator between Cornelius and Anson.

---

# 🎯 Final Vision

Dugong is designed as a **behavioral agent system**, not merely a decorative desktop pet.

Its long-term evolution has three layers:

---

## Layer 1 — Stable Single-Player Core (V1)

A lightweight, always-on-top desktop companion that:

- Runs independently on any machine
- Has a floating draggable window
- Maintains internal state:
  - `energy`
  - `mood`
  - `focus`
  - `mode`
- Updates state on fixed time intervals (tick-based system)
- Persists state locally (JSON)
- Emits structured Events for every meaningful action
- Renders visual reactions based on state

This layer guarantees:

> Stability, modularity, testability, and architectural clarity.

V1 is about building a **clean core**, not fancy animation.

---

## Layer 2 — Mediated Interaction (Future Direction)

Dugong becomes the medium through which:

Cornelius → Dugong → Anson  
Anson → Dugong → Cornelius  

Instead of messaging each other directly, behaviors are translated into structured events.

Interaction is based on:

### Event (Instant Signal)
Examples:
- `mode_change`
- `focus_start`
- `focus_break`
- `commit`
- `streak`
- `manual_ping`

### State (Persistent Context)
Examples:
- current mode
- accumulated focus
- daily streak

### Signal (Agent Expression)
Examples:
- bubble text
- animation
- sprite change
- small notification badge

Key principle:

> Behavior first. Chat second.

---

## Layer 3 — Transport & Intelligence Expansion

Future versions may support:

- GitHub-based synchronization (low-frequency, low complexity)
- LAN-based real-time transport
- Cloud relay server
- Automatic behavior detection
- Decision logs
- Growth mechanics
- Unlockable skins

Core design constraint:

> Business logic must NEVER depend on transport.

Transport is replaceable infrastructure.

---

# 🧠 Architectural Overview

We follow strict separation of concerns.

## 1. UI Shell
- Window
- Dragging
- Context menu
- Click events

## 2. Controller
- Translates UI input into state transitions
- Drives tick cycle
- Triggers render updates

## 3. Core State (Pure Logic)
- State machine
- Tick rules
- Mode transitions
- Clamp logic

## 4. Renderer
- Maps state → sprite
- Maps state → bubble text
- UI hints

Side modules:

- Persistence (JSON)
- Event Bus (interaction abstraction)
- Transport layer (reserved)

---

# 📁 Repository Structure
dugong/
README.md

docs/
SPEC_V1.md
ARCHITECTURE.md
ROADMAP.md
PROTOCOL.md

dugong_app/
init.py
main.py

core/
  state.py
  rules.py
  events.py
  event_bus.py
  clock.py

ui/
  shell_qt.py
  renderer.py
  assets/

persistence/
  storage_json.py

interaction/
  protocol.py
  transport_base.py
  transport_file.py
  transport_github.py
  transport_lan.py

services/
  timers.py
  sensors_stub.py
tests/
test_state_tick.py
test_protocol.py

scripts/
run_dev.sh


---

# 🧩 V1 Scope Definition

V1 is strictly:

- Single-player
- Fully local
- Architecturally ready for expansion

### Must Have

- Floating always-on-top window
- Draggable
- Right-click menu with:
  - study
  - chill
  - rest
- 60-second tick update cycle
- energy / mood / focus drift logic
- JSON persistence
- Event emission system
- Click-triggered bubble text

### Not in V1

- No real networking
- No transport activation
- No automatic detection
- No complex animation
- No growth mechanics

---

# 👥 Division of Responsibility

## Cornelius — System Architect

Responsible for:

- `core/`
- `persistence/`
- `event_bus`
- `protocol`
- `tests/`
- architecture documentation

Deliverable standard:

- Tick system deterministic
- State transitions testable
- JSON persistence stable
- Clean event abstraction

---

## Anson — Product & Interaction

Responsible for:

- `ui/`
- Window behavior
- Drag logic
- Context menu
- Sprite mapping
- Bubble expression style
- Asset management

Deliverable standard:

- Dugong feels alive
- Interaction smooth
- No visual glitches
- Clean separation from core logic

---

# 🔮 Design Philosophy

Dugong is:

- A mirror of behavior
- A mediator of interaction
- A structured agent
- A long-term evolving system

It is not:

- A toy
- A chat bot
- A decorative widget

---

# 🚀 Long-Term Objective

In 3 years, Dugong should:

- Reflect real productivity signals
- Mediate structured interaction
- Maintain logs of behavioral history
- Act as a personal symbolic agent
- Be architecturally clean enough to scale

---

Dugong begins simple.

But it is built to grow.

---

# V1 Current Implementation Status (Updated: 2026-02-17)

This section reflects what is already implemented in code.

## Visible In UI (Now)

- Floating always-on-top window
- Draggable shell
- Mode controls: `study` / `chill` / `rest`
- Manual signal button: `ping`
- Click-triggered bubble text
- Live state line: `energy` / `mood` / `focus` / `mode`

## Core/Data Capabilities (Running, Not Fully Visualized Yet)

- Deterministic 60-second tick system (`DUGONG_TICK_SECONDS` configurable)
- Structured event emission (`state_tick`, `mode_change`, `click`, `manual_ping`)
- Local persistence:
  - `dugong_state.json` (state snapshot)
  - `event_journal/` (daily event logs)
  - `daily_summary.json` (daily aggregates + streak)
  - `focus_sessions.json` (derived study sessions)
- Event journal retention policy (`DUGONG_JOURNAL_RETENTION_DAYS`)

## Important Clarification

Some V1.1+ data features are currently **recorded in files** but not yet fully surfaced in UI (for example `focus_sessions.json` visualization).
