import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ClipItem, get, post, Project } from "../api";

const AXES = ["hook", "standalone", "payoff", "clarity", "emotion", "retention"];

export default function Review() {
  const [params] = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [pid, setPid] = useState(params.get("project") || "");
  const [clips, setClips] = useState<ClipItem[]>([]);
  const [idx, setIdx] = useState(0);
  const video = useRef<HTMLVideoElement>(null);

  const loadProjects = useCallback(() => {
    get<{items: Project[]}>("/api/projects").then(r => r.items).then((ps) => {
      setProjects(ps);
      if (!pid && ps[0]) setPid(ps[0].id);
    }).catch(() => {});
  }, [pid]);
  useEffect(loadProjects, [loadProjects]);
  useEffect(() => {
    if (!pid) return;
    get<ClipItem[]>(`/api/projects/${pid}/clips`).then((cs) => { setClips(cs); setIdx(0); }).catch(() => {});
  }, [pid]);

  const cur = clips[Math.min(idx, Math.max(0, clips.length - 1))];
  const decide = useCallback(async (d: string) => {
    if (!cur) return;
    await post(`/api/clips/${cur.id}/${d === "approved" ? "approve" : "reject"}`, { decision: d });
    setClips((cs) => cs.map((c) => (c.id === cur.id ? { ...c, decision: d } : c)));
  }, [cur]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = (e.target as HTMLElement)?.tagName;
      if (/INPUT|TEXTAREA|SELECT/.test(t || "")) return;
      if (e.key === "ArrowRight") setIdx((i) => Math.min(i + 1, clips.length - 1));
      else if (e.key === "ArrowLeft") setIdx((i) => Math.max(i - 1, 0));
      else if (e.key === " ") { e.preventDefault(); const v = video.current; if (v) (v.paused ? v.play() : v.pause()); }
      else if (e.key === "a" || e.key === "A") void decide("approved");
      else if (e.key === "r" || e.key === "R") void decide("rejected");
      else if (e.key === "e" || e.key === "E") void decide("needs_edit");
      else if (e.key === "x" || e.key === "X") void decide("exported");
    };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [clips.length, decide]);

  const dl = (id: string, kind: "title" | "caption") => {
    const el = document.getElementById(`rv-${kind}`) as HTMLInputElement | null;
    if (el) { el.select(); void navigator.clipboard?.writeText(el.value); }
  };

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h1 className="text-xl font-bold">Review</h1>
        <select value={pid} onChange={(e) => setPid(e.target.value)}
          className="rounded-lg border border-slate-700 bg-[#0a0d12] px-2 py-1 text-sm">
          {projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
        <span className="flex-1" />
        <span className="hidden text-xs text-slate-500 md:inline">
          ←/→ move, space play, A approve, R reject, E edit, X export
        </span>
      </div>
      {!cur && <div className="rounded-xl border border-slate-800 p-4 text-sm text-slate-400">No clips in this project yet.</div>}
      {cur && (
        <div className="grid gap-3 lg:grid-cols-[1.15fr_1fr]">
          <div>
            <video ref={video} controls preload="metadata" src={`/api/clips/${cur.id}/download`}
              className="max-h-[62vh] w-full rounded-lg bg-black" />
            <div className="mt-2 flex flex-wrap gap-1">
              {clips.map((c, i) => (
                <button key={c.id} onClick={() => setIdx(i)}
                  className={`rounded-lg border px-2 py-1 text-xs ${i === idx ? "border-[#5f8dd3]" : "border-slate-700"}`}>{i + 1}</button>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-slate-800 bg-[#11151d] p-4">
            <div className="mb-1 text-sm text-slate-400">CLIP {idx + 1}/{clips.length} · {cur.start.toFixed(1)}s to {cur.end.toFixed(1)}s · {cur.decision || "pending"}</div>
            {Object.keys(cur.axes || {}).length > 0 && (
              <div className="mb-2">
                {AXES.filter((a) => a in cur.axes).map((a) => (
                  <div key={a} className="grid grid-cols-[90px_1fr_34px] items-center gap-2 text-xs">
                    <span className="capitalize text-slate-400">{a}</span>
                    <div className="h-1.5 overflow-hidden rounded bg-slate-800">
                      <div className="h-full bg-[#5f8dd3]" style={{ width: `${(cur.axes[a] || 0) * 10}%` }} /></div>
                    <span className="text-right tabular-nums">{(cur.axes[a] || 0).toFixed(1)}</span>
                  </div>
                ))}
              </div>
            )}
            <div className="mb-2 text-sm">Validation: {cur.validation ? Object.entries(cur.validation.checks || {}).map(([k, v]) => `${k}:${v ? "pass" : "FAIL"}`).join(", ") : "pending"}</div>
            <label className="mt-2 block text-xs text-slate-400">Title <button onClick={() => dl(cur.id, "title")} className="ml-1 rounded border border-slate-700 px-1">copy</button></label>
            <input id="rv-title" readOnly value={(cur.metadata.titles[cur.metadata.chosen_title] || cur.metadata.titles[0] || "").slice(0, 120)}
              className="w-full rounded-lg border border-slate-700 bg-[#0a0d12] px-2 py-1 text-sm" />
            <label className="mt-2 block text-xs text-slate-400">Caption <button onClick={() => dl(cur.id, "caption")} className="ml-1 rounded border border-slate-700 px-1">copy</button></label>
            <input id="rv-caption" readOnly value={cur.metadata.caption}
              className="w-full rounded-lg border border-slate-700 bg-[#0a0d12] px-2 py-1 text-sm" />
            <div className="mt-1 text-xs text-slate-400">Tags: {(cur.metadata.hashtags || []).join(" ")}</div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button onClick={() => void decide("approved")} className="rounded-lg border border-emerald-700 px-3 py-1.5 text-sm text-emerald-300">Approve (A)</button>
              <button onClick={() => void decide("rejected")} className="rounded-lg border border-red-800 px-3 py-1.5 text-sm text-red-300">Reject (R)</button>
              <button onClick={() => void decide("needs_edit")} className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm">Edit (E)</button>
              <button onClick={() => void decide("exported")} className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm">Export (X)</button>
            </div>
            <div className="mt-3 text-xs text-slate-500">Generate is not publish. Approved clips leave this app only via Export.</div>
          </div>
        </div>
      )}
    </div>
  );
}
