import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get, Job, Project } from "../api";

export default function Overview() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  useEffect(() => {
    get<Project[]>("/api/projects").then(setProjects).catch(() => {});
    get<Job[]>("/api/jobs").then(setJobs).catch(() => {});
  }, []);
  const active = jobs.find((j) => j.status === "running" || j.status === "queued");
  const stats: [string, number][] = [
    ["Projects", projects.length],
    ["Jobs", jobs.length],
    ["Running", jobs.filter((j) => j.status === "running").length],
    ["Ready for review", jobs.filter((j) => j.status === "ready_for_review").length],
  ];
  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">Overview</h1>
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {stats.map(([l, n]) => (
          <div key={l} className="rounded-xl border border-slate-800 bg-[#11151d] p-4">
            <div className="text-2xl font-extrabold tabular-nums">{n}</div>
            <div className="text-xs text-slate-400">{l}</div>
          </div>
        ))}
      </div>
      <div className="mb-4 rounded-xl border border-slate-800 bg-[#11151d] p-4">
        <h2 className="mb-2 text-sm font-semibold">Active processing</h2>
        {active ? (
          <div><div className="text-sm">{active.id.slice(0, 8)} ({active.current_stage})</div>
            <div className="mt-2 h-2 overflow-hidden rounded bg-slate-800">
              <div className="h-full bg-[#5f8dd3]" style={{ width: `${active.progress}%` }} /></div></div>
        ) : <div className="text-sm text-slate-400">Idle. Create a project to begin.</div>}
      </div>
      <div className="rounded-xl border border-slate-800 bg-[#11151d] p-4">
        <h2 className="mb-2 text-sm font-semibold">Recent projects</h2>
        {projects.slice(0, 5).map((p) => (
          <div key={p.id} className="flex items-center gap-2 border-t border-slate-800 py-2 text-sm">
            <span className="font-medium">{p.title}</span>
            <span className="text-slate-500">{p.status}</span>
            <span className="flex-1" />
            <Link className="text-[#5f8dd3]" to={`/review?project=${p.id}`}>Review</Link>
          </div>
        ))}
        {!projects.length && <div className="text-sm text-slate-400">No projects yet.</div>}
      </div>
    </div>
  );
}
