# -*- coding: utf-8 -*-
"""邮件发送模块：使用网易企业邮箱 SMTP 发送审核邮件。

支持 HTML 正文（内嵌 slogan 图） + 附件（渲染图），纯 Python 标准库实现。
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

import config


def build_message(
    sender_email: str,
    to_emails: list[str],
    subject: str,
    html_body: str,
    attachments: list[str | Path] | None = None,
    inline_images: dict[str, str | Path] | None = None,
    cc_emails: list[str] | None = None,
) -> MIMEMultipart:
    """构建邮件（HTML 正文 + 内嵌图片 + 可选附件 + 可选抄送）。

    Args:
        sender_email: 发件人
        to_emails: 收件人列表
        subject: 主题
        html_body: HTML 正文（内嵌图用 cid:xxx 引用）
        attachments: 附件路径列表
        inline_images: {cid名称: 图片路径}，如 {"slogan": "D:/logo/slogan.png"}
        cc_emails: 抄送列表
    """
    msg = MIMEMultipart("related")
    msg["From"] = formataddr((config.SENDER_NAME, sender_email))
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject
    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)

    # HTML 正文放在 alternative 里
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    # 内嵌图片（cid 引用）
    if inline_images:
        for cid_name, img_path in inline_images.items():
            img_path = Path(img_path)
            if not img_path.exists():
                print(f"[email_sender] 内嵌图片不存在，跳过: {img_path}")
                continue
            with open(img_path, "rb") as f:
                img_part = MIMEImage(f.read(), _subtype="png")
                img_part.add_header("Content-ID", f"<{cid_name}>")
                img_part.add_header(
                    "Content-Disposition", "inline", filename=img_path.name
                )
                msg.attach(img_part)

    # 普通附件
    if attachments:
        for path in attachments:
            path = Path(path)
            if not path.exists():
                print(f"[email_sender] 附件不存在，跳过: {path}")
                continue
            with open(path, "rb") as f:
                part = MIMEApplication(f.read(), Name=path.name)
                part.add_header(
                    "Content-Disposition", "attachment", filename=path.name
                )
                msg.attach(part)

    return msg


def send_email(
    msg: MIMEMultipart,
    sender_email: str,
    sender_password: str,
    smtp_server: str | None = None,
    smtp_port: int | None = None,
    use_ssl: bool | None = None,
) -> bool:
    """通过 SMTP 发送邮件。"""
    server = smtp_server or config.SMTP_SERVER
    port = smtp_port or config.SMTP_PORT
    ssl_mode = use_ssl if use_ssl is not None else config.SMTP_USE_SSL

    try:
        if ssl_mode:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(server, port, context=context) as smtp:
                smtp.login(sender_email, sender_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server, port) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(sender_email, sender_password)
                smtp.send_message(msg)

        recipients = [msg["To"]]
        if msg.get("Cc"):
            recipients.append(msg["Cc"])
        print(f"[email_sender] 邮件发送成功 → {', '.join(recipients)}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"[email_sender] 登录失败（SMTP 认证错误）: {e}")
        print(
            "[email_sender] 提示：网易企业邮箱需要在后台开启 SMTP 服务"
            "并设置客户端专用密码"
        )
        return False
    except Exception as e:
        print(f"[email_sender] 邮件发送失败: {e}")
        return False


def resolve_account_name(account: str | None = None) -> str:
    """账号名 → 发布账号显示名。

    >>> resolve_account_name("chym")   → "沧海月明"
    >>> resolve_account_name(None)     → "极鱼社O组"
    """
    if account and account in config.ACCOUNT_DISPLAY_NAMES:
        return config.ACCOUNT_DISPLAY_NAMES[account]
    if account:
        return account  # 直接使用传入的账号名
    return config.DEFAULT_PUBLISH_ACCOUNT


def parse_schedule_time(time_str: str) -> "datetime.datetime":
    """解析定时发送时间字符串，兼容斜杠/横杠、带秒/不带秒格式。

    >>> parse_schedule_time("2026/8/14 17:00:00")
    datetime.datetime(2026, 8, 14, 17, 0)
    """
    import datetime

    for fmt in (
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M",
    ):
        try:
            return datetime.datetime.strptime(time_str.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(
        f"无法解析定时发送时间: {time_str!r}（示例: 2026/8/14 17:00:00）"
    )


def wait_until(target: "datetime.datetime") -> None:
    """阻塞等待到指定时间，每 30 秒打印一次倒计时，支持 Ctrl+C 中断。"""
    import datetime
    import time

    while True:
        remaining = target - datetime.datetime.now()
        if remaining.total_seconds() <= 0:
            return
        total = int(remaining.total_seconds())
        hours, rem = divmod(total, 3600)
        mins, secs = divmod(rem, 60)
        print(
            f"[email_sender] 距定时发送还有 {hours}小时{mins}分{secs}秒"
            f"（当前 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）"
        )
        time.sleep(min(30.0, remaining.total_seconds()))


def _build_body_html(review_result: str, name: str, author: str,
                     publish_time: str, publish_account: str) -> str:
    """按审核结果生成 HTML 正文。"""
    if review_result == "同意":
        return config.EMAIL_BODY_APPROVED.format(
            name=name, author=author,
            publish_time=publish_time, publish_account=publish_account,
        )
    return config.EMAIL_BODY_REJECTED.format(
        name=name, author=author, publish_account=publish_account,
    )


def build_body_lines(review_result: str, name: str, author: str,
                     publish_time: str, publish_account: str) -> list[str]:
    """按审核结果生成纯文本正文行（网页写信编辑器用），与 HTML 模板同一套数据。

    网易网页端编辑器不支持直接粘贴 HTML 源码里的 cid 图，故按行打文本 +
    底部插 slogan 图，内容和 SMTP 路径保持一致。
    """
    lines = [
        f"资源名称：{name} - {author}",
        "内审评议意见：同意",
    ]
    if review_result == "同意":
        lines.append("网易开平审核：同意")
        lines.append(f"上架时间：{publish_time}")
    else:
        lines.append("网易开平审核：不同意")
        lines.append("理由：已有相似皮肤，需添加更多原创元素")
    lines.append(f"发布账号：{publish_account}")
    return lines


def schedule_via_task_scheduler(*, name: str, author: str, review_result: str,
                                to_emails: list[str], cc_emails: list[str] | None,
                                publish_time: str, publish_account: str | None,
                                final_image: str | Path | None,
                                target: "datetime.datetime") -> bool:
    """注册 Windows 一次性计划任务，到点自动执行 SMTP 立即发送。立即返回，不占终端。

    Returns:
        True = 注册成功；False = 注册失败（调用方回退为前台等待）。
    """
    import datetime
    import json
    import random
    import string
    import subprocess
    import sys
    import tempfile

    # schtasks 时间精度到分钟：秒>0 时顺延到下一分钟，保证不早于目标时间发送
    fire = target
    if fire.second:
        fire = fire + datetime.timedelta(minutes=1)
    fire = fire.replace(second=0, microsecond=0)

    task_id = f"{fire:%Y%m%d_%H%M}_{''.join(random.choices(string.hexdigits[:16], k=3))}"
    task_name = f"MC_Skin_Email_{task_id}"

    # 待发送参数 + 启动脚本都放系统临时目录（无空格路径，绕开 schtasks 引号问题）
    job_dir = Path(tempfile.gettempdir()) / "mc_skin_scheduled_jobs"
    job_dir.mkdir(parents=True, exist_ok=True)
    job_file = job_dir / f"{task_id}.json"
    bat_file = job_dir / f"{task_id}.bat"

    job = {
        "name": name,
        "author": author,
        "review_result": review_result,
        "publish_time": publish_time,
        "publish_account": publish_account,
        "final_image": str(final_image) if final_image else None,
        "to_emails": list(to_emails),
        "cc_emails": list(cc_emails) if cc_emails else None,
    }
    job_file.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")

    # 启动 bat：纯 ASCII（路径无中文），到点执行 email_sender.py --job-file，跑完自删
    script = Path(__file__).resolve()
    python = sys.executable
    bat_file.write_text(
        f"@echo off\n"
        f'"{python}" "{script}" --job-file "{job_file}"\n'
        f'del "%~f0" >nul 2>&1\n',
        encoding="ascii",
    )

    cmd = [
        "schtasks", "/Create", "/F",
        "/TN", task_name,
        "/SC", "ONCE",
        "/SD", f"{fire:%Y/%m/%d}",
        "/ST", f"{fire:%H:%M}",
        "/TR", f'"{bat_file}"',
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(f"[email_sender] schtasks 执行失败: {e}")
        return False
    if proc.returncode != 0:
        print(f"[email_sender] 计划任务注册失败: {proc.stderr.strip() or proc.stdout.strip()}")
        return False

    print(f"[email_sender] ✓ 已注册计划任务 {task_name}，到点 {fire:%Y-%m-%d %H:%M} 自动发送")
    print(f"[email_sender]   无需保持终端/浏览器（电脑需在到点时开机）")
    print(f"[email_sender]   删除任务: schtasks /Delete /TN {task_name} /F")
    print(f"[email_sender]   查看任务: schtasks /Query /FO LIST | findstr {task_name}")
    return True


def _try_schedule_via_webmail(*, name: str, author: str, review_result: str,
                              publish_time: str, publish_account: str | None,
                              final_image: str | Path | None,
                              to_emails: list[str], cc_emails: list[str] | None,
                              target: "datetime.datetime") -> str:
    """尝试在网易网页版邮箱排定云端定时发信（电脑关机也能到点发送）。

    Returns:
        "scheduled" = 已排到网易云端，本机可关机；
        "failed"    = 未提交任何内容（可安全回退）；
        "uncertain" = 已点发送但未确认是否排定（勿回退，防双发）。
    """
    try:
        from webmail_scheduler import WebmailScheduler

        display_account = resolve_account_name(publish_account)
        body_lines = build_body_lines(
            review_result, name, author, publish_time, display_account
        )
        subject = config.EMAIL_SUBJECT_TEMPLATE.format(name=name, author=author)

        sched = WebmailScheduler()
        sched.__enter__()
        try:
            return sched.schedule_email(
                to_emails=to_emails,
                subject=subject,
                body_lines=body_lines,
                target=target,
                final_image=final_image,
                cc_emails=cc_emails,
            )
        finally:
            sched.__exit__(None, None, None)
    except Exception as e:
        print(f"[email_sender] 网页端云端定时发信异常: {e}")
        return "failed"


def send_review_email(
    name: str,
    author: str,
    review_result: str = "同意",
    publish_time: str = "",
    publish_account: str | None = None,
    final_image: str | Path | None = None,
    to_emails: list[str] | None = None,
    cc_emails: list[str] | None = None,
    schedule_time: str | None = None,
    scheduler: str = "auto",
) -> bool:
    """发送皮肤审核邮件。

    根据审核结果选择对应模板：
      - 同意 → 含"上架时间"
      - 不同意 → 含"理由：已有相似皮肤，需添加更多原创元素"

    Args:
        name: 资源名称
        author: 作者
        review_result: 审核结果，"同意" 或 "不同意"
        publish_time: 上架时间（审核通过时），如 "2026-08-03 17:50"
        publish_account: 发布账号标识（如 "chym"），自动映射为显示名
        final_image: 最终渲染图路径（作为附件）
        to_emails: 收件人列表
        cc_emails: 抄送列表
        schedule_time: 定时发送时间（可选），如 "2026/8/14 17:00:00"。
            未来时间 → 按 scheduler 排定发送，立即返回；
            已过或为空 → 走 SMTP 立即发送
        scheduler: 定时调度方式（未来时间时生效）：
            "auto"    = 优先网易云端定时发信（提交前失败才回退 Windows 计划任务；
                        结果未知不回退，防双发）
            "webmail" = 强制网易云端定时发信（失败不发送）
            "task"    = 强制 Windows 计划任务（旧方式，电脑需在到点开机）
    """
    import datetime

    # 发布账号显示名
    display_account = resolve_account_name(publish_account)

    # 定时发送时间解析（未来时间才使用；已过或为空 → 立即发送）
    target = None
    if schedule_time:
        target = parse_schedule_time(schedule_time)

    # 上架时间：未指定时，定时发送取计划发送时间，否则取当前时间
    if not publish_time:
        if target and target > datetime.datetime.now():
            publish_time = target.strftime("%Y-%m-%d %H:%M")
        else:
            publish_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    subject = config.EMAIL_SUBJECT_TEMPLATE.format(name=name, author=author)
    html_body = _build_body_html(
        review_result, name, author, publish_time, display_account
    )

    # 定时发送：未来时间 → 注册 Windows 计划任务到点自动 SMTP 发送，立即返回
    if target:
        if target <= datetime.datetime.now():
            print(
                f"[email_sender] 定时发送时间 {target:%Y-%m-%d %H:%M:%S}"
                " 已过，立即发送"
            )
        else:
            if to_emails is None:
                reviewer = config.REVIEWER_EMAIL
                if not reviewer:
                    print("[email_sender] 未设置收件人（REVIEWER_EMAIL 为空），跳过发送")
                    return False
                to_emails = [reviewer]

            mode = (scheduler or config.MAIL_SCHEDULER_MODE or "auto").lower()
            if mode == "task":
                # 旧方式：Windows 计划任务（电脑需在到点开机）
                ok = schedule_via_task_scheduler(
                    name=name,
                    author=author,
                    review_result=review_result,
                    publish_time=publish_time,
                    publish_account=publish_account,
                    final_image=final_image,
                    to_emails=to_emails,
                    cc_emails=cc_emails,
                    target=target,
                )
                if ok:
                    return True
                print("[email_sender] 计划任务注册失败，回退为前台等待到点（Ctrl+C 可中断）...")
                wait_until(target)
                print("[email_sender] 时间到，开始发送...")
            elif mode == "webmail":
                # 只走网易云端定时发信（关机也能发），失败不发送
                state = _try_schedule_via_webmail(
                    name=name, author=author, review_result=review_result,
                    publish_time=publish_time, publish_account=publish_account,
                    final_image=final_image, to_emails=to_emails,
                    cc_emails=cc_emails, target=target,
                )
                if state == "scheduled":
                    return True
                print("[email_sender] 网页端云端定时发信未排定，本次未发送。")
                return False
            else:  # auto
                # 优先云端（关机也能发）；提交前失败才回退计划任务；结果未知不回退防双发
                state = _try_schedule_via_webmail(
                    name=name, author=author, review_result=review_result,
                    publish_time=publish_time, publish_account=publish_account,
                    final_image=final_image, to_emails=to_emails,
                    cc_emails=cc_emails, target=target,
                )
                if state == "scheduled":
                    return True
                if state == "uncertain":
                    print("[email_sender] 云端定时发信结果未知：请在网易网页版「定时发信」列表核对，"
                          "不要重复排定（已避免回退造成双发）。")
                    return False
                # state == "failed"：云端未提交，安全回退 Windows 计划任务
                print("[email_sender] 网页端云端定时发信不可用/未配置，回退为 Windows 计划任务...")
                ok = schedule_via_task_scheduler(
                    name=name,
                    author=author,
                    review_result=review_result,
                    publish_time=publish_time,
                    publish_account=publish_account,
                    final_image=final_image,
                    to_emails=to_emails,
                    cc_emails=cc_emails,
                    target=target,
                )
                if ok:
                    return True
                print("[email_sender] 计划任务注册失败，回退为前台等待到点（Ctrl+C 可中断）...")
                wait_until(target)
                print("[email_sender] 时间到，开始发送...")

    if to_emails is None:
        reviewer = config.REVIEWER_EMAIL
        if not reviewer:
            print("[email_sender] 未设置收件人（REVIEWER_EMAIL 为空），跳过发送")
            return False
        to_emails = [reviewer]

    # 内嵌图片：底部 slogan 宣传图
    inline_images = {}
    slogan_path = config.SLOGAN_IMAGE_PATH
    if slogan_path.exists():
        inline_images["slogan"] = slogan_path
    else:
        print(f"[email_sender] slogan 图不存在，跳过内嵌: {slogan_path}")

    # 附件：最终渲染图
    attachments = []
    if final_image:
        final_path = Path(final_image)
        if final_path.exists():
            attachments.append(final_path)
        else:
            print(f"[email_sender] 渲染图不存在，跳过附件: {final_path}")

    msg = build_message(
        sender_email=config.SENDER_EMAIL,
        to_emails=to_emails,
        subject=subject,
        html_body=html_body,
        attachments=attachments,
        inline_images=inline_images,
        cc_emails=cc_emails,
    )

    return send_email(msg, config.SENDER_EMAIL, config.SENDER_PASSWORD)


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="发送审核邮件（独立使用）")
    ap.add_argument("--to", default="", help="收件人邮箱（多个用逗号分隔）")
    ap.add_argument("--name", default="", help="资源名称")
    ap.add_argument("--author", default="", help="作者")
    ap.add_argument("--result", default="同意", choices=["同意", "不同意"],
                    help="审核结果（默认: 同意）")
    ap.add_argument("--publish-time", default="", metavar="TIME",
                    help="上架时间（默认取当前时间）")
    ap.add_argument("--time", default="", metavar="TIME",
                    help='定时发送时间，如 "2026/8/14 17:00:00"。'
                         '未来时间 → 注册 Windows 计划任务到点自动发送，'
                         '立即返回、不占终端；不填立即发送')
    ap.add_argument("--account", default=None, help="发布账号（如 chym）")
    ap.add_argument("--image", default=None, help="最终渲染图路径（附件）")
    ap.add_argument("--cc", default=None, help="抄送邮箱")
    ap.add_argument("--job-file", default=None, metavar="JSON",
                    help="（内部）读取待发送参数并立即发送，用于计划任务到点调用")
    ap.add_argument("--scheduler", default="auto", choices=["auto", "webmail", "task"],
                    help="定时发送方式：auto=优先网易云端(失败回退计划任务) "
                         "/ webmail=强制云端(失败不发送) / task=强制Windows计划任务")
    ap.add_argument("--inspect-mail", action="store_true",
                    help="校准网易邮箱写信/定时发信选择器（打开浏览器手动操作）")
    ap.add_argument("--add-mail-account", action="store_true",
                    help="首次登录网易邮箱并保存网页端登录态（云端定时发信前置步骤）")
    args = ap.parse_args()

    # 计划任务到点调用：读取参数立即 SMTP 发送
    if args.job_file:
        import json
        job = json.loads(Path(args.job_file).read_text(encoding="utf-8"))
        try:
            ok = send_review_email(
                name=job["name"],
                author=job.get("author", ""),
                review_result=job.get("review_result", "同意"),
                publish_time=job.get("publish_time", ""),
                publish_account=job.get("publish_account"),
                final_image=job.get("final_image"),
                to_emails=job.get("to_emails"),
                cc_emails=job.get("cc_emails"),
                schedule_time=None,
            )
        finally:
            try:
                Path(args.job_file).unlink()
            except Exception:
                pass
        sys.exit(0 if ok else 1)

    if args.inspect_mail:
        from webmail_scheduler import inspect_mail
        inspect_mail()
        sys.exit(0)

    if args.add_mail_account:
        from webmail_scheduler import add_mail_account
        add_mail_account()
        sys.exit(0)

    if not args.to or not args.name:
        ap.print_help()
        sys.exit(1)

    to_list = [e.strip() for e in args.to.split(",") if e.strip()]
    cc_list = [e.strip() for e in args.cc.split(",") if e.strip()] if args.cc else None

    ok = send_review_email(
        name=args.name,
        author=args.author,
        review_result=args.result,
        publish_time=args.publish_time,
        publish_account=args.account,
        final_image=args.image,
        to_emails=to_list,
        cc_emails=cc_list,
        schedule_time=args.time,
        scheduler=args.scheduler,
    )
    sys.exit(0 if ok else 1)
