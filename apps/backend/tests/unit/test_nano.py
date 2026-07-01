"""NanoClient.prepare_shutdown — the real outbound drain call, HTTP layer stubbed.

The route tests fake NanoClient; these pin the client itself: it parses a well-formed
ack, and maps transport errors / bad shapes to NanoUnavailable so the route can refuse to
patch. No live nano.
"""

import httpx2
import pytest

from app import nano as nano_mod
from app.nano import NanoClient, NanoUnavailable


class _Resp:
    def __init__(self, payload, status_error=None):
        self._payload, self._err = payload, status_error

    def raise_for_status(self):
        if self._err is not None:
            raise self._err

    def json(self):
        return self._payload


def test_prepare_shutdown_parses_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_post(url, *, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        return _Resp({"drained": True, "recordings_finalized": 3, "pipeline_stopped": True})

    monkeypatch.setattr(nano_mod.httpx2, "post", fake_post)
    ack = NanoClient("http://nano:8000/", token="tok").prepare_shutdown()

    assert ack.drained is True
    assert ack.recordings_finalized == 3
    assert captured["url"] == "http://nano:8000/api/admin/prepare-shutdown"
    assert captured["headers"]["Authorization"] == "Bearer tok"


def test_prepare_shutdown_defaults_optional_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        nano_mod.httpx2, "post", lambda url, *, headers, timeout: _Resp({"drained": True})
    )
    ack = NanoClient("http://nano:8000").prepare_shutdown()
    assert ack.drained is True
    assert ack.recordings_finalized == 0
    assert ack.pipeline_stopped is False


def test_prepare_shutdown_http_error_raises_nano_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(url, *, headers, timeout):
        raise httpx2.HTTPError("connection refused")

    monkeypatch.setattr(nano_mod.httpx2, "post", boom)
    with pytest.raises(NanoUnavailable):
        NanoClient("http://nano:8000").prepare_shutdown()


def test_prepare_shutdown_bad_shape_raises_nano_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Missing the required 'drained' field → validation failure → NanoUnavailable.
    monkeypatch.setattr(
        nano_mod.httpx2, "post", lambda url, *, headers, timeout: _Resp({"whatever": 1})
    )
    with pytest.raises(NanoUnavailable, match="unexpected shape"):
        NanoClient("http://nano:8000").prepare_shutdown()
