export default function Settings() {
  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">Settings</h1>
      <div className="rounded-xl border border-slate-800 bg-[#11151d] p-4 text-sm text-slate-300">
        <p>Runtime configuration lives in <code>.env</code> on the server (never in this UI):</p>
        <ul className="mt-2 list-inside list-disc text-slate-400">
          <li>DATABASE_URL, STORAGE_PATH, FFMPEG_PATH</li>
          <li>WHISPER_MODEL / DEVICE / COMPUTE_TYPE</li>
          <li>LLM_PROVIDER (heuristic, openai_compat, ollama, local), LLM_BASE_URL, LLM_MODEL</li>
          <li>MAX_UPLOAD_MB, MAX_CONCURRENT_JOBS, AUTH_TOKEN</li>
        </ul>
        <p className="mt-2 text-slate-500">Provider keys are never displayed here and never logged.</p>
      </div>
    </div>
  );
}
