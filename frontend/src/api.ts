import type { Health, ProjectSummary, ProjectView, Quality, Storyboard, Theme } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/api/health"),
  themes: () => request<Theme[]>("/api/themes"),
  projects: () => request<ProjectSummary[]>("/api/projects"),
  project: (id: string) => request<ProjectView>(`/api/projects/${id}`),
  sceneCode: (id: string, sceneId: string) => request<string>(`/api/projects/${id}/scenes/${sceneId}/code`),
  create: (body: { request: string; audience: string; max_scenes: number; budget_usd: number; theme_id: string }) =>
    post<ProjectView>("/api/projects", body),
  saveStoryboard: (id: string, board: Storyboard) =>
    request<ProjectView>(`/api/projects/${id}/storyboard`, { method: "PUT", body: JSON.stringify(board) }),
  generate: (id: string, final_quality: Quality) =>
    post<ProjectView>(`/api/projects/${id}/generate`, { final_quality }),
  revise: (id: string, sceneId: string, feedback: string, final_quality: Quality) =>
    post<ProjectView>(`/api/projects/${id}/scenes/${sceneId}/revise`, { feedback, final_quality }),
  resume: (id: string, budget_usd: number | null, final_quality: Quality) =>
    post<ProjectView>(`/api/projects/${id}/resume`, { budget_usd, final_quality }),
};
