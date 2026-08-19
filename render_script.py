# -*- coding: utf-8 -*-
"""Blender 内部脚本：在 Blender 进程里运行，负责替换皮肤贴图并渲染。

核心策略：
  1. 加载用户皮肤（128×128 / 64×64 / 64×32 等任意 MC 格式）
  2. 遍历所有材质的 Image Texture 节点
  3. 对每个候选纹理：
     - 同尺寸：直接像素级覆盖
     - 用户皮肤更大（如 128→64）：**创建同尺寸新 Image datablock，替换节点引用**
       → 不丢失用户皮肤质量，材质/节点链保持不变
     - 用户皮肤更小：缩放后覆盖
  4. 保留原 .blend 不动（所有修改仅在本次渲染生效）
"""
import sys
import os
import argparse


def _parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--skin", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--res", default=None)
    return p.parse_args(argv)


def _copy_pixels(src_pixels, src_channels, dst_img):
    """把 src_pixels 拷贝到 dst_img.pixels。"""
    dst_channels = dst_img.channels
    dst_w, dst_h = dst_img.size
    total = dst_w * dst_h
    dst_buf = list(dst_img.pixels[:])
    for i in range(total):
        si = i * src_channels
        di = i * dst_channels
        if src_channels == 4 and dst_channels == 4:
            dst_buf[di:di + 4] = src_pixels[si:si + 4]
        elif src_channels == 4 and dst_channels == 3:
            dst_buf[di:di + 3] = src_pixels[si:si + 3]
        elif src_channels == 3 and dst_channels == 4:
            dst_buf[di:di + 3] = src_pixels[si:si + 3]
            dst_buf[di + 3] = 1.0
        elif src_channels == dst_channels:
            dst_buf[di:di + dst_channels] = src_pixels[si:si + src_channels]
        else:
            min_ch = min(src_channels, dst_channels)
            for c in range(min_ch):
                dst_buf[di + c] = src_pixels[si + c]
            if dst_channels > min_ch:
                dst_buf[di + min_ch] = 1.0
    dst_img.pixels = dst_buf
    dst_img.update()


def _resize_pixels(src_pixels, src_ch, src_w, src_h, dst_w, dst_h):
    """纯 Python 像素缩放（最近邻）。返回 (flat_list, channels)。"""
    ch = src_ch
    dst_buf = [0.0] * (dst_w * dst_h * ch)
    for dy in range(dst_h):
        for dx in range(dst_w):
            sx = int(dx * src_w / dst_w)
            sy = int(dy * src_h / dst_h)
            si = (sy * src_w + sx) * ch
            di = (dy * dst_w + dx) * ch
            for c in range(ch):
                dst_buf[di + c] = src_pixels[si + c]
    return dst_buf


def _apply_skin_to_node(skin_img, skin_ch, node,
                        replaced_imgs, replaced_mats):
    """把皮肤应用到一个 Image Texture 节点。

    策略：
      - 同尺寸 → 直接像素覆盖
      - 皮肤更大 → 创建新的大尺寸 Image datablock，替换节点引用
      - 皮肤更小 → 缩放后像素覆盖
    """
    import bpy
    old_img = node.image
    if old_img is None:
        return
    dst_w, dst_h = old_img.size
    src_w, src_h = skin_img.size

    # 跳过 Viewer Node
    if old_img.name == "Viewer Node":
        return

    if (dst_w, dst_h) == (src_w, src_h):
        # ---- 同尺寸：直接像素覆盖 ----
        src_pixels = list(skin_img.pixels[:])
        _copy_pixels(src_pixels, skin_ch, old_img)
        replaced_imgs.add(old_img.name)
        mat = getattr(node, "id_data", None)
        if mat:
            replaced_mats.add(mat.name)
        return

    if src_w >= dst_w and src_h >= dst_h:
        # ---- 皮肤更大：升级 Image datablock ----
        # 创建新的 Image datablock，尺寸 = 用户皮肤尺寸
        new_name = old_img.name + "_hd"
        new_img = bpy.data.images.new(new_name, width=src_w, height=src_h)
        # 拷贝用户皮肤像素
        src_pixels = list(skin_img.pixels[:])
        new_buf = [0.0] * (src_w * src_h * skin_ch)
        total = src_w * src_h
        for i in range(total):
            si = i * skin_ch
            di = i * skin_ch  # 同通道数直接拷贝
            for c in range(skin_ch):
                new_buf[di + c] = src_pixels[si + c]
        new_img.pixels = new_buf
        new_img.update()

        # 替换节点引用
        node.image = new_img
        # 如果其他节点也引用旧图，一并替换
        for m in bpy.data.materials:
            if not getattr(m, "use_nodes", False) or m.node_tree is None:
                continue
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image is old_img:
                    n.image = new_img

        replaced_imgs.add(new_name)
        replaced_imgs.add(old_img.name)
        mat = getattr(node, "id_data", None)
        if mat:
            replaced_mats.add(mat.name)
        return

    # ---- 皮肤更小：缩放后覆盖 ----
    src_pixels = list(skin_img.pixels[:])
    resized = _resize_pixels(src_pixels, skin_ch, src_w, src_h, dst_w, dst_h)
    _copy_pixels(resized, skin_ch, old_img)
    replaced_imgs.add(old_img.name)
    mat = getattr(node, "id_data", None)
    if mat:
        replaced_mats.add(mat.name)


