"""Build deterministic GeoSafe-FIS PWA icons and install the approved OG image."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SOURCE_OG = Path(
    r"C:\Users\Windows 11\.codex\generated_images\019fce08-851d-7cc0-a432-734ebbc4e36c\exec-ce911bd4-8ccd-453b-8e30-b4b0e977862e.png"
)


def icon(size: int, *, maskable: bool = False) -> Image.Image:
    scale = size / 512
    canvas = Image.new("RGB", (size, size), "#073b4c")
    draw = ImageDraw.Draw(canvas)
    margin = int((70 if maskable else 38) * scale)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=int(105 * scale),
        fill="#0b7a75",
        outline="#8de0d6",
        width=max(2, int(9 * scale)),
    )
    cx = size // 2
    top = int(118 * scale)
    radius = int(94 * scale)
    pin = [
        (cx, int(402 * scale)),
        (cx - int(124 * scale), int(262 * scale)),
        (cx - radius, top),
        (cx, int(76 * scale)),
        (cx + radius, top),
        (cx + int(124 * scale), int(262 * scale)),
    ]
    draw.polygon(pin, fill="#062f3d")
    draw.ellipse(
        (cx - int(106 * scale), int(90 * scale), cx + int(106 * scale), int(302 * scale)),
        fill="#f7faf8",
        outline="#8de0d6",
        width=max(2, int(8 * scale)),
    )
    colors = ["#277ea3", "#0b7a75", "#c58a2b"]
    for index, color in enumerate(colors):
        y = int((160 + index * 47) * scale)
        points = []
        for step in range(9):
            x = cx - int(70 * scale) + int(step * 17.5 * scale)
            offset = int((8 if step % 2 else -8) * scale)
            points.append((x, y + offset))
        draw.line(points, fill=color, width=max(3, int(12 * scale)), joint="curve")
    return canvas


def main() -> None:
    icons = WEB / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    if not SOURCE_OG.is_file():
        raise FileNotFoundError(f"Approved social image is missing: {SOURCE_OG}")
    shutil.copy2(SOURCE_OG, WEB / "og.png")
    icon(192).save(icons / "icon-192.png", optimize=True)
    icon(512).save(icons / "icon-512.png", optimize=True)
    icon(512, maskable=True).save(icons / "icon-maskable-512.png", optimize=True)


if __name__ == "__main__":
    main()
