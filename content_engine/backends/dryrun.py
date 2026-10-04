"""Offline backend: writes the exact payload a real backend would send plus a
placeholder image, so a campaign can be planned and reviewed with no API key."""
from __future__ import annotations

import html
import json
from pathlib import Path

from ..models import CreativeSpec


class DryRunBackend:
    name = "dryrun"

    def __init__(self, payload_builder=None):
        # payload_builder(spec) -> dict; lets dry runs show the real Comfy payload.
        self.payload_builder = payload_builder

    def render(self, spec: CreativeSpec, out_dir: Path) -> CreativeSpec:
        out_dir.mkdir(parents=True, exist_ok=True)
        if self.payload_builder:
            payload_path = out_dir / f"{spec.id}.payload.json"
            payload_path.write_text(json.dumps(self.payload_builder(spec), indent=2,
                                               ensure_ascii=False), encoding="utf-8")
            spec.backend_job = {"payload": payload_path.name}
        w, h = spec.format.width, spec.format.height
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<rect width="100%" height="100%" fill="#e9e4dc"/>'
            f'<rect x="{w*0.3:.0f}" y="{h*0.3:.0f}" width="{w*0.4:.0f}" height="{h*0.4:.0f}" '
            f'rx="24" fill="#cfc6b8"/>'
            f'<text x="50%" y="50%" font-family="sans-serif" font-size="{max(w, h)//40}" '
            f'fill="#6b6257" text-anchor="middle">{html.escape(spec.product)} · seed {spec.seed}</text>'
            f'</svg>'
        )
        img = out_dir / f"{spec.id}.svg"
        img.write_text(svg, encoding="utf-8")
        spec.assets = [img.name]
        return spec
