import { useEffect, useState } from "react";
import { get, put } from "../api";
import { Button, Chip, Notice, PageHead, Panel, PanelTitle } from "../components/ui";

type Engine = "auto" | "local" | "github";

interface SettingsResp {
  stt_provider: Engine;
  stt_override: string;
  whisper: { model: string; device: string; compute_type: string };
  github: { token_set: boolean; owner: string; repo: string };
}

interface ProvidersResp {
  stt: {
    kind: string;
    model: string;
    available: boolean;
    engines: Record<Engine, boolean>;
    local_mode: string;
    github_mode: string;
  };
}

interface Status {
  tone: "ok" | "bad" | "neutral";
  text: string;
}

const ENGINE_OPTIONS: { value: Engine; label: string; sub: string }[] = [
  { value: "auto", label: "Auto", sub: "local when available, GitHub Actions otherwise" },
  { value: "local", label: "This machine", sub: "faster-whisper, model small" },
  { value: "github", label: "GitHub Actions", sub: "runner transcribes via private gist" },
];

const KEYS = [
  ["Storage", "DATABASE_URL, STORAGE_PATH, FFMPEG_PATH"],
  ["Speech", "WHISPER_MODEL, DEVICE, COMPUTE_TYPE"],
  ["LLM", "LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL"],
  ["Limits", "MAX_UPLOAD_MB, MAX_CONCURRENT_JOBS"],
  ["Secrets", "AUTH_TOKEN (never rendered)"],
] as const;

export default function Settings() {
  const [s, setS] = useState<SettingsResp | null>(null);
  const [p, setP] = useState<ProvidersResp | null>(null);
  const [draft, setDraft] = useState<Engine | "">("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void get<SettingsResp>("/api/system/settings")
      .then((d) => {
        setS(d);
        setDraft(d.stt_provider);
      })
      .catch(() => {});
    void get<ProvidersResp>("/api/system/providers").then(setP).catch(() => {});
  }, []);

  const dirty = draft !== "" && s !== null && draft !== s.stt_provider;
  const hasDraft = draft !== "";

  const status = (v: Engine): Status => {
    if (!p) return { tone: "neutral", text: "Checking" };
    const ok = p.stt.engines[v];
    const tone: "ok" | "bad" = ok ? "ok" : "bad";
    if (v === "local") return { tone, text: p.stt.local_mode };
    if (v === "github") return { tone, text: p.stt.github_mode };
    return { tone, text: ok ? "a transcription engine is available" : "no transcription engine available" };
  };

  const save = async () => {
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const next = await put<SettingsResp>("/api/system/settings", { stt_provider: draft });
      setS(next);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const currentLabel = s ? ENGINE_OPTIONS.find((o) => o.value === s.stt_provider)?.label : "";
  const active = status(draft || "auto");

  return (
    <div>
      <PageHead kicker="System" title="Settings" />
      <Panel>
        <PanelTitle hint={p ? `whisper model ${p.stt.model}` : "whisper model n/a"}>
          Transcription engine
        </PanelTitle>
        <div
          role="radiogroup"
          aria-label="Transcription engine"
          className="grid gap-2 sm:grid-cols-3"
        >
          {ENGINE_OPTIONS.map((o) => {
            const active = draft === o.value;
            return (
              <button
                key={o.value}
                role="radio"
                aria-checked={active}
                onClick={() => {
                  setDraft(o.value);
                  setSaved(false);
                }}
                className={`min-h-[44px] rounded-[10px] border px-3.5 py-2.5 text-left transition-all duration-150 ease-out ${
                  active ? "border-primary/60 bg-surface-2" : "border-line bg-transparent hover:bg-surface-2"
                }`}
              >
                <div className={`text-sm font-semibold ${active ? "text-ink" : "text-body"}`}>
                  {o.label}
                </div>
                <div className="mt-0.5 text-xs leading-relaxed text-faint">{o.sub}</div>
              </button>
            );
          })}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2.5 border-t border-line pt-4">
          <Chip tone={active.tone}>
            {active.tone === "ok" ? "ready" : active.tone === "bad" ? "unavailable" : "checking"}
          </Chip>
          <span className="text-sm text-muted">{active.text}</span>
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
          <div className="text-xs leading-relaxed text-faint">
            {s?.stt_override
              ? `Server override applies${currentLabel ? ` (${currentLabel})` : ""}`
              : "Sourced from .env on the server"}
          </div>
          <Button
            variant="primary"
            onClick={save}
            disabled={!dirty || saving || !hasDraft}
          >
            {saving ? "Saving" : "Save transcription engine"}
          </Button>
        </div>

        {saved ? (
          <div className="mt-4">
            <Notice tone="ok">Saved. Applies when a job enters transcription.</Notice>
          </div>
        ) : null}
        {error ? (
          <div className="mt-4">
            <Notice tone="bad" onClose={() => setError("")}>{error}</Notice>
          </div>
        ) : null}
      </Panel>

      <Panel className="mt-5">
        <PanelTitle>Runtime configuration</PanelTitle>
        <div className="text-sm text-muted">
          Full configuration lives in{" "}
          <code className="mono rounded bg-surface-2 px-1.5 py-0.5 text-xs text-body">.env</code>{" "}
          on the server. Transcription engine is the one value editable from this screen.
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {KEYS.map(([label, keys]) => (
            <div key={label} className="rounded-[10px] border border-line bg-surface p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
                {label}
              </div>
              <div className="mono mt-2 text-xs leading-relaxed text-body">{keys}</div>
            </div>
          ))}
        </div>
        <div className="mt-5 border-t border-line pt-4 text-xs text-faint">
          Provider keys are never displayed in this UI and never logged.
        </div>
      </Panel>
    </div>
  );
}