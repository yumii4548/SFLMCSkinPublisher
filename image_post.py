# -*- coding: utf-8 -*-
"""图片后处理：
1. 读取 Blender 渲染图
2. 裁剪成人物居中的 1:1 正方形
3. 在中央叠加半透明 logo
4. 输出最终图片（保留原背景）

依赖 Pillow:  pip install pillow
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

import config


def _find_content_center(img: Image.Image) -> tuple[int, int, int, int, float, float]:
    """找人物中心（质心）+ bbox。

    返回 (left, top, right, bottom, cx, cy) —— cx/cy 是最大连通域的质心坐标（原图像素）。
    """
    ow, oh = img.size

    # 1) 下采样加速
    ds = 4
    small = img.resize((max(1, ow // ds), max(1, oh // ds)), Image.BILINEAR)
    w, h = small.size

    # 2) 采样背景色
    rgb = small.convert("RGB")
    px = rgb.load()
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1],
               px[0, h // 2], px[w - 1, h // 2],
               px[w // 2, 0], px[w // 2, h - 1]]
    bg_r = sum(c[0] for c in corners) / len(corners)
    bg_g = sum(c[1] for c in corners) / len(corners)
    bg_b = sum(c[2] for c in corners) / len(corners)
    threshold = 18.0

    # 3) 生成二值蒙版
    mask = Image.new("1", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            diff = ((r - bg_r) ** 2 + (g - bg_g) ** 2 + (b - bg_b) ** 2) ** 0.5
            if diff > threshold:
                mp[x, y] = 1

    # 4) 连通域 → 最大块的质心 + bbox
    mpx = mask.load()
    visited = bytearray(w * h)
    best_area = 0
    best_cx, best_cy = w / 2, h / 2
    best_bbox = (0, 0, w, h)

    for sy in range(h):
        for sx in range(w):
            if not mpx[sx, sy] or visited[sy * w + sx]:
                continue
            stack = [(sx, sy)]
            visited[sy * w + sx] = 1
            l, t, r, b = sx, sy, sx, sy
            area = 0
            sum_x, sum_y = 0.0, 0.0
            while stack:
                x, y = stack.pop()
                area += 1
                sum_x += x
                sum_y += y
                if x < l: l = x
                if x > r: r = x
                if y < t: t = y
                if y > b: b = y
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not visited[ny * w + nx] and mpx[nx, ny]:
                        visited[ny * w + nx] = 1
                        stack.append((nx, ny))
            if area > best_area:
                best_area = area
                best_cx = sum_x / area
                best_cy = sum_y / area
                best_bbox = (l, t, min(w, r + 1), min(h, b + 1))

    # 5) 还原到原图
    l, t, r, b = best_bbox
    l = l * ds
    t = t * ds
    r = min(r * ds, ow)
    b = min(b * ds, oh)
    cx = best_cx * ds
    cy = best_cy * ds

    if (r - l) < 10 or (b - t) < 10:
        return (0, 0, ow, oh, ow / 2, oh / 2)
    return (l, t, r, b, cx, cy)


def crop_centered_square(img: Image.Image, target: int) -> Image.Image:
    """裁剪成人物居中的 1:1 正方形。

    策略：最大连通域的 bbox 包含两个人物时，用 bbox 左偏位置（38%）作为主角中心。
    """
    w, h = img.size
    left, top, right, bottom, cx, cy = _find_content_center(img)

    content_w = right - left
    content_h = bottom - top

    # 两个人物整体居中：bbox 左偏 45%（右角色身体更宽，需要左移）
    cx = left + content_w * 0.6
    cy = top + content_h * 0.50

    side = max(content_w, content_h) * 1.08
    side = min(side, max(w, h))
    half = side / 2

    crop_left = int(max(0, cx - half))
    crop_right = int(min(w, cx + half))
    crop_top = int(max(0, cy - half))
    crop_bottom = int(min(h, cy + half))

    cw = crop_right - crop_left
    ch = crop_bottom - crop_top
    if cw != ch:
        s = min(cw, ch)
        if cw > s:
            offset = (cw - s) // 2
            crop_left += offset
            crop_right = crop_left + s
        else:
            crop_bottom = crop_top + s
            if crop_bottom > h:
                crop_bottom = h
                crop_top = h - s

    cropped = img.crop((crop_left, crop_top, crop_right, crop_bottom))
    return cropped.resize((target, target), Image.LANCZOS)


def add_logo(img: Image.Image, logo_path: str | Path,
             scale: float, opacity: float, top_margin: float) -> Image.Image:
    """在中央叠加半透明 logo。"""
    logo_path = Path(logo_path)
    if not logo_path.exists():
        raise FileNotFoundError(f"logo 不存在: {logo_path}")

    logo = Image.open(logo_path).convert("RGBA")
    base = img.convert("RGBA")

    new_w = max(1, int(base.width * scale))
    ratio = new_w / logo.width
    new_h = max(1, int(logo.height * ratio))
    logo = logo.resize((new_w, new_h), Image.LANCZOS)

    if opacity < 1.0:
        alpha = logo.getchannel("A").point(lambda p: int(p * opacity))
        logo.putalpha(alpha)

    # 正中央
    x = (base.width - new_w) // 2
    y = (base.height - new_h) // 2
    base.alpha_composite(logo, (x, y))
    return base


def process_image(render_path: str | Path,
                  output_path: str | Path | None = None) -> Path:
    """完整后处理：裁剪 1:1 + 加 logo，输出最终图片。"""
    render_path = Path(render_path)
    if output_path is None:
        output_path = render_path.parent / "final.png"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(render_path)
    print(f"[image_post] 原始渲染尺寸: {img.size}")

    square = crop_centered_square(img, config.OUTPUT_SIZE)
    print(f"[image_post] 裁剪为 1:1: {square.size}")

    final = add_logo(square, config.LOGO_PATH,
                     config.LOGO_SCALE, config.LOGO_OPACITY, config.LOGO_TOP_MARGIN)

    final.save(output_path, "PNG")
    print(f"[image_post] 最终图片: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python image_post.py <渲染图> [输出图]")
        sys.exit(1)
    process_image(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
