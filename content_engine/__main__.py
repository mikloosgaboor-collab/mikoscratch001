"""CLI: python -m content_engine <campaign.json> [--backend dryrun|comfy] ...

Examples:
  python -m content_engine content_engine/brands/offline/campaigns/switch_off_q4.json
  COMFY_API_KEY=comfyui-... python -m content_engine <campaign> --backend comfy
  python -m content_engine <campaign> --backend comfy --base-url http://127.0.0.1:8188
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from .backends.comfy import CLOUD_URL, ComfyBackend
from .backends.dryrun import DryRunBackend
from .models import Brand, Campaign
from .planner import plan
from .report import write_manifest, write_review_sheet

HERE = Path(__file__).parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="content_engine")
    ap.add_argument("campaign", type=Path)
    ap.add_argument("--backend", choices=["dryrun", "comfy"], default="dryrun")
    ap.add_argument("--workflow", type=Path, default=HERE / "workflows" / "sdxl_txt2img.api.json")
    ap.add_argument("--base-url", default=os.environ.get("COMFY_BASE_URL", CLOUD_URL))
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--limit", type=int, default=0, help="render only the first N creatives")
    ap.add_argument("--allow-flagged", action="store_true",
                    help="render creatives that failed the claims check")
    args = ap.parse_args(argv)

    campaign = Campaign.load(args.campaign)
    brand = Brand.load(HERE / "brands" / campaign.brand / "brand.json")
    specs = plan(brand, campaign)
    if args.limit:
        specs = specs[:args.limit]

    comfy = ComfyBackend(args.workflow, base_url=args.base_url,
                         api_key=os.environ.get("COMFY_API_KEY"))
    if args.backend == "comfy":
        if args.base_url == CLOUD_URL and not comfy.api_key:
            ap.error("COMFY_API_KEY is required for Comfy Cloud "
                     "(create one at https://platform.comfy.org/profile/api-keys)")
        backend = comfy
    else:
        backend = DryRunBackend(payload_builder=comfy.build_payload)

    run_dir = args.out / campaign.id / time.strftime("%Y%m%d-%H%M%S")
    failures = 0
    for i, spec in enumerate(specs, 1):
        if spec.compliance and not args.allow_flagged:
            print(f"[{i}/{len(specs)}] SKIP {spec.id}: {'; '.join(spec.compliance)}")
            continue
        try:
            backend.render(spec, run_dir)
            print(f"[{i}/{len(specs)}] ok   {spec.id} -> {', '.join(spec.assets)}")
        except Exception as e:  # keep the batch going; failures land in the manifest
            failures += 1
            spec.backend_job["error"] = str(e)
            print(f"[{i}/{len(specs)}] FAIL {spec.id}: {e}", file=sys.stderr)

    run_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(specs, run_dir, {"brand": brand.id, "campaign": campaign.id,
                                    "backend": backend.name})
    for loc in campaign.locales:
        print("review sheet:", write_review_sheet(brand, campaign, specs, run_dir, loc))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
