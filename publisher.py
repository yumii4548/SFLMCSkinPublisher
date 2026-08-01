# -*- coding: utf-8 -*-
"""mcdev 网页自动化发布（基于真实页面 /#/pe/edit/new 结构）。

页面结构（单页长滚动，非 tab）：
  1. 资源名称                            ← 填
  2. 是否加入到"我的山头"专区             ← 不动
  3. 是否原创作品                         ← 选"是"
  4. 模组标签（readonly）                 ← 不动
  5. 活动参与说明                         ← 不动
  6. 是否为关联模组                       ← 不动
  7. 是否同步生成PC模组                   ← 选"是"（点完后PC基本信息/PC详情信息才出现）
  8. 是否含有地图                         ← 不动
  === PC基本信息（点"是否同步生成PC模组=是"后出现）===
  9. PC模组标签                           ← 选"休闲"（el-select 下拉，点开直接选）
 10. PC前置模组                           ← 不动
 11. PC模组简介                          ← 填"皮肤资源"（短简介）
 12. 定价类型                             ← el-radio 单选：钻石/绿宝石/免费
 13. 钻石定价档位（选钻石时出现）         ← 匹配"300钻石"等档位
 14. 价格（钻石时 disabled，自动填）
 15. PE详情信息（textarea，带"预览"按钮） ← 填用户模板（长简介）
 16. 更新纪要说明（不填！不是PE详情信息）
 17. PC详情信息（contenteditable富文本）  ← 填用户模板（长简介）
 18. 资源类别主类别=皮肤（已默认）        ← 不动
 19. 次类别=原版风格（已默认）            ← 不动
 20. modAPI版本（已默认）                 ← 不动
 21. 体型：Slim(细) / 标准(粗)            ← 按 arm 值选
 22. 文件上传区（64/128皮肤PNG + 多尺寸图）← 上传
 23. 其他（模组类别/适用范围/多尺寸图）    ← 不动
 24. 底部按钮：保存 / 提交审核            ← 先保存

只动用户提到过的 + 必须的几项（体型、定价档位），其他不动。
"""
from __future__ import annotations

import time
from pathlib import Path

import config


