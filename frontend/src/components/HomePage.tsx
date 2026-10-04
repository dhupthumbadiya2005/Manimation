import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import type { ProjectSummary, Theme } from "../types";
import { PhaseBadge } from "./bits";
import ThemePicker from "./ThemePicker";

const EXAMPLES = [
  "Visualize the Pythagorean theorem with a geometric proof",
  "Why the derivative of x squared is 2x, using tangent lines",
  "Fourier series as rotating vectors drawing a square wave",
  "Projectile motion: why the path is a parabola",
  "How binary search finds a number in a sorted array",
  "Breadth-first search on a tree, level by level",
];

const AUDIENCES = [
  "curious high-school and university students",
  "middle-school students meeting the idea for the first time",
  "undergraduate STEM students",
  "graduate students and researchers",
];

export default function HomePage() {
  const [themes, setThemes] = useState<Theme[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [prompt, setPrompt] = useState("");
  const [audience, setAudience] = useState(AUDIENCES[0]);
  const [scenes, setScenes] = useState(3);
  const [budget, setBudget] = useState(0.75);
  const [themeId, setThemeId] = useState("3b1b");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.themes().then(setThemes, () => {});
    api.projects().then(setProjects, () => {});
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const view = await api.create({ request: prompt.trim(), audience, max_scenes: scenes, budget_usd: budget, theme_id: themeId });
      location.hash = `#/p/${view.id}`;
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="home">
      <section className="panel create">
        <h1>What should the video explain?</h1>
        <p className="lede">
          Describe a theorem, formula, simulation or algorithm. The Director plans a storyboard you can review, then the
          agents code, render and narrate it in the 3Blue1Brown style.
        </p>
        <form onSubmit={submit}>
          <textarea
            className="prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. Explain why the sum of the angles of a triangle is 180 degrees"
            rows={3}
            required
            minLength={5}
          />
          <div className="chips">
            {EXAMPLES.map((ex) => (
              <button type="button" key={ex} className="chip" onClick={() => setPrompt(ex)}>
                {ex}
              </button>
            ))}
          </div>

          <div className="field-row">
            <label className="field grow">
              <span>Audience</span>
              <select value={audience} onChange={(e) => setAudience(e.target.value)}>
                {AUDIENCES.map((a) => (
                  <option key={a}>{a}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Scenes</span>
              <select value={scenes} onChange={(e) => setScenes(Number(e.target.value))}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Budget (USD)</span>
              <input type="number" min={0.05} max={20} step={0.05} value={budget} onChange={(e) => setBudget(Number(e.target.value))} />
            </label>
          </div>

          <div className="field">
            <span>Color theme</span>
            <ThemePicker themes={themes} value={themeId} onChange={setThemeId} />
          </div>

          {error && <div className="banner error">{error}</div>}
          <button className="primary-btn" disabled={busy || prompt.trim().length < 5}>
            {busy ? "Starting…" : "Plan storyboard"}
          </button>
          <p className="hint">The budget is a hard cap: generation stops before spending more, and you can resume later.</p>
        </form>
      </section>

      <section className="panel list">
        <h2>Your videos</h2>
        {projects.length === 0 && <p className="muted">No videos yet.</p>}
        <ul className="project-list">
          {projects.map((p) => (
            <li key={p.id}>
              <a href={`#/p/${p.id}`}>
                <span className="title">{p.title}</span>
                <span className="meta">
                  <PhaseBadge phase={p.phase} /> {new Date(p.created * 1000).toLocaleString()} · ${p.spent_usd.toFixed(3)}
                </span>
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
