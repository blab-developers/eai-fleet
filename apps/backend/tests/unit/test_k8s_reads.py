"""K8sClient read/rollback parsing — the DaemonSet + ControllerRevision shapes.

The route-level tests use a FakeK8s; these exercise the REAL parsing in ``K8sClient``
(container-image extraction, revision ownership filter + sort, previous-image pick)
against canned API JSON, with the HTTP layer (``_get_json``) stubbed. No cluster.

⚠️ The exact ControllerRevision ``data`` shape is cluster-verified separately (same
convention as prometheus.py's PromQL): here we pin the logic that consumes it.
"""

import pytest

from app.k8s import K8sClient, KubernetesUnavailable, _container_image

_NS, _DS, _CONTAINER = "eai-nano", "eai-nano-inference", "inference"


def _client() -> K8sClient:
    """A K8sClient without the in-cluster file reads (bypass __init__ file checks)."""
    c = K8sClient.__new__(K8sClient)
    c._api_url = "https://k8s.test"
    c._token = "t"
    c._ca = "ca.crt"
    c._timeout = 5.0
    return c


def _ds(image: str) -> dict:
    return {
        "spec": {
            "selector": {"matchLabels": {"app": "eai-nano-inference"}},
            "template": {"spec": {"containers": [{"name": _CONTAINER, "image": image}]}},
        }
    }


def _revision(rev: int, image: str, owner: str = _DS) -> dict:
    return {
        "revision": rev,
        "metadata": {"ownerReferences": [{"kind": "DaemonSet", "name": owner}]},
        "data": {
            "spec": {"template": {"spec": {"containers": [{"name": _CONTAINER, "image": image}]}}}
        },
    }


def test_container_image_extracts_and_handles_missing() -> None:
    spec = {"template": {"spec": {"containers": [{"name": "inference", "image": "img:v9"}]}}}
    assert _container_image(spec, "inference") == "img:v9"
    assert _container_image(spec, "sidecar") is None
    assert _container_image({}, "inference") is None


def test_get_daemonset_image_reads_container(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _client()
    monkeypatch.setattr(c, "_get_json", lambda url, what: _ds("img:v5"))
    assert c.get_daemonset_image(_NS, _DS, _CONTAINER) == "img:v5"


def test_get_daemonset_image_missing_container_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _client()
    monkeypatch.setattr(c, "_get_json", lambda url, what: _ds("img:v5"))
    with pytest.raises(KubernetesUnavailable):
        c.get_daemonset_image(_NS, _DS, "nonesuch")


def test_previous_image_picks_second_newest_owned_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _client()
    # Deliberately out of order + a foreign-owned revision that must be ignored.
    responses = {
        "daemonsets": _ds("img:v3"),
        "controllerrevisions": {
            "items": [
                _revision(2, "img:v2"),
                _revision(1, "img:v1"),
                _revision(3, "img:v3"),
                _revision(99, "other:v99", owner="some-other-ds"),
            ]
        },
    }

    def fake_get(url: str, what: str) -> dict:
        return (
            responses["controllerrevisions"]
            if "controllerrevisions" in url
            else responses["daemonsets"]
        )

    monkeypatch.setattr(c, "_get_json", fake_get)
    # Newest owned revision is 3 (img:v3); the previous is 2 (img:v2).
    assert c.previous_daemonset_image(_NS, _DS, _CONTAINER) == "img:v2"


def test_previous_image_raises_when_only_one_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _client()

    def fake_get(url: str, what: str) -> dict:
        if "controllerrevisions" in url:
            return {"items": [_revision(1, "img:v1")]}
        return _ds("img:v1")

    monkeypatch.setattr(c, "_get_json", fake_get)
    with pytest.raises(KubernetesUnavailable, match="roll back"):
        c.previous_daemonset_image(_NS, _DS, _CONTAINER)
