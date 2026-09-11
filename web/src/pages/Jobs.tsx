import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get, post, type Job } from "../api";
import { useLiveJob } from "../lib/jobstream";
import { StageStepper } from "../components/StageStepper";
import {
  Button,
  Chip,
  EmptyState,
  PageHead,
  Panel,
  Progress,
  type ChipTone,
} from "../components/ui";
import { FilmIcon, RetryIcon, XIcon } from "../icons";
import { timeAgo } from "../lib/format";

function toneFor(status: string): ChipTone {
  if (status === "ready_for_review") return "ok";
  if (status === "failed") return "bad";
  if (status === "cancelled") return "warn";
  if (status === "running" || status === "queued") return "neutral";
  return "neutral";
}

function LiveDetail({ jobId, projectId }: { jobId: string; projectId: string }) {
  const { job, error } = useLiveJob(jobId);
  if (!job) {
    return <div className="py-2 text-sm text-faint">{error || "Loading stages..."}</div>;
  }
  const canCancel = job.status === "running" || job.status === "queued";
  const canRetry = job.status === "failed" || job.status === "cancelled";
  return (
    <div className="border-t border-line pt-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="mono text-[11px] text-faint">
          {job.progress}% · {job.current_stage ?? "queued"}
        </div>
        <div className="flex gap-2">
          <Link to={`/review?project=${projectId}`}>
            <Button variant="primary" size="sm">See cuts</Button>
          </Link>
          {canCancel ? (
            <Button variant="ghost" size="sm" onClick={() => void post(`/api/jobs/${jobId}/cancel`)}>
              <XIcon size={14} />
              Cancel
            </Button>
          ) : null}
          {canRetry ? (
            <Button variant="ghost" size="sm" onClick={() => void post(`/api/jobs/${jobId}/retry`)}>
              <RetryIcon size={14} />
              Retry
            </Button>
          ) : null}
        </div>
      </div>
      <div className="mb-4">
        <Progress value={job.progress} />
      </div>
      <StageStepper
        stages={job.stages ?? []}
        current={job.current_stage}
        status={job.status}
        error={job.error}
      />
      {job.params && Object.keys(job.params).length ? (
        <div className="mono mt-4 border-t border-line pt-3 text-[11px] text-faint">
          {Object.entries(job.params).map(([k, v]) => (
            <span key={k} className="mr-4">
              {k}
              <span className="text-muted">:{typeof v === "string" ? JSON.stringify(v) : String(v)}</span>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function Jobs() {
  const [list, setList] = useState<Job[]>([]);
  const [open, setOpen] = useState<string | null>(null);

  const load = () =>
    void get<Job[]>("/api/jobs").then(setList).catch(() => {});

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <PageHead
        kicker="Ops"
        title="Jobs"
        right={
          list.length ? (
            <span className="mono text-xs text-faint">{list.length} tracked</span>
          ) : null
        }
      />

      {list.length ? (
        <div className="space-y-3">
          {list.map((j) => {
            const expanded = open === j.id;
            return (
              <div key={j.id} className="panel overflow-hidden">
                <button
                  onClick={() => setOpen(expanded ? null : j.id)}
                  className="flex w-full items-center gap-3 p-4 text-left transition-colors duration-150 ease-out hover:bg-surface-2/60"
                >
                  <span
                    className={`mono flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border text-[11px] ${
                      j.status === "running" || j.status === "queued"
                        ? "border-primary/30 text-primary"
                        : "border-line text-faint"
                    }`}
                  >
                    {j.id.slice(0, 3)}
                  </span>
                  <span className="mono hidden text-xs text-faint sm:inline">{j.id.slice(0, 8)}</span>
                  <span className="min-w-0 flex-1">
                    <span
                      className={`truncate text-sm ${
                        j.status === "running" ? "text-primary" : "text-body"
                      }`}
                    >
                      {j.current_stage ? j.current_stage.replace(/_/g, " ") : "queued"}
                    </span>
                    <span className="mono mt-0.5 block text-[10px] text-faint">
                      {timeAgo(j.created_at)}
                    </span>
                  </span>
                  <span className="mono hidden w-12 text-right text-xs text-muted md:inline">
                    {j.progress}%
                  </span>
                  <Chip tone={toneFor(j.status)}>{j.status.replace(/_/g, " ")}</Chip>
                  <span
                    className={`text-faint transition-transform duration-200 ${
                      expanded ? "rotate-45" : ""
                    }`}
                  >
                    <XIcon size={14} />
                  </span>
                </button>
                <div className="px-4 pb-4">
                  {expanded ? (
                    <LiveDetail jobId={j.id} projectId={j.project_id} />
                  ) : (
                    <div className="pr-14">
                      <Progress value={j.progress} />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <Panel>
          <EmptyState
            icon={<FilmIcon size={26} />}
            title="Nothing is running"
            copy="Jobs appear here the moment a video enters the pipeline from the Studio."
            action={
              <Link to="/">
                <Button variant="primary" size="sm">
                  Start a job
                </Button>
              </Link>
            }
          />
        </Panel>
      )}
    </div>
  );
}