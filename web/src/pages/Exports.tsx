import { useEffect, useState } from "react";
import { get, post, Project } from "../api";

export default function Exports() {
  const [projects, setProjects] = useState<Project[]>([]);
  useEffect(() => { get<Project[]>("/api/projects").then(setProjects).catch(() => {}); }, []);
  const run = async (pid: string) => {
    const e = await post<{ storage_key: string; manifest: { clips: unknown[] } }>(`/api/projects/${pid}/export`);
    alert(`Exported ${e.manifest.clips.length} clips (${e.storage_key})`);
  };
  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">Exports</h1>
      {projects.map((p) => (
        <div key={p.id} className="mb-2 flex items-center gap-2 rounded-xl border border-slate-800 bg-[#11151d] p-3 text-sm">
          <span className="font-medium">{p.title}</span><span className="flex-1" />
          <button onClick={() => void run(p.id)} className="rounded-lg bg-[#2e5aa8] px-3 py-1.5 text-xs font-semibold text-white">Export bundle</button>
        </div>
      ))}
    </div>
  );
}
