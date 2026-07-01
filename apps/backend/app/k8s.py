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
from datetime import UTC, datetime
from urllib.parse import quote

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
        self._timeout = settings.kubernetes_timeout_s

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
                timeout=self._timeout,
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

    def get_daemonset_image(self, namespace: str, name: str, container: str) -> str:
        """Read ``container``'s current image on the given DaemonSet.

        The read the mutating client lacked (PLAN.md §6: "the k8s client only patches
        the image; it can't read the current one"). Powers the fleet's running-version
        display. Fleet-wide — one DaemonSet, one image, in v1.
        """
        url = f"{self._api_url}/apis/apps/v1/namespaces/{namespace}/daemonsets/{name}"
        ds = self._get_json(url, f"DaemonSet {namespace}/{name}")
        image = _container_image(ds.get("spec", {}), container)
        if image is None:
            raise KubernetesUnavailable(
                f"container {container!r} not found (or imageless) in DaemonSet {namespace}/{name}"
            )
        return image

    def restart_daemonset(self, namespace: str, name: str) -> None:
        """Roll the DaemonSet's pods — the ``kubectl rollout restart`` mechanism.

        Stamps a ``kubectl.kubernetes.io/restartedAt`` annotation on the pod template;
        the change to the template spec makes the DaemonSet controller recreate every
        pod. Fleet-wide in v1 (one DaemonSet), same as set-image.
        """
        url = f"{self._api_url}/apis/apps/v1/namespaces/{namespace}/daemonsets/{name}"
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {"kubectl.kubernetes.io/restartedAt": stamp},
                    },
                },
            },
        }
        log.info("rollout-restart DaemonSet %s/%s (restartedAt=%s)", namespace, name, stamp)
        self._strategic_patch(url, body, f"DaemonSet {namespace}/{name}")

    def previous_daemonset_image(self, namespace: str, name: str, container: str) -> str:
        """The image of the DaemonSet's immediately previous revision — the rollback target.

        Reads the cluster's ControllerRevision history (k8s retains it per DaemonSet),
        picks the second-newest revision owned by this DaemonSet, and returns
        ``container``'s image from that revision's stored pod template. Raises if there
        is no prior revision to roll back to.
        """
        ds_url = f"{self._api_url}/apis/apps/v1/namespaces/{namespace}/daemonsets/{name}"
        ds = self._get_json(ds_url, f"DaemonSet {namespace}/{name}")
        match_labels = ds.get("spec", {}).get("selector", {}).get("matchLabels", {})
        if not match_labels:
            raise KubernetesUnavailable(
                f"DaemonSet {namespace}/{name} has no selector.matchLabels to find revisions"
            )
        selector = quote(",".join(f"{k}={v}" for k, v in sorted(match_labels.items())))
        cr_url = (
            f"{self._api_url}/apis/apps/v1/namespaces/{namespace}"
            f"/controllerrevisions?labelSelector={selector}"
        )
        items = self._get_json(cr_url, f"ControllerRevisions for {namespace}/{name}").get(
            "items", []
        )
        # Only revisions owned by THIS DaemonSet, oldest→newest by revision number.
        owned = [
            r
            for r in items
            if any(
                o.get("kind") == "DaemonSet" and o.get("name") == name
                for o in r.get("metadata", {}).get("ownerReferences", [])
            )
        ]
        owned.sort(key=lambda r: r.get("revision", 0))
        if len(owned) < 2:
            raise KubernetesUnavailable(
                f"no prior revision of DaemonSet {namespace}/{name} to roll back to"
            )
        # ControllerRevision.data holds the DaemonSet's pod template under spec.template.
        prev_spec = owned[-2].get("data", {}).get("spec", {})
        image = _container_image(prev_spec, container)
        if image is None:
            raise KubernetesUnavailable(
                f"previous revision of {namespace}/{name} has no image for container {container!r}"
            )
        return image

    # --- shared HTTP helpers (new read/restart/rollback paths) ---------------------

    def _auth_headers(self, content_type: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        if content_type is not None:
            headers["Content-Type"] = content_type
        return headers

    def _get_json(self, url: str, what: str) -> dict:
        try:
            response = httpx2.get(
                url, headers=self._auth_headers(), verify=self._ca, timeout=self._timeout
            )
        except httpx2.HTTPError as e:
            raise KubernetesUnavailable(f"k8s GET transport failed: {e}") from e
        if response.status_code == 404:
            raise KubernetesUnavailable(
                f"{what} not found — has the nano deploy been applied to this cluster?"
            )
        if response.status_code >= 400:
            raise KubernetesUnavailable(
                f"k8s GET returned HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            return response.json()
        except ValueError as e:
            raise KubernetesUnavailable(f"k8s GET returned non-JSON: {e}") from e

    def _strategic_patch(self, url: str, body: dict, what: str) -> None:
        try:
            response = httpx2.patch(
                url,
                headers=self._auth_headers("application/strategic-merge-patch+json"),
                json=body,
                verify=self._ca,
                timeout=self._timeout,
            )
        except httpx2.HTTPError as e:
            raise KubernetesUnavailable(f"k8s PATCH transport failed: {e}") from e
        if response.status_code == 404:
            raise KubernetesUnavailable(
                f"{what} not found — has the nano deploy been applied to this cluster?"
            )
        if response.status_code >= 400:
            raise KubernetesUnavailable(
                f"k8s PATCH returned HTTP {response.status_code}: {response.text[:200]}"
            )


def _container_image(pod_spec_parent: dict, container: str) -> str | None:
    """Pull ``container``'s image out of a ``{template: {spec: {containers: [...]}}}`` block.

    Shared by the live DaemonSet read and the ControllerRevision (previous-revision) read —
    both nest the pod template the same way. Returns None if the container is absent or imageless.
    """
    containers = pod_spec_parent.get("template", {}).get("spec", {}).get("containers", [])
    for entry in containers:
        if entry.get("name") == container:
            return entry.get("image") or None
    return None