def main():
    import bpy

    args = _parse_args()
    skin_path = os.path.abspath(args.skin)
    out_path = os.path.abspath(args.out)

    if not os.path.exists(skin_path):
        raise FileNotFoundError(f"皮肤展开图不存在: {skin_path}")

    # ---- 1. 加载用户皮肤 ----
    skin_img = bpy.data.images.load(skin_path, check_existing=False)
    skin_size = (skin_img.size[0], skin_img.size[1])
    skin_ch = skin_img.channels
    print(f"[render_script] 皮肤尺寸: {skin_size}  通道: {skin_ch}")

    replaced_mats = set()
    replaced_imgs = set()

    # ---- 2. 遍历所有材质的 Image Texture 节点 ----
    mc_skin_sizes = {(64, 64), (64, 32), (128, 128), (128, 64), (256, 256)}

    for mat in bpy.data.materials:
        if not getattr(mat, "use_nodes", False) or mat.node_tree is None:
            continue
        for node in mat.node_tree.nodes:
            if node.type != "TEX_IMAGE" or node.image is None:
                continue
            img = node.image
            if img.name == "Viewer Node":
                print(f"[render_script] 跳过 Viewer Node")
                continue
            # 只处理 MC 皮肤尺寸的纹理
            if (img.size[0], img.size[1]) in mc_skin_sizes:
                try:
                    _apply_skin_to_node(skin_img, skin_ch, node,
                                        replaced_imgs, replaced_mats)
                except Exception as e:
                    print(f"[render_script] 跳过 {img.name}: {e}")

    # ---- 3. 兜底：bpy.data.images 里同尺寸的 ----
    for img in bpy.data.images:
        if img.name in replaced_imgs:
            continue
        if img.name == "Viewer Node":
            continue
        if (img.size[0], img.size[1]) in mc_skin_sizes:
            # 尝试覆盖（如果没被节点引用，直接覆盖像素）
            if (img.size[0], img.size[1]) == skin_size:
                src_pixels = list(skin_img.pixels[:])
                _copy_pixels(src_pixels, skin_ch, img)
                replaced_imgs.add(img.name)
            elif skin_size[0] >= img.size[0] and skin_size[1] >= img.size[1]:
                # 皮肤更大：创建新 Image 并替换所有引用
                new_name = img.name + "_hd"
                new_img = bpy.data.images.new(new_name, width=skin_size[0], height=skin_size[1])
                src_pixels = list(skin_img.pixels[:])
                new_buf = [0.0] * (skin_size[0] * skin_size[1] * skin_ch)
                for i in range(skin_size[0] * skin_size[1]):
                    si = i * skin_ch
                    di = i * skin_ch
                    for c in range(skin_ch):
                        new_buf[di + c] = src_pixels[si + c]
                new_img.pixels = new_buf
                new_img.update()
                # 替换引用
                for m in bpy.data.materials:
                    if not getattr(m, "use_nodes", False) or m.node_tree is None:
                        continue
                    for n in m.node_tree.nodes:
                        if n.type == "TEX_IMAGE" and n.image is img:
                            n.image = new_img
                replaced_imgs.add(new_name)

    print(f"[render_script] 已替换材质: {sorted(replaced_mats) or '(无)'}")
    print(f"[render_script] 已覆盖纹理: {sorted(replaced_imgs) or '(无)'}")

    if not replaced_imgs:
        print("[render_script] WARNING: 未找到任何可替换的皮肤纹理！")

    # ---- 4. 渲染 ----
    scn = bpy.context.scene
    if args.res:
        w, h = args.res.lower().split("x")
        scn.render.resolution_x = int(w)
        scn.render.resolution_y = int(h)
    scn.render.filepath = out_path
    scn.render.image_settings.file_format = "PNG"
    scn.render.image_settings.color_mode = "RGBA"
    if hasattr(scn, "cycles"):
        scn.cycles.samples = args.samples
        # 关闭降噪避免 OIDN 内存不足崩溃；用较高采样数补偿画质
        scn.cycles.use_denoising = False

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.render.render(write_still=True)
    print(f"[render_script] 渲染完成 -> {out_path}")

    try:
        bpy.data.images.remove(skin_img)
    except Exception:
        pass


if __name__ == "__main__":
    main()
