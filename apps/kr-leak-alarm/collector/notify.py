"""
notify.py — 신규 건 알림 (데스크톱 토스트 / 웹훅 / 이메일).

보안 설계:
  * PowerShell 토스트: 피해자명·그룹명이 스크립트 문자열로 보간되지 않는다.
    값은 환경변수로 전달하고 PowerShell 안에서 XML escape 한다 → 명령 주입 불가.
  * 웹훅: URL 은 .env 에서만 읽고, https + 허용 호스트만 통과시킨다.
  * 알림 본문의 URL 은 전부 defang 되어 채팅에서 클릭할 수 없다.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import smtplib
import ssl
import subprocess
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse

from .safety import defang_url, sanitize_text

log = logging.getLogger(__name__)

WEBHOOK_ALLOWED_HOSTS = {
    "hooks.slack.com",
    "discord.com",
    "discordapp.com",
    "canary.discord.com",
    "ptb.discord.com",
}

TIER_LABEL = {
    "confirmed": "확정",
    "strong": "유력",
    "likely": "추정",
    "review": "검토필요",
    "none": "무관",
}

SUPPLY_LABEL = {
    "direct": "직거래",
    "critical": "핵심벤더",
    "korea_ops": "한국진출",
    "sector": "업종위험",
    "none": "",
}
SUPPLY_ORDER = ["none", "sector", "korea_ops", "critical", "direct"]


# ─────────────────────────────────────────────────────────────
# 메시지 구성
# ─────────────────────────────────────────────────────────────

def filter_for_notification(
    items: list[dict[str, Any]], notify_cfg: dict[str, Any]
) -> list[dict[str, Any]]:
    """알림을 보낼 항목만 골라낸다.

    한국 관련 건과 공급망 건은 성격이 달라 임계값을 따로 둔다.
    공급망 건은 기본적으로 '핵심벤더' 이상만 알림 — 업종위험까지 울리면
    하루에도 수십 번 토스트가 떠서 알림 자체를 무시하게 된다.
    """
    kr_min = int(notify_cfg.get("kr_min_score", 60))
    supply_min_tier = notify_cfg.get("supply_min_tier", "critical")
    try:
        supply_min = SUPPLY_ORDER.index(supply_min_tier)
    except ValueError:
        supply_min = SUPPLY_ORDER.index("critical")

    out: list[dict[str, Any]] = []
    for it in items:
        if int(it.get("kr_score") or 0) >= kr_min:
            out.append(it)
            continue
        tier = it.get("supply_tier") or "none"
        if tier in SUPPLY_ORDER and SUPPLY_ORDER.index(tier) >= supply_min:
            out.append(it)
    return out


def _axis_of(it: dict[str, Any]) -> tuple[str, str]:
    """이 항목을 어느 축의 근거로 보여줄지 고른다 (점수가 높은 쪽)."""
    kr_score = int(it.get("kr_score") or 0)
    supply_score = int(it.get("supply_score") or 0)
    if supply_score > kr_score:
        return "supply", SUPPLY_LABEL.get(it.get("supply_tier", ""), "")
    return "kr", TIER_LABEL.get(it.get("kr_tier", ""), it.get("kr_tier", ""))


def _summarize(items: list[dict[str, Any]], limit: int) -> tuple[str, str]:
    total = len(items)
    shown = items[:limit]

    kr_n = sum(1 for i in items if _axis_of(i)[0] == "kr")
    supply_n = total - kr_n
    if supply_n and kr_n:
        title = f"[Kr-Leak-alarm] 신규 {total}건 (한국 {kr_n} · 공급망 {supply_n})"
    elif supply_n:
        title = f"[Kr-Leak-alarm] 공급망 위험 신규 {total}건"
    else:
        title = f"[Kr-Leak-alarm] 한국 관련 신규 {total}건"

    lines: list[str] = []
    for it in shown:
        axis, label = _axis_of(it)
        victim = sanitize_text(it.get("victim"), 120)
        group = sanitize_text(it.get("group_name") or it.get("group"), 60)
        site = sanitize_text(it.get("website"), 100)
        country = sanitize_text(it.get("country"), 4)
        when = (it.get("discovered") or it.get("published") or "")[:10]
        site_part = f" · {defang_url(site)}" if site else ""
        mark = "🔗" if axis == "supply" else "🇰🇷"
        country_part = f" [{country}]" if country and axis == "supply" else ""
        lines.append(f"{mark} [{label}] {victim}{country_part} — {group}{site_part} ({when})")

    if total > limit:
        lines.append(f"… 외 {total - limit}건")
    return title, "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# 1. Windows 데스크톱 토스트
# ─────────────────────────────────────────────────────────────

_PS_TOAST = r"""
$ErrorActionPreference = 'Stop'
try {
  [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
  $t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
        [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
  $nodes = $t.GetElementsByTagName('text')
  $nodes.Item(0).AppendChild($t.CreateTextNode($env:KRLEAK_TOAST_TITLE)) | Out-Null
  $nodes.Item(1).AppendChild($t.CreateTextNode($env:KRLEAK_TOAST_BODY))  | Out-Null
  $n = [Windows.UI.Notifications.ToastNotification]::new($t)
  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Kr-Leak-alarm').Show($n)
} catch {
  # WinRT 토스트를 못 쓰는 환경(구버전/서버 SKU)에서는 풍선 알림으로 폴백
  Add-Type -AssemblyName System.Windows.Forms
  $b = New-Object System.Windows.Forms.NotifyIcon
  $b.Icon = [System.Drawing.SystemIcons]::Information
  $b.BalloonTipTitle = $env:KRLEAK_TOAST_TITLE
  $b.BalloonTipText  = $env:KRLEAK_TOAST_BODY
  $b.Visible = $true
  $b.ShowBalloonTip(10000)
  Start-Sleep -Seconds 10
  $b.Dispose()
}
"""


def desktop_toast(title: str, body: str) -> bool:
    """네이티브 알림 표시. 실패해도 전체 실행을 막지 않는다."""
    title = sanitize_text(title, 120)
    body = sanitize_text(body, 600)
    system = platform.system()

    try:
        if system == "Windows":
            env = dict(os.environ, KRLEAK_TOAST_TITLE=title, KRLEAK_TOAST_BODY=body)
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_TOAST],
                env=env, capture_output=True, timeout=40, shell=False, check=False,
            )
            return True
        if system == "Darwin":
            subprocess.run(["osascript", "-e",
                            'display notification "" with title ""'],
                           capture_output=True, timeout=15, shell=False, check=False)
            return True
        if system == "Linux":
            subprocess.run(["notify-send", "--", title, body],
                           capture_output=True, timeout=15, shell=False, check=False)
            return True
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("데스크톱 알림 실패(무시하고 계속): %s", exc)
    return False


# ─────────────────────────────────────────────────────────────
# 2. 웹훅 (Slack / Discord)
# ─────────────────────────────────────────────────────────────

def send_webhook(title: str, body: str, kind: str = "slack") -> bool:
    url = (os.environ.get("KRLEAK_WEBHOOK_URL") or "").strip()
    if not url:
        log.info("웹훅 URL(.env KRLEAK_WEBHOOK_URL)이 비어 있어 건너뜁니다.")
        return False

    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in WEBHOOK_ALLOWED_HOSTS:
        log.error("웹훅 URL 이 허용 목록 밖이라 전송을 차단했습니다: %s", parsed.hostname)
        return False

    text = f"*{title}*\n{body}"
    payload = {"content": text[:1900]} if kind == "discord" else {"text": text[:3900]}

    try:
        import requests

        resp = requests.post(
            url, json=payload, timeout=20,
            headers={"User-Agent": "Kr-Leak-alarm/1.0"}, allow_redirects=False,
        )
        if resp.status_code >= 300:
            log.error("웹훅 전송 실패: HTTP %s", resp.status_code)
            return False
        return True
    except Exception as exc:
        log.error("웹훅 전송 오류: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────
# 3. 이메일
# ─────────────────────────────────────────────────────────────

def send_email(title: str, body: str, recipients: list[str]) -> bool:
    host = os.environ.get("KRLEAK_SMTP_HOST", "").strip()
    if not host or not recipients:
        return False

    port = int(os.environ.get("KRLEAK_SMTP_PORT", "587") or 587)
    user = os.environ.get("KRLEAK_SMTP_USER", "").strip()
    password = os.environ.get("KRLEAK_SMTP_PASSWORD", "")
    sender = os.environ.get("KRLEAK_SMTP_FROM", "").strip() or user

    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(body + "\n\n-- Kr-Leak-alarm (URL 은 안전을 위해 defang 처리되었습니다)")

    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30, context=ctx) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.starttls(context=ctx)
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        return True
    except Exception as exc:
        log.error("이메일 전송 실패: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────
# 통합 진입점
# ─────────────────────────────────────────────────────────────

def notify_new(items: list[dict[str, Any]], notify_cfg: dict[str, Any]) -> dict[str, bool]:
    if not items:
        return {}

    items = filter_for_notification(items, notify_cfg)
    if not items:
        log.info("신규 건은 있으나 알림 임계값 미만이라 발송하지 않습니다. (대시보드에는 표시됩니다)")
        return {}

    limit = int(notify_cfg.get("max_items_per_notification", 10))
    title, body = _summarize(items, limit)
    results: dict[str, bool] = {}

    if notify_cfg.get("desktop_toast", True):
        results["desktop"] = desktop_toast(title, body)

    hook = notify_cfg.get("webhook", {}) or {}
    if hook.get("enabled"):
        results["webhook"] = send_webhook(title, body, hook.get("type", "slack"))

    mail = notify_cfg.get("email", {}) or {}
    if mail.get("enabled"):
        results["email"] = send_email(title, body, list(mail.get("to", [])))

    log.info("알림 결과: %s", json.dumps(results, ensure_ascii=False))
    return results
