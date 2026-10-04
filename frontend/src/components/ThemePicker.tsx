import type { Theme } from "../types";

const SWATCH_ROLES = ["primary", "secondary", "highlight", "accent", "gold"] as const;

export default function ThemePicker(props: { themes: Theme[]; value: string; onChange: (id: string) => void }) {
  return (
    <div className="theme-grid" role="radiogroup" aria-label="Color theme">
      {props.themes.map((t) => (
        <button
          key={t.id}
          type="button"
          role="radio"
          aria-checked={props.value === t.id}
          className={`theme-card ${props.value === t.id ? "selected" : ""}`}
          style={{ background: t.background, color: t.text }}
          onClick={() => props.onChange(t.id)}
        >
          <span className="theme-math" style={{ color: t.primary }}>
            f(<span style={{ color: t.highlight }}>x</span>)
          </span>
          <span className="swatches">
            {SWATCH_ROLES.map((r) => (
              <span key={r} className="swatch" style={{ background: t[r] }} />
            ))}
          </span>
          <span className="theme-name">{t.name}</span>
        </button>
      ))}
    </div>
  );
}
