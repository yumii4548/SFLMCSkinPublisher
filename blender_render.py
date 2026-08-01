# -*- coding: utf-8 -*-
"""Blender 渲染调度：以 headless 方式启动 Blender，调用 render_script.py 完成渲染。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import config


def render_skin(arm: str, skin_image_path: str | Path,
                output_path: str | Path | None = None) -> Path:
    """用预设模型渲染皮肤。

    Args:
        arm: "thick"（粗手臂/Steve）或 "thin"（细手臂/Alex）
        skin_image_path: 皮肤展开图 PNG 路径
        output_path: 渲染输出路径；None 则输出到 ./output/render.png
    Returns:
        渲染图片路径
    """
    if arm not in config.MODEL_FILES:
        raise ValueError(f"未知手臂类型: {arm}（应为 thick/thin）")

    blend_path = config.BLENDER_MODELS_DIR / config.MODEL_FILES[arm]
    if not blend_path.exists():
        raise FileNotFoundError(f"预设模型不存在: {blend_path}")

    skin_image_path = Path(skin_image_path)
    if output_path is None:
        output_path = Path("output") / f"render_{arm}.png"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    script_path = Path(__file__).parent / "render_script.py"

    res_arg = ""
    if config.RENDER_RESOLUTION:
        w, h = config.RENDER_RESOLUTION
        res_arg = f"{w}x{h}"

    cmd = [
        config.BLENDER_EXE,
        "--background",
        str(blend_path),
        "--python", str(script_path),
        "--",
        "--skin", str(skin_image_path),
        "--out", str(output_path),
        "--samples", str(config.RENDER_SAMPLES),
    ]
    if res_arg:
        cmd += ["--res", res_arg]

    print(f"[blender_render] 启动 Blender: {config.BLENDER_EXE}")
    print(f"[blender_render] 模型: {blend_path.name}  皮肤: {skin_image_path.name}")
    print(f"[blender_render] 输出: {output_path}")

    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Blender 渲染失败，退出码 {result.returncode}")

    if not output_path.exists():
        raise RuntimeError(f"渲染完成但未找到输出文件: {output_path}")

    print(f"[blender_render] 渲染成功: {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python blender_render.py <thick|thin> <skin.png> [output.png]")
        sys.exit(1)
    arm_type = sys.argv[1]
    skin = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else None
    render_skin(arm_type, skin, out)
