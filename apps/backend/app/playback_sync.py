"""Playback-readiness checks for a pulled recording (pristine mp4 + ndjson sidecar).

Fleet pulls each nano session as a sibling ``<id>.mp4`` + ``<id>.ndjson`` pair
(``recordings_pull``). Before that pair is played back (nano frontend) or ingested
(eai-catalog device-prediction ingest), it must be *playback-sound*: the detection
sidecar has to line up with the video timeline so overlays land on the right frames.

This module is the pure, dependency-free verifier of that property. It does NOT render
— rendering is the nano's job — it checks the timing/timestamp/overlay-sync **invariants**
that decide whether rendering will be correct:

  * **timestamps** — each sidecar line carries a ``pts_ns`` rebased to recording start,
    so the first detection sits at ~0 and timestamps are monotonic non-decreasing;
  * **timing** — the sidecar's pts span covers the video's duration (read from the mp4
    ``mvhd`` box), i.e. detections exist across the whole clip, not just a slice;
  * **overlay sync** — every video presentation time maps to a well-defined detection
    set via a forward-only *hold-last-by-PTS* join (the same join the nano replay uses),
    and detection geometry is normalised to [0, 1] so it scales to any render size.

The sidecar line schema mirrors eai-nano's ``DetectionFrame`` (``extra="ignore"`` so the
nano can add fields): ``{"pts_ns": int, "dets": [{"bbox": [x,y,w,h], "cat": str,
"conf": float, "seg": [[...]]?}]}``.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

_NS_PER_S = 1_000_000_000


class Detection(BaseModel):
    """One detection on a frame. Geometry is normalised to the unit square."""

    model_config = ConfigDict(extra="ignore")

    bbox: list[float] = Field(min_length=4, max_length=4, description="[x, y, w, h] in [0,1]")
    cat: str = ""  # class label; the nano emits "" for unlabeled/context detections
    conf: float = Field(ge=0.0, le=1.0)
    seg: list[list[float]] = Field(default_factory=list, description="normalised polygons")


class SidecarFrame(BaseModel):
    """One inferred frame: a presentation timestamp plus its detections."""

    model_config = ConfigDict(extra="ignore")

    pts_ns: int = Field(ge=0, description="presentation time, ns, rebased to recording start")
    dets: list[Detection] = Field(default_factory=list)


class PlaybackSyncReport(BaseModel):
    """Verdict + evidence for one (mp4, sidecar) pair. ``ok`` ⇔ ``issues`` is empty."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    issues: list[str] = Field(default_factory=list)

    frame_count: int = Field(ge=0)
    first_pts_ns: int | None = None
    last_pts_ns: int | None = None
    sidecar_span_s: float = Field(ge=0.0)
    video_duration_s: float | None = Field(default=None, ge=0.0)
    coverage_ratio: float | None = Field(default=None, ge=0.0)

    monotonic: bool = False
    rebased_to_start: bool = False
    within_bounds: bool = False
    spans_video: bool = False
    normalized_geometry: bool = False


class SidecarOverlayIndex:
    """The forward-only *hold-last-by-PTS* overlay join used at playback time.

    For an increasing sequence of video presentation times, ``at(pts_ns)`` returns the
    detections of the most recent sidecar frame with ``frame.pts_ns <= pts_ns`` — holding
    the last frame between sparse inferences (the sidecar runs at the inference rate, the
    video at full fps). The internal cursor only advances, so a whole clip is joined in one
    linear pass — exactly what the nano's ``SidecarReplaySource`` does.
    """

    def __init__(self, frames: list[SidecarFrame]) -> None:
        # Sorted, defensive copy: the join assumes non-decreasing pts.
        self._frames = sorted(frames, key=lambda f: f.pts_ns)
        self._cursor = 0

    def at(self, pts_ns: int) -> list[Detection]:
        """Detections active at ``pts_ns`` (empty before the first inferred frame)."""
        while (
            self._cursor + 1 < len(self._frames)
            and self._frames[self._cursor + 1].pts_ns <= pts_ns
        ):
            self._cursor += 1
        if not self._frames or self._frames[self._cursor].pts_ns > pts_ns:
            return []
        return self._frames[self._cursor].dets


def read_sidecar(path: Path) -> list[SidecarFrame]:
    """Parse an ndjson sidecar into validated frames (blank lines skipped)."""
    frames: list[SidecarFrame] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            frames.append(SidecarFrame.model_validate_json(raw))
        except ValueError as e:
            raise ValueError(f"{path.name}:{lineno}: malformed sidecar line: {e}") from e
    return frames


