# Pipeline

```
ingest -> analyze -> transcribe -> segment -> rank -> resolve/render -> validate
QUEUED INGESTING ANALYZING TRANSCRIBING SEGMENTING RANKING RESOLVING RENDERING VALIDATING READY_FOR_REVIEW
```

1. **ingest**: local path copy, URL via yt-dlp/direct fetch, WeTransfer via
   vendored transferwee, or pre-uploaded storage key. Validates MIME/extension/size.
2. **analyze**: single FFprobe pass, cached on the project (never re-probed).
3. **transcribe**: faster-whisper (configurable model/device), word timestamps
   mandatory. `tiny` for smoke tests, `small` default, `large` for quality.
4. **segment**: scenes (PySceneDetect, else ffmpeg `select`), silence
   (`silencedetect`), sentence grouping (punctuation + pauses), candidate
   windows snapped to sentence starts, eligibility filter BEFORE ranking.
5. **rank**: structured 6-axis scoring (hook .30, standalone .20, payoff .15,
   clarity .15, emotion .10, retention .10). Profiles in project config
   (`ranking_profile`: balanced/viral/educational/emotional/storytelling/podcast)
   rescale weights. Invalid LLM JSON: retry once, then heuristic.
6. **resolve/render**: snap to word boundaries + padding (default 0.4s/0.6s),
   sentence-end pull-up, clamp to duration. Reframe center/face/speaker/smart
   with fallback chain. libass captions (5 styles). H264 + faststart.
   Audio loudnorm optional.
7. **validate**: FFprobe every clip (resolution, duration, streams, nonzero,
   captions present). Report `{status: READY|FAIL, checks}`.
