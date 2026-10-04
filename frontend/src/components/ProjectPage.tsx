import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useProjectEvents } from "../useProjectEvents";
import type { ProjectView, Quality } from "../types";
import { BudgetMeter, PhaseBadge, Spinner } from "./bits";
import LogPanel from "./LogPanel";
import SceneCard from "./SceneCard";
import StatusBanner from "./StatusBanner";
import StoryboardEditor from "./StoryboardEditor";

export default function ProjectPage({ id }: { id: string }) {
  const [view, setView] = useState<ProjectView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [quality, setQuality] = useState<Quality>("medium");
  // Bumped when a job finishes so <video> elements reload files rendered in place.
  const [mediaVersion, setMediaVersion] = useState(0);

  const wasBusy = useRef(false);

  const refresh = useCallback(() => {
    api.project(id).then(
      (v) => {
        if (wasBusy.current && !v.busy) setMediaVersion((n) => n + 1);
        wasBusy.current = v.busy;
        setView(v);
        setError(null);
      },
      (err) => setError((err as Error).message),
    );
  }, [id]);

  useEffect(refresh, [refresh]);
  const { lines, connected } = useProjectEvents(id, refresh);

  // Wrap actions: show errors, adopt the returned view.
  const act = (fn: () => Promise<ProjectView>) => () => {
    setError(null);
    fn().then(
      (v) => {
        wasBusy.current = v.busy;
        setView(v);
      },
      (err) => setError((err as Error).message),
    );
  };

  if (!view) {
    return <div className="panel">{error ? <div className="banner error">{error}</div> : <Spinner />}</div>;
  }

  const board = view.storyboard;
  const canEdit = !view.busy && (view.phase === "done" || view.phase === "stopped" || view.phase === "failed");
  const v = mediaVersion ? `?v=${mediaVersion}` : "";

  return (
    <div className="project">
      <section className="panel project-head">
        <div>
          <div className="eyebrow">
            <PhaseBadge phase={view.phase} /> {view.busy && <Spinner />}
          </div>
          <h1>{board?.title ?? view.request}</h1>
          {board?.summary && <p className="lede">{board.summary}</p>}
          <p className="muted small">
            Prompt: “{view.request}” · audience: {view.audience} · theme: {view.theme_id}
          </p>
        </div>
        <div className="head-side">
          <BudgetMeter spent={view.budget.spent_usd} limit={view.budget.limit_usd} byAgent={view.budget.by_agent} />
          <label className="field compact">
            <span>Render quality</span>
            <select value={quality} onChange={(e) => setQuality(e.target.value as Quality)}>
              <option value="low">Low · 480p, fastest</option>
              <option value="medium">Medium · 720p</option>
              <option value="high">High · 1080p60, slowest</option>
            </select>
          </label>
        </div>
      </section>

      {error && <div className="banner error">{error}</div>}
      <StatusBanner view={view} onResume={(budget) => act(() => api.resume(id, budget, quality))()} />

      {view.phase === "planning" && (
        <section className="panel center">
          <Spinner /> The Director is planning the storyboard…
        </section>
      )}

      {view.final_url && (
        <section className="panel final">
          <h2>Final video</h2>
          <video key={view.final_url + v} src={view.final_url + v} controls className="video" />
          <a className="secondary-btn" href={view.final_url} download={`${id}.mp4`}>
            Download MP4
          </a>
        </section>
      )}

      {board && view.phase === "awaiting_approval" && (
        <StoryboardEditor
          board={board}
          busy={view.busy}
          onSave={(b) => api.saveStoryboard(id, b).then(setView)}
          onApprove={act(() => api.generate(id, quality))}
        />
      )}

      {board && view.phase !== "awaiting_approval" && view.scenes.length > 0 && (
        <section className="scenes">
          {view.scenes.map((scene, i) => (
            <SceneCard
              key={scene.id}
              projectId={id}
              scene={scene}
              plan={board.scenes[i]}
              mediaVersion={mediaVersion}
              canEdit={canEdit}
              onRevise={(feedback) => act(() => api.revise(id, scene.id, feedback, quality))()}
            />
          ))}
        </section>
      )}

      <LogPanel lines={lines} connected={connected} />
    </div>
  );
}
