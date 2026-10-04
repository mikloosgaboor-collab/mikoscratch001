"""Comfy backend: runs an API-format ComfyUI workflow per creative.

Works against Comfy Cloud (https://cloud.comfy.org, X-API-Key auth) and a local
ComfyUI (http://127.0.0.1:8188, no auth) — both serve /api/prompt, /api/history
and /api/view. Workflow templates are API-format JSON (ComfyUI: "Export (API)",
or have Comfy Agent build the graph and export it) where any string value may be
a placeholder: {{prompt}}, {{negative_prompt}}, {{width}}, {{height}}, {{seed}},
{{filename_prefix}}. A value that is exactly one placeholder takes the typed value
(so "{{width}}" becomes the int 1080).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..models import CreativeSpec

CLOUD_URL = "https://cloud.comfy.org"


def fill_template(node, values: dict):
    if isinstance(node, dict):
        return {k: fill_template(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [fill_template(v, values) for v in node]
    if isinstance(node, str):
        for key, val in values.items():
            token = "{{" + key + "}}"
            if node == token:
                return val
            if token in node:
                node = node.replace(token, str(val))
    return node


def spec_values(spec: CreativeSpec) -> dict:
    return {
        "prompt": spec.prompt,
        "negative_prompt": spec.negative_prompt,
        "width": spec.format.width,
        "height": spec.format.height,
        "seed": spec.seed,
        "filename_prefix": spec.id,
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class ComfyBackend:
    name = "comfy"

    def __init__(self, workflow_path: str | Path, base_url: str = CLOUD_URL,
                 api_key: str | None = None, poll_seconds: float = 3.0,
                 timeout_seconds: float = 600.0):
        self.workflow = json.loads(Path(workflow_path).read_text(encoding="utf-8"))
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self._opener = urllib.request.build_opener(_NoRedirect)

    def build_payload(self, spec: CreativeSpec) -> dict:
        return {"prompt": fill_template(self.workflow, spec_values(spec))}

    def _request(self, method: str, path: str, body: dict | None = None):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        req = urllib.request.Request(
            self.base_url + path, method=method, headers=headers,
            data=json.dumps(body).encode() if body is not None else None)
        try:
            return self._opener.open(req, timeout=60)
        except urllib.error.HTTPError as e:
            # Cloud /api/view answers 302 to a signed storage URL; hand it back.
            if e.code in (301, 302, 303, 307, 308):
                return e
            detail = e.read().decode(errors="replace")[:500]
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from None

    def _json(self, method: str, path: str, body: dict | None = None) -> dict:
        with self._request(method, path, body) as r:
            return json.loads(r.read() or b"{}")

    def submit(self, spec: CreativeSpec) -> str:
        resp = self._json("POST", "/api/prompt", self.build_payload(spec))
        if "prompt_id" not in resp:
            raise RuntimeError(f"submit failed for {spec.id}: {resp}")
        return resp["prompt_id"]

    def wait(self, prompt_id: str) -> dict:
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            hist = self._json("GET", f"/api/history/{prompt_id}")
            entry = hist.get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"job {prompt_id} failed: {status.get('messages')}")
                if entry.get("outputs"):
                    return entry["outputs"]
            time.sleep(self.poll_seconds)
        raise TimeoutError(f"job {prompt_id} not finished after {self.timeout_seconds}s")

    def download(self, image: dict, dest: Path) -> None:
        q = urllib.parse.urlencode({k: image.get(k, "") for k in ("filename", "subfolder", "type")})
        resp = self._request("GET", f"/api/view?{q}")
        location = resp.headers.get("Location") if isinstance(resp, urllib.error.HTTPError) else None
        if location:
            # Signed storage URL: fetch without our API key.
            resp.close()
            resp = urllib.request.urlopen(location, timeout=120)
        with resp:
            dest.write_bytes(resp.read())

    def render(self, spec: CreativeSpec, out_dir: Path) -> CreativeSpec:
        out_dir.mkdir(parents=True, exist_ok=True)
        prompt_id = self.submit(spec)
        spec.backend_job = {"backend": self.name, "base_url": self.base_url, "prompt_id": prompt_id}
        outputs = self.wait(prompt_id)
        images = [img for node in outputs.values() for img in node.get("images", [])
                  if img.get("type") == "output"]
        for i, img in enumerate(images):
            suffix = Path(img["filename"]).suffix or ".png"
            dest = out_dir / f"{spec.id}_{i}{suffix}"
            self.download(img, dest)
            spec.assets.append(dest.name)
        if not spec.assets:
            raise RuntimeError(f"job {prompt_id} produced no output images")
        return spec
