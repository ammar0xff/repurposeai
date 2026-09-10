"""LLM provider abstraction. Transcript text only; never secrets/paths.
Every provider degrades to heuristic scoring when unreachable."""
import json
import os
import urllib.request
from abc import ABC, abstractmethod

AXES = ("hook", "standalone", "payoff", "clarity", "emotion", "retention")
WEIGHTS = {"hook": 0.30, "standalone": 0.20, "payoff": 0.15,
           "clarity": 0.15, "emotion": 0.10, "retention": 0.10}

PROMPT_VERSION = "ranking/v1"


def overall(axes: dict) -> float:
    return round(sum(float(axes.get(k, 0)) * w for k, w in WEIGHTS.items()), 2)


def load_prompt(name: str = "ranking/v1") -> str:
    from pathlib import Path
    p = Path(__file__).parent.parent.parent / "prompts" / f"{name}.txt"
    return p.read_text()


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def score(self, candidates: list, model: str = "", timeout: int = 120) -> list:
        """Return [{id, hook.., retention.., title, caption, reason}]."""

    def score_safe(self, candidates: list, model: str = "") -> tuple[list, str]:
        """(records, source) — never raises; falls back to heuristic markers."""
        try:
            if not self.available():
                raise RuntimeError("provider unavailable")
            return self.score(candidates, model), self.name
        except Exception as e:
            return [], f"heuristic (LLM unavailable: {e})"


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compat"

    def __init__(self, base_url: str = "", api_key: str = "", model: str = ""):
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "")

    def available(self) -> bool:
        return bool(self.base_url and self.model)

    def _post(self, payload: dict, timeout: int) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last = None
        for attempt in (1, 2, 3):
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/chat/completions",
                    data=json.dumps(payload).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read()
                if not raw:
                    raise ValueError("empty response body")
                return json.loads(raw)
            except Exception as e:
                last = e
                import time as _t
                _t.sleep(3 * attempt)
        raise last  # type: ignore[misc]

    def score(self, candidates: list, model: str = "", timeout: int = 120) -> list:
        tab = "\n".join(
            f"[{c['id']}] {c.get('start', 0):.0f}-{c.get('end', 0):.0f}s | "
            f"hook: {c.get('hook_text', '')[:140]} | text: {c.get('text', '')[:400]}"
            for c in candidates)
        prompt = load_prompt().replace("{N}", str(len(candidates))).replace("{CANDS}", tab[:14000])
        data = self._post({"model": model or self.model, "temperature": 0.3,
                           "max_tokens": 3000,
                           "messages": [{"role": "user", "content": prompt}]}, timeout)
        txt = data["choices"][0]["message"]["content"]
        s, e = txt.find("["), txt.rfind("]")
        recs = json.loads(txt[s:e + 1])
        out = []
        for r in recs:
            if not isinstance(r, dict) or "id" not in r:
                continue
            axes = {k: max(0, min(10, float(r.get(k, 5)))) for k in AXES}
            out.append({"id": r["id"], "axes": axes, "overall": overall(axes),
                        "title": r.get("title", ""), "caption": r.get("caption", ""),
                        "reason": r.get("reason", ""), "prompt_version": PROMPT_VERSION,
                        "model": model or self.model})
        if not out:
            raise ValueError("no valid scored candidates in LLM output")
        return out


class OllamaProvider(OpenAICompatibleProvider):
    name = "ollama"

    def __init__(self, base_url: str = "", model: str = ""):
        super().__init__(base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://127.0.0.1:11434") + "/v1", "", model)


class LocalProvider(LLMProvider):
    """Reserved for bundled local inference. Currently always unavailable;
    exists so configuration never hard-codes a remote."""
    name = "local"

    def available(self) -> bool:
        return False

    def score(self, candidates: list, model: str = "", timeout: int = 120) -> list:
        raise RuntimeError("no local model configured")


def get_llm_provider(kind: str = "") -> LLMProvider:
    kind = (kind or os.environ.get("LLM_PROVIDER", "heuristic")).lower()
    if kind == "openai_compat":
        return OpenAICompatibleProvider()
    if kind == "ollama":
        return OllamaProvider(model=os.environ.get("LLM_MODEL", ""))
    if kind == "local":
        return LocalProvider()
    return LocalProvider()  # heuristic path: caller falls back explicitly
