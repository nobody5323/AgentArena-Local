from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentsVariant:
    name: str
    path: Path
    agents_md: Path


def load_variants(variants_dir: Path) -> list[AgentsVariant]:
    variants: list[AgentsVariant] = []
    for child in sorted(variants_dir.iterdir()):
        if not child.is_dir():
            continue
        agents_md = child / "AGENTS.md"
        if agents_md.exists():
            variants.append(AgentsVariant(name=child.name, path=child, agents_md=agents_md))
    return variants
