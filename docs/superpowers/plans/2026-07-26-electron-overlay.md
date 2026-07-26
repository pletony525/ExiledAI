# Electron Overlay Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Step 5 Electron overlay shell — an always-on-top, hotkey-toggled chat window wired to the existing validated RAG backend — per `docs/superpowers/specs/2026-07-26-electron-overlay-design.md`.

**Architecture:** A thin FastAPI server (`backend/api_server.py`) wraps the already-validated `rag_loop.py` retrieval/generation logic behind `POST /ask`. An Electron app (`overlay/`) shows a React chat UI in an always-on-top, frameless, transparent window toggled by a global hotkey, calling the FastAPI server over `localhost` via plain `fetch()`.

**Tech Stack:** Python (FastAPI, uvicorn) for the API layer; Node/Electron + React + Vite for the overlay. No new Python test framework introduced — this project verifies backend changes via direct invocation against the live Postgres/OpenAI stack (the same style Step 4 used), not mocked unit tests.

## Global Constraints

- Window size: 420x560px, fixed (not resizable).
- Global hotkey: `CommandOrControl+Shift+Space`, toggles `show()`/`hide()` — not click-through.
- FastAPI server: `http://localhost:8000`, single `POST /ask` endpoint.
- `backend/api_server.py` MUST import and reuse `rag_loop.py`'s functions — never duplicate retrieval/generation logic.
- Dev-mode only: `npm run build` + `npm run start` (`electron .`). No packaged installer (electron-builder etc.) in this plan.
- Electron window starts hidden; the hotkey reveals it.
- This plan does not include Step 6 (clipboard item-context hotkey) — explicitly out of scope per the design spec.

---

### Task 1: Refactor `rag_loop.py` to separate retrieval logic from CLI printing

**Files:**
- Modify: `backend/rag_loop.py`

**Interfaces:**
- Produces: `get_answer(client, cur, question: str, entity_names: list[tuple]) -> dict` returning `{"answer": str, "retrieved": list[dict]}`, where each `retrieved` entry is `{"source": str, "content_type": str | None, "name": str, "distance": float, "exact_match": bool}`. This is what Task 2's FastAPI server will import and call.

- [ ] **Step 1: Capture baseline CLI output before refactoring**

Run from `backend/`:
```bash
.venv/bin/python rag_loop.py "What does the unique item Ab Aeterno do?" > /tmp/baseline_output.txt 2>&1
cat /tmp/baseline_output.txt
```
Expected: a `Retrieved:` section listing 5 chunks (top one should be `Ab Aeterno`, distance ~0.4), followed by an `Answer:` section describing Ab Aeterno's armour/movement speed properties. Keep this output for comparison in Step 3.

- [ ] **Step 2: Apply the refactor**

Replace the full contents of `backend/rag_loop.py` with:

