# -*- coding: utf-8 -*-
"""网易邮箱网页端「云端定时发信」—— 电脑关机也能发。

原理：SMTP 协议本身没有"定时"概念，网易 SMTP 也不在云端存定时任务。
但网易**网页版**邮箱（写信界面）的「定时发信」会把邮件存到网易云端
（草稿箱/定时发信列表），到点由网易服务器自动发出 —— 与电脑是否开机无关。

本模块用 Playwright（与 publisher.py 同一套路）自动完成：
  登录（持久化 profile 复用登录态）→ 写信 → 填收件人/主题/正文（文本行 + slogan 图）
  /附件（渲染图）→ 开启「定时发信」选择时间 → 点发送。排好即退出。

选器采用「语义 + 备选」写法（真实 DOM 以 qiye.163.com 为准），首次使用需：
  ① python email_sender.py --add-mail-account   （手动登录一次，保存登录态）
  ② python email_sender.py --inspect-mail       （手动写一封带定时发信的信，校准选器）
"""
from __future__ import annotations

import datetime
import time
from pathlib import Path

import config


class WebmailScheduler:
    def __init__(self, headless: bool = False, slow_mo: int = 300,
                 profile_dir: str | Path | None = None):
        self.headless = headless
        self.slow_mo = slow_mo
        self.profile_dir = Path(profile_dir) if profile_dir else config.MAIL_PROFILE_DIR
        self._playwright = None
        self._context = None
        self._page = None

    # ---------- 生命周期 ----------
    def start(self):
        from playwright.sync_api import sync_playwright
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1440, "height": 900},
            args=[
                "--start-maximized",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--memory-pressure-off",
            ],
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        print(f"[webmail] 邮件浏览器 profile: {self.profile_dir}")
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
        for sel in [s.strip() for s in selector_csv.split(",") if s.strip()]:
            try:
                loc = self._page.locator(sel).first
                loc.wait_for(state="visible", timeout=4000)
                loc.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.3)
                return
            except Exception:
                continue

    def _resolve_first(self, selector_csv: str):
        """从逗号分隔的选择器列表里找第一个命中且可见的元素，返回 locator.first；找不到返回 None"""
        for sel in [s.strip() for s in selector_csv.split(",") if s.strip()]:
            try:
                loc = self._page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    return loc
            except Exception:
                continue
        return None

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
                print(f"[webmail] 点击成功: {sel[:80]}")
                return True
            except Exception:
                continue
        print(f"[webmail] 点击失败: {selector_csv[:80]}")
        return False

    def _fill_any(self, selector_csv: str, value: str, timeout: int = 8000) -> bool:
        self._scroll_to_field(selector_csv)
        for sel in [s.strip() for s in selector_csv.split(",") if s.strip()]:
            try:
                loc = self._page.locator(sel).first
                loc.wait_for(state="visible", timeout=timeout)
                loc.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.2)
                try:
                    loc.fill("")
                    loc.fill(value)
                except Exception:
                    loc.click()
                    self._page.keyboard.press("Control+a")
                    self._page.keyboard.type(value)
                print(f"[webmail] 填写成功: {sel[:80]}")
                return True
            except Exception:
                continue
        print(f"[webmail] 填写失败: {selector_csv[:80]}")
        return False

    def _fill_rich_editor(self, lines: list[str], separator: str = "Shift+Enter") -> bool:
        """在正文富文本编辑器里写入文本行（行间用 separator）。

        网易正文编辑器可能是 iframe（locator.fill 对 iframe 无效），
        故统一：聚焦编辑区 → Control+A 清空 → 逐行 keyboard.type。
        """
        for sel in [s.strip() for s in config.MAIL_SELECTORS["editor_body"].split(",") if s.strip()]:
            try:
                loc = self._page.locator(sel).first
                loc.wait_for(state="visible", timeout=6000)
                target = loc
                # iframe 情况：取内部 body
                try:
                    frame = loc.content_frame()
                    if frame:
                        body = frame.locator("body").first
                        if body.count() > 0:
                            target = body
                except Exception:
                    pass
                target.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.25)
                target.click()
                time.sleep(0.2)
                self._page.keyboard.press("Control+a")
                time.sleep(0.08)
                self._page.keyboard.press("Delete")
                time.sleep(0.1)
                for i, line in enumerate(lines):
                    if line:
                        self._page.keyboard.type(line)
                    if i < len(lines) - 1:
                        self._page.keyboard.press(separator)
                print("[webmail] 正文已填写")
                return True
            except Exception as e:
                print(f"[webmail] 正文编辑器尝试失败({sel[:60]}): {e}")
                continue
        print("[webmail] 正文编辑器未找到（选器需校准 editor_body）")
        return False

    def _upload_via_filechooser(self, btn_selector: str, file_path: str, label: str) -> bool:
        """监听 filechooser + 点按钮上传文件（与 publisher 相同策略）。"""
        file_path = str(Path(file_path).resolve())
        if not Path(file_path).is_file():
            print(f"[webmail] {label} 文件不存在，跳过: {file_path}")
            return False
        for sel in [s.strip() for s in btn_selector.split(",") if s.strip()]:
            try:
                btn = self._page.locator(sel).first
                btn.wait_for(state="visible", timeout=4000)
                btn.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.2)
                with self._page.expect_file_chooser(timeout=5000) as fc_info:
                    try:
                        btn.click(timeout=3000)
                    except Exception:
                        btn.click(force=True, timeout=2500)
                fc = fc_info.value
                fc.set_files(file_path)
                time.sleep(1.5)  # 等网易上传进度条跑完
                print(f"[webmail] {label} 已上传: {Path(file_path).name}")
                return True
            except Exception:
                continue
        print(f"[webmail] {label} 上传失败（未触发文件选择）: {Path(file_path).name}")
        return False

    # ---------- 登录 / 导航 ----------
    def _ensure_login(self, prompt: bool = False) -> bool:
        """确保网页版邮箱已登录。

        prompt=False（调度路径）：未登录直接返回 False，让调用方回退；
        prompt=True（手动登录/校准路径）：阻塞等待用户手动登录。
        """
        try:
            self._page.goto(config.MAIL_WEB_URL, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"[webmail] 打开邮箱失败: {e}")
            return False
        time.sleep(2.0)

        if self._resolve_first(config.MAIL_SELECTORS["mail_logged_in"]):
            print("[webmail] 已登录网易邮箱")
            return True
        if self._resolve_first(config.MAIL_SELECTORS["mail_login_page"]):
            if not prompt:
                print("[webmail] 邮箱网页端未登录。请先运行: python email_sender.py --add-mail-account")
                return False
            print("[webmail] 请在浏览器中手动登录（含验证码），完成后回到终端按回车继续...")
            input()
            return True
        # 无法判断登录态：按已登录继续，让后续步骤暴露问题
        print("[webmail] 未检测到明确的登录页，按已登录继续")
        return True

    def _navigate_to_compose(self) -> bool:
        if config.MAIL_COMPOSE_URL:
            try:
                self._page.goto(config.MAIL_COMPOSE_URL, wait_until="domcontentloaded", timeout=45000)
                time.sleep(2.0)
                if self._resolve_first(config.MAIL_SELECTORS["input_to"]):
                    return True
            except Exception as e:
                print(f"[webmail] 直达写信页失败({e})，改为点击「写信」")
        if not self._click_any(config.MAIL_SELECTORS["btn_write_mail"], timeout=10000):
            print("[webmail] 未找到「写信」按钮（选器需校准 btn_write_mail）")
            return False
        time.sleep(2.0)
        if not self._resolve_first(config.MAIL_SELECTORS["input_to"]):
            print("[webmail] 写信页未出现收件人输入框（选器需校准 input_to）")
            return False
        return True

    # ---------- 写信字段 ----------
    def _fill_to(self, to_emails: list[str]) -> bool:
        loc = self._resolve_first(config.MAIL_SELECTORS["input_to"])
        if loc is None:
            print("[webmail] 收件人输入框未找到（选器需校准 input_to）")
            return False
        try:
            loc.scroll_into_view_if_needed(timeout=3000)
            time.sleep(0.2)
            loc.click()
            time.sleep(0.2)
            for addr in to_emails:
                self._page.keyboard.type(addr)
                time.sleep(0.3)
                self._page.keyboard.press("Enter")  # 网易逐个地址用回车确认
                time.sleep(0.3)
            print(f"[webmail] 收件人已填写: {', '.join(to_emails)}")
            return True
        except Exception as e:
            print(f"[webmail] 收件人填写失败: {e}")
            return False

    def _fill_subject(self, subject: str) -> bool:
        return self._fill_any(config.MAIL_SELECTORS["input_subject"], subject, timeout=6000)

    def _insert_inline_image(self, image_path: str | Path | None) -> bool:
        """正文底部插入 slogan 图。缺图/失败仅警告，不中断排定。"""
        if not image_path or not Path(image_path).is_file():
            return True
        ok = self._upload_via_filechooser(
            config.MAIL_SELECTORS["btn_insert_image"], str(image_path), "slogan 内嵌图"
        )
        if not ok:
            print("[webmail] 警告：slogan 图未插入（不影响定时排定）")
        return True

    def _attach_file(self, file_path: str | Path) -> bool:
        """附加渲染图（审核结果的核心交付物，失败则中止排定）。"""
        return self._upload_via_filechooser(
            config.MAIL_SELECTORS["btn_attach"], str(file_path), "附件"
        )

    # ---------- 定时发信 ----------
    def _enable_timed_send(self, target: "datetime.datetime") -> bool:
        # 时间精确到分钟：有秒/微秒则顺延到下一分钟，保证云端不早发
        fire = target
        if fire.second or fire.microsecond:
            fire = fire + datetime.timedelta(minutes=1)
            fire = fire.replace(second=0, microsecond=0)

        # 1. 打开定时发信（部分版本藏在「更多选项」里）
        if not self._click_any(config.MAIL_SELECTORS["btn_timed_send"], timeout=6000):
            if not self._click_any(config.MAIL_SELECTORS["btn_more_options"], timeout=6000):
                print("[webmail] 未找到「定时发信/更多选项」入口（选器需校准）")
                return False
            time.sleep(0.5)
            if not self._click_any(config.MAIL_SELECTORS["option_timed_send"], timeout=6000):
                print("[webmail] 展开更多选项后未找到「定时发信」（选器需校准）")
                return False
        time.sleep(0.5)

        # 2. 日期（YYYY-MM-DD）
        date_str = fire.strftime("%Y-%m-%d")
        if not self._fill_any(config.MAIL_SELECTORS["timed_date_input"], date_str, timeout=6000):
            print("[webmail] 定时日期输入框未找到（--inspect-mail 校准 timed_date_input）")
            return False

        # 3. 时 / 分
        ok_hour = self._fill_any(config.MAIL_SELECTORS["timed_time_hour"], f"{fire.hour:02d}", timeout=4000)
        ok_min = self._fill_any(config.MAIL_SELECTORS["timed_time_min"], f"{fire.minute:02d}", timeout=4000)
        if not (ok_hour or ok_min):
            print("[webmail] 定时时分输入框未找到（--inspect-mail 校准 timed_time_hour/minute）")
            return False

        print(f"[webmail] 定时发送时间已设置: {fire:%Y-%m-%d %H:%M}")
        return True

    def _send(self) -> str:
        """点发送。返回三态：
        'scheduled' = 成功提示已确认，已排到网易云端；
        'uncertain' = 已点发送但未捕获成功提示，无法确认是否已排定；
        'failed'    = 发送按钮未点成，未提交任何内容。
        """
        if not self._click_any(config.MAIL_SELECTORS["btn_send"], timeout=8000):
            print("[webmail] 发送按钮未找到/无法点击，未提交任何内容")
            return "failed"

        # 部分版本点发送后会先弹「确定」确认框
        if config.MAIL_SELECTORS.get("btn_confirm_timed"):
            try:
                confirm = self._page.locator(config.MAIL_SELECTORS["btn_confirm_timed"]).first
                confirm.wait_for(state="visible", timeout=2500)
                confirm.click(timeout=3000)
            except Exception:
                pass

        try:
            self._page.wait_for_selector(config.MAIL_SELECTORS["success_toast"], timeout=15000)
            print("[webmail] ✓ 邮件已排定在网易云端定时发送")
            return "scheduled"
        except Exception:
            print("[webmail] 已点发送但未捕获成功提示，请到网页版「定时发信」列表核对")
            return "uncertain"

    # ---------- 主流程 ----------
    def schedule_email(self, to_emails: list[str], subject: str, body_lines: list[str],
                       target: "datetime.datetime",
                       final_image: str | Path | None = None,
                       cc_emails: list[str] | None = None) -> str:
        """排定网易云端定时发信。返回 'scheduled' / 'failed' / 'uncertain'。"""
        if not self._ensure_login(prompt=False):
            return "failed"
        if not self._navigate_to_compose():
            return "failed"
        if not self._fill_to(to_emails):
            return "failed"
        if cc_emails:
            if self._click_any(config.MAIL_SELECTORS["btn_cc"], timeout=4000):
                time.sleep(0.3)
                self._fill_any(config.MAIL_SELECTORS["input_cc"], ", ".join(cc_emails), timeout=4000)
            # 抄送失败不中断
        if not self._fill_subject(subject):
            return "failed"
        if not self._fill_rich_editor(body_lines):
            return "failed"
        self._insert_inline_image(config.SLOGAN_IMAGE_PATH)  # 非致命
        if final_image:
            if not self._attach_file(final_image):
                print("[webmail] 附件上传失败，本次排定中止")
                return "failed"
        if not self._enable_timed_send(target):
            return "failed"
        return self._send()


