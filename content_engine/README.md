# Content Engine

A multi-brand content pipeline: **brand profile + campaign brief → matrix of on-brand ad creatives**, rendered on Comfy (Comfy Cloud or a local ComfyUI), with localized copy, a claims check and a review sheet for client approval.

```
brands/<brand>/brand.json        voice, palette, art direction, products, audiences, banned claims
brands/<brand>/campaigns/*.json  objective, theme, products × audiences × formats × locales
        │
   planner.py   → CreativeSpec per cell: image prompt + HU/EN copy + compliance flags + stable seed
        │
   backends/    → dryrun (payloads + placeholders, no key)  |  comfy (POST /api/prompt → history → view)
        │
   report.py    → out/<campaign>/<run>/manifest.json + review_<locale>.html (copy overlaid on images)
```

Adding a client = adding one `brands/<id>/brand.json` file. No code changes needed.

## Run

```bash
# Plan + dry run (no key): writes the exact Comfy payloads and a review sheet
python3 -m content_engine content_engine/brands/offline/campaigns/switch_off_q4.json

# Comfy Cloud (paid plan; key from https://platform.comfy.org/profile/api-keys)
COMFY_API_KEY=comfyui-... python3 -m content_engine <campaign.json> --backend comfy --limit 3

# Local ComfyUI
python3 -m content_engine <campaign.json> --backend comfy --base-url http://127.0.0.1:8188

# Tests (includes an end-to-end run against a mock Comfy Cloud server)
python3 -m unittest discover -s content_engine/tests -t .
```

## Where Comfy Agent fits

Comfy Agent (launched Oct 1 2026) runs inside the ComfyUI canvas on Comfy Cloud. It has no public API, so the engine can't call it directly. Use it as the **workflow designer**:

1. In Comfy Cloud, ask Comfy Agent to build the brand's look (model choice, LoRA, upscaler, product compositing, etc.).
2. Mark the inputs with placeholders: `{{prompt}}`, `{{negative_prompt}}`, `{{width}}`, `{{height}}`, `{{seed}}`, `{{filename_prefix}}`.
3. Export it as API-format JSON into `workflows/`, then pass `--workflow workflows/<file>.json`.

The engine then runs that graph across the whole campaign matrix through the Cloud API.
`mcp.comfy-cloud.json` connects Claude Code (or any MCP client) to Comfy Cloud MCP (`https://cloud.comfy.org/mcp`), for agent-in-the-loop exploration such as searching templates and models or running one-offs.

## Notes
- `workflows/sdxl_txt2img.api.json` is a baseline SDXL graph. Check that the checkpoint name exists in your Comfy Cloud model library, or swap in an Agent-built workflow.
- The claims check is a phrase blocklist based on EU 1223/2009 + 655/2013 (no medicinal or "chemical-free" claims) and the 2024/825 ban on generic green claims. It does not replace a regulatory review.
- **The Offline profile is a draft.** The brand could not be verified online, so its products, palette and positioning are placeholders to replace with real brand guidelines.
