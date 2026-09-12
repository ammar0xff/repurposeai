const TOKEN_KEY = "rpa_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) => {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
};

export const unauthEvent = "rpa:unauth";

export interface ApiError extends Error {
  status: number;
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  if (body && !isForm) headers["Content-Type"] = "application/json";
  let r: Response;
  try {
    r = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch {
    const e = new Error("Network error. Check the connection.") as ApiError;
    e.status = 0;
    throw e;
  }
  if (r.status === 401) {
    window.dispatchEvent(new CustomEvent(unauthEvent));
  }
  if (!r.ok) {
    let msg = `${method} ${path}: ${r.status}`;
    try {
      const j = await r.json();
      if (typeof j?.message === "string") msg = j.message;
    } catch {
      /* keep default message */
    }
    const e = new Error(msg) as ApiError;
    e.status = r.status;
    throw e;
  }
  return r.json() as Promise<T>;
}

export const get = <T,>(p: string) => req<T>("GET", p);
export const post = <T,>(p: string, b?: unknown) => req<T>("POST", p, b);
export const del = <T,>(p: string) => req<T>("DELETE", p);
export const put = <T,>(p: string, b?: unknown) => req<T>("PUT", p, b);

export const authHeaders = (): Record<string, string> => {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export function uploadMedia(pid: string, file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return req<{ storage_key: string; size: number }>(
    "POST",
    `/api/projects/${pid}/upload`,
    fd,
  );
}

export async function clipVideoUrl(id: string): Promise<string> {
  const r = await fetch(`/api/clips/${id}/download`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`download ${r.status}`);
  const blob = await r.blob();
  return URL.createObjectURL(blob);
}

export interface Project {
  id: string;
  title: string;
  description: string;
  language: string | null;
  duration: number;
  status: string;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Stage {
  name: string;
  status: string;
  progress: number;
  started_at: string;
  completed_at: string;
  error: string;
}

export interface Job {
  id: string;
  project_id: string;
  status: string;
  progress: number;
  current_stage: string;
  error: string;
  created_at: string;
}

export interface JobDetail extends Job {
  params: Record<string, unknown>;
  stages: Stage[];
}

export interface ClipItem {
  id: string;
  start: number;
  end: number;
  status: string;
  render_profile: string;
  validation: { status?: string; checks?: Record<string, boolean> };
  axes: Record<string, number>;
  score: number;
  metadata: {
    titles: string[];
    caption: string;
    hashtags: string[];
    chosen_title: number;
  };
  decision: string | null;
}

export interface Campaign {
  id: string;
  name: string;
  version: number;
  rules: Record<string, unknown>;
  verified: boolean;
  p0_missing: string[];
  blockers: string[];
  ready: boolean;
}

export interface Metrics {
  now: string;
  stale_timeout_s: number;
  jobs: Record<string, number>;
  running: { id: string; stage: string; progress: number; heartbeat_age_s: number }[];
  stale_running: string[];
  recent_failed: { id: string; stage: string; error: string; updated_at: string }[];
  disk_free_gb: number;
  db_size_bytes: number;
}

export interface SequenceItem {
  clip_id: string;
  start?: number | null;
  end?: number | null;
  reframe?: string | null;
  caption_style?: string | null;
  credit?: string | null;
  transition?: string | null;
  transition_duration?: number | null;
  clip?: { start: number; end: number; status: string; render_profile: string };
}

export interface SequenceValidation {
  status?: string;
  checks?: Record<string, boolean>;
}

export interface Sequence {
  id: string;
  name: string;
  items: SequenceItem[];
  rendered_key: string;
  rendered_validation: SequenceValidation;
}

export interface SequenceRender {
  id: string;
  storage_key: string;
  validation: SequenceValidation;
  duration: number;
  download_url: string;
}

export function getSequence(pid: string) {
  return get<Sequence>(`/api/projects/${pid}/sequence`);
}

export function putSequence(pid: string, body: { name?: string; items?: SequenceItem[] }) {
  return put<Sequence>(`/api/projects/${pid}/sequence`, body);
}

export function autofillSequence(pid: string) {
  return post<Sequence>(`/api/projects/${pid}/sequence/autofill`);
}

export function renderSequence(
  pid: string,
  body: { transition?: string | null; transition_duration?: number | null },
) {
  return post<SequenceRender>(`/api/projects/${pid}/sequence/render`, body);
}

export async function sequenceDownloadUrl(pid: string): Promise<string> {
  const r = await fetch(`/api/projects/${pid}/sequence/download`, {
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error(`download ${r.status}`);
  const blob = await r.blob();
  return URL.createObjectURL(blob);
}