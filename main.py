# -*- coding: utf-8 -*-
"""MC 皮肤自动上架工具 —— 主入口

程序作者：极鱼社 SwiftFishLab

极鱼社 (SwiftFishLab) 创立于 2021 年，起源于《我的世界》中国版。
截至 2024 年，国服组件累计下载量突破 1100 万，订阅人数 20 万+，
上架组件超 500 款，2022-2023 年度长期稳居平台百强。
目前团队也在拓展国际版内容，入驻了爱发电、闲鱼、小红书等平台。
同时承接皮肤定制、我的世界中国版免费代投、建筑承包、存档互通等多项服务。

资源定制、技术咨询、交流反馈欢迎加入 QQ 群：914029611

流程：
  1. 解压用户上传的 zip（含 info.txt + 皮肤 PNG）
  2. 根据手臂类型调用预设 Blender 模型渲染
  3. 裁剪为人物居中的 1:1 图片 + 叠加半透明 logo
  4. 自动登录 mcdev 并发布新资源（双端）

用法：
  # 完整流程（用默认账号发布）
  python main.py <压缩包.zip>

  # 指定账号发布（多账号切换）
  python main.py <压缩包.zip> --account myaccount

  # 指定手臂类型（覆盖 info.txt）
  python main.py <压缩包.zip> --arm thick

  # 只渲染不上架
  python main.py <压缩包.zip> --skip-publish

  # 跳过渲染，用已有图片上架
  python main.py <压缩包.zip> --skip-render --image <最终图.png>

  # 账号管理
  python main.py --list-accounts
  python main.py --add-account <账号名>

  # 校准网页选择器
  python main.py --inspect [--account <账号名>]

首次运行发布时，会打开浏览器要求手动登录；登录态按账号隔离保存，
之后自动复用。选择器如有偏差，用 --inspect 校准后回填 config.py。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import config
from parser import parse_zip, SkinPackage
import blender_render
import image_post


def build_description(pkg: SkinPackage) -> str:
    """根据模板构建简介文本。"""
    # 定价转可读文本：diamond→"300钻石"，emerald→"20绿宝石"，free→"免费"
    if pkg.price_type == "diamond":
        price_text = f"{pkg.price_value}钻石"
    elif pkg.price_type == "emerald":
        price_text = f"{pkg.price_value}绿宝石"
    elif pkg.price_type == "free":
        price_text = "免费"
    else:
        price_text = pkg.price
    return config.DESCRIPTION_TEMPLATE.format(
        name=pkg.name,
        author=pkg.author,
        price=price_text,
    )


def run_pipeline(zip_path: str, account: str, arm_override: str | None = None,
                 skip_render: bool = False, skip_publish: bool = False,
                 existing_image: str | None = None, headless_publish: bool = False):
    print("=" * 60)
    print("MC 皮肤自动上架工具")
    print("程序作者：极鱼社 SwiftFishLab")
    print("©2026 SwiftFishLab All Right Reserved")
    print("-" * 60)
    print("极鱼社 (SwiftFishLab) 创立于 2021 年，起源于《我的世界》中国版")
    print("截至 2024 年，国服组件累计下载量突破 1100 万，订阅 20 万+")
    print("上架组件超 500 款，2022-2023 年度长期稳居平台百强")
    print("资源定制、技术咨询、交流反馈 QQ 群：914029611")
    print("=" * 60)

    # ---- 1. 解析压缩包 ----
    print("\n[1/4] 解析压缩包...")
    pkg: SkinPackage = parse_zip(zip_path)
    arm = arm_override or pkg.arm
    print(f"  资源名称: {pkg.name}")
    print(f"  作者    : {pkg.author}")
    print(f"  定价    : {pkg.price} ({pkg.price_type}={pkg.price_value})")
    print(f"  简介    : {pkg.description[:40]}{'...' if len(pkg.description) > 40 else ''}")
    print(f"  手臂类型: {arm} ({'粗手臂/Steve' if arm == 'thick' else '细手臂/Alex'})")
    print(f"  皮肤图  : {pkg.skin_image_path}")
    print(f"  发布账号: {account}")

    # ---- 2. Blender 渲染 ----
    if skip_render and existing_image:
        final_image = Path(existing_image)
        print(f"\n[2/4] 跳过渲染，使用已有图片: {final_image}")
    else:
        print("\n[2/4] Blender 渲染...")
        render_path = blender_render.render_skin(arm, pkg.skin_image_path)
        print(f"  渲染图: {render_path}")

        # ---- 3. 图片后处理 ----
        print("\n[3/4] 图片后处理（裁剪 1:1 + logo）...")
        final_image = image_post.process_image(render_path)
        print(f"  最终图: {final_image}")

    if skip_publish:
        print("\n[4/4] 已跳过网页发布（--skip-publish）。")
        print(f"\n完成。最终图片: {final_image}")
        return final_image

    # ---- 4. 网页发布 ----
    print(f"\n[4/4] 发布到 mcdev（账号: {account}）...")

    # 长简介只放纯文本；真正的"渲染图 + 宣传图"按用户指定在 PE/PC详情 Quill 编辑器内
    # 先点 image button 传渲染图，再点一次传宣传图（通过 filechooser / 隐藏 input 插入）
    text_only = build_description(pkg)
    description = text_only
    print(f"  简介预览:\n  {description}")

    print(f"  皮肤源文件: {pkg.skin_image_path}")
    print(f"  渲染最终图: {final_image}")
    promo_path = str(config.PROMO_IMAGE_PATH) if config.PROMO_IMAGE_PATH.exists() else None
    if promo_path:
        print(f"  宣传图: {promo_path}")
    else:
        print(f"  宣传图不存在: {config.PROMO_IMAGE_PATH}（仍传渲染图占位）")

    from publisher import McdevPublisher
    pub = McdevPublisher(account=account, headless=headless_publish)
    pub.__enter__()
    try:
        ok = pub.publish(
            name=pkg.name,
            price_type=pkg.price_type,
            price_value=pkg.price_value,
            description=description,          # 纯文本（Quill 内先填文本）
            arm_type=pkg.arm,
            source_skin_png=str(pkg.skin_image_path),
            final_image=str(final_image),     # 1) PE/PC详情编辑器内插图第1张；2) 上传区#2..N 也全传它
            promo_image=promo_path,           # PE/PC详情编辑器内插图第2张（宣传图）
        )
    except Exception as e:
        print(f"\n发布异常: {e}")
        ok = False

    if ok:
        print("\n✓ 发布成功！浏览器保持打开，可手动检查。")
    else:
        print("\n✗ 发布未完成，浏览器保持打开，请检查。")
    print("[提示] 浏览器保持打开状态，关闭窗口或按 Ctrl+C 退出。")
    try:
        input()  # 等待用户按回车再关闭
    except (KeyboardInterrupt, EOFError):
        pass
    pub.__exit__(None, None, None)
    return final_image


def main():
    ap = argparse.ArgumentParser(
        description="MC 皮肤自动上架工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("zip", nargs="?", help="用户上传的压缩包路径")
    ap.add_argument("--arm", choices=["thick", "thin"], default=None,
                    help="手臂类型：thick=粗手臂(Steve) thin=细手臂(Alex)，覆盖 info.txt")
    ap.add_argument("--account", default=config.DEFAULT_ACCOUNT,
                    help=f"发布账号名（默认 {config.DEFAULT_ACCOUNT}），多账号切换用")
    ap.add_argument("--skip-render", action="store_true", help="跳过 Blender 渲染")
    ap.add_argument("--skip-publish", action="store_true", help="跳过网页发布")
    ap.add_argument("--image", help="配合 --skip-render 使用，指定已有最终图")
    ap.add_argument("--headless", action="store_true", help="无头模式发布（不推荐首次用）")
    ap.add_argument("--inspect", action="store_true", help="校准网页选择器模式")
    ap.add_argument("--list-accounts", action="store_true", help="列出所有已创建账号")
    ap.add_argument("--add-account", default=None, metavar="NAME",
                    help="创建/登录一个新账号（打开浏览器手动登录后保存）")
    args = ap.parse_args()

    # 账号管理
    if args.list_accounts:
        accounts = config.list_accounts()
        print("已创建的账号：")
        if not accounts:
            print("  （无，使用 --add-account <名称> 创建）")
        for a in accounts:
            tag = " (默认)" if a == config.DEFAULT_ACCOUNT else ""
            print(f"  - {a}{tag}")
        return

    if args.add_account:
        from publisher import add_account
        add_account(args.add_account, headless=args.headless)
        return

    if args.inspect:
        from publisher import inspect
        inspect(account=args.account)
        return

    if not args.zip:
        ap.print_help()
        sys.exit(1)

    if not Path(args.zip).exists():
        print(f"错误：压缩包不存在: {args.zip}")
        sys.exit(1)

    print(f"Blender 路径: {config.BLENDER_EXE}")
    print(f"预设模型目录: {config.BLENDER_MODELS_DIR}")
    print(f"发布账号    : {args.account}")

    run_pipeline(
        zip_path=args.zip,
        account=args.account,
        arm_override=args.arm,
        skip_render=args.skip_render,
        skip_publish=args.skip_publish,
        existing_image=args.image,
        headless_publish=args.headless,
    )


if __name__ == "__main__":
    main()
