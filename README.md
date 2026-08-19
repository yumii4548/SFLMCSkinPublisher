# MC 皮肤自动上架工具

程序作者：**极鱼社 SwiftFishLab**

一键完成 Minecraft 中国版皮肤的全流程上架：解压 → Blender 渲染 → 图片后处理 → 网页自动发布。

---

## 目录

- [功能概览](#功能概览)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [压缩包准备](#压缩包准备)
- [命令行用法](#命令行用法)
- [配置说明](#配置说明)
- [工作流程详解](#工作流程详解)
- [多账号管理](#多账号管理)
- [定价说明](#定价说明)
- [常见问题](#常见问题)
- [项目结构](#项目结构)
- [联系方式](#联系方式)

---

## 功能概览

| 步骤 | 说明 |
|------|------|
| ① 解析压缩包 | 自动识别 `info.txt` 中的名称、作者、定价、手臂类型等信息，提取皮肤 PNG |
| ② Blender 渲染 | 根据手臂类型（粗/细）自动调用预设 3D 模型，替换贴图后渲染出图 |
| ③ 图片后处理 | 裁剪为 1000×1000 人物居中正方形，叠加半透明工作室 logo |
| ④ 网页自动发布 | 自动登录 mcdev，填写表单、上传文件、插图，全程自动化 |

支持**部分流程运行**：可以只渲染不发布，也可以用已有图片直接发布。

---

## 环境要求

### 1. Python

Python 3.10+，安装依赖：

```bash
pip install -r requirements.txt
playwright install chromium
```

依赖包：
- `Pillow` — 图片处理（裁剪、缩放、logo 叠加）
- `playwright` — 浏览器自动化（mcdev 网页操作）

### 2. Blender

需要本地安装 Blender（2.8 ~ 4.5 均可）。

程序会按以下优先级自动探测 `blender.exe`：
1. 环境变量 `BLENDER_EXE` 指定的路径
2. Steam 库中的 Blender
3. 常见安装路径（C/D/E/F/G 盘 Program Files）
4. 系统 PATH 中的 `blender`

如果自动探测不对，可以在运行前设置环境变量：

```bash
set BLENDER_EXE=D:\你的路径\blender.exe
python main.py 皮肤.zip
```

### 3. 预设 3D 模型

需要在 `config.py` 中配置的模型目录下放置两个 `.blend` 文件：

| 文件名 | 用途 |
|--------|------|
| `Steve-造型5.blend` | 粗手臂（Steve 型） |
| `Alex-造型5.blend` | 细手臂（Alex 型） |

模型需包含材质节点中的皮肤贴图（纹理名 `Steve.png` / `Alex.png`），程序会自动替换为用户皮肤。

### 4. Logo 与宣传图

| 配置项 | 用途 |
|--------|------|
| `LOGO_PATH` | 叠加在渲染图上的半透明工作室 logo |
| `PROMO_IMAGE_PATH` | 简介末尾追加的宣传图 |

---

## 快速开始

```bash
# 1. 首次使用：添加账号（浏览器打开后手动登录，关闭窗口即保存）
python main.py --add-account default

# 2. 准备一个压缩包（含 info.txt + 皮肤展开图 PNG）

# 3. 一键上架
python main.py 我的皮肤.zip
```

---

## 压缩包准备

将 `info.txt` 和皮肤展开图 PNG 打包成一个 zip 文件。

### info.txt 格式（推荐 key=value 写法）

**钻石定价（300 钻石）：**
```
name=我的超酷皮肤
author=作者名
price_type=1
price_value=300
desc=这是一个很棒的皮肤简介
arm=粗
```

**绿宝石定价（30 绿宝石）：**
```
name=绿宝石皮肤
author=作者名
price_type=2
price_value=30
desc=绿宝石专属皮肤
arm=细
```

**免费皮肤：**
```
name=免费福利皮肤
author=作者名
price_type=3
desc=免费送给大家
arm=粗
```

### 字段说明

| 字段 | 必填 | 说明 | 可选值 |
|------|------|------|--------|
| `name` | ✅ | 资源名称 | 任意文本 |
| `author` | ❌ | 作者名（默认 `yumi`） | 任意文本 |
| `price_type` | ✅ | 定价类型 | `1`=钻石, `2`=绿宝石, `3`=免费 |
| `price_value` | 看类型 | 定价数值 | 钻石/绿宝石时必填（如 `300`、`30`），免费时省略 |
| `desc` | ❌ | 简介 | 任意文本 |
| `arm` | ❌ | 手臂类型（默认粗） | `粗`/`thick`/`steve` 或 `细`/`thin`/`alex` |

### 兼容写法

也支持旧版纯行式格式：

```
我的超酷皮肤
作者名
300钻石
这是一个很棒的皮肤简介
粗
```

或两行定价（类型 + 数值分行）：

```
我的超酷皮肤
作者名
1
300
这是一个很棒的皮肤简介
粗
```

### 皮肤图片要求

- 格式：PNG
- 尺寸：64×64 或 128×128（标准 MC 皮肤展开图）
- 文件名不限，程序自动取 zip 内最大的 PNG

### 压缩包结构示例

```
my_skin.zip
├── info.txt      # 元信息
└── skin.png      # 皮肤展开图
```

---

## 命令行用法

### 基础命令

```bash
# 完整流程（渲染 + 自动上架，使用默认账号）
python main.py <压缩包.zip>

# 查看帮助
python main.py --help
```

### 流程控制

```bash
# 只渲染不上架（适合只想生成图片的场景）
python main.py 皮肤.zip --skip-publish

# 跳过渲染，用已有图片直接上架
python main.py 皮肤.zip --skip-render --image 最终图.png

# 无头模式（不显示浏览器窗口，仅推荐已登录过的账号用）
python main.py 皮肤.zip --headless
```

### 账号管理

```bash
# 列出所有已创建的账号
python main.py --list-accounts

# 创建/登录一个新账号（打开浏览器手动登录，关闭窗口即保存）
python main.py --add-account 账号名

# 使用指定账号发布
python main.py 皮肤.zip --account 账号名
```

### 高级选项

```bash
# 覆盖 info.txt 中的手臂类型
python main.py 皮肤.zip --arm thick    # 粗手臂
python main.py 皮肤.zip --arm thin     # 细手臂

# 校准网页选择器（网站更新后选择器可能失效，用此模式手动走一遍流程）
python main.py --inspect
python main.py --inspect --account 账号名
```

---

## 配置说明

所有配置集中在 `config.py` 中，以下是关键配置项：

### 路径配置

```python
# Blender 预设模型目录
BLENDER_MODELS_DIR = Path(r"D:\desktop\工作室\工作室文件\MC皮肤渲染")

# logo 图片路径（叠加在渲染图上）
LOGO_PATH = Path(r"D:\desktop\logo\logo.png")

# 宣传图路径（简介末尾追加）
PROMO_IMAGE_PATH = Path(r"D:\desktop\logo\promo.png")
```

### 渲染参数

```python
RENDER_SAMPLES = 64    # Cycles 采样数（场景用 Eevee 则忽略）
RENDER_FORMAT = "PNG"  # 渲染输出格式
```

### 图片后处理参数

```python
OUTPUT_SIZE = 1000     # 最终 1:1 图片边长（px）
LOGO_SCALE = 0.70      # logo 宽度占图片宽度的比例
LOGO_OPACITY = 0.30    # logo 不透明度（0.0 ~ 1.0）
LOGO_TOP_MARGIN = 0.38 # logo 距顶部留白
```

### 简介模板

```python
DESCRIPTION_TEMPLATE = """作品名称 {name}

作者 {author}

封面 yumi

定价 {price}

--------------

MC极鱼社交流/反馈/定制：914029611

加入我们/代投：2176179242，83345672

--------------"""
```

模板中的 `{name}`、`{author}`、`{price}` 会自动替换为 info.txt 中的值。

### 网页选择器

`SELECTORS` 字典定义了 mcdev 发布页面各表单项的 CSS 选择器。如果网站改版导致自动化失败，用 `--inspect` 模式校准后回填此字典。

---

## 工作流程详解

### 第一步：解析压缩包

1. 解压 zip 到同名目录
2. 自动查找 `info.txt`（支持任意包含 "info" 的文件名）
3. 自动查找皮肤 PNG（取文件大小最大的 PNG）
4. 解析 `info.txt` 中的元信息（名称、作者、定价、手臂类型、简介）

### 第二步：Blender 渲染

1. 根据手臂类型选择对应 `.blend` 模型文件
2. 以 headless 模式启动 Blender
3. 运行 `render_script.py`：
   - 加载用户皮肤展开图
   - 遍历材质节点，找到 MC 皮肤尺寸的 Image Texture
   - 同尺寸直接覆盖像素；更大尺寸创建新 Image datablock 保留画质；更小尺寸缩放后覆盖
   - 渲染单帧 PNG 输出到 `output/render_{arm}.png`
4. 不修改原始 `.blend` 文件

### 第三步：图片后处理

1. 读取渲染图
2. 裁剪中间 1080px 宽区域（x: 406~1486）
3. 缩放为 1000×1000 正方形
4. 在正中央叠加半透明 logo
5. 输出 `output/final.png`

### 第四步：网页自动发布

1. 使用 Playwright 打开 Chromium（复用已保存的登录态）
2. 导航到 mcdev「发布新资源」页面
3. 按顺序填写表单：
   - 资源名称
   - 是否原创作品 → 是
   - 是否同步生成 PC 模组 → 是
   - PC 模组标签 → 休闲
   - PC 模组简介 → 皮肤资源
   - 定价类型（钻石/绿宝石/免费）
   - PE 详情信息 → 填简介模板 + 插图
   - PC 详情信息 → 填简介模板 + 插图
   - 资源类别 → 主类别=皮肤，次类别=原版风格
   - 体型 → Slim(细) 或 标准(粗)
4. 上传文件：
   - 皮肤源文件（64×64/128×128 PNG）
   - 各尺寸插槽全部上传渲染结果图（1000×1000）
5. 点"适用范围"→"客户端"
6. 点击"保存"
7. 浏览器保持打开，可在浏览器中手动确认后点"提交审核"

> **注意**：程序只点「保存」不点「提交审核」，方便你在浏览器里做最终检查。

---

## 多账号管理

每个账号有独立的浏览器 profile 目录（存放在 `accounts/<账号名>/`），登录态完全隔离。

```bash
# 创建账号 A
python main.py --add-account account_a
# → 浏览器打开，手动登录账号 A，关闭窗口

# 创建账号 B
python main.py --add-account account_b
# → 浏览器打开，手动登录账号 B，关闭窗口

# 用账号 A 发布
python main.py 皮肤.zip --account account_a

# 用账号 B 发布
python main.py 皮肤.zip --account account_b

# 查看所有账号
python main.py --list-accounts
# 输出：
#   - account_a
#   - account_b
#   - default (默认)
```

---

## 定价说明

### 钻石档位

| price_value | 网页档位 | 选择方式 |
|-------------|----------|----------|
| 300 | 第 1 档直购定价 | 点下拉第 1 项 |
| 600 | 第 2 档直购定价 | 点下拉第 2 项 |
| 1000 | 第 3 档直购定价 | 点下拉第 3 项 |
| 2000 | 第 4 档直购定价 | 点下拉第 4 项 |
| 3000 | 第 5 档直购定价 | 点下拉第 5 项 |
| 5000 | 第 6 档直购定价 | 点下拉第 6 项 |
| 10000 | 第 7 档直购定价 | 点下拉第 7 项 |
| 20000 | 第 8 档直购定价 | 点下拉第 8 项 |

info.txt 中写 `price_type=1` + `price_value=300`（或其他支持的值）。

### 绿宝石

| price_value | 操作 |
|-------------|------|
| 10 | 预设值，不改动 |
| 20 | 点 + 按钮 1 下 |
| 30 | 点 + 按钮 2 下 |
| 50 | 点 + 按钮 4 下 |
| 100 | 点 + 按钮 9 下 |

info.txt 中写 `price_type=2` + `price_value=30`（或其他 10 的倍数）。

### 免费

info.txt 中写 `price_type=3`，不需要 `price_value`。

---

## 常见问题

### Q: 首次运行报错 "浏览器需要登录"

**A:** 使用 `--add-account` 创建账号：

```bash
python main.py --add-account default
```

浏览器会自动打开 mcdev 网站，手动输入账号密码登录后关闭浏览器窗口即可。之后再次运行程序会自动复用登录态。

### Q: Blender 找不到

**A:** 三种解决方式：

1. **设置环境变量（推荐）**：
   ```bash
   set BLENDER_EXE=D:\Blender\blender.exe
   python main.py 皮肤.zip
   ```

2. **修改 `config.py`**：将 `BLENDER_EXE_OVERRIDE` 的逻辑改为直接硬编码路径。

3. **安装 Steam 版 Blender**：程序会自动搜索 Steam 库。

### Q: 预设模型文件找不到

**A:** 确认 `config.py` 中 `BLENDER_MODELS_DIR` 路径正确，且目录下存在：
- `Steve-造型5.blend`
- `Alex-造型5.blend`

### Q: 网页自动化失败 / 选择器失效

**A:** mcdev 网站更新后 CSS 选择器可能变化。使用校准模式：

```bash
python main.py --inspect
```

浏览器打开后手动走一遍发布流程，记录新的选择器，然后更新 `config.py` 中 `SELECTORS` 字典的对应项。

### Q: 上传图片时弹出资源管理器窗口

**A:** 程序已通过 Playwright 的 `filechooser` 拦截机制自动处理文件选择对话框，正常情况下不会弹出系统窗口。如果出现弹窗，可能是网站改版导致 DOM 结构变化，建议运行 `--inspect` 校准。

### Q: 渲染后图片不对劲（人物位置偏了 / 没拍到人）

**A:** 检查以下配置：

1. `image_post.py` 中硬编码的裁剪坐标 `crop_left=406, crop_right=1486` 是否适合你的 Blender 场景相机——如果相机位置不同需要调整。
2. `config.py` 中 `BLENDER_MODELS_DIR` 是否正确指向了包含模型文件的目录。

### Q: 能不能同时发布到多个账号

**A:** 可以，分别运行：

```bash
python main.py 皮肤.zip --account account_a
python main.py 皮肤.zip --account account_b
```

每个账号独立登录态，互不影响。

### Q: 能不能只渲染不发布

**A:** 可以：

```bash
python main.py 皮肤.zip --skip-publish
```

渲染结果图片保存在 `output/final.png`。

### Q: 能不能用已经渲染好的图片直接发布

**A:** 可以：

```bash
python main.py 皮肤.zip --skip-render --image output/final.png
```

这样会跳过 Blender 渲染步骤，直接用你指定的图片上架。

### Q: 程序卡住不动了

**A:** 可能原因：
- Playwright 浏览器正在等待页面加载，检查浏览器窗口中是否弹出了登录页面或验证码。
- Blender 渲染时间较长（取决于模型复杂度和采样数），观察终端是否有 `[render_script]` 开头的输出。
- 可按 `Ctrl+C` 退出，检查终端最后输出的日志定位卡在哪个步骤。

---

## 项目结构

```
mc-skin-publisher/
├── main.py             # 主入口，流程编排 + 命令行参数
├── config.py           # 全局配置（路径、渲染参数、网页选择器、多账号）
├── parser.py           # 压缩包解析（info.txt + 皮肤 PNG 提取）
├── blender_render.py   # Blender 调度模块（启动 headless Blender）
├── render_script.py    # Blender 内部脚本（替换贴图 + 渲染，在 Blender 进程内运行）
├── image_post.py       # 图片后处理（裁剪 1:1、缩放、logo 叠加）
├── publisher.py        # mcdev 网页自动化（Playwright 填表 + 上传 + 保存）
├── requirements.txt    # Python 依赖
├── accounts/           # 账号登录态目录（每个账号一个子目录）
├── output/             # 渲染输出目录（render.png, final.png）
├── README.md           # 本文档
└── 使用教程.md          # 旧版使用教程
```

---

## 联系方式

- **QQ 群**：914029611（交流 / 反馈 / 定制）
- **代投 / 合作**：QQ 2176179242、83345672
- **平台**：我的世界中国版、爱发电、闲鱼、小红书

---

> 极鱼社 (SwiftFishLab) 创立于 2021 年，起源于《我的世界》中国版。
> 截至 2024 年，国服组件累计下载量突破 **1100 万**，订阅人数 **20 万+**，
> 上架组件超 **500 款**，2022-2023 年度长期稳居平台百强。

©2026 SwiftFishLab All Right Reserved
