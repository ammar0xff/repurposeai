import { useEffect, useState } from "react";
import { del, get, post, Project } from "../api";

export default function Projects() {
  const [list, setList] = useState<Project[]>([]);
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const load = () => get<{items: Project[]}>("/api/projects").then(r => r.items).then(setList).catch(() => {});
  useEffect(() => { load(); }, []);
  const create = async () => {
    if (!title.trim()) return;
    const p = await post<Project>("/api/projects", { title });
    setTitle("");
    if (source.trim()) {
      await post(`/api/projects/${p.id}/process`, { source: source.trim(), params: { clip_count: 3 } });
      setSource("");
    }
    load();
  };
  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">Projects</h1>
      <div className="mb-4 rounded-xl border border-slate-800 bg-[#11151d] p-4">
        <h2 className="mb-2 text-sm font-semibold">New project</h2>
        <div className="flex flex-col gap-2 md:flex-row">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title"
            className="w-full rounded-lg border border-slate-700 bg-[#0a0d12] px-3 py-2 text-sm" />
          <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source path or URL (optional, starts job)"
            className="w-full rounded-lg border border-slate-700 bg-[#0a0d12] px-3 py-2 text-sm" />
          <button onClick={create} className="rounded-lg bg-[#2e5aa8] px-4 py-2 text-sm font-semibold text-white">Create</button>
        </div>
      </div>
      {list.map((p) => (
        <div key={p.id} className="mb-2 flex items-center gap-2 rounded-xl border border-slate-800 bg-[#11151d] p-3 text-sm">
          <span className="font-medium">{p.title}</span>
          <span className="text-slate-500">{p.status} {p.duration ? `(${Math.round(p.duration)}s)` : ""}</span>
          <span className="flex-1" />
          <button onClick={async () => { await del(`/api/projects/${p.id}`); load(); }}
            className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-300">Delete</button>
        </div>
      ))}
    </div>
  );
}
