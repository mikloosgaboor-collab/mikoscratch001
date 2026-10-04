"""Writes manifest.json and a self-contained HTML review sheet for a run."""
from __future__ import annotations

import html
import json
from dataclasses import asdict
from pathlib import Path

from .models import Brand, Campaign, CreativeSpec


def write_manifest(specs: list[CreativeSpec], out_dir: Path, meta: dict) -> Path:
    path = out_dir / "manifest.json"
    path.write_text(json.dumps({**meta, "creatives": [asdict(s) for s in specs]},
                               indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_review_sheet(brand: Brand, campaign: Campaign, specs: list[CreativeSpec],
                       out_dir: Path, locale: str) -> Path:
    e = html.escape
    accent = brand.palette.get("accent", "#222")
    cards = []
    for s in specs:
        c = s.copy[locale]
        img = s.assets[0] if s.assets else ""
        flags = "".join(f'<li>{e(i)}</li>' for i in s.compliance)
        cards.append(f"""
<figure class="card">
  <div class="ad" style="aspect-ratio:{s.format.width}/{s.format.height}">
    <img src="{e(img)}" alt="{e(s.id)}">
    <div class="copy">
      <h2>{e(c['headline'])}</h2>
      <p>{e(c['body'])}</p>
      <span class="cta">{e(c['cta'])}</span>
      {f'<small>{e(c["disclaimer"])}</small>' if c['disclaimer'] else ''}
    </div>
  </div>
  <figcaption>
    <b>{e(brand.audience(s.audience).label)}</b> · {e(brand.product(s.product).name)}
    · {e(s.format.placement)} · v{s.variant}
    {f'<ul class="flags">{flags}</ul>' if flags else '<span class="ok">compliance ✓</span>'}
    <details><summary>prompt</summary><p>{e(s.prompt)}</p></details>
  </figcaption>
</figure>""")
    page = f"""<!doctype html>
<html lang="{e(locale)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(brand.name)} · {e(campaign.id)} · {e(locale)}</title>
<style>
:root{{--accent:{accent};--bg:#f6f4f0;--fg:#1d1b18;--muted:#6b6560;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151412;--fg:#eee9e2;--muted:#a39d95;--card:#1f1d1a}}}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
header{{max-width:1200px;margin:0 auto 24px}} header p{{color:var(--muted);margin:4px 0}}
.grid{{max-width:1200px;margin:0 auto;display:grid;gap:20px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}}
.card{{margin:0;background:var(--card);border-radius:12px;overflow:hidden;box-shadow:0 1px 3px #0002}}
.ad{{position:relative;width:100%;overflow:hidden;background:#ddd}}
.ad img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
.copy{{position:absolute;left:0;right:0;bottom:0;padding:16px;color:#fff;
  background:linear-gradient(transparent,#000a 45%)}}
.copy h2{{margin:0 0 4px;font-size:1.15rem;line-height:1.2}} .copy p{{margin:0 0 8px;font-size:.85rem}}
.cta{{display:inline-block;background:var(--accent);color:#fff;padding:4px 12px;border-radius:999px;font-size:.8rem;font-weight:600}}
.copy small{{display:block;margin-top:6px;font-size:.65rem;opacity:.8}}
figcaption{{padding:12px 14px;font-size:.8rem;color:var(--muted)}} figcaption b{{color:var(--fg)}}
.flags{{color:#c0392b;margin:6px 0;padding-left:18px}} .ok{{display:block;color:#2e8b57;margin-top:4px}}
details p{{font-size:.75rem}}
</style></head><body>
<header><h1>{e(brand.name)} — {e(campaign.theme)}</h1>
<p>{e(campaign.objective)}</p>
<p>{len(specs)} creatives · locale {e(locale)} · campaign <code>{e(campaign.id)}</code></p></header>
<main class="grid">{''.join(cards)}</main>
</body></html>"""
    path = out_dir / f"review_{locale}.html"
    path.write_text(page, encoding="utf-8")
    return path
