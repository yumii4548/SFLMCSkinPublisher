# -*- coding: utf-8 -*-
"""全局配置：路径、Blender 自动探测、渲染参数、图片处理参数、mcdev 选择器、多账号。

选择器部分因无法实时检查网站，采用「语义 + 备选」写法，并附带 --inspect 模式
辅助你首次校准。校准后可在此文件直接覆盖 SELECTORS。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# ============================================================
# 1. 本地资源路径（按你的需求预设）
# ============================================================
BLENDER_MODELS_DIR = Path(r"D:\desktop\工作室\工作室文件\MC皮肤渲染")
LOGO_PATH = Path(r"D:\desktop\logo\53af42236a51a787c5d02b8e375b242f.png")

# 宣传图路径（简介末尾自动追加的统一宣传图）
PROMO_IMAGE_PATH = Path(r"D:\desktop\logo\promo.png")

# 默认作者（info.txt 未指定时使用）
DEFAULT_AUTHOR = "yumi"

# 手臂类型 -> .blend 文件名
MODEL_FILES = {
    "thick": "Steve-造型5.blend",   # 粗手臂（Steve）
    "thin":  "Alex-造型5.blend",    # 细手臂（Alex）
}

# .blend 内引用的默认皮肤贴图名（替换目标）
SKIN_TEXTURE_NAMES = ("Steve.png", "Alex.png")

# ============================================================
# 2. Blender 可执行文件自动探测（Steam 版优先）
# ============================================================
# 最高优先级：环境变量直接指定 blender.exe 路径。
# 使用方式（同一个 cmd 窗口里跑）：
#   set BLENDER_EXE=D:\你的路径\blender.exe
#   python main.py 你的压缩包.zip
BLENDER_EXE_OVERRIDE = os.environ.get("BLENDER_EXE", "").strip()


def _possible_steam_roots() -> list[str]:
    """常见的 Steam 安装根目录（C/D/E/F/G 盘全覆盖）。"""
    roots = []
    if os.environ.get("STEAM_PATH"):
        roots.append(os.environ["STEAM_PATH"])
    for drive in ["C", "D", "E", "F", "G"]:
        roots.append(f"{drive}:\\Program Files (x86)\\Steam")
        roots.append(f"{drive}:\\Steam")
        roots.append(f"{drive}:\\Program Files\\Steam")
    # 用户目录下也可能
    roots.append(str(Path.home() / "AppData" / "Roaming" / "Steam"))
    return roots


def _read_steam_libraries() -> list[str]:
    """解析所有可能的 Steam 根目录里的 libraryfolders.vdf，返回 steamapps 根目录。"""
    all_libs: list[Path] = []
    for steam_root in _possible_steam_roots():
        root = Path(steam_root)
        steamapps = root / "steamapps"
        if steamapps.exists():
            all_libs.append(steamapps)
        vdf = steamapps / "libraryfolders.vdf"
        if vdf.exists():
            try:
                text = vdf.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                    all_libs.append(Path(m.group(1).replace("\\\\", "\\")) / "steamapps")
            except Exception:
                pass
    # 去重保序
    seen = set()
    unique = []
    for p in all_libs:
        sp = str(p)
        if sp not in seen and p.exists():
            seen.add(sp)
            unique.append(sp)
    return unique


def find_blender() -> str:
    """自动查找 blender.exe。

    优先级：
      1. 环境变量 BLENDER_EXE 覆盖
      2. 开始菜单常见安装路径（覆盖 2.8~4.5 全版本）
      3. Steam 所有库里的 Blender
      4. 常见盘位的 Program Files
      5. PATH 里的 blender
    """
    if BLENDER_EXE_OVERRIDE and Path(BLENDER_EXE_OVERRIDE).exists():
        return BLENDER_EXE_OVERRIDE

    versions = ["", " 4.5", " 4.4", " 4.3", " 4.2", " 4.1", " 4.0",
                " 3.6", " 3.5", " 3.4", " 3.3", " 3.2", " 3.0",
                " 2.93", " 2.92", " 2.90"]
    candidates: list[str] = []
    for drive in ["C", "D", "E", "F", "G"]:
        for v in versions:
            candidates.append(f"{drive}:\\Program Files\\Blender Foundation\\Blender{v}\\blender.exe")
            candidates.append(f"{drive}:\\Program Files (x86)\\Blender Foundation\\Blender{v}\\blender.exe")
    for lib in _read_steam_libraries():
        candidates.append(str(Path(lib) / "common" / "Blender" / "blender.exe"))

    for c in candidates:
        if Path(c).exists():
            return c
    return "blender"


BLENDER_EXE = find_blender()

# ============================================================
# 3. 渲染参数
# ============================================================
# 渲染分辨率。设为 None 则沿用 .blend 自带相机/分辨率（推荐，因预设模型已布好光与相机）。
RENDER_RESOLUTION = None  # 例: (1920, 1080)；None = 用 .blend 默认
RENDER_SAMPLES = 64       # Cycles 采样数（若场景用 Eevee 则忽略）
RENDER_FORMAT = "PNG"

# ============================================================
# 4. 图片后处理参数
# ============================================================
OUTPUT_SIZE = 1000        # 最终 1:1 图片边长（px）
LOGO_SCALE = 0.70         # logo 宽度占图片宽度的比例（放大2倍）
LOGO_OPACITY = 0.30       # logo 不透明度（30% 半透明）
LOGO_TOP_MARGIN = 0.38    # logo 距顶部的留白（约在图片中央偏上位置）

# ============================================================
# 4.1 简介模板（发布时填入简介文本框）
# ============================================================
DESCRIPTION_TEMPLATE = """作品名称 {name}

