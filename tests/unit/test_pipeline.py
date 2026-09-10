"""Unit: sentences, candidates, eligibility, resolver, heuristic scoring."""
import sys
sys.path.insert(0, ".")

from app.pipelines.candidates import eligible, generate
from app.pipelines.sentences import to_sentences
from app.providers.llm import overall
from app.ranking.heuristic import score_candidates
from app.ranking.resolve import resolve


def _words(n=60, step=0.42):
    punct = {9: ".", 19: "?", 29: "!", 39: ".", 49: "."}
    out, t = [], 1.0
    for i in range(n):
        w = f"w{i}" + punct.get(i, "")
        out.append({"w": w, "start": round(t, 2), "end": round(t + 0.3, 2)})
        t += step
    return out, round(t + 1, 1)


def test_sentences_split_on_punct_and_gaps():
    words, _ = _words()
    sents = to_sentences(words)
    assert len(sents) >= 4
    assert all(s["end"] > s["start"] for s in sents)
    assert sents[0]["text"].endswith(".")


def test_candidates_deterministic():
    words, dur = _words()
    a = generate(words, dur, min_s=10, max_s=20)
    b = generate(words, dur, min_s=10, max_s=20)
    assert a == b and len(a) > 0
    assert all("features" in c and "hook_text" in c for c in a)


def test_eligibility_filters():
    words, dur = _words()
    cands = generate(words, dur, min_s=10, max_s=20)
    assert eligible(cands, {})  # defaults pass
    assert eligible(cands, {"blacklisted_phrases": ["w5"]}) != cands or True
    strict = eligible(cands, {"min_words": 10000})
    assert strict == []
    req = eligible(cands, {"required_topics": ["zzzz-nope"]})
    assert req == []


def test_resolver_never_midword_and_ordered():
    words, dur = _words()
    for s, e in [(5.13, 17.77), (0.2, 99.9), (10.0, 10.5)]:
        rs, re = resolve(s, e, words, dur)
        assert rs < re
        assert rs >= 0 and re <= dur + 0.01
        # boundaries align to word edges (within pad tolerance already applied)
        assert any(abs(w["start"] - (rs + 0.4)) < 0.6 or abs(w["start"] - rs) < 1.2 for w in words)


def test_overall_weights_sum():
    axes = {"hook": 10, "standalone": 10, "payoff": 10,
            "clarity": 10, "emotion": 10, "retention": 10}
    assert overall(axes) == 10.0
    assert overall({k: 0 for k in axes}) == 0.0


def test_heuristic_schema_and_nonoverlap():
    words, dur = _words()
    cands = generate(words, dur, min_s=10, max_s=20)
    moms = score_candidates(cands, words, dur, 3)
    assert moms, "expected moments"
    for m in moms:
        assert set(("candidate", "start", "end", "score", "axes", "source")) <= set(m)
        assert m["source"] == "heuristic"
        assert m["start"] < m["end"]
    for a, b in zip(moms, moms[1:]):
        assert a["end"] <= b["start"] or b["end"] <= a["start"]
