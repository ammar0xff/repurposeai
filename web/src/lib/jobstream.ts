import { useEffect, useState } from "react";
import { authHeaders, get, type JobDetail, type Stage } from "../api";

export function errMsg(e: unknown): string {
  if (e instanceof Error && e.message) return e.message;
  return "Something went wrong. Try again.";
}

export interface LiveJob {
  job: JobDetail | null;
  error: string;
}

function mergeStageData(j: JobDetail, data: {
  status?: string;
  progress?: number;
  stage?: string;
  error?: string;
  stages?: Stage[];
}): JobDetail {
  return {
    ...j,
    id: j.id,
    project_id: j.project_id,
    created_at: j.created_at,
    params: j.params ?? {},
    status: data.status ?? j.status,
    progress: data.progress ?? j.progress,
    current_stage: data.stage ?? j.current_stage,
    error: data.error ?? j.error,
    stages: data.stages ?? j.stages ?? [],
  };
}

export function useLiveJob(jobId: string | null): LiveJob {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      setError("");
      return;
    }
    let disposed = false;
    const markDead = () => {
      disposed = true;
    };
    const loadPoll = async () => {
      try {
        const j = await get<JobDetail>(`/api/jobs/${jobId}`);
        if (!disposed) {
          setJob((prev) =>
            prev && prev.stages.length > 0 && j.stages.length === 0
              ? mergeStageData(prev, j)
              : j,
          );
          setError("");
        }
      } catch (e) {
        if (!disposed) setError(errMsg(e));
      }
    };
    void loadPoll();
    const poll = setInterval(loadPoll, 4000);

    let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
    const stream = async () => {
      try {
        const r = await fetch(`/api/jobs/${jobId}/events`, {
          headers: authHeaders(),
        });
        if (!r.ok || !r.body) throw new Error(`event stream ${r.status}`);
        reader = r.body.getReader();
        const dec = new TextDecoder();
        let buf = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          let sep;
          while ((sep = buf.indexOf("\n\n")) !== -1) {
            const frame = buf.slice(0, sep);
            buf = buf.slice(sep + 2);
            const line = frame
              .split("\n")
              .find((l) => l.startsWith("data: "));
            if (line && !disposed) {
              try {
                const d = JSON.parse(line.slice(6));
                setJob((prev) =>
                  prev
                    ? mergeStageData(prev, d)
                    : ({
                        id: jobId,
                        project_id: "",
                        created_at: "",
                        params: {},
                        ...d,
                      } as JobDetail),
                );
                if (d.error) setError("");
              } catch {
                /* malformed frame; poll fallback owns truth */
              }
            }
            if (disposed) break;
          }
          if (disposed) return;
        }
      } catch {
        /* reader closed or network: poll continues */
      }
    };
    void stream();

    return markDead;
  }, [jobId]);

  return { job, error };
}