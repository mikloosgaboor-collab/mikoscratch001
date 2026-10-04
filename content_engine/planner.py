"""Turns a brand profile + campaign brief into a matrix of creative specs.

Matrix = products x audiences (filtered by affinity) x formats x variants.
Prompts are composed from brand-level style, audience scene and product visual,
so every client gets on-brand output without hand-writing prompts.
"""
from __future__ import annotations

import re

from .models import Brand, Campaign, CreativeSpec


def _aspect_hint(width: int, height: int) -> str:
    r = width / height
    if r < 0.7:
        return "vertical composition, subject in upper two thirds, clean space at bottom for text"
    if r > 1.4:
        return "wide composition, subject on one side, clean negative space on the other for text"
    return "balanced composition with clean negative space for a headline"


def build_prompt(brand: Brand, campaign: Campaign, product_id: str, audience_id: str,
                 width: int, height: int) -> str:
    p = brand.product(product_id)
    a = brand.audience(audience_id)
    palette = ", ".join(f"{k} {v}" for k, v in brand.palette.items())
    return " ".join([
        f"Advertising photograph for {brand.name} hair care, campaign theme: {campaign.theme}.",
        f"Scene: {a.scene}.",
        f"Product in frame: {p.visual}, label facing camera, sharp and legible.",
        f"Art direction: {brand.visual_style}. Colour palette: {palette}.",
        _aspect_hint(width, height) + ".",
        "No text, no typography, no watermark in the image.",
    ])


def check_compliance(text: str, brand: Brand) -> list[str]:
    """Flags banned claims (case-insensitive whole-phrase match)."""
    issues = []
    for phrase in brand.banned_claims:
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.IGNORECASE):
            issues.append(f"banned claim: '{phrase}'")
    return issues


def plan(brand: Brand, campaign: Campaign) -> list[CreativeSpec]:
    specs: list[CreativeSpec] = []
    for aid in campaign.audiences:
        audience = brand.audience(aid)
        products = [pid for pid in campaign.products
                    if not audience.product_affinity or pid in audience.product_affinity]
        for pid in products:
            product = brand.product(pid)
            for fmt in campaign.formats:
                for v in range(campaign.variants):
                    copy = {}
                    issues: list[str] = []
                    for loc in campaign.locales:
                        hooks = audience.hooks[loc]
                        c = {
                            "headline": hooks[v % len(hooks)],
                            "body": product.benefit[loc],
                            "cta": brand.cta[loc],
                            "disclaimer": brand.disclaimers.get(loc, ""),
                        }
                        copy[loc] = c
                        issues += [f"[{loc}] {i}" for i in
                                   check_compliance(" ".join(c.values()), brand)]
                    # Stable seed per cell so reruns reproduce the same image.
                    seed = campaign.seed + len(specs)
                    specs.append(CreativeSpec(
                        id=f"{campaign.id}__{aid}__{pid}__{fmt.id}__v{v + 1}",
                        campaign=campaign.id, product=pid, audience=aid, format=fmt,
                        variant=v + 1, seed=seed,
                        prompt=build_prompt(brand, campaign, pid, aid, fmt.width, fmt.height),
                        negative_prompt=brand.negative_prompt,
                        copy=copy, compliance=issues,
                    ))
    return specs
