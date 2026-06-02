"""Unit tests for the recordings PULL core — diff, download (ranged), sha256 verify.

No live nano, no cluster: httpx2 is mocked. The downloaded files on disk are the receipt,
so reconcile() is idempotent and exact duplicates are skipped (Spec 024).
"""

import hashlib
from datetime import datetime
from unittest.mock import MagicMock, patch

import recordings_pull as rp
from recordings_pull import ManifestFile, RecordingsPuller, plan_pulls


def _mf(mid: str, kind: str, filename: str, data: bytes, **kw) -> ManifestFile:
    return ManifestFile(
        media_file_id=mid,
        kind=kind,
        filename=filename,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        created_at=datetime(2026, 6, 2),
        **kw,
    )


def _manifest_payload(files: list[ManifestFile]) -> dict:
    return {
        "device_id": "nano-1",
        "files": [f.model_dump(mode="json") for f in files],
        "total": len(files),
        "limit": 100,
        "offset": 0,
    }


def _get_mock(payload: dict) -> MagicMock:
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


def test_plan_pulls_diffs_against_disk(tmp_path):
    data = b"video-bytes"
    manifest = [
        _mf("v1", "video", "video.mp4", data),
        _mf("s1", "sidecar", "sidecar.ndjson", b"{}"),
    ]
    # v1 already on disk with matching bytes → only s1 needs pulling.
    p = tmp_path / "v1" / "video.mp4"
    p.parent.mkdir(parents=True)
    p.write_bytes(data)

    todo = plan_pulls(manifest, tmp_path)
    assert [f.media_file_id for f in todo] == ["s1"]


def test_plan_skips_unsealed_and_unhashed(tmp_path):
    manifest = [
        ManifestFile(
            media_file_id="x", kind="video", filename="v.mp4", size_bytes=1,
            sha256=None, created_at=datetime(2026, 6, 2),
        ),
        ManifestFile(
            media_file_id="y", kind="video", filename="v.mp4", size_bytes=1,
            sha256="abc", created_at=datetime(2026, 6, 2), sealed=False,
        ),
    ]
    assert plan_pulls(manifest, tmp_path) == []


def test_reconcile_downloads_verifies_and_is_idempotent(tmp_path):
    data = b"the-video-bytes"
    payload = _manifest_payload([_mf("v1", "video", "video.mp4", data)])

    with (
        patch.object(rp.httpx2, "get", return_value=_get_mock(payload)),
        patch.object(rp.httpx2, "stream", return_value=_stream_mock(data)),
    ):
        summary = RecordingsPuller("http://nano-1:8000", "tok", tmp_path).reconcile()

    assert (summary.pulled, summary.failed, summary.skipped) == (1, 0, 0)
    assert (tmp_path / "v1" / "video.mp4").read_bytes() == data

    # Re-run: file present + sha matches → skipped (the receipt is the file).
    with (
        patch.object(rp.httpx2, "get", return_value=_get_mock(payload)),
        patch.object(rp.httpx2, "stream", return_value=_stream_mock(data)) as stream,
    ):
        again = RecordingsPuller("http://nano-1:8000", "tok", tmp_path).reconcile()
    assert (again.pulled, again.skipped) == (0, 1)
    stream.assert_not_called()  # nothing to download


def test_reconcile_rejects_sha_mismatch(tmp_path):
    payload = _manifest_payload([_mf("v1", "video", "v.mp4", b"good-bytes")])
    with (
        patch.object(rp.httpx2, "get", return_value=_get_mock(payload)),
        patch.object(rp.httpx2, "stream", return_value=_stream_mock(b"CORRUPTED")),
    ):
        summary = RecordingsPuller("http://nano-1:8000", "tok", tmp_path).reconcile()

    assert (summary.pulled, summary.failed) == (0, 1)
    assert not (tmp_path / "v1" / "v.mp4").exists()  # corrupt download discarded
