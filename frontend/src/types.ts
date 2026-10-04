// Mirrors backend/app/schemas (storyboard.py, api.py).

export type Role =
  | "text" | "muted" | "primary" | "secondary" | "highlight" | "accent" | "gold" | "teal" | "purple";
export type Quality = "low" | "medium" | "high";
export type Phase =
  | "created" | "planning" | "awaiting_approval" | "generating" | "done" | "stopped" | "failed";

export interface PlannedObject {
  id: string;
  kind: string;
  content: string;
  zone: string;
  color_role: Role;
}

export interface Beat {
  narration: string;
  visual: string;
  objects: PlannedObject[];
}

export interface ScenePlan {
  id: string;
  title: string;
  goal: string;
  techniques: string[];
  beats: Beat[];
}

export interface Storyboard {
  title: string;
  summary: string;
  symbol_colors: { symbol: string; role: Role }[];
  scenes: ScenePlan[];
}

export interface SceneView {
  id: string;
  title: string;
  status: string;
  fixer_turns: number;
  fixer_edits: number;
  autofixes: string[];
  last_feedback: string;
  preview_url: string | null;
  has_code: boolean;
}

export interface ProjectView {
  id: string;
  request: string;
  audience: string;
  theme_id: string;
  phase: Phase;
  error: { code: string; message: string } | null;
  busy: boolean;
  created: number;
  budget: { limit_usd: number; spent_usd: number; calls: number; by_agent: Record<string, number> };
  storyboard: Storyboard | null;
  scenes: SceneView[];
  final_url: string | null;
}

export interface ProjectSummary {
  id: string;
  title: string;
  phase: Phase;
  created: number;
  final_url: string | null;
  spent_usd: number;
}

export interface Theme {
  id: string;
  name: string;
  background: string;
  text: string;
  muted: string;
  primary: string;
  secondary: string;
  highlight: string;
  accent: string;
  gold: string;
  teal: string;
  purple: string;
}

export interface Health {
  ok: boolean;
  demo_mode: boolean;
  api_key_configured: boolean;
  profile: string;
  tts: string;
  tts_voice: string | null;
}

export type PipelineEvent =
  | { type: "log"; line: string; ts: number }
  | { type: "state"; phase: Phase; job: string | null; ts: number }
  | { type: "ping" };