class McdevPublisher:
    def __init__(self, account: str = config.DEFAULT_ACCOUNT,
                 headless: bool = False, slow_mo: int = config.ACTION_DELAY_MS):
        self.account = account
        self.headless = headless
        self.slow_mo = slow_mo
        self._playwright = None
        self._context = None
        self._page = None

    # ---------- 生命周期 ----------
    def start(self):
        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().start()
        profile_dir = config.get_account_dir(self.account)
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1440, "height": 900},
            args=["--start-maximized"],
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        print(f"[publisher] 使用账号: {self.account}  (profile: {profile_dir})")
        return self

    def stop(self):
        try:
            if self._context:
                self._context.close()
        finally:
            if self._playwright:
                self._playwright.stop()

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    @property
    def page(self):
        return self._page

    # ---------- 工具方法 ----------
    def _scroll_to_field(self, selector_csv: str):
        """滚动到某个字段。"""
        for sel in [s.strip() for s in selector_csv.split(",") if s.strip()]:
            try:
                loc = self._page.locator(sel).first
                loc.wait_for(state="visible", timeout=4000)
                loc.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.3)
                return
            except Exception:
                continue

    def _click_any(self, selector_csv: str, timeout: int = 8000, scroll: bool = True) -> bool:
        if scroll:
            self._scroll_to_field(selector_csv)
        for sel in [s.strip() for s in selector_csv.split(",") if s.strip()]:
            try:
                loc = self._page.locator(sel).first
                loc.wait_for(state="visible", timeout=timeout)
                loc.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.2)
                loc.click()
                print(f"[publisher] 点击成功: {sel[:80]}")
                return True
            except Exception:
                continue
        print(f"[publisher] 点击失败: {selector_csv[:80]}")
        return False

    def _fill_any(self, selector_csv: str, value: str, timeout: int = 8000) -> bool:
        self._scroll_to_field(selector_csv)
        for sel in [s.strip() for s in selector_csv.split(",") if s.strip()]:
            try:
                loc = self._page.locator(sel).first
                loc.wait_for(state="visible", timeout=timeout)
                loc.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.2)
                loc.click()
                loc.fill("")
                loc.fill(value)
                print(f"[publisher] 填写成功: {sel[:80]}")
                return True
            except Exception:
                continue
        print(f"[publisher] 填写失败: {selector_csv[:80]}")
        return False

    def _select_dropdown(self, select_selector: str, option_selector: str,
                         timeout: int = 8000, confirm_step: bool = True) -> bool:
        """Element UI el-select 三步法（confirm_step=True）或两步法（confirm_step=False）

        confirm_step=True（PC模组标签/定价档位等需要收起确认）:
            ① 点 input → 打开下拉
            ② 点选项里的 span → 选中项
            ③ 点 select 右侧箭头 i.el-select__caret → 收起/确认

        confirm_step=False（PE资源管理的主/次类别）:
            ① 点 input → 打开下拉
            ② 点选项里的 span → 选中项
        """
        self._scroll_to_field(select_selector)

        # ===== 第 1 步：点 input 打开下拉 =====
        select_loc = self._resolve_first(select_selector)
        if select_loc is None:
            print(f"[publisher] select 未找到: {select_selector[:80]}")
            return False
        try:
            select_loc.scroll_into_view_if_needed(timeout=3000)
            time.sleep(0.2)
            select_loc.click(timeout=3000)
        except Exception:
            try:
                select_loc.click(force=True, timeout=2000)
            except Exception as e:
                print(f"[publisher] select 点击失败: {e}")
                return False
        # 等待下拉打开
        wait_end = time.time() + 3.0
        opened = False
        while time.time() < wait_end:
            try:
                if self._page.locator(".el-select-dropdown:visible").count() > 0:
                    opened = True
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if not opened:
            # 再点一次
            try:
                select_loc.click(force=True, timeout=2000)
                time.sleep(0.8)
            except Exception:
                pass

        # ===== 第 2 步：在可见下拉容器内点选项里的 span =====
        time.sleep(0.35)
        # 先找可见的下拉容器，把选项搜索范围限定在里面（避免匹配到隐藏下拉的选项）
        visible_dropdown = None
        try:
            dd_list = self._page.locator(".el-select-dropdown:visible")
            cnt = dd_list.count()
            if cnt > 0:
                visible_dropdown = dd_list.nth(cnt - 1)  # 取最上层（最后一个可见的）
        except Exception:
            pass

        opt_chosen = False
        for sel in [s.strip() for s in option_selector.split(",") if s.strip()]:
            try:
                # 优先在可见下拉容器内找选项
                if visible_dropdown:
                    try:
                        loc = visible_dropdown.locator(sel).first
                        if loc.count() > 0 and loc.is_visible():
                            loc.click(timeout=3000)
                            print(f"[publisher] 下拉选项选中（可见容器内）: {sel[:80]}")
                            opt_chosen = True
                            break
                    except Exception:
                        pass
                # 兜底：全页面找
                loc = self._page.locator(sel).first
                loc.wait_for(state="visible", timeout=timeout)
                try:
                    loc.click(timeout=3000)
                except Exception:
                    loc.click(force=True, timeout=2000)
                print(f"[publisher] 下拉选项选中: {sel[:80]}")
                opt_chosen = True
                break
            except Exception:
                continue
        if not opt_chosen:
            print(f"[publisher] 下拉选项点击失败: {option_selector[:80]}")
            return False

        # ===== 第 3 步（仅 confirm_step=True）：点 select 右侧箭头 i.el-select__caret 收起/确认 =====
        if not confirm_step:
            # 两步法：PE资源管理的主/次类别选完 span 即结束
            print(f"[publisher] 下拉选择成功（input→span）: {option_selector[:80]}")
            return True

        # 真实DOM: <i class="el-select__caret el-input__icon el-icon-arrow-up">
        time.sleep(0.25)
        caret_clicked = False
        # 在已选中的 select 容器附近找箭头图标
        caret_selectors = [
            "i.el-select__caret.el-icon-arrow-up:visible",
            "i.el-select__caret:visible",
            "i.el-input__icon.el-icon-arrow-up:visible",
            "i.el-select__caret",
            "i.el-input__icon.el-icon-arrow-up",
        ]
        for cs in caret_selectors:
            try:
                caret = self._page.locator(cs).first
                if caret.count() > 0:
                    caret.scroll_into_view_if_needed(timeout=2000)
                    try:
                        caret.click(timeout=2000)
                    except Exception:
                        caret.click(force=True, timeout=1500)
                    caret_clicked = True
                    break
            except Exception:
                continue
        if not caret_clicked:
            # 兜底：再点一次 input
            select_loc2 = self._resolve_first(select_selector)
            if select_loc2 is not None:
                try:
                    select_loc2.scroll_into_view_if_needed(timeout=2000)
                    select_loc2.click(timeout=2000)
                except Exception:
                    try:
                        select_loc2.click(force=True, timeout=1500)
                    except Exception:
                        try:
                            self._page.mouse.click(10, 10)
                        except Exception:
                            pass

        print(f"[publisher] 下拉选择成功（input→span→i）: {option_selector[:80]}")
        return True

    def _select_dropdown_by_index(self, select_selector: str, item_index: int,
                                   timeout: int = 8000) -> bool:
        """按索引选下拉项：点 input 打开下拉 → 点第 item_index 个 .el-select-dropdown__item。

        适用于钻石档位等选项顺序固定的场景：
          item_index=0 → 第1个选项（300钻石）
          item_index=1 → 第2个选项（600钻石）
          ...
        """
        self._scroll_to_field(select_selector)

        # 第 1 步：点 input 打开下拉
        select_loc = self._resolve_first(select_selector)
        if select_loc is None:
            print(f"[publisher] select 未找到: {select_selector[:80]}")
            return False
        try:
            select_loc.scroll_into_view_if_needed(timeout=3000)
            time.sleep(0.2)
            select_loc.click(timeout=3000)
        except Exception:
            try:
                select_loc.click(force=True, timeout=2000)
            except Exception as e:
                print(f"[publisher] select 点击失败: {e}")
                return False

        # 等待下拉打开
        wait_end = time.time() + 3.0
        opened = False
        while time.time() < wait_end:
            try:
                if self._page.locator(".el-select-dropdown:visible").count() > 0:
                    opened = True
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if not opened:
            try:
                select_loc.click(force=True, timeout=2000)
                time.sleep(0.8)
            except Exception:
                pass

        # 第 2 步：在可见下拉容器内点第 item_index 个选项的 span
        time.sleep(0.35)
        try:
            dd_list = self._page.locator(".el-select-dropdown:visible")
            cnt = dd_list.count()
            if cnt > 0:
                visible_dropdown = dd_list.nth(cnt - 1)
                items = visible_dropdown.locator(".el-select-dropdown__item")
                total_items = items.count()
                print(f"[publisher]   下拉共 {total_items} 项，点第 {item_index+1} 项")
                if item_index < total_items:
                    # 优先点 li 内的 span（用户指定操作），兜底点 li 本身
                    target = items.nth(item_index)
                    span = target.locator("span")
                    if span.count() > 0:
                        span.click(timeout=3000)
                    else:
                        target.click(timeout=3000)
                    print(f"[publisher] 下拉按索引选择成功（第{item_index+1}项）")
                    return True
                else:
                    print(f"[publisher] 索引超出范围（{item_index} >= {total_items}）")
                    return False
        except Exception as e:
            print(f"[publisher] 下拉按索引选择失败: {e}")
            return False

    def _resolve_first(self, selector_csv: str):
        """从逗号分隔的选择器列表里找第一个命中且可见的元素，返回 locator.first；找不到返回 None"""
        for sel in [s.strip() for s in selector_csv.split(",") if s.strip()]:
            try:
                loc = self._page.locator(sel).first
                if loc.count() > 0:
                    return loc
            except Exception:
                continue
        return None

    def _set_file_at_index(self, file_path: str, index: int) -> bool:
        """给第 index 个 input[type='file'] 上传文件，并确认编辑图片弹窗。"""
        file_path = str(Path(file_path).resolve())
        try:
            loc = self._page.locator("input[type='file']").nth(index)
            loc.set_input_files(file_path)
            time.sleep(1.5)
            # 每次上传完图片后，可能弹出"编辑图片"弹窗（含 cropper-img），需要点"确定"才能生效
            self._confirm_image_crop_dialog()
            return True
        except Exception:
            print(f"[publisher] 第{index}号文件上传失败")
            return False

    def _confirm_image_crop_dialog(self, timeout_sec: float = 6.0):
        """编辑图片弹窗：检测是否有可见 dialog/modal，在弹窗内点"确定"按钮。

        真实按钮结构（不是 el-button，是自定义的 div）:
          <div class="btn-item btn-text text-confirm">确定</div>
        作用域严格限制在最上层可见弹窗内，避免对全页面做暴力点击。
        兜底：确定 / 确认 / 完成 / 保存 / 主按钮。
        如果在 timeout_sec 内没看到弹窗，说明该上传项不需要编辑（如zip/皮肤源文件），直接返回。
        """
        end_ts = time.time() + timeout_sec
        dialog_loc = None
        # 1) 等弹窗出现
        while time.time() < end_ts:
            try:
                candidates = self._page.locator(
                    "[role='dialog']:visible, .el-dialog:visible, .cropper-dialog:visible, .modal:visible, .v-modal + .el-dialog, .el-message-box:visible, .image-crop-dialog:visible, .el-image-viewer__wrapper:visible"
                )
                n = candidates.count()
                if n > 0:
                    dialog_loc = candidates.nth(n - 1)
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if dialog_loc is None:
            # 没有弹窗（皮肤源文件、zip包、非图片上传一般不弹）
            return

        # 2) 在弹窗内找"确定"按钮（真实优先级：div.text-confirm → 其他文本按钮 → 主按钮）
        extra = config.SELECTORS.get("image_dialog_confirm_btn", "")
        btn_selectors = []
        if extra:
            # 先限定在弹窗作用域内：前缀 "dialog_loc.locator(extra)"，extra 里的每项用逗号分
            for part in [s.strip() for s in extra.split(",") if s.strip()]:
                btn_selectors.append(part)
        btn_selectors += [
            'div:has-text("确定"):visible',
            'button:has-text("确定"):visible',
            'button:has-text("确认"):visible',
            'button:has-text("完成"):visible',
            'button:has-text("保存"):visible',
            ".el-button--primary:visible",
        ]
        btn_loc = None
        for bs in btn_selectors:
            try:
                cand = dialog_loc.locator(bs)
                if cand.count() > 0:
                    # 跳过 disabled
                    try:
                        if cand.first.is_disabled():
                            time.sleep(0.6)
                    except Exception:
                        pass
                    btn_loc = cand.first
                    break
            except Exception:
                continue
        if btn_loc is None:
            print("[publisher] 弹窗内未找到确定/确认/完成/保存按钮，跳过")
            return

        # 3) 点按钮（必要时 force click），等弹窗消失
        try:
            btn_loc.click(timeout=3000)
        except Exception:
            try:
                btn_loc.click(force=True, timeout=2000)
            except Exception as e2:
                print(f"[publisher] 弹窗确定按钮点击失败: {e2}")
                return
        # 等待弹窗消失（或 3s 超时）
        wait_end = time.time() + 3.0
        while time.time() < wait_end:
            try:
                if dialog_loc.count() == 0 or not dialog_loc.is_visible():
                    break
            except Exception:
                break
            time.sleep(0.2)
        print("[publisher]   已点编辑图片弹窗的确定按钮")

    @staticmethod
    def _price_to_diamond_tier(price_value: int) -> int:
        """按 mcdev 钻石档位表反推第X档。

        真实下拉项格式："第{X}档直购定价：{N}钻石"
        已知档位（按常见值）：300=1档，600=2档，1000=3档，2000=4档，3000=5档，5000=6档，10000=7档
        不在映射表里按价格大小顺序估算（兜底）。
        """
        price_value = int(price_value)
        tier_map = {
            100: 1, 200: 1, 300: 1,
            500: 2, 600: 2,
            800: 3, 1000: 3,
            1500: 4, 2000: 4,
            2500: 5, 3000: 5,
            4000: 6, 5000: 6,
            8000: 7, 10000: 7,
            15000: 8, 20000: 8,
        }
        if price_value in tier_map:
            return tier_map[price_value]
        # 兜底：按顺序找最近档（每档大约翻倍递增）
        sorted_keys = sorted(tier_map.keys())
        for k in sorted_keys:
            if price_value <= k:
                return tier_map[k]
        return tier_map[sorted_keys[-1]] if sorted_keys else 1

    def _fill_quill_editor(self, editor_loc, text: str, timeout: float = 3.0):
        """在 Quill editor (div.ql-editor[contenteditable=true]) 里写入文本 + 换行。"""
        try:
            editor_loc.scroll_into_view_if_needed(timeout=3000)
            time.sleep(0.25)
            editor_loc.click()
            time.sleep(0.2)
            # 全选清空
            self._page.keyboard.press("Control+a")
            time.sleep(0.08)
            self._page.keyboard.press("Delete")
            time.sleep(0.1)
            lines = text.split("\n")
            for j, line in enumerate(lines):
                if line:
                    self._page.keyboard.type(line)
                if j < len(lines) - 1:
                    self._page.keyboard.press("Shift+Enter")
            return True
        except Exception as e:
            print(f"[publisher]   Quill editor 写入失败: {e}")
            return False

    def _insert_quill_image(self, editor_index: int, image_paths: list[str | Path]):
        """在 Quill 编辑器内部插入本地图片（先填文本，后插图）。

        editor_index=0 → PE详情信息（第一个 .ql-toolbar + .ql-editor）
        editor_index=1 → PC详情信息（第二个）
        真实交互（按用户指定）：
          1. 光标 focus 到 editor 的正文末尾
          2. 点该编辑器 toolbar 内的 <button>（image SVG 图标）→ 弹文件选择
          3. 给 filechooser / 隐藏 input[type=file] 塞第一张图（渲染图 final.png）
          4. 再点一次同一个 image button → 塞第二张图（宣传图 promo_image）
        """
        if not image_paths:
            return True
        # 1. 取第 N 个 ql-toolbar（与 ql-editor 一一对应，严格同序）
        btns = self._page.locator(config.SELECTORS["quill_image_button"])
        total_btns = btns.count()
        print(f"[publisher]   页面共有 {total_btns} 个 Quill 图片按钮；本次用 editor_index={editor_index}")
        if total_btns <= editor_index:
            # 兜底：直接取所有 ql-image-button 的最后一个可用的 or nth(editor_index)
            try:
                all_toolbar_btns = self._page.locator(
                    "div.ql-toolbar button, .ql-toolbar .ql-image, .toolbar button svg"
                )
                if all_toolbar_btns.count() > editor_index:
                    btns = all_toolbar_btns
            except Exception:
                pass
        # 2. focus 到对应 editor 正文（先点最后一个 <p> 确保光标在末尾，再回车）
        try:
            editors = self._page.locator("div.ql-editor[contenteditable='true']")
            if editors.count() > editor_index:
                editor = editors.nth(editor_index)
                editor.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.2)
                # 点击 editor 内最后一个 <p> 元素，确保光标在正文最末尾
                last_p = editor.locator("p").last
                if last_p.count() > 0:
                    last_p.click()
                    time.sleep(0.1)
                else:
                    editor.click()
                    time.sleep(0.1)
                # 在末尾按 Enter 回车，确保图片在新段落
                self._page.keyboard.press("End")
                self._page.keyboard.press("Enter")
                time.sleep(0.1)
        except Exception as e:
            print(f"[publisher]   Quill 正文聚焦失败（继续尝试插图）: {e}")

        # 3. 对每一张图：点 button → 监听 filechooser → set_files
        all_ok = True
        for k, img in enumerate(image_paths):
            img_path = str(Path(img).resolve())
            if not Path(img_path).is_file():
                print(f"[publisher]   图#{k+1} 文件不存在，跳过: {img_path}")
                all_ok = False
                continue
            try:
                btn = btns.nth(editor_index) if btns.count() > editor_index else btns.last
            except Exception:
                btn = btns.first
            try:
                btn.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.2)
            except Exception:
                pass
            print(f"[publisher]   插入详情图#{k+1}: {Path(img_path).name}")
            inserted = False
            # —— 策略 A：监听 filechooser + 点 button（最优先）
            try:
                with self._page.expect_file_chooser(timeout=5000) as fc_info:
                    try:
                        btn.click(timeout=3000)
                    except Exception:
                        btn.click(force=True, timeout=2500)
                fc = fc_info.value
                fc.set_files(img_path)
                inserted = True
                print("[publisher]     已通过 filechooser 插图")
            except Exception as e_a:
                # —— 策略 B：找隐藏的 input[type=file]（点击 image 按钮后一般会临时出现）
                try:
                    print(f"[publisher]     filechooser 策略未触发({e_a})，改用隐藏 input[type=file]...")
                    before_inp = self._page.locator("input[type='file']").count()
                    try:
                        btn.click(force=True, timeout=2500)
                    except Exception:
                        pass
                    time.sleep(0.4)
                    after_inp = self._page.locator("input[type='file']").count()
                    # 如果点击后新增了 file input，就 set 它
                    target_inp = None
                    if after_inp > before_inp:
                        target_inp = self._page.locator("input[type='file']").nth(after_inp - 1)
                    else:
                        # 兜底：在 ql-toolbar 或其相邻父节点里找 file input
                        try:
                            idx_in_container = self._page.evaluate("""(el) => {
                                let c = el;
                                for (let i = 0; i < 6 && c; i++) {
                                    const fs = c.querySelectorAll ? c.querySelectorAll("input[type='file']") : [];
                                    if (fs && fs.length) {
                                        const all = Array.from(document.querySelectorAll("input[type='file']"));
                                        const idx = all.indexOf(fs[fs.length - 1]);
                                        return idx >= 0 ? idx : -1;
                                    }
                                    c = c.parentElement || c.parentNode;
                                }
                                return -1;
                            }""", btn.element_handle())
                            if int(idx_in_container) >= 0:
                                target_inp = self._page.locator("input[type='file']").nth(int(idx_in_container))
                        except Exception:
                            target_inp = None
                    if target_inp is None:
                        # 最后兜底：最后一个 file input
                        cnt = self._page.locator("input[type='file']").count()
                        if cnt > 0:
                            target_inp = self._page.locator("input[type='file']").nth(cnt - 1)
                    if target_inp is not None:
                        target_inp.set_input_files(img_path)
                        inserted = True
                        print("[publisher]     已通过隐藏 input[type=file] 插图")
                except Exception as e_b:
                    print(f"[publisher]     隐藏 input 策略也失败: {e_b}")
            # 等 Quill 把图渲染进 DOM（或等 1.3s）
            if inserted:
                time.sleep(1.3)
            else:
                all_ok = False
            # 下一张图插入前：点 editor 内最后一个 <p> 确保光标在末尾，再按 Enter 换行
            try:
                editors = self._page.locator("div.ql-editor[contenteditable='true']")
                if editors.count() > editor_index:
                    ed = editors.nth(editor_index)
                    last_p = ed.locator("p").last
                    if last_p.count() > 0:
                        last_p.click()
                    else:
                        ed.click()
                    time.sleep(0.05)
                    self._page.keyboard.press("End")
                    self._page.keyboard.press("Enter")
                    time.sleep(0.08)
            except Exception:
                pass
        return all_ok

    def _ensure_login(self):
        url = self._page.url
        if "login" in url.lower() or self._page.locator("input[type='password']").count() > 0:
            print(f"[publisher] 账号 {self.account} 需要登录，请在浏览器中手动登录。")
            print("[publisher] 登录完成后回到终端按回车继续...")
            input()

    # ============================================================
    # 主流程（严格按用户指定字段操作，其余不动）
    # ============================================================
    def navigate_to_publish(self):
        print("\n[publisher] 导航到发布新资源页")
        # 直接打开新建页
        self._page.goto(config.MCDEV_HOME_URL, wait_until="domcontentloaded")
        self._ensure_login()
        time.sleep(1.5)
        # 点「上架与资源管理」→ 「发布新资源」
        self._click_any(config.SELECTORS["nav_content_mgmt"], timeout=6000)
        time.sleep(0.8)
        if not self._click_any(config.SELECTORS["nav_publish_new"], timeout=6000):
            self._page.goto(config.MCDEV_EDIT_URL.replace(
                "4689431348426443454", "new"), wait_until="domcontentloaded")
            self._ensure_login()
        time.sleep(2.0)  # 给 SPA 渲染

    def fill_form(self, name: str, price_type: str, price_value: int,
                  description: str, arm_type: str,
                  final_image: str = None,
                  promo_image: str = None):
        """填写表单（按从上到下顺序，每项滚动到位再操作）。

        关键：PC基本信息和PC详情信息只有在点"是否同步生成PC模组=是"后才出现。
        """
        # 1. 资源名称
        print("\n[publisher] [1/9] 填资源名称")
        self._fill_any(config.SELECTORS["input_name"], name)

        # 2. 是否原创作品 → 是
        print("\n[publisher] [2/9] 是否原创作品 → 是")
        self._click_any(config.SELECTORS["radio_original_yes"], timeout=6000)

        # 3. 是否同步生成PC模组 → 是（点完后PC基本信息/PC详情信息才会出现）
        print("\n[publisher] [3/9] 是否同步生成PC模组 → 是")
        self._click_any(config.SELECTORS["radio_sync_pc_yes"], timeout=6000)

        # 等待 PC模组标签 字段出现（确认PC区域已展开）
        print("[publisher]   等待PC基本信息字段出现...")
        try:
            self._page.locator(
                ".el-form-item:has-text('PC模组标签')"
            ).first.wait_for(state="visible", timeout=8000)
            print("[publisher]   PC基本信息字段已出现")
        except Exception:
            print("[publisher]   警告：PC模组标签字段未出现，继续尝试...")

        # 4. PC模组标签 → 休闲（点开下拉直接选）
        print("\n[publisher] [4/9] PC模组标签 → 休闲")
        self._select_dropdown(
            config.SELECTORS["select_pc_tag"],
            config.SELECTORS["option_pc_tag_casual"],
            timeout=8000,
        )

        # 5. PC模组简介 → 皮肤资源
        print("\n[publisher] [5/9] PC模组简介 → 皮肤资源")
        self._fill_any(config.SELECTORS["input_pc_intro"], "皮肤资源")

        # 6. 定价（钻石/绿宝石/免费）
        print(f"\n[publisher] [6/9] 定价类型 → {price_type}")
        radio_map = {
            "diamond": config.SELECTORS["radio_price_diamond"],
            "emerald": config.SELECTORS["radio_price_emerald"],
            "free": config.SELECTORS["radio_price_free"],
        }
        target_radio = radio_map.get(price_type, config.SELECTORS["radio_price_diamond"])
        self._click_any(target_radio, timeout=6000)

        if price_type == "diamond":
            # 钻石档位：直接按索引点选（300=第1个, 600=第2个, 1000=第3个...）
            # 下拉框 data-trae-ref='e249'，选项是 .el-select-dropdown__item 列表
            time.sleep(0.6)
            tier_index = self._price_to_diamond_tier(price_value)
            item_index = tier_index - 1  # 转为 0-based 索引
            print(f"[publisher]   选钻石档位（{price_value}钻石 → 第{tier_index}档 → 下拉第{item_index+1}项）")
            self._select_dropdown_by_index(
                config.SELECTORS["select_price_tier"],
                item_index,
                timeout=6000,
            )
        elif price_type == "emerald":
            # 绿宝石：预设值是10，每点一下加10按钮 +10
            # 10绿宝石不动；30绿宝石点2下；100绿宝石点9下
            time.sleep(0.3)
            clicks_needed = (price_value - 10) // 10
            if clicks_needed <= 0:
                print(f"[publisher]   绿宝石数量=10（预设值，无需修改）")
            else:
                print(f"[publisher]   绿宝石数量 → {price_value}（点+按钮 {clicks_needed} 下）")
                try:
                    # 定位 + 按钮：span.el-input-number__increase
                    increase_btn = self._page.locator(
                        "span.el-input-number__increase"
                    ).first
                    if increase_btn.count() == 0:
                        # 兜底：定价区域内的 + 按钮
                        increase_btn = self._page.locator(
                            ".el-form-item:has-text('价格') span.el-input-number__increase"
                        ).first
                    increase_btn.scroll_into_view_if_needed(timeout=3000)
                    time.sleep(0.2)
                    for _ in range(clicks_needed):
                        increase_btn.click()
                        time.sleep(0.1)
                    print(f"[publisher]   绿宝石数量设置成功: {price_value}")
                except Exception as e:
                    print(f"[publisher]   绿宝石数量设置失败: {e}")

        # 7. PE详情信息 → 填长简介文本 + 插图（渲染图1张 + 宣传图1张）
        print("\n[publisher] [7/9] PE详情信息 → 填预设模板 + 插图")
        self._fill_pe_detail(description)
        if final_image:
            images_pe = [final_image] + ([promo_image] if promo_image else [])
            print(f"[publisher]   → 在 PE详情信息 插入 {len(images_pe)} 张图")
            self._insert_quill_image(editor_index=0, image_paths=images_pe)

        # 8. PC详情信息 → 填长简介文本 + 插图（渲染图1张 + 宣传图1张）
        print("\n[publisher] [8/9] PC详情信息 → 填预设模板 + 插图")
        self._fill_pc_detail(description)
        if final_image:
            images_pc = [final_image] + ([promo_image] if promo_image else [])
            print(f"[publisher]   → 在 PC详情信息 插入 {len(images_pc)} 张图")
            self._insert_quill_image(editor_index=1, image_paths=images_pc)

    def _fill_pe_detail(self, description: str):
        """填 PE详情信息（Quill 富文本编辑器，div.ql-editor[contenteditable=true]）。

        真实DOM：
          <div class="ql-editor" contenteditable="true" data-placeholder="在这里输入内容">
        页面共 2 个 .ql-editor：nth(0) = PE详情信息，nth(1) = PC详情信息
        """
        try:
            editors = self._page.locator("div.ql-editor[contenteditable='true']")
            count = editors.count()
            print(f"[publisher]   找到 {count} 个 Quill 编辑器 (div.ql-editor)")
            if count == 0:
                print("[publisher]   未找到 Quill 编辑器，PE详情信息跳过")
                return
            editor = editors.nth(0)  # 第1个 = PE详情信息
            ok = self._fill_quill_editor(editor, description)
            if ok:
                print("[publisher]   PE详情信息填写成功")
            else:
                # 兜底：第0个 contenteditable
                editors2 = self._page.locator("[contenteditable='true']")
                if editors2.count() > 0:
                    self._fill_quill_editor(editors2.nth(0), description)
                    print("[publisher]   PE详情信息填写成功（兜底）")
        except Exception as e:
            print(f"[publisher]   PE详情信息填写失败: {e}")

    def _fill_pc_detail(self, description: str):
        """填 PC详情信息（Quill 富文本编辑器，div.ql-editor[contenteditable=true]）。

        真实DOM：同 PE详情信息，nth(1) = PC详情信息
        """
        try:
            editors = self._page.locator("div.ql-editor[contenteditable='true']")
            count = editors.count()
            print(f"[publisher]   找到 {count} 个 Quill 编辑器 (div.ql-editor)")
            if count < 2:
                print("[publisher]   Quill 编辑器数量不够，兜底用最后一个 contenteditable")
                editors2 = self._page.locator("[contenteditable='true']")
                if editors2.count() > 0:
                    editor = editors2.nth(editors2.count() - 1)
                    self._fill_quill_editor(editor, description)
                    print("[publisher]   PC详情信息填写成功（兜底）")
                return
            editor = editors.nth(1)  # 第2个 = PC详情信息
            ok = self._fill_quill_editor(editor, description)
            if ok:
                print("[publisher]   PC详情信息填写成功")
        except Exception as e:
            print(f"[publisher]   PC详情信息填写失败: {e}")

    def select_body_type(self, arm_type: str):
        """体型：Slim=细 / 标准=粗。
        真实点击元素都是 span.el-radio__inner（已在 config 选择器内优先配置）。
        """
        print(f"\n[publisher] 体型 → {'Slim(细)' if arm_type == 'thin' else '标准(粗)'}")
        if arm_type == "thin":
            self._click_any(config.SELECTORS["radio_body_slim"], timeout=6000)
        else:
            self._click_any(config.SELECTORS["radio_body_standard"], timeout=6000)

    def select_pe_category(self):
        """PE资源管理 内：资源类别 → 主类别=皮肤，次类别=原版风格。
        真实DOM：
          主类别 <input placeholder="请选择主类别" readonly> → <li><span>皮肤</span></li>
          次类别 <input placeholder="请选择次类别" readonly> → <li><span>原版风格</span></li>
        """
        print("\n[publisher] PE资源管理 → 资源类别")
        time.sleep(0.2)
        # 主类别=皮肤（两步：input → span）
        print("[publisher]   主类别 → 皮肤")
        self._select_dropdown(
            config.SELECTORS["select_category_main"],
            config.SELECTORS["option_category_skin"],
            timeout=6000,
            confirm_step=False,
        )
        time.sleep(0.15)
        # 次类别=原版风格（两步：input → span）
        print("[publisher]   次类别 → 原版风格")
        self._select_dropdown(
            config.SELECTORS["select_category_sub"],
            config.SELECTORS["option_category_vanilla"],
            timeout=6000,
            confirm_step=False,
        )

    def upload_files(self, source_skin_png: str, final_image: str, promo_image: str = None):
        """
        上传文件：
          #0 皮肤源文件：先点 <i title="点击上传包体" class="el-icon-plus avatar-uploader-icon"> 触发，再给它关联的 input[type=file] 塞 png
          #1 资源包 zip（不动，跳过）
          #2..N 其他所有尺寸：全部传 final.png（1000×1000 渲染结果图），上传完每张自动点"编辑图片弹窗确定"
        """
        print("\n[publisher] 文件上传")

        # 滚动到上传区
        try:
            self._page.evaluate("window.scrollTo(0, Math.min(document.body.scrollHeight*0.6, 6500))")
            time.sleep(0.5)
            # 先滚动到皮肤包体上传图标（保证可见）
            trig = self._page.locator(config.SELECTORS["skin_upload_trigger"]).first
            trig.scroll_into_view_if_needed(timeout=4000)
            time.sleep(0.3)
        except Exception:
            pass

        total = self._page.locator("input[type='file']").count()
        print(f"[publisher]   页面共有 {total} 个文件上传框")

        if total < 1:
            print("[publisher] 没找到文件上传框")
            return

        # —— 皮肤源文件：定位 i[title=点击上传包体] 所在的 div.el-upload 内的 input[type=file] ——
        # 真实DOM结构（e250）:
        #   <div class="Up">
        #     <div class="Upcon">
        #       <div class="avatar-uploader">
        #         <div class="el-upload" data-trae-ref="e250">
        #           <i title="点击上传包体" class="el-icon-plus avatar-uploader-icon"></i>
        #           <input type="file" name="fpfile" class="el-upload__input">  ← 和 i 是兄弟元素
        #         </div>
        #       </div>
        #     </div>
        #     <div class="Uplimit"><p>固定大小，宽*高：64*64、128*128</p>...</div>
        #   </div>
        # Element UI avatar-uploader 不弹系统对话框，直接给隐藏 input[type=file] 设文件即可
        print(f"[publisher]   [皮肤源文件] → {Path(source_skin_png).name}")
        skin_ok = False
        try:
            # 精确定位：i[title=点击上传包体] 所在的 div.el-upload 内的 input[type=file]
            skin_file_input = self._page.locator(
                "div.el-upload:has(i[title='点击上传包体']) input[type='file']"
            ).first
            if skin_file_input.count() > 0:
                skin_file_input.set_input_files(source_skin_png)
                skin_ok = True
                print("[publisher]   皮肤源文件已上传（i[title=点击上传包体] 同级 input[type=file]）")
            else:
                # 兜底1：从 i 向上找祖先 div.el-upload，再找里面的 input
                trigger = self._page.locator(config.SELECTORS["skin_upload_trigger"]).first
                trigger.scroll_into_view_if_needed(timeout=4000)
                time.sleep(0.2)
                idx = self._page.evaluate("""(el) => {
                    let cur = el;
                    for (let i = 0; i < 6 && cur; i++) {
                        const fs = cur.querySelectorAll ? cur.querySelectorAll("input[type='file']") : [];
                        if (fs && fs.length) {
                            const all = Array.from(document.querySelectorAll("input[type='file']"));
                            return all.indexOf(fs[0]);
                        }
                        cur = cur.parentElement || cur.parentNode;
                    }
                    return -1;
                }""", trigger.element_handle())
                if int(idx) >= 0:
                    self._page.locator("input[type='file']").nth(int(idx)).set_input_files(source_skin_png)
                    skin_ok = True
                    print(f"[publisher]   皮肤源文件已上传（祖先容器内 input#{idx}）")
                else:
                    # 兜底2：filechooser
                    trigger.click(force=True)
                    time.sleep(0.3)
                    self._page.locator("input[type='file']").nth(0).set_input_files(source_skin_png)
                    skin_ok = True
                    print("[publisher]   皮肤源文件已上传（兜底第0个 input）")
            # 皮肤源文件一般不弹编辑图片弹窗
            time.sleep(1.0)
            self._confirm_image_crop_dialog(timeout_sec=2.0)
        except Exception as e:
            print(f"[publisher]   皮肤源文件上传异常: {e}")
        if not skin_ok:
            print("[publisher]   皮肤源文件走兜底 _set_file_at_index(0)")
            self._set_file_at_index(source_skin_png, 0)

        # —— 所有尺寸图：一个个点 <i title="点击上传文件" class="el-icon-plus avatar-uploader-icon"> 传 final.png
        # 每传一张就弹编辑图片弹窗 → 点 <div class="btn-item btn-text text-confirm">确定</div>
        triggers = self._page.locator(config.SELECTORS["image_upload_trigger"])
        trig_count = triggers.count()
        print(f"[publisher]   找到 {trig_count} 个图片上传触发器 <i title='点击上传文件'>")
        if trig_count == 0:
            # 兜底：还是老办法按 index 上传
            print("[publisher]   找不到触发器，按 input[type=file]#2..N 兜底")
            uploaded_count = 0
            for i in range(2, total):
                print(f"[publisher]   [上传#{i}] → {Path(final_image).name}")
                ok = self._set_file_at_index(final_image, i)
                if ok:
                    uploaded_count += 1
                if uploaded_count >= 12:
                    break
        else:
            uploaded_count = 0
            max_upload = max(12, trig_count)  # 全传完
            for k in range(trig_count):
                if uploaded_count >= max_upload:
                    break
                try:
                    trig = triggers.nth(k)
                    # 如果当前图标已经不可见（比如该位置已经上传图片后被替换成缩略图了）就跳过
                    if trig.count() == 0 or not trig.is_visible():
                        # 重新取一次最新列表（DOM可能变了）
                        triggers = self._page.locator(config.SELECTORS["image_upload_trigger"])
                        if k >= triggers.count():
                            break
                        trig = triggers.nth(k)
                        if trig.count() == 0 or not trig.is_visible():
                            continue
                    trig.scroll_into_view_if_needed(timeout=3000)
                    time.sleep(0.15)
                    print(f"[publisher]   [图#{k+1}] → {Path(final_image).name}")
                    # 用 expect_file_chooser 拦截系统弹窗，使其不显示
                    uploaded_via_fc = False
                    try:
                        with self._page.expect_file_chooser(timeout=5000) as fc_info:
                            trig.click(force=True)
                        fc = fc_info.value
                        fc.set_files(final_image)
                        uploaded_via_fc = True
                        print("[publisher]     已通过 filechooser 上传（弹窗已拦截）")
                    except Exception:
                        pass
                    # 如果 filechooser 没触发，走隐藏 input[type=file] 方式
                    if not uploaded_via_fc:
                        before = self._page.locator("input[type='file']").count()
                        time.sleep(0.25)
                        after = self._page.locator("input[type='file']").count()
                        img_input = None
                        try:
                            target_idx = self._page.evaluate("""(el) => {
                                let cur = el;
                                for (let i = 0; i < 8 && cur; i++) {
                                    const found = cur.querySelectorAll ? cur.querySelectorAll("input[type='file']") : [];
                                    if (found && found.length) {
                                        const all = Array.from(document.querySelectorAll("input[type='file']"));
                                        const idx = all.indexOf(found[0]);
                                        return idx >= 0 ? idx : 0;
                                    }
                                    cur = cur.parentElement || cur.parentNode;
                                }
                                if (after > before) return after - 1;
                                return Math.min(before - 1, Math.max(2, before));
                            }""", trig.element_handle())
                            idx = int(target_idx) if target_idx is not None else 2 + uploaded_count
                            img_input = self._page.locator("input[type='file']").nth(idx)
                        except Exception:
                            idx = min(2 + uploaded_count, self._page.locator("input[type='file']").count() - 1)
                            img_input = self._page.locator("input[type='file']").nth(max(idx, 0))
                        try:
                            img_input.set_input_files(final_image)
                        except Exception as ie:
                            time.sleep(0.8)
                            try:
                                img_input.set_input_files(final_image)
                            except Exception as ie2:
                                idx_fallback = min(2 + uploaded_count, self._page.locator("input[type='file']").count() - 1)
                                self._set_file_at_index(final_image, max(idx_fallback, 0))
                    # 等编辑图片弹窗出现 + 点确定
                    time.sleep(1.3)
                    self._confirm_image_crop_dialog(timeout_sec=6.0)
                    uploaded_count += 1
                    # 重新取 triggers，因为DOM结构可能变化（当前位置被缩略图替代，新加号出现在后面）
                    triggers = self._page.locator(config.SELECTORS["image_upload_trigger"])
                except Exception as e:
                    print(f"[publisher]   [图#{k+1}] 上传异常: {e}")
                    continue
            print(f"[publisher]   图片上传完成，共 {uploaded_count} 张")

    def save_or_submit(self) -> bool:
        """先点"保存"（更安全，不直接提审）。"""
        time.sleep(1.0)
        print("\n[publisher] 点击 保存 ...")
        ok = self._click_any(config.SELECTORS["btn_save"], timeout=10000, scroll=True)
        if ok:
            try:
                self._page.wait_for_selector(
                    config.SELECTORS["success_toast"], timeout=20000)
                print("[publisher] 保存成功！可以在浏览器里手动检查后点'提交审核'。")
            except Exception:
                print("[publisher] 已点击保存，但未捕获保存成功提示，请到浏览器确认。")
        return ok

    def publish(self, name: str, price_type: str, price_value: int,
                description: str, arm_type: str,
                source_skin_png: str,
                final_image: str,
                promo_image: str = None) -> bool:
        """完整流程。"""
        self.navigate_to_publish()
        self.fill_form(name, price_type, price_value, description, arm_type,
                       final_image=final_image, promo_image=promo_image)
        self.select_pe_category()
        self.select_body_type(arm_type)
        self.upload_files(source_skin_png, final_image, promo_image)
        # 上传完所有图片后：点"适用范围"→"客户端" radio
        print("\n[publisher] 点击 适用范围 → 客户端")
        self._click_any(config.SELECTORS["radio_client_scope"], timeout=6000, scroll=True)
        time.sleep(0.5)
        # 点保存
        return self.save_or_submit()


