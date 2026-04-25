"""Small helpers for optional asset-backed skin pieces."""
from __future__ import annotations

from pathlib import Path


SKIN_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SKIN_DIR / "assets"


def skin_asset(*parts: str) -> Path:
    return ASSETS_DIR.joinpath(*parts)


def optional_border_image(
    asset: Path,
    margins: tuple[int, int, int, int],
    *,
    fallback: str,
) -> str:
    """Return border-image QSS when an asset exists, otherwise a fallback block."""
    if not asset.exists():
        return fallback
    top, right, bottom, left = margins
    return (
        f"border-image: url({asset.as_posix()}) "
        f"{top} {right} {bottom} {left} stretch stretch;"
        "background: transparent;"
        "border: 0;"
    )

