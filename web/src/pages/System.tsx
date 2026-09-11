import { useEffect, useState } from "react";
import { get, type Metrics } from "../api";
import {
  Chip,
  Dot,
  PageHead,
  Panel,
  PanelTitle,
  Progress,
  Stat,
} from "../components/ui";

interface Readiness {
  checks: Record<string, { status: string; error?: string; free_gb?: number }>;
  ready: boolean;
}

interface Providers {
  llm: { kind: string; model: string; available: boolean; note?: string };
  stt: { kind: string; model: string; available: boolean };
}

export default function System() {
  const [h, setH] = useState<Readiness | null>(null);
  const [p, setP] = useState<Providers | null>(null);
  const [m, setM] = useState<Metrics | null>(null);

  useEffect(() => {
    void get<Readiness>("/api/system/readiness").then(setH).catch(() => {});
    void get<Providers>("/api/system/providers").then(setP).catch(() => {});
    void get<Metrics>("/api/system/metrics").then(setM).catch(() => {});
  }, []);

  return (
    <div>
      <PageHead
        kicker="System"
        title="Cutting room checks"
        right={
          h ? (
            <Chip tone={h.ready ? "ok" : "bad"}>{h.ready ? "Ready" : "Not ready"}</Chip>
          ) : null
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Disk free" value={m ? `${m.disk_free_gb} GB` : "n/a"} />
        <Stat
          label="Running"
          value={m ? m.running.length : "n/a"}
          sub={m?.stale_running.length ? `${m.stale_running.length} stale` : "all heartbeats alive"}
        />
        <Stat label="Queued" value={m ? String(m.jobs?.queued ?? 0) : "n/a"} />
        <Stat
          label="Recent failures"
          value={m ? m.recent_failed.length : "n/a"}
          sub="last 10 jobs"
        />
      </div>

      <div className="mt-5 grid items-start gap-5 lg:grid-cols-3">
        <Panel>
          <PanelTitle hint={h && h.checks.disk ? `${h.checks.disk.free_gb} GB free` : ""}>
            Readiness
          </PanelTitle>
          <div className="space-y-1.5">
            {h ? (
              Object.entries(h.checks).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2.5 py-0.5 text-sm">
                  <Dot tone={v.status === "ok" ? "ok" : "bad"} />
                  <span className="flex-1 capitalize text-body">{k}</span>
                  <Chip tone={v.status === "ok" ? "ok" : "bad"}>{v.status}</Chip>
                </div>
              ))
            ) : (
              <div className="space-y-2">
                <div className="skeleton h-6 rounded" />
                <div className="skeleton h-6 rounded" />
                <div className="skeleton h-6 rounded" />
              </div>
            )}
          </div>
        </Panel>

        <Panel>
          <PanelTitle>Providers</PanelTitle>
          {p ? (
            <div className="space-y-4">
              <div>
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="text-sm font-medium text-body">STT</span>
                  <span className="mono text-[11px] text-faint">{p.stt.model}</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-faint">{p.stt.kind}</span>
                  <Chip tone={p.stt.available ? "ok" : "bad"}>
                    {p.stt.available ? "available" : "missing"}
                  </Chip>
                </div>
              </div>
              <div>
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="text-sm font-medium text-body">LLM</span>
                  <span className="mono text-[11px] text-faint">{p.llm.model}</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-faint">{p.llm.kind}</span>
                  <Chip tone={p.llm.available ? "ok" : "bad"}>
                    {p.llm.available ? "available" : "missing"}
                  </Chip>
                </div>
                {p.llm.note ? (
                  <div className="mt-1 text-[11px] text-faint">{p.llm.note}</div>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="text-sm text-faint">Loading providers...</div>
          )}
        </Panel>

        <Panel>
          <PanelTitle>Jobs by state</PanelTitle>
          {m ? (
            <div className="space-y-2">
              {Object.entries(m.jobs).length ? (
                Object.entries(m.jobs).map(([k, n]) => (
                  <div key={k} className="flex items-center gap-2.5 text-sm">
                    <span className="flex-1 capitalize text-muted">{k}</span>
                    <Progress value={n} />
                    <span className="mono w-6 text-right text-xs text-body">{n}</span>
                  </div>
                ))
              ) : (
                <div className="text-sm text-faint">No jobs recorded yet.</div>
              )}
              <div className="mono border-t border-line pt-2 text-[11px] text-faint">
                db {m.db_size_bytes > 0 ? `${(m.db_size_bytes / 1e6).toFixed(1)} MB` : "n/a"} · stale
                timeout {m.stale_timeout_s}s
              </div>
            </div>
          ) : (
            <div className="text-sm text-faint">Loading metrics...</div>
          )}
        </Panel>
      </div>

      {m && m.recent_failed.length ? (
        <Panel className="mt-5">
          <PanelTitle hint={`${m.recent_failed.length} of last 10`}>Recent failures</PanelTitle>
          <div className="space-y-2">
            {m.recent_failed.map((f) => (
              <div key={f.id} className="flex items-start gap-2.5 text-sm">
                <Dot tone="bad" />
                <span className="mono text-xs text-faint">{f.id.slice(0, 8)}</span>
                <span className="w-24 shrink-0 capitalize text-muted">{f.stage || "?"}</span>
                <span className="flex-1 truncate text-xs text-body">{f.error}</span>
              </div>
            ))}
          </div>
        </Panel>
      ) : null}

      {h?.checks && !h.ready ? (
        <div className="mt-5 text-xs text-faint">
          STT and LLM probes may fail on the API host because native audio libs and models
          run on the worker hardware. Check the runner logs before treating red as broken.
        </div>
      ) : null}
    </div>
  );
}