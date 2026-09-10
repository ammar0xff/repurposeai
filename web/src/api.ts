const BASE = "";
async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method, headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${method} ${path}: ${r.status}`);
  return r.json() as Promise<T>;
}
export const get = <T,>(p: string) => req<T>("GET", p);
export const post = <T,>(p: string, b?: unknown) => req<T>("POST", p, b);
export const del = <T,>(p: string) => req<T>("DELETE", p);
export interface Project { id: string; title: string; status: string; duration: number; config: Record<string, unknown>; }
export interface Job { id: string; project_id: string; status: string; progress: number; current_stage: string; error: string; }
export interface ClipItem { id: string; start: number; end: number; status: string;
  render_profile: string; validation: { status?: string; checks?: Record<string, boolean> };
  axes: Record<string, number>; score: number;
  metadata: { titles: string[]; caption: string; hashtags: string[]; chosen_title: number };
  decision: string | null; }
