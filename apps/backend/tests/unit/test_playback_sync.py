"""Playback timing / timestamp / overlay-sync verification (task: storage playback).

Builds a *pristine* mp4 + ndjson sidecar pair in-memory (a tiny but real ISO-BMFF
``ftyp``+``moov/mvhd`` so the duration reader has something to parse — no ffmpeg) and
asserts the verifier accepts a well-synced pair and rejects each way a pair can go out
of sync: non-monotonic timestamps, a sidecar not rebased to start, detections past the
end of the video, sparse coverage, and de-normalised geometry. Also covers the
hold-last-by-PTS overlay join used at playback time.
"""

import json
from pathlib import Path

import pytest

from app.playback_sync import (
    SidecarFrame,
    SidecarOverlayIndex,
    read_mp4_duration_s,
    verify_playback_sync,
)

_NS = 1_000_000_000


# --- fixture builders -------------------------------------------------------------------


def _box(btype: bytes, payload: bytes) -> bytes:
    return (8 + len(payload)).to_bytes(4, "big") + btype + payload


def _mvhd_v0(timescale: int, duration: int) -> bytes:
    body = b"\x00\x00\x00\x00"  # version 0 + flags
    body += (0).to_bytes(4, "big") + (0).to_bytes(4, "big")  # creation, modification
    body += timescale.to_bytes(4, "big") + duration.to_bytes(4, "big")
    body += b"\x00" * 80  # rate/volume/matrix/… (unused by the reader)
    return _box(b"mvhd", body)


def _mvhd_v1(timescale: int, duration: int) -> bytes:
    body = b"\x01\x00\x00\x00"  # version 1 + flags
    body += (0).to_bytes(8, "big") + (0).to_bytes(8, "big")  # 64-bit creation, modification
    body += timescale.to_bytes(4, "big") + duration.to_bytes(8, "big")
    body += b"\x00" * 80
    return _box(b"mvhd", body)


def _write_mp4(
    path: Path, *, timescale: int = 1000, duration: int = 20_000, v1: bool = False
) -> Path:
    ftyp = _box(b"ftyp", b"isom" + (0).to_bytes(4, "big") + b"isomiso2mp41")
    mvhd = _mvhd_v1(timescale, duration) if v1 else _mvhd_v0(timescale, duration)
    path.write_bytes(ftyp + _box(b"moov", mvhd))
    return path


def _det(cat: str = "polyp") -> dict:
    return {"bbox": [0.1, 0.1, 0.2, 0.2], "cat": cat, "conf": 0.9, "seg": [[0.1, 0.1, 0.3, 0.3]]}