```python
import os
import re
import sys

import psycopg
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
TOP_K = 5

SYSTEM_PROMPT = """You are a Path of Exile 2 build and trade advisor. Answer the \
user's question using ONLY the context chunks below, which come from a database \
of POE2 unique items, skill gems, support gems, and item modifiers.

If the context does not contain enough information to answer confidently, say so \
explicitly rather than guessing - do not use outside knowledge about Path of Exile 2 \
beyond what's in the context. Cite specific item/gem/mod names from the context when \
relevant."""


def retrieve(cur, question_embedding, top_k=TOP_K):
    vector_literal = "[" + ",".join(f"{x:.7f}" for x in question_embedding) + "]"
    cur.execute(
        """
        SELECT source, content, metadata, embedding <=> %s::vector AS distance
        FROM chunks
        ORDER BY distance
        LIMIT %s
        """,
        (vector_literal, top_k),
    )
    return cur.fetchall()


def build_prompt(question, chunks):
    context = "\n---\n".join(content for _, content, _, _ in chunks)
    return f"Context:\n---\n{context}\n---\n\nQuestion: {question}"


def load_entity_names(cur):
    """Names of uniques/gems for the exact-match fallback below. Mods are excluded -
    their names (e.g. "Sturdy", "Resilient") are too generic/short and would cause
    false-positive matches against unrelated questions."""
    cur.execute(
        """
        SELECT source, metadata->>'item_name' AS name
        FROM chunks
        WHERE metadata->>'content_type' IN ('unique_item', 'skill_gem', 'support_gem')
        """
    )
    return cur.fetchall()


def find_named_entity_match(question, entity_names):
    """Dense vector search alone can miss a specific named entity even when its chunk
    is perfectly good (confirmed during Step 4 testing - e.g. Astramentis, Abyssal Pact
    didn't surface in top-5 despite complete data). This exact/word-boundary match is a
    cheap, purely additive fallback: it can only add a relevant chunk, never remove one."""
    q_lower = question.lower()
    best = None
    for source, name in entity_names:
        if not name:
            continue
        pattern = r"\b" + re.escape(name.lower()) + r"\b"
        if re.search(pattern, q_lower) and (best is None or len(name) > len(best[1])):
            best = (source, name)
    return best


def fetch_chunk_by_source(cur, source):
    cur.execute("SELECT source, content, metadata, 0.0 FROM chunks WHERE source = %s", (source,))
    return cur.fetchone()


def get_answer(client, cur, question, entity_names):
    """Core retrieval + generation logic, shared by the CLI (main()) and the FastAPI
    server (api_server.py). Returns structured data instead of printing, so both
    callers can present it however they need."""
    embedding = client.embeddings.create(model=EMBED_MODEL, input=[question]).data[0].embedding
    chunks = retrieve(cur, embedding)

    match = find_named_entity_match(question, entity_names)
    if match and not any(c[0] == match[0] for c in chunks):
        exact_chunk = fetch_chunk_by_source(cur, match[0])
        if exact_chunk:
            chunks = [exact_chunk] + chunks

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(question, chunks)},
        ],
    )

    retrieved = [
        {
            "source": source,
            "content_type": metadata.get("content_type"),
            "name": metadata.get("item_name") or metadata.get("mod_name") or source,
            "distance": distance,
            "exact_match": bool(match and source == match[0]),
        }
        for source, _, metadata, distance in chunks
    ]

    return {"answer": response.choices[0].message.content, "retrieved": retrieved}


def answer_question(client, cur, question, entity_names):
    """CLI wrapper around get_answer() - prints the same output format as before."""
    result = get_answer(client, cur, question, entity_names)

    print("\nRetrieved:")
    for r in result["retrieved"]:
        tag = " [exact-match]" if r["exact_match"] else ""
        print(f"  [{r['distance']:.3f}] ({r['content_type']}) {r['name']}{tag}")

    print("\nAnswer:")
    print(result["answer"])


def main():
    database_url = os.environ.get("DATABASE_URL")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not database_url or not openai_api_key:
        print("DATABASE_URL and OPENAI_API_KEY must both be set (env or .env)", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=openai_api_key)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            entity_names = load_entity_names(cur)

            if len(sys.argv) > 1:
                answer_question(client, cur, " ".join(sys.argv[1:]), entity_names)
                return

            print("POE2 Advisor - ask a question (blank line or Ctrl-D to quit)")
            while True:
                try:
                    question = input("\n> ").strip()
                except EOFError:
                    break
                if not question:
                    break
                answer_question(client, cur, question, entity_names)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Re-run the same command and compare**

```bash
.venv/bin/python rag_loop.py "What does the unique item Ab Aeterno do?" > /tmp/refactored_output.txt 2>&1
diff /tmp/baseline_output.txt /tmp/refactored_output.txt
```
Expected: the `Retrieved:` section is byte-identical (same 5 sources, same distances, same order). The `Answer:` text may differ in exact wording (GPT-4o-mini isn't deterministic) but should still correctly describe Ab Aeterno's armour/movement speed properties. If the `Retrieved:` section differs at all, the refactor changed behavior - stop and fix before continuing.

- [ ] **Step 4: Commit**

```bash
git add backend/rag_loop.py
git commit -m "refactor: extract get_answer() from rag_loop.py for reuse by the API server"
```

---

### Task 2: Create the FastAPI server wrapping `get_answer()`

**Files:**
- Create: `backend/api_server.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: `get_answer(client, cur, question, entity_names) -> {"answer": str, "retrieved": list[dict]}` and `load_entity_names(cur) -> list[tuple]` from `rag_loop.py` (Task 1).
- Produces: `POST http://localhost:8000/ask` accepting `{"question": str}`, returning `{"answer": str}`. This is what Task 5's React UI will call.

- [ ] **Step 1: Add FastAPI and uvicorn to requirements.txt**

Add these two lines to `backend/requirements.txt`:
```
fastapi==0.115.6
uvicorn==0.34.0
```

Install them:
```bash
cd backend && .venv/bin/pip install fastapi==0.115.6 uvicorn==0.34.0
```

- [ ] **Step 2: Write `backend/api_server.py`**

```python
import os
from contextlib import asynccontextmanager

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

from rag_loop import get_answer, load_entity_names

load_dotenv()

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = os.environ["DATABASE_URL"]
    openai_api_key = os.environ["OPENAI_API_KEY"]
    state["client"] = OpenAI(api_key=openai_api_key)
    state["conn"] = psycopg.connect(database_url)
    state["cur"] = state["conn"].cursor()
    state["entity_names"] = load_entity_names(state["cur"])
    yield
    state["cur"].close()
    state["conn"].close()


app = FastAPI(lifespan=lifespan)

# Allow the Electron renderer (loaded via file://) to call this server. This is a
# personal-use, localhost-only tool - not exposed beyond the local machine - so an
# open CORS policy is fine here and avoids chasing the exact file:// origin string.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    result = get_answer(state["client"], state["cur"], req.question, state["entity_names"])
    return {"answer": result["answer"]}
```

