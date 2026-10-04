import type { Phase } from "../types";

const PHASE_LABEL: Record<Phase, string> = {
  created: "Created",
  planning: "Planning",
  awaiting_approval: "Review storyboard",
  generating: "Generating",
  done: "Done",
  stopped: "Paused",
  failed: "Failed",
};

export function PhaseBadge({ phase }: { phase: Phase }) {
  return <span className={`badge phase-${phase}`}>{PHASE_LABEL[phase] ?? phase}</span>;
}

const STATUS_LABEL: Record<string, string> = {
  pending: "Waiting",
  coding: "Writing code",
  coded: "Code written",
  rendering: "Rendering",
  fixing: "Fixing with edits",
  passed: "Ready",
  passed_with_warnings: "Ready (layout warnings)",
  failed: "Failed",
};

export function SceneStatus({ status }: { status: string }) {
  return <span className={`badge status-${status}`}>{STATUS_LABEL[status] ?? status}</span>;
}

export function Spinner() {
  return <span className="spinner" aria-hidden />;
}

export function BudgetMeter({ spent, limit, byAgent }: { spent: number; limit: number; byAgent: Record<string, number> }) {
  const pct = Math.min(100, (spent / Math.max(limit, 1e-9)) * 100);
  const detail = Object.entries(byAgent)
    .map(([agent, cost]) => `${agent} $${cost.toFixed(3)}`)
    .join(" · ");
  return (
    <div className="budget" title={detail || "No API calls yet"}>
      <div className="budget-head">
        <span>API spend</span>
        <span>
          ${spent.toFixed(3)} <span className="muted">of ${limit.toFixed(2)}</span>
        </span>
      </div>
      <div className="bar">
        <div className={`bar-fill ${pct > 85 ? "hot" : ""}`} style={{ width: `${pct}%` }} />
      </div>
      {detail && <div className="budget-detail muted">{detail}</div>}
    </div>
  );
}
