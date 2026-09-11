import { Panel, PageHead } from "../components/ui";

const KEYS = [
  ["Storage", "DATABASE_URL, STORAGE_PATH, FFMPEG_PATH"],
  ["Speech", "WHISPER_MODEL, DEVICE, COMPUTE_TYPE"],
  ["LLM", "LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL"],
  ["Limits", "MAX_UPLOAD_MB, MAX_CONCURRENT_JOBS"],
  ["Secrets", "AUTH_TOKEN (never rendered)"],
] as const;

export default function Settings() {
  return (
    <div>
      <PageHead kicker="System" title="Settings" />
      <Panel>
        <div className="text-sm text-muted">
          Runtime configuration lives in{" "}
          <code className="mono rounded bg-surface-2 px-1.5 py-0.5 text-xs text-body">.env</code>{" "}
          on the server. Nothing here is configurable from this screen, on purpose.
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