- [ ] **Step 3: Start the server and verify with a real request**

```bash
cd backend && .venv/bin/uvicorn api_server:app --port 8000 &
sleep 2
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the unique item Ab Aeterno do?"}'
```
Expected: a JSON object like `{"answer": "Ab Aeterno (Grand Cuisses)... 296 Armour... 21% increased Movement Speed..."}`. Then stop the server:
```bash
kill %1
```

- [ ] **Step 4: Commit**

```bash
git add backend/api_server.py backend/requirements.txt
git commit -m "feat: add FastAPI server wrapping the RAG loop for the Electron overlay"
```

---

### Task 3: Scaffold the Electron + Vite + React project

**Files:**
- Create: `overlay/package.json`
- Create: `overlay/vite.config.js`
- Create: `overlay/index.html`
- Create: `overlay/src/main.jsx`
- Create: `overlay/src/App.jsx`
- Create: `overlay/electron/main.js`

**Interfaces:**
- Produces: a working `npm run build && npm run start` cycle that opens a plain (not-yet-styled) Electron window showing a React-rendered page. Task 4 builds window behavior on top of this; Task 5 builds the real UI on top of this.

- [ ] **Step 1: Write `overlay/package.json`**

```json
{
  "name": "poe2-advisor-overlay",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "main": "electron/main.js",
  "scripts": {
    "build": "vite build",
    "start": "electron .",
    "dev": "vite build && electron ."
  },
  "devDependencies": {
    "vite": "^6.0.0",
    "@vitejs/plugin-react": "^4.3.4",
    "electron": "^33.2.0"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }
}
```

- [ ] **Step 2: Write `overlay/vite.config.js`**

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base: './' is required - Electron loads the built page via file://, not an
// http server, so absolute asset paths like /assets/index.js would fail to resolve.
export default defineConfig({
  plugins: [react()],
  base: './',
})
```

- [ ] **Step 3: Write `overlay/index.html`**

```html
<!doctype html>
<html>
  <head>
    <meta charset="UTF-8" />
    <title>POE2 Advisor</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 4: Write `overlay/src/main.jsx`**

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

- [ ] **Step 5: Write a placeholder `overlay/src/App.jsx`**

Task 5 replaces this with the real chat UI - this placeholder exists only to prove the build/window pipeline works before adding window-behavior (Task 4) and UI complexity (Task 5) on top of it.

```jsx
export default function App() {
  return <div>POE2 Advisor</div>
}
```

- [ ] **Step 6: Write a minimal `overlay/electron/main.js`**

No always-on-top/frameless/hotkey behavior yet - Task 4 adds that. This step only proves Electron can load the Vite build output.

```js
import { app, BrowserWindow } from 'electron'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

function createWindow() {
  const win = new BrowserWindow({
    width: 420,
    height: 560,
  })
  win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
```

- [ ] **Step 7: Install dependencies and verify the window opens**

```bash
cd overlay && npm install && npm run dev
```
Expected: a window opens showing the text "POE2 Advisor". This is a manual visual check - Electron GUI behavior isn't covered by this project's existing test tooling, consistent with the design spec's own testing section (window/hotkey behavior is verified by running and observing, not by an automated test suite). Close the window when confirmed.

- [ ] **Step 8: Commit**

```bash
git add overlay/
git commit -m "feat: scaffold Electron + Vite + React overlay skeleton"
```

---

### Task 4: Configure the overlay window (always-on-top, frameless, transparent, global hotkey)

**Files:**
- Modify: `overlay/electron/main.js`
- Create: `overlay/electron/preload.js`

**Interfaces:**
- Produces: a hidden-by-default window toggled by `CommandOrControl+Shift+Space`, always-on-top, frameless, transparent, `skipTaskbar`, fixed 420x560. Task 5's UI renders inside this window unchanged.

- [ ] **Step 1: Write a minimal `overlay/electron/preload.js`**

The renderer only needs plain `fetch()` to talk to the FastAPI server - no Node API access is required, so this stays effectively empty (contextIsolation is on by default in modern Electron).

```js
// No privileged APIs exposed - the renderer only needs fetch(), which is
// available in the sandboxed renderer without any preload bridging.
```

- [ ] **Step 2: Replace `overlay/electron/main.js` with the full window configuration**

