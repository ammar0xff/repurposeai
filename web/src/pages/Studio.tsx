import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get, post, type Job, type Project } from "../api";
import { useLiveJob } from "../lib/jobstream";
import DropGate, { type Started } from "../components/DropGate";
import { StageStepper } from "../components/StageStepper";
import {
  Button,
  Chip,
  EmptyState,
  Panel,
  PanelTitle,
  Progress,
  Stat,
} from "../components/ui";
import { FilmIcon, ReviewIcon } from "../icons";
import { fmtTime, timeAgo } from "../lib/format";

export default function Studio() {
  const [recent, setRecent] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [started, setStarted] = useState<Started | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [retrying, setRetrying] = useState(false);

  const { job, error } = useLiveJob(started?.jobId ?? null);

  const load = useCallback(() => {
    void get<{ items: Project[] }>("/api/projects")
      .then((r) => setRecent(r.items.slice(0, 6)))
      .catch(() => {});
    void get<Job[]>("/api/jobs")
      .then((r) => setJobs(r))
      .catch(() => {});
  }, []);

  useEffect(load, [load]);

  const begin = (s: Started) => {
    setStarted(s);
    void get<Project>(`/api/projects/${s.projectId}`)
      .then(setProject)
      .catch(() => {});
  };

  const done =
    job &&
    (job.status === "ready_for_review" || job.status === "failed" || job.status === "cancelled");

  const retry = async () => {
    if (!started || retrying) return;
    setRetrying(true);
    try {
      await post(`/api/jobs/${started.jobId}/retry`);
    } finally {
      setRetrying(false);
    }
  };

  const runningJobs = jobs.filter((j) => j.status === "running" || j.status === "queued");
  const readyJobs = jobs.filter((j) => j.status === "ready_for_review").length;

  if (started) {
    return (
      <div className="mx-auto max-w-3xl">
        <div className="mono mb-2 text-[11px] uppercase tracking-[0.16em] text-faint">
          Console
        </div>
        <h1 className="mb-1 text-2xl font-bold tracking-tight text-ink">
          Cutting {project?.title ?? "your video"} into shorts
        </h1>
        <div className="mono mb-6 text-xs text-faint">
          {started.jobId.slice(0, 8)} · {job?.status ?? "starting"}
        </div>

        <Panel>
          <div className="mb-4 flex items-center justify-between gap-3">
            <PanelTitle hint={job ? `${job.progress}%` : "connecting"}>
              Pipeline
            </PanelTitle>
            <div className="flex shrink-0 gap-2">
              {job && (job.status === "running" || job.status === "queued") ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void post(`/api/jobs/${started.jobId}/cancel`)}
                >
                  Cancel
                </Button>
              ) : null}
              {job && (job.status === "failed" || job.status === "cancelled") ? (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => void retry()}
                  disabled={retrying}
                >
                  {retrying ? "Restarting..." : "Retry the cut"}
                </Button>
              ) : null}
            </div>
          </div>

          {job ? (
            <div className="mb-5">
              <Progress value={job.progress} />
              <div className="mono mt-2 flex justify-between text-[11px] text-faint">
                <span>{job.current_stage ?? "queued"}</span>
                <span>{job.status}</span>
              </div>
            </div>
          ) : null}

          <div className="mb-5">
            <StageStepper
              stages={job?.stages ?? []}
              current={job?.current_stage}
              status={job?.status}
              error={job?.error}
            />
            {!job && error ? <div className="mt-2 text-xs text-danger">{error}</div> : null}
          </div>

          {done ? (
            job.status === "ready_for_review" ? (
              <div className="flex flex-col items-start justify-between gap-3 rounded-[10px] border border-success/40 bg-success-tint p-4 sm:flex-row sm:items-center">
                <div>
                  <div className="text-sm font-semibold text-success">Cuts are ready</div>
                  <div className="text-xs text-muted">
                    Ranked, captioned and rendered. Read them now, then decide key by key.
                  </div>
                </div>
                <Link to={`/review?project=${started.projectId}`}>
                  <Button variant="primary" size="sm">
                    <ReviewIcon size={15} />
                    Open review
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="rounded-[10px] border border-danger/40 bg-danger-tint p-4 text-sm text-danger">
                The cut stopped at {job?.current_stage ?? "?"}. Retry resumes from the
                interrupted stage, nothing is re-ingested.
              </div>
            )
          ) : null}
        </Panel>

        <div className="mt-4 text-xs text-faint">
          <button onClick={() => setStarted(null)} className="underline decoration-dotted hover:text-muted">
            Start another video
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mono mb-2 text-[11px] uppercase tracking-[0.16em] text-faint">
        Screening room · Studio
      </div>
      <h1 className="max-w-2xl text-balance text-[40px] font-bold leading-[1.05] tracking-tight text-ink sm:text-5xl">
        Long video in.{" "}
        <span className="text-primary">Shorts out.</span>
      </h1>
      <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-muted">
        Drop a full recording and RepurposeAI splits it into moments worth keeping:
        scored hooks, captions and titles, rendered as cuts. You approve, export and
        post. Generating is never publishing.
      </p>

      <div className="mt-8">
        <DropGate onStart={begin} />
      </div>

      <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Projects" value={recent.length + (started ? 1 : 0)} />
        <Stat
          label="Running now"
          value={runningJobs.length}
          sub={runningJobs.length ? `${runningJobs[0].current_stage ?? "queued"} · ${runningJobs[0].progress}%` : "idle"}
        />
        <Stat label="Awaiting review" value={readyJobs} />
        <Stat label="Library" value="Studio" sub="everything starts here" />
      </div>

      <div className="mt-10">
        <PanelTitle hint={`${recent.length} latest`}>Jump back in</PanelTitle>
        {recent.length ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((p) => (
              <Link
                key={p.id}
                to={`/review?project=${p.id}`}
                className="panel group overflow-hidden transition-all duration-200 ease-out hover:-translate-y-0.5 hover:border-primary/40"
              >
                <div className="relative flex aspect-video items-center justify-center bg-gradient-to-br from-primary-tint via-surface-2 to-surface-3">
                  <FilmIcon size={30} className="text-primary/70 transition-transform duration-200 ease-out group-hover:scale-105" />
                  <span className="absolute left-2.5 top-2.5">
                    <Chip tone={p.status === "processing" ? "warn" : "neutral"}>{p.status}</Chip>
                  </span>
                </div>
                <div className="p-4">
                  <div className="truncate font-semibold text-ink">{p.title}</div>
                  <div className="mono mt-1 text-[11px] text-faint">
                    {p.duration ? fmtTime(p.duration) : "no duration yet"} ·{" "}
                    {timeAgo(p.updated_at)}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Nothing on the shelves yet"
            copy="Your projects will land here, one cut at a time."
            action={
              <span className="text-xs text-faint">No clips yet. The studio is above.</span>
            }
          />
        )}
      </div>
    </div>
  );
}