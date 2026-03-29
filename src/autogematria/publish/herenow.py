"""Helpers for publishing static bundles to here.now."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib import request


HERE_NOW_PUBLISH_URL = "https://here.now/api/v1/publish"
DEFAULT_CLIENT = "codex/autogematria"


def _file_manifest_entry(path: Path, root: Path) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    content_type, _ = mimetypes.guess_type(path.name)
    if content_type is None:
        content_type = "application/octet-stream"
    if content_type.startswith("text/") or content_type in {
        "application/json",
        "application/javascript",
        "application/xml",
    }:
        content_type = f"{content_type}; charset=utf-8"
    data = path.read_bytes()
    return {
        "path": rel,
        "size": len(data),
        "contentType": content_type,
        "hash": hashlib.sha256(data).hexdigest(),
    }


def _json_request(
    url: str,
    *,
    method: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    encoded = None
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    if body is not None:
        encoded = json.dumps(body).encode("utf-8")
    req = request.Request(url, data=encoded, method=method, headers=request_headers)
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def _upload_file(upload: dict[str, Any], local_path: Path) -> None:
    put_headers = upload.get("headers") or {}
    req = request.Request(
        upload["url"],
        data=local_path.read_bytes(),
        method=upload.get("method") or "PUT",
        headers=put_headers,
    )
    with request.urlopen(req):
        return


def publish_directory(
    site_dir: str | Path,
    *,
    api_key: str | None = None,
    client_name: str = DEFAULT_CLIENT,
    viewer_title: str | None = None,
    viewer_description: str | None = None,
) -> dict[str, Any]:
    """Publish a static directory to here.now and return the deployment metadata."""
    root = Path(site_dir)
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"Cannot publish empty site directory: {root}")

    manifest = [_file_manifest_entry(path, root) for path in files]
    body: dict[str, Any] = {"files": manifest}
    if viewer_title or viewer_description:
        body["viewer"] = {}
        if viewer_title:
            body["viewer"]["title"] = viewer_title
        if viewer_description:
            body["viewer"]["description"] = viewer_description

    headers = {"X-HereNow-Client": client_name}
    auth_key = api_key or os.environ.get("HERENOW_API_KEY")
    if auth_key:
        headers["Authorization"] = f"Bearer {auth_key}"

    created = _json_request(HERE_NOW_PUBLISH_URL, method="POST", body=body, headers=headers)
    upload = created["upload"]
    uploads_by_path = {entry["path"]: entry for entry in upload.get("uploads", [])}
    for path in files:
        rel = path.relative_to(root).as_posix()
        upload_entry = uploads_by_path.get(rel)
        if upload_entry is not None:
            _upload_file(upload_entry, path)

    finalized = _json_request(
        upload["finalizeUrl"],
        method="POST",
        body={"versionId": upload["versionId"]},
        headers=headers,
    )
    result = {
        "slug": created.get("slug"),
        "site_url": finalized.get("siteUrl") or created.get("siteUrl"),
        "version_id": upload.get("versionId"),
        "current_version_id": finalized.get("currentVersionId"),
    }
    for key in ("claimUrl", "claimToken", "expiresAt", "anonymous", "warning"):
        if key in created:
            result[key] = created[key]
    return result