# ============================================================
# 账号管理 / 校准
# ============================================================
def add_mail_account(headless: bool = False):
    """首次登录网易邮箱并保存网页端登录态（云端定时发信前置步骤）。"""
    from playwright.sync_api import sync_playwright
    profile_dir = config.MAIL_PROFILE_DIR
    profile_dir.mkdir(parents=True, exist_ok=True)
    print(f"[add_mail_account] 邮箱 profile: {profile_dir}")
    print(f"[add_mail_account] 浏览器将打开 {config.MAIL_WEB_URL}，请手动登录后关闭浏览器窗口以保存登录态。")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1440, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(config.MAIL_WEB_URL)
        print("[add_mail_account] 已打开网易邮箱。登录账号后关闭浏览器窗口即可。")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        context.close()
    print("[add_mail_account] 邮箱登录态已保存。")


def inspect_mail(headless: bool = False):
    """校准模式：打开浏览器，手动写一封带定时发信的信，记录选择器后回填 config.MAIL_SELECTORS。"""
    from playwright.sync_api import sync_playwright
    profile_dir = config.MAIL_PROFILE_DIR
    profile_dir.mkdir(parents=True, exist_ok=True)
    print("[inspect_mail] 在浏览器中手动操作：写信 + 开「定时发信」，记录真实 DOM 选择器后回填 config.MAIL_SELECTORS")
    print("[inspect_mail] 完成后关闭浏览器窗口结束校准。")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1440, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(config.MAIL_WEB_URL)
        print("[inspect_mail] 浏览器已打开，请手动操作。关闭浏览器结束校准。")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        context.close()


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="网易邮箱网页端云端定时发信（独立测试）")
    ap.add_argument("--add-account", action="store_true", help="手动登录一次，保存网页端登录态")
    ap.add_argument("--inspect", action="store_true", help="校准写信/定时发信选择器")
    args = ap.parse_args()

    if args.add_account:
        add_mail_account()
        sys.exit(0)
    if args.inspect:
        inspect_mail()
        sys.exit(0)

    # 独立测试：排一封定时邮件
    sched = WebmailScheduler()
    state = "failed"
    try:
        sched.__enter__()
        try:
            state = sched.schedule_email(
                to_emails=["test@example.com"],
                subject="测试云端定时发信",
                body_lines=["资源名称：测试 - 作者", "内审评议意见：同意"],
                target=datetime.datetime.now() + datetime.timedelta(minutes=5),
            )
            print(f"[main] 排定结果: {state}")
        finally:
            sched.__exit__(None, None, None)
    except Exception as e:
        print(f"[main] 异常: {e}")
    sys.exit(0 if state == "scheduled" else 1)
