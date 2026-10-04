"""Data model for the content engine: brand profiles, campaign briefs and creative specs."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Product:
    id: str
    name: str
    benefit: dict[str, str]          # locale -> one-line benefit
    visual: str                      # how the product should look in-frame
    tags: list[str] = field(default_factory=list)


@dataclass
class Audience:
    id: str
    label: str
    insight: str                     # the tension/need the creative speaks to
    scene: str                       # setting + casting direction for imagery
    hooks: dict[str, list[str]]      # locale -> headline options
    product_affinity: list[str] = field(default_factory=list)  # product ids; empty = all


@dataclass
class Brand:
    id: str
    name: str
    locales: list[str]
    voice: str
    palette: dict[str, str]
    visual_style: str
    negative_prompt: str
    cta: dict[str, str]
    banned_claims: list[str]
    disclaimers: dict[str, str]
    products: list[Product]
    audiences: list[Audience]

    @classmethod
    def load(cls, path: str | Path) -> "Brand":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["products"] = [Product(**p) for p in data["products"]]
        data["audiences"] = [Audience(**a) for a in data["audiences"]]
        data.pop("_sources", None)
        data.pop("_notes", None)
        return cls(**data)

    def product(self, pid: str) -> Product:
        return next(p for p in self.products if p.id == pid)

    def audience(self, aid: str) -> Audience:
        return next(a for a in self.audiences if a.id == aid)


@dataclass
class Format:
    id: str          # e.g. "ig_feed"
    width: int
    height: int
    placement: str   # human label, e.g. "Instagram feed 4:5"


@dataclass
class Campaign:
    id: str
    brand: str
    objective: str
    theme: str
    products: list[str]
    audiences: list[str]
    formats: list[Format]
    locales: list[str]
    variants: int = 1
    seed: int = 1

    @classmethod
    def load(cls, path: str | Path) -> "Campaign":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["formats"] = [Format(**f) for f in data["formats"]]
        return cls(**data)


@dataclass
class CreativeSpec:
    """One renderable unit: an image prompt plus localized copy for a placement."""
    id: str
    campaign: str
    product: str
    audience: str
    format: Format
    variant: int
    seed: int
    prompt: str
    negative_prompt: str
    copy: dict[str, dict[str, str]]          # locale -> {headline, body, cta, disclaimer}
    compliance: list[str] = field(default_factory=list)  # issues; empty = clean
    assets: list[str] = field(default_factory=list)      # rendered file paths
    backend_job: dict = field(default_factory=dict)      # backend ids / payload refs
