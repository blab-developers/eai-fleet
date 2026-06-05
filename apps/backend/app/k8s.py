"""Minimal Kubernetes API client — httpx2-only.

We deliberately avoid the official ``kubernetes`` Python package: it pulls
``urllib3`` and the repo's HTTP-client convention is ``httpx2`` only (parity
with eai-nano AGENTS.md). The only mutation we make against the cluster is a
strategic-merge PATCH on a DaemonSet's container image, so a thin client is
plenty.

Auth uses the canonical in-cluster shape: a bearer token at
``/var/run/secrets/kubernetes.io/serviceaccount/token`` and the API server CA at
``…/ca.crt``. Even though the deployed fleet container is a Docker container
(not a Pod), the eai-infra ansible role drops both files at those paths via
bind mounts — so the same code works in-Pod (future) and on the host today.
"""

import logging

import httpx2

from app.config import settings

log = logging.getLogger(__name__)


class KubernetesUnavailable(RuntimeError):
    """Raised when the cluster API can't be reached or rejects the call."""


class K8sClient:
    """Strategic-merge-patch client for the in-cluster k8s API."""

    def __init__(self) -> None:
        if not settings.kubernetes_token_path.exists():
            raise KubernetesUnavailable(
                f"k8s bearer token not found at {settings.kubernetes_token_path}; "
                "the eai-infra role must mount it into the container."
            )
        if not settings.kubernetes_ca_path.exists():
            raise KubernetesUnavailable(
                f"k8s API CA bundle not found at {settings.kubernetes_ca_path}; "
                "the eai-infra role must mount it into the container."
            )
        # Token rotation: cluster-issued SA tokens are long-lived for the v1
        # demo (the role provisions a token-with-no-expiry secret); reading once
        # at construction is fine. Future per-Pod tokens would be projected
        # short-lived and need re-reading on 401.
        self._token = settings.kubernetes_token_path.read_text().strip()
        self._api_url = settings.kubernetes_api_url.rstrip("/")
        self._ca = str(settings.kubernetes_ca_path)
        self._timeout_s = settings.kubernetes_timeout_s

    def patch_daemonset_image(
        self,
        namespace: str,
        name: str,
        container: str,
        image: str,
    ) -> None:
        """Set ``container``'s image on the given DaemonSet via strategic merge.

        Strategic merge patch lets us specify just the one container by name —
        the k8s API merges it into the DS's existing container list rather than
        replacing the whole list. Other containers in the same pod (if any)
        are untouched.
        """
        url = f"{self._api_url}/apis/apps/v1/namespaces/{namespace}/daemonsets/{name}"
        body = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"name": container, "image": image}],
                    },
                },
            },
        }
        log.info(
            "patching DaemonSet %s/%s container %s → %s",
            namespace,
            name,
            container,
            image,
        )
        try:
            response = httpx2.patch(
                url,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/strategic-merge-patch+json",
                    "Accept": "application/json",
                },
                json=body,
                verify=self._ca,
                timeout=self._timeout_s,
            )
        except httpx2.HTTPError as e:
            raise KubernetesUnavailable(f"k8s PATCH transport failed: {e}") from e
        if response.status_code == 404:
            raise KubernetesUnavailable(
                f"DaemonSet {namespace}/{name} not found — has the nano deploy "
                "(eai-nano/deploy/10-inference.yaml) been applied to this cluster?"
            )
        if response.status_code >= 400:
            # The 200 char cap keeps a runaway k8s error message out of logs +
            # API responses; the full payload is still in container logs at info.
            raise KubernetesUnavailable(
                f"k8s PATCH returned HTTP {response.status_code}: {response.text[:200]}"
            )
