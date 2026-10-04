# MANImation Studio — Architecture & Build Plan

## Context
We're building a full-stack platform where math/physics/CS educators type **one prompt** ("Explain the Fourier series as rotating vectors") and get a **3Blue1Brown-style narrated video**. The engine is strictly **Python Manim (Community Edition)**, backend **FastAPI**, frontend **React**. The repo (`/Users/dhup/Projects/manimation`) is empty — this is a greenfield build.

Decisions confirmed with user: **Demo-ready MVP** (single user, SQLite, local render worker, no auth — but structured so multi-user is an additive change), **voiceover via manim-voiceover**, **Claude** as the LLM.

### What research says works (and fails)
- **TheoremExplainAgent** (arXiv 2502.19400): Planner (storyboard + narration) → Coder (Manim per scene) + TTS. Agentic planning is *essential* for long coherent videos; best agent hit ~94% render success. Main residual failure: **visual layout issues** (overlaps, off-screen text), not crashes.
- **Code2Video** (arXiv 2510.01174, ICML'26): Planner → Coder (auto-debug) → **Critic** using "visual anchor" grid prompts + multimodal frame feedback to fix layout. ~40% better than direct codegen.
- Common LLM-Manim failure modes we must design against: (1) mixing **ManimGL** APIs (`ShowCreation`, `TextMobject`, `self.frame`) into ManimCE code, (2) hallucinated kwargs, (3) LaTeX compile errors, (4) overlapping/out-of-frame mobjects, (5) one giant script where one bug kills the whole video.

→ Our design: **Plan → Code per scene → Validate → Render → Repair → Visually critique → Assemble**, with deterministic guardrails between every LLM step.

---

## 1. Agent Architecture

A **code-orchestrated pipeline** (plain Python state machine, not an autonomous free-roaming agent) — each agent is a focused Claude call with structured output; deterministic tools sit between them. This is easier to debug, cheaper, and gives a clean multi-agent story for presentation.

```
 Prompt + Theme + Audience level
          │
   ┌──────▼───────┐   Storyboard JSON (scenes → beats → narration, objects, color roles)
   │ 1. Director  │── user can review/edit storyboard in UI (human-in-the-loop) ──┐
   └──────────────┘                                                              │
          ┌──────────────────────── for each scene (parallel) ◄──────────────────┘
          ▼
   ┌──────────────┐  code   ┌──────────────┐ ok ┌──────────────┐ mp4+frames ┌──────────────┐
   │ 2. Scene     │────────►│ 3. Static    │───►│ 4. Renderer  │───────────►│ 6. Visual    │
   │    Coder     │         │   Validator  │    │  (sandboxed) │            │    Critic    │
   └──────▲───────┘         └──────┬───────┘    └──────┬───────┘            └──────┬───────┘
          │                  error │            error  │               layout issues│
          │                 ┌──────▼────────────────────▼──────┐                   │
          └─────────────────│ 5. Fixer (edit-only, max 8 turns)│◄──────────────────┘
                            └──────────────────────────────────┘
                                         │ all scenes pass
                                  ┌──────▼───────┐
                                  │ 7. Assembler │ ffmpeg concat → final 1080p60 mp4
                                  └──────────────┘
```

| # | Agent / Tool | Kind | Model | Input → Output |
|---|---|---|---|---|
| 1 | **Director (Planner)** | LLM | economy: `claude-sonnet-5-5` effort `medium` (quality profile: `claude-opus-5-5` `high`), structured output | Prompt, theme, audience, target length → `Storyboard` JSON |
| 2 | **Scene Coder** | LLM | `claude-sonnet-5-5`, effort `medium` | One `Scene` spec + theme API + cookbook snippets → one Python file with one `ThemedVoiceoverScene` subclass |
| 3 | **Static Validator** | Deterministic | — | AST parse, class-name check, import allow-list, banned calls (`os`, `subprocess`, `open`, network), **ManimGL-API blocklist**, symbol existence check against installed `manim` (via `inspect`), pre-compile every `MathTex` string with LaTeX |
| 4 | **Renderer** | Deterministic | — | `manim -ql` (480p15 preview) in subprocess w/ timeout + temp dir; also dumps **layout log** (see §2) and samples keyframes |
| 5 | **Fixer** | LLM agent (tools) | economy: `claude-sonnet-5-5` `medium` (quality: `claude-opus-5-5`) | Numbered file + error/layout report + error-KB hints → small `str_replace`/`insert` edits via Anthropic's text-editor tool, then `render_scene` tool to verify; whole-file rewrites refused; stops the moment a render is clean |
| 6 | **Visual Critic** | LLM (vision) + deterministic | `claude-sonnet-5-5` | Keyframes + layout log → pass / list of concrete fixes (fed back to Debugger; max 2 rounds) |
| 7 | **Assembler** | Deterministic | — | Re-render passed scenes at `-qh`/1080p60, ffmpeg concat, output mp4 + per-scene clips |

All Claude calls: Anthropic Python SDK, streaming + `.get_final_message()`, `fallbacks: "default"` (server-side refusal fallback beta), prompt caching on the large static system prompts (theme API + cookbook), structured outputs (`output_config.format`) for Director and Critic.

### Why these choices
- **Per-scene code** (not one big script): isolates failures, enables parallel rendering, and lets the user regenerate a single scene.
- **Deterministic validator before render**: catches ~most errors in milliseconds without a 30s render.
- **Opus for thinking-heavy steps (plan, debug), Sonnet for volume (code, critique)**.

---

## 2. Making the code *accurate* (the core quality levers)

1. **Theme + helper library the LLM codes against** (`backend/manim_kit/`): instead of free-form Manim, the Coder subclasses `ThemedVoiceoverScene` and uses semantic colors (`T.primary`, `T.secondary`, `T.highlight`, `T.var_x`) and tested helpers (`title_card()`, `equation_chain()`, `labeled_axes()`, `place_in_zone()`). Less surface area = fewer bugs, guaranteed consistent style.
2. **Layout zones** ("visual anchors"): the frame is split into named zones (`TOP`, `CENTER`, `LEFT`, `RIGHT`, `BOTTOM_CAPTION`). The Director assigns each object a zone; helper `place_in_zone()` auto-scales to fit. Directly targets the #1 failure mode.
3. **Layout instrumentation**: `ThemedVoiceoverScene.play()` is wrapped to log every on-screen mobject's bounding box after each animation → `layout.json`. Deterministic checks: out-of-frame, text overlap, text too small. Critic gets these facts plus frames.
4. **Curated cookbook** (`backend/knowledge/cookbook/*.py`): ~30 verified ManimCE snippets of 3B1B idioms — `TransformMatchingTex`, `ValueTracker` + `always_redraw`, `Axes.plot`, `NumberPlane` transforms, `MathTex` substring coloring, vector fields, graphs/trees for CS. Each is CI-rendered so we know it works. Director tags scenes with techniques; Coder gets only matching snippets.
5. **API grounding**: when a render fails with a missing attribute or unexpected keyword, the real signature / closest real names are looked up from the installed manim (`knowledge.api_hints`) and added to the Fixer's report — free, no LLM call.
6. **Error knowledge base** (`backend/knowledge/errors.yaml`): regex → known fix (e.g. `NameError: ShowCreation` → `Create`; LaTeX `Missing $` → use `MathTex` not `Tex`). Matched hints go to the Fixer first; grows over time.
7. **Color semantics à la 3B1B**: Director assigns each mathematical symbol a color role once (`x → var_x/blue`, `f(x) → yellow`) and that mapping is enforced in every scene via `tex_to_color_map`.

---

## 2b. Credit controls

- **Hard budget per video** (`--budget`, default `MANIMATION_BUDGET_USD=0.75`), stored in the project; every call is logged to `usage.jsonl` with its cost; the run stops *before* a call that would start with < $0.03 left.
- **Economy profile by default** (Sonnet 5.5 everywhere, `medium` effort); `--profile quality` moves Director/Fixer to Opus 5.5.
- **Edit, don't regenerate**: failures are repaired by the Fixer with targeted edits (typical fix: 1 call, ~250 output tokens) instead of re-writing the scene.
- **Free first**: static validation, ManimGL→CE auto-renames, and layout checks run before any LLM call; the Fixer is only invoked when something is wrong.
- **Prompt caching**: the shared system prompt (instructions + toolkit reference) is a cache breakpoint, reused by every scene; tool loops use automatic caching.
- **Checkpoints**: storyboard, scene code, statuses and final renders are saved per step; `--resume` never pays for finished work, and unchanged final renders are reused.
- **Credits exhausted**: a 402 `billing_error` (or low-balance 400) stops the whole run immediately with a clear message, the billing link, and the `--resume` command. API surfaces it as error code `credits_exhausted`.
- Measured: a 2-scene narrated video cost **$0.073**; a live edit-based fix cost **$0.015**.

## 3. Theme System (3Blue1Brown default)

`Theme` = pydantic model, serialized in DB, rendered into `manim_kit/theme.py` at render time.

Default **"3Blue1Brown Classic"**:
- background `#1C1C1C`; text `#FFFFFF`; primary `#58C4DD` (BLUE); secondary `#83C167` (GREEN); highlight `#FFFF00` (YELLOW); accent `#FC6255` (RED); extra `#F0AC5F` (GOLD), `#5CD0B3` (TEAL), `#9A72AC` (PURPLE)
- LaTeX font: default Computer Modern (the 3B1B look); text font configurable
- Motion defaults: `run_time` 1–2s, `rate_func=smooth`, `Write` for equations, `TransformMatchingTex` for derivations, `FadeOut` cleanup between beats
Additional presets: "Chalkboard", "Light Paper", "Solarized". Users can make custom themes in the UI (color pickers → same schema).

---

## 4. Data Contracts (pydantic, `backend/app/schemas/`)

```
Storyboard { title, audience_level, theme_id, color_roles{symbol→role}, scenes[Scene] }
Scene      { id, title, goal, techniques[str], est_duration_s, beats[Beat] }
Beat       { narration: str, visual: str (frame-level description),
             objects[{id, kind: MathTex|Axes|Graph|Shape|Text|..., content, zone, color_role}],
             animations[{action: write|transform|create|move|fade|highlight, targets[], notes}] }
SceneAttempt { scene_id, n, code, stage: validate|render|critique, status, errors, video_path, frames[] }
```
Beats ↔ narration map 1:1 onto `with self.voiceover(text=beat.narration) as tracker:` blocks so animation length auto-syncs to speech.

---

## 5. Backend (FastAPI)

```
backend/
├── app/
│   ├── main.py                 # FastAPI app, CORS, static /media
│   ├── api/  projects.py jobs.py themes.py scenes.py ws.py
│   ├── schemas/                # pydantic contracts above
│   ├── pipeline/
│   │   ├── orchestrator.py     # state machine, emits events
│   │   ├── director.py  coder.py  debugger.py  critic.py
│   │   ├── validator.py  renderer.py  assembler.py  frames.py
│   │   └── prompts/            # versioned system prompts (.md)
│   ├── llm/client.py           # Anthropic client, caching, fallbacks, retries, cost logging
│   └── worker.py               # asyncio job queue + ProcessPool for renders
├── manim_kit/                  # theme.py, base_scene.py, helpers.py, zones.py, layout_log.py
├── knowledge/                  # cookbook/, errors.yaml, api_reference.md
├── scripts/build_api_reference.py
└── tests/
```

**Endpoints**
- `POST /projects` (prompt, theme_id, audience, length) → creates project + starts **plan** job
- `GET/PUT /projects/{id}/storyboard` — review & edit before coding
- `POST /projects/{id}/generate` → code+render job; `POST /projects/{id}/scenes/{sid}/regenerate` (optional feedback text)
- `POST /projects/{id}/finalize` → 1080p60 assemble
- `GET /themes`, `POST /themes`
- `WS /ws/projects/{id}` — live events: `stage_changed`, `agent_log`, `scene_status`, `preview_ready`, `error`

**Execution/sandbox (MVP)**: renders run in a subprocess with timeout (e.g. 180s/scene), isolated temp dir, validator-enforced import allow-list. Ship as **Docker** image (python 3.12 + manim + texlive-latex-extra + ffmpeg + sox) via `docker-compose` so the LaTeX/ffmpeg setup is reproducible. Later: swap asyncio queue for Redis+arq/Celery with no API change.

**Voiceover**: `manim-voiceover` with `GTTSService` default (free); service is configurable (Azure/ElevenLabs/local TTS later). Fallback if plugin breaks: pre-generate TTS per beat, pass durations to Coder, mux with ffmpeg.

---

## 6. Frontend (React + Vite + TypeScript)

Minimal but complete; Tailwind for speed.
1. **Create** — prompt box, domain preset (Math/Physics/CS), audience level, length, **theme picker** (live swatch preview, 3B1B default).
2. **Storyboard review** — scene cards with beats/narration, editable; "Approve & Generate".
3. **Studio** — live pipeline timeline per scene (Coding → Validating → Rendering → Fixing → Critiquing ✓), streaming agent log via WebSocket, per-scene preview players, code viewer (Monaco, read-only), "Regenerate scene with feedback".
4. **Final** — full video player, download mp4, download source `.py`.

```
frontend/src/{pages/, components/, api/client.ts, hooks/useProjectSocket.ts, types/ (mirrors pydantic)}
```

---

## 7. Build Phases

Status as of 2026-10-03:

1. **Foundation** — done: `manim_kit` (theme, zones, layout log, base scene, helpers), 18 tested cookbook scenes, single-container Docker image.
2. **Pipeline CLI** — done: Director → Coder → Validator → Renderer → Fixer (edit-only) → Assembler (`python -m app.cli`), credit controls, `--resume`, demo mode.
3. **Voiceover + Critic + Assembler** — narration (gTTS), deterministic layout checks and assembly done; **Visual Critic (vision LLM) not built yet** (needs API credits to develop and tune).
4. **Backend API** — done: REST + WebSocket events, one background worker, projects stored as checkpointed folders (no separate DB: the folder already holds every step, so a DB would duplicate it).
5. **Frontend** — done: React + Vite, Create → Storyboard review/edit → live progress → per-scene change requests (applied as edits) → final video; credits-exhausted banner with Resume.
6. **Hardening** — eval script ready (`scripts/eval.py`, 15 prompts); free API-signature hints for the Fixer. Running the eval needs credits.

---

## 8. Verification
- **Unit**: validator (catches ManimGL APIs, banned imports, bad LaTeX), zone placement math, schema round-trips.
- **Cookbook CI**: every snippet renders at `-ql` without error.
- **Pipeline eval** (`scripts/eval.py`): fixed set of ~15 prompts (Pythagorean theorem, derivative as slope, Fourier epicycles, projectile motion, simple harmonic motion, binary search, Dijkstra, sorting, matrix as linear transform…) → report render-success %, mean repair attempts, layout-violation count, tokens/$ per video.
- **End-to-end**: `docker compose up`, open React app, submit "Visualize the Pythagorean theorem with a geometric proof", approve storyboard, watch live progress, play final narrated 1080p video with 3B1B colors; regenerate one scene with feedback and confirm only that scene re-renders.

## Sources
- [TheoremExplainAgent (arXiv 2502.19400)](https://arxiv.org/html/2502.19400v2)
- [Code2Video (arXiv 2510.01174)](https://arxiv.org/pdf/2510.01174) · [OpenCV overview](https://opencv.org/code2video/)
- [3B1B-style palette reference](https://cdn.jsdelivr.net/gh/subinium/3b1b-style-animation-skill@main/README.md)
- [manim-voiceover (PyPI)](https://pypi.org/project/manim-voiceover/)
