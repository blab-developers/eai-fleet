"""Unit tests for the recordings PULL core — list, download (ranged), idempotency.

No live nano, no cluster: httpx2 is mocked. The downloaded files on disk are the receipt,
so reconcile() is idempotent — present files are skipped (Spec 024). The nano's saved-session
list carries no sha256/size, so "file exists locally" is the skip key.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import app.recordings_pull as rp
from app.recordings_pull import RecordingsPuller, SavedSession


def _saved_payload(
    sessions: list[SavedSession], total: int | None = None, offset: int = 0
) -> dict[str, object]:
    return {
        "items": [s.model_dump(mode="json") for s in sessions],
        "total": total if total is not None else len(sessions),
        "limit": 100,
        "offset": offset,
    }


def _get_mock(payload: dict[str, object]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    return resp


def _stream_mock(data: bytes, status_code: int = 200) -> MagicMock:
    body = MagicMock()
    body.raise_for_status = MagicMock()
    body.status_code = status_code
    body.iter_bytes = MagicMock(return_value=[data])
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=body)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_reconcile_pulls_video_and_sidecar_then_idempotent(tmp_path: Path) -> None:
    sess = SavedSession(inference_id="VID0001", has_sidecar=True)
    with (
        patch.object(rp.httpx2, "get", return_value=_get_mock(_saved_payload([sess]))),
        patch.object(rp.httpx2, "stream", return_value=_stream_mock(b"bytes")),
    ):
        summary = RecordingsPuller("http://nano-1:8000", "tok", tmp_path).reconcile()

    assert (summary.sessions_total, summary.pulled, summary.skipped, summary.failed) == (1, 2, 0, 0)
    assert (tmp_path / "VID0001" / "VID0001.mp4").exists()
    assert (tmp_path / "VID0001" / "VID0001.ndjson").exists()

    # Re-run: both files present → skipped, nothing downloaded (the file is the receipt).
    with (
        patch.object(rp.httpx2, "get", return_value=_get_mock(_saved_payload([sess]))),
        patch.object(rp.httpx2, "stream", return_value=_stream_mock(b"bytes")) as stream,
    ):
        again = RecordingsPuller("http://nano-1:8000", "tok", tmp_path).reconcile()
    assert (again.pulled, again.skipped) == (0, 2)
    stream.assert_not_called()


def test_reconcile_skips_sidecar_when_absent(tmp_path: Path) -> None:
    sess = SavedSession(inference_id="VID0002", has_sidecar=False)
    with (
        patch.object(rp.httpx2, "get", return_value=_get_mock(_saved_payload([sess]))),
        patch.object(rp.httpx2, "stream", return_value=_stream_mock(b"v")),
    ):
        summary = RecordingsPuller("http://nano-1:8000", "tok", tmp_path).reconcile()

    assert (summary.pulled, summary.skipped) == (1, 0)
    assert (tmp_path / "VID0002" / "VID0002.mp4").exists()
    assert not (tmp_path / "VID0002" / "VID0002.ndjson").exists()


def test_reconcile_counts_download_failure(tmp_path: Path) -> None:
    sess = SavedSession(inference_id="VID0003", has_sidecar=False)

    def _raise(*_a: object, **_k: object) -> None:
        raise rp.httpx2.HTTPError("boom")

    with (
        patch.object(rp.httpx2, "get", return_value=_get_mock(_saved_payload([sess]))),
        patch.object(rp.httpx2, "stream", side_effect=_raise),
    ):
        summary = RecordingsPuller("http://nano-1:8000", "tok", tmp_path).reconcile()

    assert (summary.pulled, summary.failed) == (0, 1)
    assert not (tmp_path / "VID0003" / "VID0003.mp4").exists()  # partial not promoted


def test_fetch_sessions_paginates(tmp_path: Path) -> None:
    pages = [
        _saved_payload(
            [SavedSession(inference_id="a"), SavedSession(inference_id="b")], total=3, offset=0
        ),
        _saved_payload([SavedSession(inference_id="c")], total=3, offset=2),
    ]
    seq = iter(pages)

    def _get(*_a: object, **_k: object) -> MagicMock:
        return _get_mock(next(seq))

    with patch.object(rp.httpx2, "get", side_effect=_get):
        sessions = RecordingsPuller(
            "http://nano-1:8000", "tok", tmp_path, page_size=2
        ).fetch_sessions()

    assert [s.inference_id for s in sessions] == ["a", "b", "c"]
