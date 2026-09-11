# RepurposeAI — project context

**What it does.** Long video in, ranked captioned vertical shorts out. Local-first
AI pipeline (ingest → analyze → transcribe → segment → rank → render) with
optional remote STT via GitHub Actions. FastAPI backend + React/Tailwind web frontend.

**Who uses it.** A solo creator / clipper at a desk, late at night, phone nearby —
drops a raw interview or stream, wants the 3–5 best moments cut and captioned
without editing themselves. Not a team dashboard. Few jobs, high attention per job.

**Core flow.** Drop a video → watch it transform (stages) → review the clips it
chose → export. Failure must recover: retry resumes from the interrupted stage.

**Design posture.** Warm-lit screening room. OLED black, warm neutrals, one ember
accent, mono telemetry for the machine's inner workings. The upload is a moment,
not a form. Every stage of 8, 35, 100% tells the user what the machine is thinking.