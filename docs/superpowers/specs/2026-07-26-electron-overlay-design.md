# Electron Overlay Shell — Design

## Context

Step 5 of [[POE2 Advisor — v1 Build Plan]] (`docs/v1-build-plan.md`): an always-on-top Electron window, toggled by a global hotkey, with a chat UI wired to the backend RAG pipeline validated in Step 4 (`backend/rag_loop.py`). This design covers only the overlay shell itself — the clipboard item-context hotkey (Step 6) is explicitly out of scope, deferred per the plan.

## Constraints

- **Cross-machine testing split**: development happens on macOS; Path of Exile 2 and the actual overlay-over-game verification happen on a separate Windows machine. Anything checkable without the game (window creation, hotkey toggle, chat round-trip) is verified in this session; anything requiring the real game (renders over Borderless/Windowed Fullscreen, feel of always-on-top over the actual game, hotkey conflicts in that Windows environment) is a manual step on the Windows machine, out of this session's reach.
- **Deployment mode**: dev-mode only for v1 — `git pull` + `npm install` + run on the Windows machine. No packaged installer (`electron-builder` etc.) — that's premature complexity before the overlay concept itself is validated.
- **Two-language stack**: Python (existing, validated RAG backend) + JS/Electron (new overlay frontend), communicating over localhost HTTP. This is an already-accepted trade-off from earlier project decisions ("AI tooling is Python-first"), not reopened here.

## Architecture

New top-level `overlay/` directory (sibling to `backend/`):

- **`overlay/electron/main.js`** — Electron main process. Creates a `BrowserWindow`:
  - `alwaysOnTop: true`
  - `frame: false` (no OS chrome)
  - `transparent: true` (only the chat panel is visible, not a full rectangle)
  - `skipTaskbar: true`
  - fixed size, not resizable (v1 simplicity) — starting at 420x560px, a reasonable chat-panel size that doesn't dominate the screen; easy to tune once seen over the real game
  - Registers the accelerator `CommandOrControl+Shift+Space` via Electron's built-in `globalShortcut` module (no extra dependency) — Electron's cross-platform modifier convention, resolving to `Ctrl+Shift+Space` on the target Windows machine. Chosen to be unlikely to collide with POE2's own bindings or common OS shortcuts. Toggles `window.show()` / `window.hide()`, matching the plan's literal "toggle visibility" wording. Not a click-through toggle; when hidden the window doesn't exist on screen at all, when visible it's a normal interactive window.
- **`overlay/electron/preload.js`** — minimal preload, standard Electron security defaults (`contextIsolation: true`, `nodeIntegration: false`). The renderer only needs `fetch()`, so this stays thin.
- **`overlay/src/App.jsx`** — React chat UI (Vite-scaffolded): scrollback list + input box.
- **`backend/api_server.py`** — new thin FastAPI file exposing `POST /ask`, served on `http://localhost:8000`. Imports refactored functions from `rag_loop.py` rather than duplicating retrieval/generation logic.
- **`backend/rag_loop.py`** — small refactor: extract the core retrieval+answer logic (currently prints directly inside `answer_question`) into a function that *returns* structured data (`{"answer": str}`, at minimum). The existing CLI entry point wraps it and prints, unchanged in behavior — the Step 4 CLI tool keeps working standalone.

### Approaches considered

- **A (chosen): FastAPI wrapping `rag_loop.py` + Electron/React frontend, HTTP over localhost.** Matches the plan's explicit design intent, reuses all Step-4-validated retrieval logic (12/12 test pass, including the exact-name-match fallback) with zero duplication.
- **B (rejected): Reimplement the RAG logic in Node.js/Express**, eliminating the two-language split. Rejected because it throws away validated, tested Python work and cuts against the project's own stated purpose (Python-first AI tooling skill-building).
- **C (rejected): Electron shells out to `rag_loop.py` as a subprocess per question**, no persistent server. Rejected because it pays Python startup + DB connection + OpenAI client init cost on every single question — bad latency for a chat interface, and exactly what the plan's "small local API server" phrasing steers away from.

## Data Flow

1. User presses the hotkey → Electron shows/hides the overlay window. Game keeps running underneath, untouched.
2. User types a question, submits → React sends `POST http://localhost:8000/ask` with `{"question": "..."}`.
3. FastAPI server runs the Step-4-validated pipeline: embed question → pgvector similarity search + exact-name-match fallback → GPT-4o-mini → returns `{"answer": "..."}`.
4. React appends the question + answer to the scrollback and renders it.

The UI shows only the final answer text for v1 — not the CLI's "Retrieved: [...]" debug listing (useful for our own testing, not for an end user mid-game). Can be added later if useful.

## Error Handling

- Backend unreachable (not started, crashed, wrong port) → `fetch()` fails → chat shows an inline message ("Couldn't reach the advisor backend — is it running?") instead of a silent failure or unhandled exception.
- While awaiting the OpenAI call → a lightweight "Thinking..." placeholder in the scrollback, replaced by the real answer on completion.
- Global hotkey registration failure (e.g. conflicts with another Windows app's binding) → logged to the main-process console. No in-UI fallback — the window may not be visible yet, so there's nowhere sensible to surface it, and this is a corner case not worth over-engineering for in v1.

## Testing

- **Verifiable in this session (macOS dev machine):** window opens/closes on hotkey trigger, chat UI renders and takes input, FastAPI server responds correctly to direct requests (curl-able), full request/response round-trip between Electron renderer and FastAPI server.
- **Only verifiable on the Windows/game machine (manual, out of session scope):** whether the window actually renders on top of POE2 in Borderless/Windowed Fullscreen, whether always-on-top/frameless/transparent looks and feels right over the real game, whether the hotkey conflicts with anything in that specific Windows setup. Built to Electron's standard, well-established APIs for this — the same mechanism real overlay tools (Awakened PoE Trade, OBS) use — but final confirmation is manual and on the user.

## Out of Scope (this design)

- Step 6 (clipboard item-context hotkey) — separate, optional, deferred per the plan.
- Packaged/distributable builds (electron-builder etc.) — premature before the overlay concept is validated on the target machine.
- Click-through / interactive-transparency modes — the plan specifies a show/hide visibility toggle, not click-through; not needed for v1.

## Related

- [[POE2 Advisor — v1 Build Plan]]
