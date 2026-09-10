"""Campaign-level dry-run gate: technical READY vs submission-ready.
A clip set can be technically READY while blockers() > 0; never submit those.
Ported from the whopclip merge."""
from ..services.campaigns import bounds


def validate_clip_file(mp4_meta: dict, rules: dict, src_ok: bool,
                       src_label: str, credit_used: str, extra_tags: list) -> list:
    """mp4_meta: {file, duration, width, height, captioned, candidate(bool),
    title, caption}. Returns [(ok, label)]."""
    dur = float(mp4_meta.get("duration", 0) or 0)
    lo, hi = bounds(rules)
    tags = rules.get("hashtags", []) or []
    cap_text = (mp4_meta.get("caption", "") or "") + " " + " ".join(extra_tags)
    req_credit = (rules.get("credit", {}) or {}).get("text") or ""
    vw, vh = mp4_meta.get("width", 0), mp4_meta.get("height", 0)
    return [
        (src_ok, src_label),
        (lo - 1 <= dur <= hi + 1, f"Duration {dur:.1f}s in [{lo:.0f}-{hi:.0f}]"),
        (not req_credit or req_credit in (credit_used or ""),
         f"Required credit ({req_credit or 'n/a'})"),
        (all(t in cap_text for t in tags), f"Hashtags ({' '.join(tags)})"),
        (vw == 1080 and vh == 1920, f"Format {vw}x{vh}"),
        (bool(mp4_meta.get("captioned")), "Captioned"),
        (mp4_meta.get("candidate") is not None, "Candidate eligible"),
    ]


def check_source(source: str, rules: dict) -> tuple[bool, str]:
    allowed = [str(s).lower() for s in rules.get("sources", [])]
    src = (source or "").lower()
    base = src.rsplit("/", 1)[-1]
    if not allowed:
        return False, "Source allowed (no sources listed, brief incomplete)"
    hit = [a for a in allowed if a == "*" or a in src or a in base]
    if hit:
        return True, f"Source allowed ({hit[0]})"
    return False, f"Source allowed (got '{source}', want one of {rules.get('sources', [])})"


def validate_job(clips_meta: list, rules: dict, job: dict) -> dict:
    """clips_meta: list of mp4_meta dicts. Returns READY/NOT READY report."""
    src_ok, src_label = check_source(job.get("source", ""), rules)
    credit_used = job.get("credit_used", "")
    extra_tags = job.get("extra_tags", rules.get("hashtags", []))
    clips, all_ok = [], True
    for m in clips_meta:
        checks = validate_clip_file(m, rules, src_ok, src_label, credit_used, extra_tags)
        ok = all(c[0] for c in checks)
        all_ok &= ok
        clips.append({"file": m.get("file", ""), "pass": ok,
                      "checks": [{"ok": c[0], "label": c[1]} for c in checks]})
    if not clips:
        all_ok = False
    cap = rules.get("cap")
    summary = [
        (True, f"Campaign: {rules.get('campaign', job.get('campaign', '?'))}"),
        (all_ok, f"Status: {'PASS' if all_ok else 'FAIL'}"),
        (cap is not None, f"Under campaign cap ({cap})"),
    ]
    if not all(s[0] for s in summary):
        all_ok = False
    return {"status": "READY" if all_ok else "NOT READY",
            "summary": [{"ok": s[0], "label": s[1]} for s in summary],
            "clips": clips}