def _write_sidecar(path: Path, pts_ns_list: list[int], *, dets=None) -> Path:
    lines = [
        json.dumps({"pts_ns": p, "dets": dets if dets is not None else [_det()]})
        for p in pts_ns_list
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _even_pts(n: int = 40, step_s: float = 0.5) -> list[int]:
    return [int(i * step_s * _NS) for i in range(n)]  # 0, .5, … 19.5s


@pytest.fixture
def pristine(tmp_path: Path) -> tuple[Path, Path]:
    """A 20.0s clip with a 0.5s-cadence sidecar spanning ~0 → 19.5s."""
    mp4 = _write_mp4(tmp_path / "VID0001.mp4")
    side = _write_sidecar(tmp_path / "VID0001.ndjson", _even_pts())
    return mp4, side


# --- mp4 duration reader ----------------------------------------------------------------


def test_mp4_duration_reader_v0(tmp_path: Path) -> None:
    mp4 = _write_mp4(tmp_path / "a.mp4", timescale=1000, duration=20_000)
    assert read_mp4_duration_s(mp4) == pytest.approx(20.0)


def test_mp4_duration_reader_v1(tmp_path: Path) -> None:
    mp4 = _write_mp4(tmp_path / "a.mp4", timescale=600, duration=18_000, v1=True)
    assert read_mp4_duration_s(mp4) == pytest.approx(30.0)


def test_mp4_duration_reader_rejects_non_mp4(tmp_path: Path) -> None:
    bad = tmp_path / "notes.txt"
    bad.write_bytes(b"this is not an mp4 at all")
    with pytest.raises(ValueError, match="no 'moov' box"):
        read_mp4_duration_s(bad)


# --- the happy path ---------------------------------------------------------------------


def test_pristine_pair_is_playback_sound(pristine: tuple[Path, Path]) -> None:
    mp4, side = pristine
    report = verify_playback_sync(mp4, side)

    assert report.ok, report.issues
    assert report.issues == []
    assert report.frame_count == 40
    assert report.first_pts_ns == 0
    assert report.video_duration_s == pytest.approx(20.0)
    assert report.coverage_ratio == pytest.approx(19.5 / 20.0)
    assert report.monotonic and report.rebased_to_start
    assert report.within_bounds and report.spans_video and report.normalized_geometry


# --- each desync mode is detected -------------------------------------------------------


def test_non_monotonic_timestamps_detected(tmp_path: Path) -> None:
    mp4 = _write_mp4(tmp_path / "v.mp4")
    pts = _even_pts()
    pts[5], pts[6] = pts[6], pts[5]  # swap → goes backwards
    side = _write_sidecar(tmp_path / "v.ndjson", pts)

    report = verify_playback_sync(mp4, side)
    assert not report.ok and not report.monotonic
    assert any("monotonic" in m for m in report.issues)


def test_not_rebased_to_start_detected(tmp_path: Path) -> None:
    mp4 = _write_mp4(tmp_path / "v.mp4")
    pts = [int((5.0 + i * 0.5) * _NS) for i in range(20)]  # starts at 5s
    side = _write_sidecar(tmp_path / "v.ndjson", pts)

    report = verify_playback_sync(mp4, side)
    assert not report.ok and not report.rebased_to_start
    assert any("rebased" in m for m in report.issues)


def test_detections_past_end_of_video_detected(tmp_path: Path) -> None:
    mp4 = _write_mp4(tmp_path / "v.mp4", duration=20_000)  # 20s
    pts = _even_pts() + [int(30.0 * _NS)]  # one detection at 30s
    side = _write_sidecar(tmp_path / "v.ndjson", pts)

    report = verify_playback_sync(mp4, side)
    assert not report.ok and not report.within_bounds
    assert any("exceeds video" in m for m in report.issues)


def test_sparse_coverage_detected(tmp_path: Path) -> None:
    mp4 = _write_mp4(tmp_path / "v.mp4", duration=20_000)  # 20s
    pts = [int(i * 0.5 * _NS) for i in range(10)]  # only 0 → 4.5s
    side = _write_sidecar(tmp_path / "v.ndjson", pts)

    report = verify_playback_sync(mp4, side)
    assert not report.ok and not report.spans_video
    assert report.coverage_ratio == pytest.approx(4.5 / 20.0)
    assert any("covers" in m for m in report.issues)


def test_denormalized_geometry_detected(tmp_path: Path) -> None:
    mp4 = _write_mp4(tmp_path / "v.mp4")
    bad = {"bbox": [1.5, 0.1, 0.2, 0.2], "cat": "polyp", "conf": 0.9, "seg": []}  # x > 1
    side = _write_sidecar(tmp_path / "v.ndjson", _even_pts(), dets=[bad])

    report = verify_playback_sync(mp4, side)
    assert not report.ok and not report.normalized_geometry
    assert any("normalised" in m for m in report.issues)


def test_empty_category_label_is_tolerated(tmp_path: Path) -> None:
    """Real nano sidecars carry detections with an empty 'cat' (unlabeled/context) — these
    are valid and must not fail playback-sync (regression: pulled a live clip and the first
    frame had cat='')."""
    mp4 = _write_mp4(tmp_path / "v.mp4")
    unlabeled = {"bbox": [0.1, 0.1, 0.2, 0.2], "cat": "", "conf": 0.8, "seg": []}
    side = _write_sidecar(tmp_path / "v.ndjson", _even_pts(), dets=[unlabeled])

    report = verify_playback_sync(mp4, side)
    assert report.ok, report.issues
    assert report.normalized_geometry


def test_empty_sidecar_is_not_playback_sound(tmp_path: Path) -> None:
    mp4 = _write_mp4(tmp_path / "v.mp4")
    side = tmp_path / "v.ndjson"
    side.write_text("", encoding="utf-8")

    report = verify_playback_sync(mp4, side)
    assert not report.ok and report.frame_count == 0
    assert any("no frames" in m for m in report.issues)


def test_missing_mp4_is_reported_but_sidecar_still_checked(tmp_path: Path) -> None:
    not_mp4 = tmp_path / "v.mp4"
    not_mp4.write_bytes(b"junk-not-mp4")
    side = _write_sidecar(tmp_path / "v.ndjson", _even_pts())

    report = verify_playback_sync(not_mp4, side)
    assert not report.ok and report.video_duration_s is None
    # Timeline checks that don't need the video still ran:
    assert report.monotonic and report.rebased_to_start
    assert any("moov" in m for m in report.issues)


# --- overlay-sync join (hold-last-by-PTS) ----------------------------------------------


def test_overlay_index_holds_last_detection_between_inferences() -> None:
    frames = [
        SidecarFrame(pts_ns=0, dets=[]),
        SidecarFrame(pts_ns=1 * _NS, dets=[]),
        SidecarFrame(pts_ns=2 * _NS, dets=[]),
    ]
    # Tag each frame so we can tell which one the join returned.
    frames[0].dets = []
    idx = SidecarOverlayIndex(frames)
    # Querying forward in time advances the cursor and holds the last frame between points.
    assert idx.at(0) is frames[0].dets
    assert idx.at(int(0.5 * _NS)) is frames[0].dets  # held until next inference
    assert idx.at(1 * _NS) is frames[1].dets
    assert idx.at(int(1.9 * _NS)) is frames[1].dets  # held
    assert idx.at(5 * _NS) is frames[2].dets  # past the last → last held


def test_overlay_index_empty_before_first_inference() -> None:
    idx = SidecarOverlayIndex([SidecarFrame(pts_ns=int(2.0 * _NS), dets=[])])
    # The first inferred frame is at 2s; before it there is no overlay.
    assert idx.at(int(1.0 * _NS)) == []


def test_overlay_index_orders_unsorted_input() -> None:
    a = SidecarFrame(pts_ns=2 * _NS, dets=[])
    b = SidecarFrame(pts_ns=0, dets=[])
    c = SidecarFrame(pts_ns=1 * _NS, dets=[])
    idx = SidecarOverlayIndex([a, b, c])  # given out of order
    assert idx.at(0) is b.dets
    assert idx.at(int(1.5 * _NS)) is c.dets
    assert idx.at(int(2.5 * _NS)) is a.dets
