"""生成界面用的小图标（PNG，Tk 8.6 原生支持）。

输出到 icons/：
  gear_light.png / gear_dark.png   设置按钮
  moon_light.png / sun_dark.png    主题切换按钮
  logo.png                         顶栏品牌标志

用法：python make_icons.py
"""

from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "icons")
RENDER = 160
SIZE = 20

GEAR_LIGHT = "#4a5670"
GEAR_DARK = "#b9c2e6"
MOON = "#4a5670"
SUN = "#f2b23e"


def _polar(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    return (cx + radius * math.cos(angle), cy + radius * math.sin(angle))


def _gear(color: str, teeth: int = 8) -> Image.Image:
    img = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = RENDER / 2
    r_out, r_in, hole = RENDER * 0.44, RENDER * 0.33, RENDER * 0.14

    sector = 2 * math.pi / teeth
    points = []
    for i in range(teeth):
        base = i * sector - math.pi / 2
        points.append(_polar(cx, cy, r_in, base + 0.00 * sector))
        points.append(_polar(cx, cy, r_out, base + 0.16 * sector))
        points.append(_polar(cx, cy, r_out, base + 0.58 * sector))
        points.append(_polar(cx, cy, r_in, base + 0.74 * sector))
        points.append(_polar(cx, cy, r_in, base + 0.87 * sector))

    draw.polygon(points, fill=color)
    draw.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=(0, 0, 0, 0))
    return img


def _moon(color: str) -> Image.Image:
    img = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([RENDER * 0.08, RENDER * 0.08, RENDER * 0.92, RENDER * 0.92], fill=color)
    cx, cy, r = RENDER * 0.70, RENDER * 0.36, RENDER * 0.42
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 0))
    return img


def _sun(color: str) -> Image.Image:
    img = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = RENDER / 2
    core = RENDER * 0.26
    draw.ellipse([cx - core, cy - core, cx + core, cy + core], fill=color)

    width = int(RENDER * 0.09)
    inner, outer = RENDER * 0.36, RENDER * 0.47
    for i in range(8):
        angle = i * math.pi / 4
        draw.line(
            [_polar(cx, cy, inner, angle), _polar(cx, cy, outer, angle)],
            fill=color, width=width,
        )
    return img


def _shrink(img: Image.Image, size: int = SIZE) -> Image.Image:
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    targets = {
        "gear_light.png": _gear(GEAR_LIGHT),
        "gear_dark.png": _gear(GEAR_DARK),
        "moon_light.png": _moon(MOON),
        "sun_dark.png": _sun(SUN),
    }
    for name, image in targets.items():
        path = os.path.join(OUT_DIR, name)
        _shrink(image).save(path)
        print("已生成:", path)

    from make_icon import build as build_logo

    logo = build_logo().resize((44, 44), Image.LANCZOS)
    logo_path = os.path.join(OUT_DIR, "logo.png")
    logo.save(logo_path)
    print("已生成:", logo_path)


if __name__ == "__main__":
    main()
