"""Загрузка конфигов анализа (пороги, оружие, модель ELO)."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).parent / "config"


@dataclass(frozen=True)
class WeaponSpec:
    key: str
    name: str
    category: str
    max_speed: float
    scoped_max_speed: float | None = None

    def speed_limit(self, scoped: bool) -> float:
        """Максимальная скорость с учётом прицела (у снайперок/AUG/SG в прицеле она ниже)."""
        if scoped and self.scoped_max_speed:
            return float(self.scoped_max_speed)
        return float(self.max_speed)


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


@lru_cache
def load_thresholds(path: str | None = None) -> dict[str, Any]:
    return _load_toml(Path(path) if path else CONFIG_DIR / "thresholds.toml")


@lru_cache
def load_weapons(path: str | None = None) -> dict[str, WeaponSpec]:
    raw = _load_toml(Path(path) if path else CONFIG_DIR / "weapons.toml")
    return {
        key: WeaponSpec(
            key=key,
            name=spec["name"],
            category=spec["category"],
            max_speed=float(spec["max_speed"]),
            scoped_max_speed=float(spec["scoped_max_speed"]) if "scoped_max_speed" in spec else None,
        )
        for key, spec in raw.items()
    }


def normalize_weapon(raw: str | None) -> str:
    """'weapon_ak47' -> 'ak47'."""
    if not raw:
        return ""
    raw = str(raw)
    return raw[len("weapon_"):] if raw.startswith("weapon_") else raw


@lru_cache
def load_elo_model(path: str | None = None) -> dict[str, Any]:
    with (Path(path) if path else CONFIG_DIR / "elo_model.json").open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def load_faceit_levels(path: str | None = None) -> dict[str, Any]:
    with (Path(path) if path else CONFIG_DIR / "faceit_levels.json").open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def load_messages(locale: str = "ru") -> dict[str, str]:
    with (CONFIG_DIR / "locales" / f"{locale}.json").open(encoding="utf-8") as f:
        return json.load(f)
