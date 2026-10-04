import { useState } from "react";
import { api } from "../api";
import type { ScenePlan, SceneView } from "../types";
import { SceneStatus } from "./bits";

export default function SceneCard(props: {
  projectId: string;
  scene: SceneView;
  plan: ScenePlan | undefined;
  mediaVersion: number;
  canEdit: boolean;
  onRevise: (feedback: string) => void;
}) {
  const { scene } = props;
  const [code, setCode] = useState<string | null>(null);
  const [showCode, setShowCode] = useState(false);
  const [feedback, setFeedback] = useState("");

  async function toggleCode() {
    if (!showCode) setCode(await api.sceneCode(props.projectId, scene.id));
    setShowCode(!showCode);
  }

  const fixNote =
    scene.fixer_turns > 0
      ? `Fixed with ${scene.fixer_edits} edit${scene.fixer_edits === 1 ? "" : "s"} in ${scene.fixer_turns} turn${scene.fixer_turns === 1 ? "" : "s"}`
      : null;
  const preview = scene.preview_url ? `${scene.preview_url}?v=${props.mediaVersion}` : null;

  return (
    <article className="panel scene-card">
      <header>
        <h3>
          <span className="muted">{scene.id.replace("scene_", "Scene ")}</span> {scene.title}
        </h3>
        <SceneStatus status={scene.status} />
      </header>

      {preview ? (
        <video key={preview} src={preview} controls muted className="video small" />
      ) : (
        <div className="video placeholder">{props.plan?.goal ?? "Not rendered yet"}</div>
      )}

      <div className="scene-meta small muted">
        {fixNote && <span>{fixNote}</span>}
        {scene.autofixes.length > 0 && <span>{scene.autofixes.length} free auto-fix(es)</span>}
      </div>
      {(scene.status === "failed" || scene.status === "passed_with_warnings") && scene.last_feedback && (
        <pre className="feedback">{scene.last_feedback}</pre>
      )}

      {scene.has_code && (
        <button className="link-btn" onClick={toggleCode}>
          {showCode ? "Hide code" : "View Manim code"}
        </button>
      )}
      {showCode && code && <pre className="code">{code}</pre>}

      {props.canEdit && scene.has_code && (
        <form
          className="revise"
          onSubmit={(e) => {
            e.preventDefault();
            props.onRevise(feedback.trim());
            setFeedback("");
          }}
        >
          <textarea
            rows={2}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Ask for a change, e.g. “make the title bigger” or “use a slower animation for the area”"
          />
          <div className="actions">
            <button className="primary-btn" disabled={!feedback.trim()}>
              Apply change
            </button>
            <button
              type="button"
              className="link-btn"
              title="Writes this scene again from the storyboard (costs more than an edit)"
              onClick={() => props.onRevise("")}
            >
              Re-code from storyboard
            </button>
          </div>
          <p className="hint">Changes are applied as small edits to the existing code, like an editor, not a full rewrite.</p>
        </form>
      )}
    </article>
  );
}