def read_mp4_duration_s(path: Path) -> float:
    """Duration in seconds from the mp4 ``moov/mvhd`` box (no ffmpeg needed).

    Walks the ISO-BMFF box tree to ``moov`` → ``mvhd`` and divides ``duration`` by
    ``timescale`` (handles both version 0 and 1 mvhd). Raises ``ValueError`` if the
    movie header can't be found.
    """
    data = path.read_bytes()
    moov = _find_box(data, 0, len(data), b"moov")
    if moov is None:
        raise ValueError(f"{path.name}: no 'moov' box (not a readable mp4)")
    m_start, m_end = moov
    mvhd = _find_box(data, m_start, m_end, b"mvhd")
    if mvhd is None:
        raise ValueError(f"{path.name}: no 'mvhd' box")
    p, _ = mvhd
    version = data[p]
    if version == 1:
        timescale = int.from_bytes(data[p + 20 : p + 24], "big")
        duration = int.from_bytes(data[p + 24 : p + 32], "big")
    else:
        timescale = int.from_bytes(data[p + 12 : p + 16], "big")
        duration = int.from_bytes(data[p + 16 : p + 20], "big")
    if timescale == 0:
        raise ValueError(f"{path.name}: mvhd timescale is zero")
    return duration / timescale


def verify_playback_sync(
    mp4_path: Path,
    sidecar_path: Path,
    *,
    start_tolerance_s: float = 0.5,
    end_tolerance_s: float = 1.0,
    min_coverage: float = 0.5,
) -> PlaybackSyncReport:
    """Check that ``(mp4, sidecar)`` will play back with correct timing + overlay sync.

    ``start_tolerance_s`` — how close the first detection must sit to t=0 to count as
    rebased. ``end_tolerance_s`` — how far past the video end a pts may sit (clock jitter)
    before it's "out of bounds". ``min_coverage`` — the minimum fraction of the video the
    sidecar's pts span must cover to count as spanning the clip.
    """
    frames = read_sidecar(sidecar_path)
    issues: list[str] = []

    duration_s: float | None
    try:
        duration_s = read_mp4_duration_s(mp4_path)
    except ValueError as e:
        duration_s = None
        issues.append(str(e))

    if not frames:
        issues.append("sidecar has no frames")
        return PlaybackSyncReport(
            ok=False, issues=issues, frame_count=0, sidecar_span_s=0.0,
            video_duration_s=duration_s,
        )

    pts = [f.pts_ns for f in frames]
    first, last = pts[0], pts[-1]
    span_s = (last - first) / _NS_PER_S

    monotonic = all(b >= a for a, b in zip(pts, pts[1:], strict=False))
    if not monotonic:
        issues.append("pts_ns are not monotonic non-decreasing")

    rebased = first <= int(start_tolerance_s * _NS_PER_S)
    if not rebased:
        issues.append(
            f"first pts {first / _NS_PER_S:.3f}s not rebased to start (>{start_tolerance_s}s)"
        )

    normalized = True
    for i, f in enumerate(frames):
        for d in f.dets:
            x, y, w, h = d.bbox
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and 0.0 <= w <= 1.0 and 0.0 <= h <= 1.0):
                normalized = False
                issues.append(f"frame {i} bbox not normalised to [0,1]: {d.bbox}")
                break
            if any(not (0.0 <= v <= 1.0) for poly in d.seg for v in poly):
                normalized = False
                issues.append(f"frame {i} seg polygon not normalised to [0,1]")
                break

    within_bounds = True
    spans_video = True
    coverage: float | None = None
    if duration_s is not None:
        limit_ns = int((duration_s + end_tolerance_s) * _NS_PER_S)
        if last > limit_ns:
            within_bounds = False
            issues.append(
                f"last pts {last / _NS_PER_S:.3f}s exceeds video {duration_s:.3f}s "
                f"(+{end_tolerance_s}s tolerance)"
            )
        coverage = span_s / duration_s if duration_s > 0 else 0.0
        if coverage < min_coverage:
            spans_video = False
            issues.append(
                f"sidecar covers {coverage:.0%} of the {duration_s:.3f}s clip "
                f"(< {min_coverage:.0%})"
            )

    return PlaybackSyncReport(
        ok=not issues,
        issues=issues,
        frame_count=len(frames),
        first_pts_ns=first,
        last_pts_ns=last,
        sidecar_span_s=span_s,
        video_duration_s=duration_s,
        coverage_ratio=coverage,
        monotonic=monotonic,
        rebased_to_start=rebased,
        within_bounds=within_bounds,
        spans_video=spans_video,
        normalized_geometry=normalized,
    )


def _find_box(data: bytes, start: int, end: int, want: bytes) -> tuple[int, int] | None:
    """Return ``(payload_start, payload_end)`` of the first ``want`` box in ``[start, end)``.

    Minimal ISO-BMFF walker: each box is ``size(4) type(4) payload``; ``size == 1`` means a
    64-bit largesize follows the type; ``size == 0`` runs to ``end``. Only the boxes we need
    (``moov`` then its child ``mvhd``) are looked up, so a shallow scan is enough.
    """
    pos = start
    while pos + 8 <= end:
        size = int.from_bytes(data[pos : pos + 4], "big")
        btype = data[pos + 4 : pos + 8]
        header = 8
        if size == 1:
            size = int.from_bytes(data[pos + 8 : pos + 16], "big")
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            break
        if btype == want:
            return pos + header, pos + size
        pos += size
    return None