```js
import { app, BrowserWindow, globalShortcut } from 'electron'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

let mainWindow = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 420,
    height: 560,
    alwaysOnTop: true,
    frame: false,
    transparent: true,
    skipTaskbar: true,
    resizable: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    },
  })
  mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
}

function toggleWindow() {
  if (!mainWindow) return
  if (mainWindow.isVisible()) {
    mainWindow.hide()
  } else {
    mainWindow.show()
  }
}

app.whenReady().then(() => {
  createWindow()
  const registered = globalShortcut.register('CommandOrControl+Shift+Space', toggleWindow)
  if (!registered) {
    console.error('Failed to register global hotkey CommandOrControl+Shift+Space - it may be in use by another application.')
  }
})

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
```

- [ ] **Step 3: Verify window behavior manually**

```bash
cd overlay && npm run dev
```
Expected, in order:
1. No window is visible immediately after launch (starts hidden).
2. Press `Cmd+Shift+Space` (macOS - `CommandOrControl` maps to `Cmd` here; the target Windows machine will use `Ctrl+Shift+Space`). The window appears with no title bar or OS border, showing "POE2 Advisor" on a see-through background (only the text is visible, not a filled rectangle - full transparency confirms the frameless+transparent config is correct since App.jsx's placeholder has no background styling yet).
3. Press the hotkey again - window disappears.
4. Press the hotkey once more to show it, then try clicking on another application - the overlay window should stay drawn on top rather than getting covered (confirms `alwaysOnTop`).

Note: the window will look visually broken (raw unstyled text floating in empty space) until Task 5 adds real UI + a background. That's expected at this point - this step only verifies window *mechanics*, not appearance.

- [ ] **Step 4: Commit**

```bash
git add overlay/electron/main.js overlay/electron/preload.js
git commit -m "feat: configure always-on-top frameless overlay window with global hotkey toggle"
```

---

### Task 5: Build the chat UI and wire it to the backend

**Files:**
- Modify: `overlay/src/App.jsx`
- Create: `overlay/src/App.css`

**Interfaces:**
- Consumes: `POST http://localhost:8000/ask` from Task 2, returning `{"answer": str}`.

- [ ] **Step 1: Write `overlay/src/App.css`**

```css
html, body, #root {
  margin: 0;
  height: 100%;
  background: transparent;
}

.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: rgba(20, 20, 24, 0.92);
  color: #eee;
  font-family: sans-serif;
  border-radius: 8px;
  overflow: hidden;
}

.scrollback {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.message {
  margin-bottom: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  white-space: pre-wrap;
}

.message.user {
  background: rgba(255, 255, 255, 0.08);
}

.message.assistant {
  background: rgba(80, 120, 200, 0.15);
}

form {
  display: flex;
  padding: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

input {
  flex: 1;
  padding: 8px;
  border-radius: 4px;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: #eee;
}

input:focus {
  outline: 1px solid rgba(255, 255, 255, 0.3);
}
```

- [ ] **Step 2: Replace `overlay/src/App.jsx` with the real chat UI**

```jsx
import { useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000/ask'

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    const question = input.trim()
    if (!question || pending) return

    setMessages((prev) => [...prev, { role: 'user', text: question }])
    setInput('')
    setPending(true)
    setMessages((prev) => [...prev, { role: 'assistant', text: 'Thinking...' }])

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setMessages((prev) => [...prev.slice(0, -1), { role: 'assistant', text: data.answer }])
    } catch (err) {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: 'assistant', text: "Couldn't reach the advisor backend - is it running?" },
      ])
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="app">
      <div className="scrollback">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            {m.text}
          </div>
        ))}
      </div>
      <form onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a build, item, or gem..."
          disabled={pending}
        />
      </form>
    </div>
  )
}
```

- [ ] **Step 3: End-to-end verification with the backend running**

Terminal 1 - start the backend:
```bash
cd backend && .venv/bin/uvicorn api_server:app --port 8000
```

Terminal 2 - run the overlay:
```bash
cd overlay && npm run dev
```

Manual check:
1. Press the hotkey to show the window. It should now show a dark rounded chat panel (not raw floating text) with an input box at the bottom.
2. Type `What does the unique item Ab Aeterno do?` and press Enter.
3. Confirm a "Thinking..." message appears briefly, then is replaced with a real answer describing Ab Aeterno's properties.
4. Stop the backend server (Ctrl-C in Terminal 1).
5. Ask another question in the overlay. Confirm it shows "Couldn't reach the advisor backend - is it running?" instead of hanging, crashing, or showing a blank message.

- [ ] **Step 4: Commit**

```bash
git add overlay/src/App.jsx overlay/src/App.css
git commit -m "feat: build chat UI wired to the FastAPI backend with loading/error states"
```
