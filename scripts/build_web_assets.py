"""Build deterministic Basafe PWA icons and install the approved OG image."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SOURCE_OG = Path(
    r"C:\Users\Windows 11\.codex\generated_images\019fce08-851d-7cc0-a432-734ebbc4e36c\exec-ce911bd4-8ccd-453b-8e30-b4b0e977862e.png"
)
SOURCE_LOGO = WEB / "icons" / "basafe-logo.png"


def icon(size: int, *, maskable: bool = False) -> Image.Image:
    logo = Image.open(SOURCE_LOGO).convert("RGBA")
    canvas = Image.new("RGBA", (size, size), "#f7faf8" if maskable else (0, 0, 0, 0))
    maximum = round(size * (.64 if maskable else .9))
    logo.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
    canvas.alpha_composite(logo, ((size - logo.width) // 2, (size - logo.height) // 2))
    return canvas


def main() -> None:
    icons = WEB / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    if not SOURCE_OG.is_file():
        raise FileNotFoundError(f"Approved social image is missing: {SOURCE_OG}")
    if not SOURCE_LOGO.is_file():
        raise FileNotFoundError(f"Approved Basafe logo is missing: {SOURCE_LOGO}")
    shutil.copy2(SOURCE_OG, WEB / "og.png")
    icon(256).save(icons / "basafe-logo-256.png", optimize=True)
    icon(192).save(icons / "icon-192.png", optimize=True)
    icon(512).save(icons / "icon-512.png", optimize=True)
    icon(512, maskable=True).save(icons / "icon-maskable-512.png", optimize=True)


if __name__ == "__main__":
    main()
