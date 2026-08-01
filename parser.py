# -*- coding: utf-8 -*-
"""压缩包解析：从用户上传的 zip 中提取皮肤 PNG 与元信息（TXT）。

压缩包结构约定（TXT 文件 + 皮肤 PNG）：
    my_skin.zip
    ├── info.txt      # 元信息
    └── skin.png      # 皮肤展开图（文件名随意，取 zip 内唯一的 png）

info.txt 支持两种写法（自动识别）：

  写法 A（推荐，key=value）——定价格式（三选一）：
      name=我的超酷皮肤
      author=作者名
      price_type=1        # 1=钻石  2=绿宝石  3=免费
      price_value=300     # 钻石/绿宝石时填数字，免费可省略此行
      desc=这是一个很棒的皮肤简介
      arm=粗

      或一行式定价写法（旧格式兼容）：
      price=300钻石 / price=1 300 / price=1,300

  写法 B（纯行式）：
      我的超酷皮肤
      作者名
      1                  # 第一行定价类型：1=钻石  2=绿宝石  3=免费
      300                # 钻石/绿宝石时第二行填数字，免费省略此行
      这是一个很棒的皮肤简介
      粗

      或旧格式一行定价兼容：
      300钻石 / 10绿宝石 / 免费

arm 字段可识别：粗/thick/steve  或  细/thin/alex
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path


ARM_KEYWORDS_THICK = {"粗", "thick", "steve", "粗手臂", "steve型"}
ARM_KEYWORDS_THIN = {"细", "thin", "alex", "细手臂", "alex型"}

# 定价类型关键字 -> 标准类型
PRICE_KEYWORDS = {
    "diamond": {"钻石", "diamond", "钻"},
    "emerald": {"绿宝石", "emerald", "绿"},
    "free": {"免费", "free", "0", "无"},
}


@dataclass
class SkinPackage:
    name: str            # 资源名称
    author: str          # 作者
    price: str           # 定价原文（如 "300钻石" / "10绿宝石" / "免费"）
    price_type: str      # 定价类型: "diamond" / "emerald" / "free"
    price_value: int     # 定价值（钻石/绿宝石数量，免费为 0）
    description: str     # 简介
    arm: str             # "thick" | "thin"
    skin_image_path: Path  # 解压后的皮肤展开图路径
    work_dir: Path       # 解压根目录（调用方负责清理）


def _parse_arm(raw: str) -> str:
    val = raw.strip().lower()
    if any(k in val for k in ARM_KEYWORDS_THICK):
        return "thick"
    if any(k in val for k in ARM_KEYWORDS_THIN):
        return "thin"
    raise ValueError(f"无法识别手臂类型: {raw!r}（应为 粗/细 或 thick/thin）")


def _parse_price(raw_type: str, raw_value: str | None = None) -> tuple[str, int]:
    """解析定价，返回 (price_type, price_value)。

    核心规则（最简单清晰版）：
      1 = 钻石   → 必须有一个 >0 的数字值（如 300）
      2 = 绿宝石 → 必须有一个 >0 的数字值（如 10）
      3 = 免费   → 不需要数字值

    兼容写法：
      一行式："300钻石" / "10绿宝石" / "免费"
      组合式：raw_type="1", raw_value="300"  或  raw_type="钻石", raw_value="300"
              raw_type="1 300"（空格分隔）  或  raw_type="1,300"（逗号分隔）
    """
    tp = (raw_type or "").strip()
    tp_lower = tp.lower()

    # ————————————————————————————————————
    # 第一步：先判断是否是 "类型 + 数值" 的组合写法（一行内空格/逗号分隔）
    # 例如："1 300" / "1,300" / "钻石 300"
    # ————————————————————————————————————
    if raw_value is None and (re.search(r"[\s,，]", tp)):
        parts = re.split(r"[\s,，]+", tp, maxsplit=1)
        if len(parts) == 2 and parts[1].strip():
            return _parse_price(parts[0].strip(), parts[1].strip())

    # ————————————————————————————————————
    # 第二步：主逻辑，判断类型
    # ————————————————————————————————————

    # —— 情况 1：类型是 1（钻石）——
    if tp == "1" or any(k in tp for k in PRICE_KEYWORDS["diamond"]) or tp_lower in ("diamond", "zs"):
        n = _extract_number(raw_value) if raw_value is not None else _extract_number(tp)
        if n <= 0:
            raise ValueError(f"钻石(1) 定价需要一个大于 0 的数字，当前值: {raw_value!r} / {tp!r}")
        return "diamond", n

    # —— 情况 2：类型是 2（绿宝石）——
    if tp == "2" or any(k in tp for k in PRICE_KEYWORDS["emerald"]) or tp_lower in ("emerald", "lbs"):
        n = _extract_number(raw_value) if raw_value is not None else _extract_number(tp)
        if n <= 0:
            raise ValueError(f"绿宝石(2) 定价需要一个大于 0 的数字，当前值: {raw_value!r} / {tp!r}")
        return "emerald", n

    # —— 情况 3：类型是 3（免费）——
    if tp == "3" or any(k in tp for k in PRICE_KEYWORDS["free"]) or tp_lower == "free":
        return "free", 0

    # —— 情况 4：纯数字，默认当作钻石 ——
    n = _extract_number(tp)
    if n > 0:
        return "diamond", n

    raise ValueError(
        f"无法识别定价: {tp!r}（请使用：1=钻石+数字, 2=绿宝石+数字, 3=免费；"
        f"或旧格式：300钻石 / 10绿宝石 / 免费）"
    )


def _extract_number(s: str) -> int:
    """从字符串中提取第一个纯数字，找不到返回 0。"""
    if s is None:
        return 0
    m = re.search(r"(\d+)", str(s))
    return int(m.group(1)) if m else 0


def _looks_like_arm(s: str) -> bool:
    val = s.strip().lower()
    return any(k in val for k in ARM_KEYWORDS_THICK | ARM_KEYWORDS_THIN)


def _looks_like_price(s: str) -> bool:
    val = s.strip()
    if any(k in val for k in PRICE_KEYWORDS["diamond"] | PRICE_KEYWORDS["emerald"] | PRICE_KEYWORDS["free"]):
        return True
    if re.search(r"\d+", val):
        return True
    return False


def _parse_info_txt(text: str) -> dict:
    """解析 info.txt，返回 {name, author, price, price_type, price_value, desc, arm}。"""
    lines = [ln.rstrip("\r") for ln in text.splitlines() if ln.strip()]
    kv = {}
    plain_lines = []
    for ln in lines:
        m = re.match(r"^\s*([A-Za-z\u4e00-\u9fa5_]+)\s*[=：:]\s*(.+)$", ln)
        if m:
            kv[m.group(1).lower()] = m.group(2).strip()
        else:
            plain_lines.append(ln)

    # ————————————————————————————————
    # 写法 A：key=value 模式
    # ————————————————————————————————
    if kv:
        def get(*keys):
            for k in keys:
                for kk, vv in kv.items():
                    if k in kk:
                        return vv
            return ""

        name = get("name", "名称", "资源")
        author = get("author", "作者")
        desc = get("desc", "简介", "描述", "说明")
        arm = get("arm", "手臂", "类型")

        # —— 定价：优先用 price_type + price_value 的清晰写法 ——
        price_type_raw = get("price_type", "定价类型", "价格类型")
        price_value_raw = get("price_value", "定价数值", "价格数值", "数值", "金额")
        price_combined = get("price", "定价", "价格")

        if price_type_raw in ("1", "2", "3"):
            # 新格式：price_type=1/2/3，钻石/绿宝石需要 price_value
            price_type, price_value = _parse_price(price_type_raw, price_value_raw)
        elif price_combined:
            # 兼容旧格式：price=300钻石 或 price=1 300 等
            price_type, price_value = _parse_price(price_combined)
        else:
            price_type = ""
            price_value = 0
            price_combined = ""

        # 用纯行式补漏
        idx = 0
        if not name and plain_lines:
            name = plain_lines[0]; idx = 1
        if not author and len(plain_lines) > idx and not _looks_like_price(plain_lines[idx]) and not _looks_like_arm(plain_lines[idx]):
            author = plain_lines[idx]; idx += 1
        if not (price_type_raw or price_combined) and len(plain_lines) > idx:
            # 纯行式里找定价：先试类型行 1/2/3 + 下一行数字
            p0 = plain_lines[idx].strip()
            if p0 in ("1", "2") and idx + 1 < len(plain_lines):
                p1 = plain_lines[idx + 1].strip()
                price_type, price_value = _parse_price(p0, p1)
                price_combined = f"{p0} {p1}"
                idx += 2
            elif p0 == "3":
                price_type, price_value = _parse_price(p0)
                price_combined = p0
                idx += 1
            else:
                price_type, price_value = _parse_price(p0)
                price_combined = p0
                idx += 1
        if not desc and len(plain_lines) > idx:
            desc = plain_lines[idx]; idx += 1
        if not arm and len(plain_lines) > idx:
            arm = plain_lines[idx]

    # ————————————————————————————————
    # 写法 B：纯行式模式
    # ————————————————————————————————
    else:
        name = plain_lines[0] if len(plain_lines) > 0 else ""
        author = ""
        desc_lines = []
        arm = ""
        price_combined = ""
        price_type = ""
        price_value = 0

        idx = 1
        # 第二行：先判断是不是作者（不含定价词、不含 arm）
        if len(plain_lines) > idx:
            line2 = plain_lines[idx].strip()
            if not _looks_like_price(line2) and not _looks_like_arm(line2) and line2 not in ("1", "2", "3"):
                author = line2
                idx += 1

        # 接下来是定价：支持「1 换行 300」、「300钻石」、「3」等
        if len(plain_lines) > idx:
            p_line = plain_lines[idx].strip()
            if p_line in ("1", "2"):
                # 类型 + 下一行数字
                if idx + 1 < len(plain_lines):
                    v_line = plain_lines[idx + 1].strip()
                    price_type, price_value = _parse_price(p_line, v_line)
                    price_combined = f"{p_line} {v_line}"
                    idx += 2
                else:
                    raise ValueError(f"定价类型={p_line}（钻石/绿宝石）需要下一行填写数字值")
            elif p_line == "3":
                price_type, price_value = _parse_price(p_line)
                price_combined = p_line
                idx += 1
            else:
                # 旧格式：300钻石 / 10绿宝石 / 免费 或 1 300（空格同行）
                price_type, price_value = _parse_price(p_line)
                price_combined = p_line
                idx += 1

        # 剩下的是简介（最后一行如果是 arm 就拿出来）
        remaining = plain_lines[idx:]
        if remaining and _looks_like_arm(remaining[-1]):
            arm = remaining.pop()
        desc_lines = remaining
        desc = "\n".join(desc_lines)

    # ————————————————————————————————
    # 最终校验
    # ————————————————————————————————
    if not name:
        raise ValueError("info.txt 缺少资源名称 (name)")
    if not price_type:
        raise ValueError("info.txt 缺少定价，请使用 price_type=1/2/3 或 price=300钻石 等格式")

    arm_resolved = _parse_arm(arm or "粗")

    return {
        "name": name.strip(),
        "author": author.strip() or "yumi",
        "price": price_combined.strip() or f"{price_type} {price_value}",
        "price_type": price_type,
        "price_value": price_value,
        "desc": desc.strip(),
        "arm": arm_resolved,
    }


def parse_zip(zip_path: str | Path, dest_dir: str | Path | None = None) -> SkinPackage:
    """解压并解析压缩包。"""
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(f"压缩包不存在: {zip_path}")

    if dest_dir is None:
        dest_dir = zip_path.parent / zip_path.stem
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)

    info_files = [p for p in dest_dir.rglob("*")
                  if p.is_file() and p.suffix.lower() == ".txt" and "info" in p.name.lower()]
    if not info_files:
        info_files = [p for p in dest_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".txt"]
    if not info_files:
        raise FileNotFoundError("压缩包内未找到 info.txt")
    info_path = info_files[0]

    pngs = [p for p in dest_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".png"]
    if not pngs:
        raise FileNotFoundError("压缩包内未找到皮肤展开图 PNG")
    pngs.sort(key=lambda p: p.stat().st_size, reverse=True)
    skin_path = pngs[0]

    meta = _parse_info_txt(info_path.read_text(encoding="utf-8", errors="ignore"))

    return SkinPackage(
        name=meta["name"],
        author=meta["author"],
        price=meta["price"],
        price_type=meta["price_type"],
        price_value=meta["price_value"],
        description=meta["desc"],
        arm=meta["arm"],
        skin_image_path=skin_path,
        work_dir=dest_dir,
    )
