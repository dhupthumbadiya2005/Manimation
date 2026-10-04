# MANImation Studio

Type one prompt ("Why is the derivative of x² equal to 2x?") and get a narrated, 3Blue1Brown-style video rendered with [Manim Community](https://www.manim.community/). A team of agents plans a storyboard you can edit, writes one Manim scene per section, renders it, and repairs failures with small code edits instead of rewrites.

Architecture and design decisions: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Run it

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22, ffmpeg, sox, cairo/pango and a LaTeX distribution
(macOS: `brew install cairo pango pkg-config ffmpeg sox` plus MacTeX).

```bash
cp .env.example .env          # add ANTHROPIC_API_KEY (not needed for demo mode)

# backend
cd backend && uv sync
uv run uvicorn app.main:app --port 8000

# frontend (dev, hot reload) in another terminal
cd frontend && npm install && npm run dev      # open http://localhost:5173
```

Or build the UI once (`cd frontend && npm run build`) and open http://localhost:8000 — the backend serves it.

**Demo mode (no API key, no credits):** `MANIMATION_DEMO=1 uv run uvicorn app.main:app` — the agents answer from the tested cookbook scenes, so the whole app (planning, coding, rendering, narration, UI) works offline from the API.

**Docker (everything in one container):**

```bash
docker compose up --build     # http://localhost:8000, projects persist in ./data
```

The first build downloads ~460 MB of LaTeX/ffmpeg packages (image ~3.1 GB). Downloads are cached, so if the network drops mid-build, re-running the command resumes instead of starting over.

## Narration voice

Narration uses **Deepgram Flux TTS** when `DEEPGRAM_API_KEY` is set (default voice `flux-priya-en`, Indian English, female), otherwise free Google TTS. Change it in `.env`:

```bash
MANIMATION_TTS=deepgram            # deepgram | gtts | silent
MANIMATION_TTS_VOICE=flux-priya-en # e.g. flux-meena-en (Indian female), flux-naveen-en (Indian male)
```

Or per run: `uv run python -m app.cli "..." --tts deepgram --voice flux-naveen-en`. Narration is only generated for the final render (previews are silent). **All lines of a video are recorded in one Deepgram session**, so the voice keeps the same tone across beats and scenes (measured: pitch drift across lines dropped from ~19 Hz to ~6 Hz vs. separate requests). The recording is reused until a narration line changes; then the whole video is re-recorded in one session (a few hundred characters). Voice list: https://developers.deepgram.com/docs/flux-tts/voices

## Command line

```bash
cd backend
uv run python -m app.cli "Explain the Pythagorean theorem visually" --scenes 3 --budget 0.50
uv run python -m app.cli --resume ../data/projects/<id>          # continue after credits/budget ran out
uv run python -m app.cli "Bubble sort" --demo --quality low      # no API calls
uv run python scripts/eval.py --limit 5 --total-budget 2         # quality/cost evaluation
```

## Cost controls

- Hard budget per video (`--budget` / UI field / `MANIMATION_BUDGET_USD`); the run stops *before* exceeding it.
- Economy profile by default (Sonnet 5.5 for every agent); `MANIMATION_PROFILE=quality` uses Opus for planning and fixing.
- Fixes and change requests are applied as small edits (Anthropic text-editor tool), never full rewrites.
- Free static checks, auto-fixes and layout checks run before any paid call; prompts are cached; every step is checkpointed so resuming never pays twice.
- When credits run out the run pauses with a clear message; add credits and press **Resume**.

## Tests

```bash
cd backend && uv run pytest              # includes real renders of every cookbook scene; no API calls
cd frontend && npm run typecheck
```

## Layout

```
backend/
  app/            FastAPI app, CLI, agents (pipeline/), Claude client + budget (llm/)
  manim_kit/      theme, layout zones, layout checks, base scene, helpers used by generated code
  knowledge/      tested cookbook scenes, toolkit reference, known-error hints
  scripts/        cookbook renderer, evaluation
frontend/         React + Vite UI
data/             projects (created at runtime)
```
