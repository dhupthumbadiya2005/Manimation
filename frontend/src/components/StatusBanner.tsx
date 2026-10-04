import { useState } from "react";
import type { ProjectView } from "../types";

/** Explains why a run paused or failed and offers the way forward. */
export default function StatusBanner({ view, onResume }: { view: ProjectView; onResume: (budget: number | null) => void }) {
  const [budget, setBudget] = useState(() => Math.round((view.budget.limit_usd + 0.5) * 100) / 100);
  if (view.busy || !view.error || (view.phase !== "stopped" && view.phase !== "failed")) return null;

  const { code, message } = view.error;
  const titles: Record<string, string> = {
    credits_exhausted: "Your Anthropic credits ran out",
    budget_exceeded: "This video reached its budget",
    interrupted: "The server restarted during generation",
    llm_config: "The API key needs attention",
  };
  const needsBudget = code === "budget_exceeded";

  return (
    <section className={`banner ${code === "credits_exhausted" ? "credits" : "error"}`}>
      <strong>{titles[code] ?? "Generation stopped"}</strong>
      <p className="pre">{message}</p>
      <p className="small">Everything finished so far is saved; resuming does not pay for it again.</p>
      <div className="banner-actions">
        {needsBudget && (
          <label className="field compact inline">
            <span>New budget (USD)</span>
            <input type="number" min={0.05} max={20} step={0.05} value={budget} onChange={(e) => setBudget(Number(e.target.value))} />
          </label>
        )}
        <button className="primary-btn" onClick={() => onResume(needsBudget ? budget : null)}>
          {code === "credits_exhausted" ? "I added credits — resume" : "Resume"}
        </button>
        {code === "credits_exhausted" && (
          <a className="secondary-btn" href="https://console.anthropic.com/settings/billing" target="_blank" rel="noreferrer">
            Open billing
          </a>
        )}
      </div>
    </section>
  );
}
