"""Мелкие общие помощники для JSON-совместимого вывода."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def pct(part: float, total: float) -> float | None:
    return round(100.0 * part / total, 1) if total else None


def clean(v: Any) -> Any:
    if v is None or v is pd.NA or (isinstance(v, float) and np.isnan(v)):
        return None
    return v.item() if hasattr(v, "item") else v


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame -> список словарей без NaN/numpy-типов."""
    return [{k: clean(v) for k, v in row.items()} for row in df.to_dict(orient="records")]