# ============================================================
# 账号管理
# ============================================================
def list_accounts() -> list[str]:
    return config.list_accounts()


def add_account(name: str, headless: bool = False):
    """创建/登录一个新账号：打开浏览器，手动登录后关闭即保存登录态。"""
    from playwright.sync_api import sync_playwright
    profile_dir = config.get_account_dir(name)
    print(f"[add_account] 创建账号 '{name}'，profile: {profile_dir}")
    print(f"[add_account] 浏览器将打开 mcdev，请手动登录后关闭浏览器窗口以保存登录态。")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1440, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(config.MCDEV_HOME_URL)
        print(f"[add_account] 已打开 mcdev。登录账号 '{name}' 后关闭浏览器窗口即可。")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        context.close()
    print(f"[add_account] 账号 '{name}' 已保存。")


def inspect(account: str = config.DEFAULT_ACCOUNT):
    """打开浏览器手动走一遍发布流程，辅助校准选择器。"""
    from playwright.sync_api import sync_playwright
    profile_dir = config.get_account_dir(account)
    print(f"[inspect] 账号: {account}  profile: {profile_dir}")
    print("[inspect] 在浏览器中操作发布表单，记录选择器后回填 config.SELECTORS")
    print("[inspect] 完成后关闭浏览器窗口结束校准。")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1440, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(config.MCDEV_HOME_URL)
        print("[inspect] 浏览器已打开，请手动操作。关闭浏览器结束校准。")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        context.close()
