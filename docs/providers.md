# Providers

## LLM (`app/providers/llm.py`)

`LLMProvider` ABC: `available()` + `score(candidates) -> records`.
Implementations: `OpenAICompatibleProvider` (any `/v1/chat/completions`,
bearer key, 3-attempt backoff), `OllamaProvider` (`/v1` under the Ollama base
URL), `LocalProvider` (reserved, always unavailable until a bundled model lands).

Selection: `LLM_PROVIDER` = `heuristic` (default, no calls) | `openai_compat` |
`ollama` | `local`. Only transcript TEXT is sent. Never keys, paths, or secrets
(see `docs/security.md`, prompt-injection note: transcript is untrusted input;
prompts instruct the model to ignore embedded instructions).

## STT (`app/providers/stt.py`)

`STTProvider` ABC. `FasterWhisperProvider(model, device, compute_type)`.
`available()` runs a subprocess import probe (native wheels can SIGILL old
CPUs, which cannot be caught in-process) and caches the verdict.

## Vision / reframe

`ReframingStrategy` ABC in `app/rendering/reframe.py`. Face via MediaPipe,
Haar fallback, speaker/center/smart chain. All imports lazy.

## Adding a provider

Subclass the ABC, register in the factory (`get_llm_provider`), add
`AppEnv` config keys, document in `.env.example`, add a readiness check.

## Self-hosted gateways (e.g. freellmapi)

Any OpenAI-compatible gateway works as `LLM_PROVIDER=openai_compat` with
`LLM_BASE_URL` + `LLM_MODEL` (+ `LLM_API_KEY` for bearer auth). Only transcript
text is ever sent. The gateway stays unexposed (localhost) with the panel on
the same box; remote workers rank heuristically off real transcripts instead.
