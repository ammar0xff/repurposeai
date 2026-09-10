"""Ranking profiles: named weight presets + user custom weights.
Stored per result (profile name + effective weights) for reproducibility."""
from ..providers.llm import WEIGHTS

PRESETS = {
    "balanced": dict(WEIGHTS),
    "viral": {"hook": 0.40, "standalone": 0.20, "payoff": 0.10,
              "clarity": 0.10, "emotion": 0.10, "retention": 0.10},
    "educational": {"hook": 0.15, "standalone": 0.20, "payoff": 0.20,
                    "clarity": 0.30, "emotion": 0.05, "retention": 0.10},
    "emotional": {"hook": 0.25, "standalone": 0.15, "payoff": 0.15,
                  "clarity": 0.10, "emotion": 0.30, "retention": 0.05},
    "storytelling": {"hook": 0.20, "standalone": 0.15, "payoff": 0.25,
                     "clarity": 0.15, "emotion": 0.10, "retention": 0.15},
    "podcast": {"hook": 0.25, "standalone": 0.25, "payoff": 0.15,
                "clarity": 0.15, "emotion": 0.10, "retention": 0.10},
}


def weights_for(profile: str = "balanced", custom: dict | None = None) -> dict:
    """Resolve effective weights. Custom dicts merge over the named preset
    (unknown keys dropped, negatives clamped, renormalized to sum 1)."""
    base = dict(PRESETS.get(profile, PRESETS["balanced"]))
    if custom:
        for k in base:
            if k in custom:
                try:
                    base[k] = max(0.0, float(custom[k]))
                except (TypeError, ValueError):
                    continue
    total = sum(base.values()) or 1.0
    return {k: round(v / total, 4) for k, v in base.items()}


def overall_with(axes: dict, weights: dict) -> float:
    return round(sum(float(axes.get(k, 0)) * weights.get(k, 0) for k in weights), 2)
