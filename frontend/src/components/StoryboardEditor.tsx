import { useEffect, useState } from "react";
import type { Storyboard } from "../types";

/** Human-in-the-loop review: edit narration and visuals before any code is written. */
export default function StoryboardEditor(props: {
  board: Storyboard;
  busy: boolean;
  onSave: (board: Storyboard) => Promise<unknown>;
  onApprove: () => void;
}) {
  const [draft, setDraft] = useState(props.board);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!dirty) setDraft(props.board);
  }, [props.board, dirty]);

  function update(fn: (b: Storyboard) => void) {
    const next = structuredClone(draft);
    fn(next);
    setDraft(next);
    setDirty(true);
  }

  async function saveThen(after?: () => void) {
    setSaving(true);
    try {
      if (dirty) await props.onSave(draft);
      setDirty(false);
      after?.();
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel storyboard">
      <div className="storyboard-head">
        <div>
          <h2>Storyboard</h2>
          <p className="muted">Review and edit before any code is written. Each beat becomes one narrated step.</p>
        </div>
        <div className="symbols">
          {draft.symbol_colors.map((s) => (
            <span key={s.symbol} className={`symbol role-${s.role}`}>
              {s.symbol}
            </span>
          ))}
        </div>
      </div>

      {draft.scenes.map((scene, si) => (
        <article key={scene.id} className="scene-plan">
          <input
            className="scene-title"
            value={scene.title}
            onChange={(e) => update((b) => void (b.scenes[si].title = e.target.value))}
          />
          <p className="muted small">{scene.goal}</p>
          <ol className="beats">
            {scene.beats.map((beat, bi) => (
              <li key={bi} className="beat">
                <label>
                  <span>Narration</span>
                  <textarea
                    rows={2}
                    value={beat.narration}
                    onChange={(e) => update((b) => void (b.scenes[si].beats[bi].narration = e.target.value))}
                  />
                </label>
                <label>
                  <span>On screen</span>
                  <textarea
                    rows={2}
                    value={beat.visual}
                    onChange={(e) => update((b) => void (b.scenes[si].beats[bi].visual = e.target.value))}
                  />
                </label>
              </li>
            ))}
          </ol>
        </article>
      ))}

      <div className="actions">
        <button className="secondary-btn" disabled={!dirty || saving} onClick={() => saveThen()}>
          Save edits
        </button>
        <button className="primary-btn" disabled={props.busy || saving} onClick={() => saveThen(props.onApprove)}>
          Approve &amp; generate video
        </button>
      </div>
    </section>
  );
}
