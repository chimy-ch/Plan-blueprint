"""生成「蓝图 Blueprint」应用图标（blueprint.ico / blueprint.png）。

用法：python make_icon.py
依赖：Pillow
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 1024
MARGIN = 22
TOP = (56, 116, 255)      # 亮蓝
BOTTOM = (17, 52, 158)    # 深蓝
GREEN = (46, 170, 106)

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def build() -> Image.Image:
    canvas = Image.new("RGB", (SIZE, SIZE), BOTTOM)
    drawer = ImageDraw.Draw(canvas)
    for y in range(SIZE):
        ratio = y / (SIZE - 1)
        color = tuple(
            int(TOP[i] + (BOTTOM[i] - TOP[i]) * ratio) for i in range(3)
        )
        drawer.line([(0, y), (SIZE, y)], fill=color)

    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [MARGIN, MARGIN, SIZE - 1 - MARGIN, SIZE - 1 - MARGIN],
        radius=224,
        fill=255,
    )

    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    img.paste(canvas, (0, 0), mask)

    grid = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grid)
    step = 96
    for x in range(step, SIZE, step):
        gdraw.line([(x, 0), (x, SIZE)], fill=(255, 255, 255, 30), width=3)
    for y in range(step, SIZE, step):
        gdraw.line([(0, y), (SIZE, y)], fill=(255, 255, 255, 30), width=3)
    grid.putalpha(Image.composite(grid.getchannel("A"), Image.new("L", (SIZE, SIZE), 0), mask))
    img = Image.alpha_composite(img, grid)

    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    path = [(268, 706), (452, 520), (610, 616), (764, 352)]
    odraw.line(path, fill=(255, 255, 255, 245), width=44, joint="curve")
    for point in path[:3]:
        odraw.ellipse(
            [point[0] - 38, point[1] - 38, point[0] + 38, point[1] + 38],
            fill=(255, 255, 255, 255),
        )

    end = path[3]
    odraw.ellipse(
        [end[0] - 76, end[1] - 76, end[0] + 76, end[1] + 76], fill=GREEN + (255,)
    )
    odraw.line(
        [(end[0] - 38, end[1] + 2), (end[0] - 10, end[1] + 30), (end[0] + 40, end[1] - 26)],
        fill=(255, 255, 255, 255),
        width=20,
        joint="curve",
    )

    return Image.alpha_composite(img, overlay)


def main() -> None:
    icon = build()
    ico_path = os.path.join(HERE, "blueprint.ico")
    png_path = os.path.join(HERE, "blueprint.png")

    icon.resize((256, 256), Image.LANCZOS).save(png_path)
    icon.save(ico_path, format="ICO", sizes=ICO_SIZES)
    print("已生成:", ico_path)
    print("已生成:", png_path)


if __name__ == "__main__":
    main()
