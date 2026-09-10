"""Metadata generation: 3 title variants + description/caption/hashtags/keywords.
LLM when available (versioned prompt), deterministic heuristic otherwise.
Source is always labeled. Never publishes anything."""
import json

PROMPT_VERSION = "metadata/v1"


def _prompt_path():
    from pathlib import Path
    return Path(__file__).parent.parent.parent / "prompts" / "metadata" / "v1.txt"


def heuristic(text: str, hashtags: list | None = None) -> dict:
    words = text.split()
    head = " ".join(words[:9])
    return {
        "titles": [head[:60], " ".join(words[:6])[:60] or "Untitled clip",
                   " ".join(words[-8:])[:60] or "Untitled clip"],
        "description": text[:500],
        "caption": text[:150],
        "hashtags": list(hashtags or []),
        "keywords": sorted({w.strip(".,?!").lower() for w in words if len(w) > 4})[:10],
        "source": "heuristic", "prompt_version": PROMPT_VERSION, "model": "",
    }


def generate(text: str, provider=None, model: str = "",
             hashtags: list | None = None) -> dict:
    """Returns metadata dict. Never raises: falls back to heuristic."""
    if provider is None:
        return heuristic(text, hashtags)
    try:
        if not provider.available():
            raise RuntimeError("provider unavailable")
        prompt = _prompt_path().read_text().replace("{TEXT}", text[:2000])
        data = provider.complete([{"role": "user", "content": prompt}],
                                 model, 90, temperature=0.7, max_tokens=600)
        txt = data["choices"][0]["message"]["content"]
        s, e = txt.find("{"), txt.rfind("}")
        d = json.loads(txt[s:e + 1])
        titles = [str(t)[:120] for t in d.get("titles", [])][:3]
        if not titles:
            raise ValueError("no titles in LLM output")
        while len(titles) < 3:
            titles.append(titles[0])
        return {"titles": titles, "description": str(d.get("description", ""))[:1000],
                "caption": str(d.get("caption", ""))[:300],
                "hashtags": [str(h) for h in d.get("hashtags", [])][:12] or list(hashtags or []),
                "keywords": [str(k) for k in d.get("keywords", [])][:15],
                "source": getattr(provider, "name", "llm"),
                "prompt_version": PROMPT_VERSION, "model": model}
    except Exception:  # noqa: BLE001 - any LLM failure -> labeled heuristic fallback
        out = heuristic(text, hashtags)
        out["source"] = "heuristic (LLM unavailable)"
        return out
