import type { Stage } from "../api";
import { CheckIcon, XIcon } from "../icons";
import { Progress } from "./ui";

export function stageCopy(raw: string): string {
  const map: Record<string, string> = {
    ingest: "Pulling the file into storage",
    probe: "Reading codec and duration",
    analyze: "Scenes, faces and motion",
    transcribe: "Writing out the words",
    segment: "Carving candidate moments",
    rank: "Scoring hooks and payoff",
    caption: "Composing titles and captions",
    render: "Rendering the short-form cuts",
    validate: "Checking the cuts pass",
    export: "Packaging the bundle",
  };
  return map[raw] ?? raw.replace(/_/g, " ");
}

function DotGlyph({ state }: { state: string }) {
  if (state === "done")
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-success/15 text-success">
        <CheckIcon size={11} strokeWidth={2.4} />
      </span>
    );
  if (state === "running")
    return (
      <span className="relative flex h-5 w-5 items-center justify-center">
        <span className="absolute inline-flex h-5 w-5 animate-ping rounded-full bg-primary/25" />
        <span className="relative h-2.5 w-2.5 rounded-full bg-primary" />
      </span>
    );
  if (state === "failed" || state === "cancelled")
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-danger/15 text-danger">
        <XIcon size={11} strokeWidth={2.4} />
      </span>
    );
  return <span className="h-5 w-5 rounded-full border border-line-2" />;
}

export function StageStepper({
  stages,
  current,
  status,
  error,
}: {
  stages: Stage[];
  current?: string;
  status?: string;
  error?: string;
}) {
  if (!stages.length) {
    return (
      <div className="flex items-center gap-3 py-2 text-sm text-faint">
        <span className="inline-block h-2 w-2 animate-pulse-soft rounded-full bg-primary" />
        {current ? stageCopy(current) : "Queued"}...
      </div>
    );
  }

  const names = stages.map((s) => s.name);
  const activeIdx = current ? names.indexOf(current) : -1;

  return (
    <ol className="space-y-1">
      {stages.map((s, i) => {
        const isActive = i === activeIdx;
        const rowState =
          s.status === "done"
            ? "done"
            : s.status === "running" || isActive
              ? "running"
              : s.status === "failed" || s.status === "cancelled"
                ? "failed"
                : "pending";
        const isLast = i === stages.length - 1;
        return (
          <li key={s.name} className="relative flex gap-3 pb-1.5">
            <div className="flex flex-col items-center">
              <DotGlyph state={rowState} />
              {!isLast ? (
                <span
                  className={`mt-1 w-px flex-1 ${
                    s.status === "done" ? "bg-success/30" : "bg-line-2"
                  }`}
                />
              ) : null}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-3">
                <span
                  className={`text-sm font-medium ${
                    rowState === "pending" ? "text-faint" : "text-body"
                  }`}
                >
                  {stageCopy(s.name)}
                </span>
                {s.status === "running" ? (
                  <span className="mono text-[11px] text-primary">{s.progress}%</span>
                ) : null}
              </div>
              {s.status === "running" && s.progress > 0 ? (
                <div className="mt-1">
                  <Progress value={s.progress} />
                </div>
              ) : null}
              {s.error ? (
                <div className="mt-1 text-xs text-danger">{s.error}</div>
              ) : null}
            </div>
          </li>
        );
      })}
      {status === "failed" && error ? (
        <li className="flex gap-3">
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-danger/15 text-danger">
            <XIcon size={11} strokeWidth={2.4} />
          </span>
          <div className="pt-0.5 text-xs text-danger">{error}</div>
        </li>
      ) : null}
    </ol>
  );
}