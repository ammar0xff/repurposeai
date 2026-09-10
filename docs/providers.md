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
