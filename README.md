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