作者 {author}

封面 yumi

定价 {price}

--------------

MC极鱼社交流/反馈/定制：914029611

加入我们/代投：2176179242，83345672

--------------"""

# 定价类型 -> 网页选项映射
# mcdev 网页定价下拉/单选框的文本
PRICE_TYPE_MAP = {
    "diamond": "钻石",
    "emerald": "绿宝石",
    "free": "免费",
}

# ============================================================
# 5. mcdev 网页自动化
# ============================================================
MCDEV_HOME_URL = "https://mcdev.webapp.163.com/"
MCDEV_EDIT_URL = "https://mcdev.webapp.163.com/#/pe/edit/4689431348426443454"

# ------------------------------------------------------------
# 5.1 多账号管理
# ------------------------------------------------------------
# 每个账号一个独立 profile 目录，登录态隔离，可随时切换。
ACCOUNTS_DIR = Path(__file__).parent / "accounts"
DEFAULT_ACCOUNT = "default"  # 默认账号名


def get_account_dir(account: str) -> Path:
    """返回指定账号的浏览器 profile 目录（不存在则创建）。"""
    d = ACCOUNTS_DIR / account
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_accounts() -> list[str]:
    """列出所有已创建的账号名。"""
    if not ACCOUNTS_DIR.exists():
        return []
    return sorted(p.name for p in ACCOUNTS_DIR.iterdir() if p.is_dir())


# 兼容旧引用：默认账号的 profile 目录
BROWSER_PROFILE_DIR = get_account_dir(DEFAULT_ACCOUNT)

# ------------------------------------------------------------
# 5.2 表单选择器（基于 /#/pe/edit/new 真实 Element UI 页面结构）
# 页面是单页长滚动，不是 tab 切分。字段顺序从上到下。
# 策略：.el-form-item:has-text('中文标签') + 内部控件类型
# ------------------------------------------------------------
SELECTORS = {
    # —— 导航 ——
    "nav_content_mgmt": "text=上架与资源管理, text=上架与资源内容管理, text=内容管理",
    "nav_publish_new": "text=发布新资源, text=新建资源, text=新增资源",

    # ===== 页面实际字段顺序（从上到下，真实 snapshot 提取）=====

    # [1] 资源名称
    "input_name": "textarea[placeholder*='资源名称'], input[placeholder*='资源名称'], .el-form-item:has-text('资源名称') .el-input__inner, .el-form-item:has-text('资源名称') textarea",

    # [2] 是否原创作品 → 是
    # 真实点击元素是 radio 内部的 span.el-radio__inner
    "radio_original_yes": ".el-form-item:has-text('是否原创作品') .el-radio:has-text('是') .el-radio__inner, .el-form-item:has-text('是否原创作品') .el-radio:has-text('是')",

    # [3] 是否同步生成PC模组 → 是
    "radio_sync_pc_yes": ".el-form-item:has-text('是否同步生成PC模组') .el-radio:has-text('是') .el-radio__inner, .el-form-item:has-text('是否同步生成PC模组') .el-radio:has-text('是')",

    # [4] PC模组标签（el-select 下拉）→ 休闲
    # 真实DOM结构：
    #   输入框: <input type="text" readonly placeholder="请选择PC模组标签" class="el-input__inner" style="height: 40px;">
    #   选项:   <li class="el-select-dropdown__item"><span>休闲</span></li>
    "select_pc_tag": "input.el-input__inner[placeholder='请选择PC模组标签']:not([disabled])",
    # PC模组标签选项：点 li 内部的 span 文本（而不是外层 li）
    "option_pc_tag_casual": ".el-select-dropdown__item span:text-is('休闲'), .el-select-dropdown__item:has(span:text-is('休闲')) > span, .el-select-dropdown__item:has-text('休闲') span",

    # [5] PC模组简介 → "皮肤资源"（短简介，上面那处）
    "input_pc_intro": ".el-form-item:has-text('PC模组简介') textarea, .el-form-item:has-text('模组简介') .el-textarea__inner",

    # [6] 定价类型 → el-radio（三选一）
    "radio_price_diamond": ".el-form-item:has-text('定价类型') .el-radio:has-text('钻石') .el-radio__inner, .el-form-item:has-text('定价类型') .el-radio:has-text('钻石')",
    "radio_price_emerald": ".el-form-item:has-text('定价类型') .el-radio:has-text('绿宝石') .el-radio__inner, .el-form-item:has-text('定价类型') .el-radio:has-text('绿宝石')",
    "radio_price_free": ".el-form-item:has-text('定价类型') .el-radio:has-text('免费') .el-radio__inner, .el-form-item:has-text('定价类型') .el-radio:has-text('免费')",

    # [6b] 钻石定价档位（选钻石时才出现）
    # 真实DOM：
    #   输入框: <input type="text" readonly placeholder="请选择" class="el-input__inner">
    #   选项:   <li class="el-select-dropdown__item"><span>第1档直购定价：300钻石</span></li>
    #           <li class="el-select-dropdown__item hover"><span>第2档直购定价：600钻石</span></li>
    # 按价格反推选项文本：value=300 → "第1档直购定价：300钻石"；value=600 → "第2档直购定价：600钻石"
    "select_price_tier": "input.el-input__inner[placeholder='请选择']:not([disabled])",
    # 钻石档位按索引选：300=第1个, 600=第2个, 1000=第3个... 直接点第N个 .el-select-dropdown__item
    "option_price_tier_template": "__by_index__",
    # 价格数字：
    #   - 钻石时：disabled，随档位联动
    #   - 绿宝石时：可编辑，真实结构: <input type="text" min="10" role="spinbutton" class="el-input__inner">
    "input_price_value": ".el-form-item:has-text('价格') input.el-input__inner, .el-form-item:has-text('价格') input[type='number'], .el-form-item:has-text('定价') input.el-input__inner",

    # [7] PE详情信息（长简介）& [8] PC详情信息 → 统一用 Quill 富文本编辑器 div.ql-editor[contenteditable=true]
    # 真实DOM：页面一共 2 个 .ql-editor
    #   nth(0) = PE详情信息，nth(1) = PC详情信息
    # 每个编辑器紧邻 1 个 .ql-toolbar（工具栏），toolbar 里有"插入图片"按钮：
    #   <button> → <svg viewBox="0 0 18 18"> → <rect class="ql-stroke" x=3 y=4 w=12 h=10> + <circle cx=6 cy=7 r=1> + <polyline points="5 12...">
    "pe_detail_editor": "div.ql-editor[contenteditable='true']",
    "pc_detail_editor": "div.ql-editor[contenteditable='true']",
    # Quill 工具栏里的"插入图片"按钮（按内部 SVG 图标特征精确匹配）：
    #   - svg viewBox=0 0 18 18，内部包含 rect.ql-stroke(x=3,y=4,w=12,h=10) + circle(cx=6,cy=7,r=1) + polyline(山形图片角标)
    # 页面有 2 个这样的按钮：nth(0)=PE编辑器工具栏, nth(1)=PC编辑器工具栏
    "quill_image_button": "div.ql-toolbar button:has(svg[viewBox='0 0 18 18'] > rect.ql-stroke[x='3'][y='4'][width='12'][height='10'] + circle.ql-fill[cx='6'][cy='7'][r='1'] + polyline[points*='5 12']), div.ql-toolbar button:has(svg[viewBox='0 0 18 18'] > rect.ql-stroke[width='12'][height='10']), div.ql-toolbar button:has(svg rect.ql-stroke), div.ql-toolbar .ql-image",
    # Quill 编辑器插入图片时会弹 file input 或系统文件选择对话框，用 filechooser 监听

    # [9] 资源类别（PE资源管理内，真实DOM：
    #   主类别: <input placeholder="请选择主类别" readonly> → <li><span>皮肤</span></li>
    #   次类别: <input placeholder="请选择次类别" readonly> → <li><span>原版风格</span></li>
    # 注意：页面有两组主/次类别，PC模组那组是 disabled 的，必须用 :not([disabled]) 排除
    "select_category_main": "input.el-input__inner[placeholder='请选择主类别']:not([disabled]), .el-form-item:has-text('资源类别') .el-input__inner[placeholder='请选择主类别']:not([disabled])",
    # 主类别选项：点 li 内部的 span 文本
    "option_category_skin": ".el-select-dropdown__item span:text-is('皮肤'), .el-select-dropdown__item:has(span:text-is('皮肤')) > span, .el-select-dropdown__item:has-text('皮肤') span",
    "select_category_sub": "input.el-input__inner[placeholder='请选择次类别']:not([disabled]), .el-form-item:has-text('资源类别') .el-input__inner[placeholder='请选择次类别']:not([disabled])",
    # 次类别选项：点 li 内部的 span 文本
    "option_category_vanilla": ".el-select-dropdown__item span:text-is('原版风格'), .el-select-dropdown__item:has(span:text-is('原版风格')) > span, .el-select-dropdown__item:has-text('原版风格') span",

    # [10] 体型 → Slim=细 / 标准=粗（用户在压缩包里指定 arm=细/粗，对应这两个）
    "radio_body_slim": ".el-form-item:has-text('体型') .el-radio:has-text('Slim') .el-radio__inner, .el-form-item:has-text('体型') .el-radio:has-text('Slim')",
    "radio_body_standard": ".el-form-item:has-text('体型') .el-radio:has-text('标准') .el-radio__inner, .el-form-item:has-text('体型') .el-radio:has-text('标准')",

    # ====== 文件上传区 ======
    # 源文件：64×64 或 128×128 PNG（页面写"固定大小，宽*高：64*64、128*128"）
    # 1000×1000 封面图（我们的 final.png 就是 1000x1000）
    # 其他各种尺寸
    "input_file_upload": "input[type='file']",
    # 皮肤源文件上传触发按钮（真实DOM：<i title="点击上传包体" class="el-icon-plus avatar-uploader-icon">）
    # 先点这个 i 图标，再给它关联的 input[type=file] 塞文件
    "skin_upload_trigger": "i.avatar-uploader-icon[title='点击上传包体'], i.el-icon-plus.avatar-uploader-icon, .avatar-uploader-icon[title*='上传包体']",
    # 其他尺寸（封面图/详情多尺寸图）上传触发：<i title="点击上传文件" class="el-icon-plus avatar-uploader-icon">
    # 页面一共有 N 个这样的 i，全部都要传渲染后的 final.png
    "image_upload_trigger": "i.avatar-uploader-icon[title='点击上传文件'], i.el-icon-plus.avatar-uploader-icon[title='点击上传文件'], .avatar-uploader-icon[title*='上传文件']",
    # 上传图片弹窗里的"确定"按钮（真实DOM：<div class="btn-item btn-text text-confirm">确定</div>）
    # 不是 element ui 的 el-button，是自定义的 div 按钮
    "image_dialog_confirm_btn": "div.btn-item.btn-text.text-confirm:has-text('确定'), div.text-confirm:has-text('确定'), [role='dialog'] div.btn-text:has-text('确定')",

    # —— 上传完所有图片后：点"适用范围"→"客户端" radio ——
    # 真实DOM: <span class="el-radio__inner"> 在 .el-form-item:has-text('适用范围') 内
    "radio_client_scope": ".el-form-item:has-text('适用范围') .el-radio:has-text('客户端') .el-radio__inner, .el-form-item:has-text('适用范围') .el-radio:has-text('客户端')",

    # —— 最终提交 ——
    "btn_submit": "button:has-text('提交审核'), button:has-text('发布'), button:has-text('保存'), .el-button--primary:has-text('提交'), .el-button--primary:has-text('保存')",
    "btn_save": "button:has-text('保存')",
    "btn_submit_review": "button:has-text('提交审核')",
    "success_toast": "text=发布成功, text=提交成功, text=保存成功, .el-message--success, .el-notification__title",
}

# 上传图片前的等待（ms），给 SPA 渲染时间
ACTION_DELAY_MS = 800

# ============================================================
# 6. 邮件通知（网易企业邮箱 SMTP）
# ============================================================

# —— SMTP 服务器 ——
SMTP_SERVER = "smtp.qiye.163.com"
SMTP_PORT = 587
SMTP_USE_SSL = False  # 587 用 STARTTLS

# —— 发件人 ——
SENDER_NAME = "极鱼社 SwiftFishLab"
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")  # 请通过环境变量提供，勿提交密码到仓库

# —— 收件人（审核团队邮箱）——
# 可通过环境变量 REVIEWER_EMAIL 覆盖，或命令行 --email-to
REVIEWER_EMAIL = os.environ.get("REVIEWER_EMAIL", "")

# —— 账号 → 发布账号显示名映射 ——
ACCOUNT_DISPLAY_NAMES = {
    "chym": "沧海月明",
    # 更多账号在此添加，未匹配的默认显示 "极鱼社O组"
}
DEFAULT_PUBLISH_ACCOUNT = "极鱼社O组"

# —— 邮件底部 slogan 宣传图 ——
SLOGAN_IMAGE_PATH = PROMO_IMAGE_PATH  # 默认复用宣传图，也可单独指定

# —— 邮件模板 ——
EMAIL_SUBJECT_TEMPLATE = "我的世界中国版开发者极鱼社对外代投审核状态通知 - {name}"

# 正文模板（审核通过时）—— 含上架时间
EMAIL_BODY_APPROVED = """\
<html><body>
<p>资源名称：{name} - {author}</p>
<p>内审评议意见：同意</p>
<p>网易开平审核：同意</p>
<p>上架时间：{publish_time}</p>
<p>发布账号：{publish_account}</p>
<br>
<p><img src="cid:slogan" style="max-width:100%"></p>
</body></html>"""

# 正文模板（审核不通过时）—— 含理由
EMAIL_BODY_REJECTED = """\
<html><body>
<p>资源名称：{name} - {author}</p>
<p>内审评议意见：同意</p>
<p>网易开平审核：不同意</p>
<p>理由：已有相似皮肤，需添加更多原创元素</p>
<p>发布账号：{publish_account}</p>
<br>
<p><img src="cid:slogan" style="max-width:100%"></p>
</body></html>"""

# ============================================================
# 7. 网易邮箱网页端 云端定时发信（webmail_scheduler.py）
# ============================================================
# 原理：定时发信在网易网页版写信界面设置后，邮件存到网易云端（草稿箱/定时发信列表），
# 到点由网易服务器自动发出 —— 电脑关机也不影响。SMTP 协议本身没有定时能力，故走浏览器自动化。
# 首次使用需：① --add-mail-account 手动登录一次存登录态；② --inspect-mail 校准选器。

# 邮箱入口（企业邮 qiye.163.com；普通 163 可改 https://mail.163.com/）
MAIL_WEB_URL = "https://qiye.163.com/"

# 直达写信页 URL（网易写信页带 session 参数，留空更稳：打开入口后点「写信」按钮）
MAIL_COMPOSE_URL = ""

# 邮件专用浏览器 profile（与 mcdev accounts/ 隔离，登录态独立、可长期复用）
MAIL_PROFILE_DIR = Path(__file__).parent / "mail_profile"

# 定时发送调度方式：
#   auto    = 优先云端定时发信（提交前失败才回退 Windows 计划任务；结果未知不回退，防双发）
#   webmail = 强制云端定时发信（失败不发送）
#   task    = 强制 Windows 计划任务（旧方式）
# 可用环境变量 MAIL_SCHEDULER_MODE 覆盖（如 MAIL_SCHEDULER_MODE=task）
MAIL_SCHEDULER_MODE = os.environ.get("MAIL_SCHEDULER_MODE", "auto").strip().lower()

# 网易写信页选择器骨架（真实 DOM 以 qiye.163.com 为准，用 --inspect-mail 校准后回填）。
# 与 SELECTORS 相同的「语义 + 备选」写法：逗号分隔，逐个尝试。
MAIL_SELECTORS = {
    # —— 登录态检测 ——
    "mail_logged_in": "a:has-text('退出'), a:has-text('退出登录'), .js-component-logout, [data-mod='logout']",
    "mail_login_page": "input[type='password'], input[name='password'], .login-form, .mail-login",
    # —— 导航 ——
    "btn_write_mail": "a:has-text('写信'), button:has-text('写信'), .js-component-write, [title='写信']",
    # —— 写信字段 ——
    "input_to": "div.nui-editableAddr-ipt, [id*='To'] div[contenteditable='true'], input[placeholder*='收件人'], .nui-ipt-input input[placeholder*='收件人']",
    "btn_cc": "a:has-text('抄送'), button:has-text('抄送'), span:has-text('抄送')",
    "input_cc": "div.nui-editableAddr-ipt, input[placeholder*='抄送'], [id*='Cc'] div[contenteditable='true']",
    "input_subject": "input[placeholder*='主题'], .nui-ipt-input input[placeholder*='主题'], [id*='Subject'] input",
    "editor_body": "iframe[id*='_mail']:visible, iframe.kmEditor:visible, div[contenteditable='true'][id*='_mail'], div.kmEditor",
    # —— 正文插图 / 附件 ——
    "btn_insert_image": "button[title*='图片'], button[title*='插入图片'], .nui-ico-image, [class*='toolbar'] button[title*='图片']",
    "btn_attach": "button[title*='附件'], .nui-ico-attach, [class*='attach'] button, button[title*='回形针']",
    # —— 定时发信 ——
    "btn_timed_send": "span:has-text('定时发信'), a:has-text('定时发信'), button:has-text('定时发信'), .nui-ico-more",
    "btn_more_options": "a:has-text('更多选项'), button:has-text('更多选项'), .nui-ico-more",
    "option_timed_send": "li:has-text('定时发信'), .nui-menu-item:has-text('定时发信'), div:has-text('定时发信')",
    "timed_date_open": "input[placeholder*='日期'], input[placeholder*='选择日期'], [class*='date'] input, .nui-ico-calendar",
    "timed_date_input": "input[placeholder*='日期'], input[placeholder*='选择日期'], [class*='date'] input",
    "timed_time_hour": "select[data-placeholder*='时'], input[placeholder*='时'], [class*='hour']",
    "timed_time_min": "select[data-placeholder*='分'], input[placeholder*='分'], [class*='minute']",
    # —— 发送 / 确认 / 成功 ——
    "btn_send": "button:has-text('发送'), .nui-btn-primary:has-text('发送'), [id*='send'] button, button:has-text('定时发信')",
    "btn_confirm_timed": "button:has-text('确定'), button:has-text('确认'), .nui-btn-primary:has-text('确定')",
    "success_toast": "text=发送成功, text=已发送, text=定时发送成功, .nui-msg, .nui-toast",
}
