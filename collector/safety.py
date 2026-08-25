"""
safety.py — 호스트 PC 보호를 위한 방어 계층.

이 모듈의 원칙:
  1. 랜섬웨어 DLS 원문에는 절대 직접 접속하지 않는다(기본 모드).
  2. 외부에서 들어온 모든 문자열은 신뢰하지 않는다 — 태그 제거, 제어문자 제거, 길이 제한.
  3. .onion / 공격자 URL 은 절대 클릭 가능한 링크로 만들지 않는다 — defang 처리.
  4. Tor 접속은 가상머신(VMware) 안에서, 명시적 동의가 있을 때만 허용한다.
"""

from __future__ import annotations

import html
import os
import platform
import re
import subprocess
import unicodedata
from typing import Any

# ─────────────────────────────────────────────────────────────
# 1. 텍스트 살균 (sanitization)
# ─────────────────────────────────────────────────────────────

MAX_FIELD_LEN = 2000

# 제어문자 (탭/줄바꿈 제외) + 방향 전환 문자(트로이 소스 공격 방어)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BIDI_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069\u200e\u200f\u061c]")
_TAG_RE = re.compile(r"<[^>]{0,400}?>")
_WS_RE = re.compile(r"[ \t\u00a0]{2,}")


def sanitize_text(value: Any, max_len: int = MAX_FIELD_LEN) -> str:
    """외부 소스 문자열을 안전한 평문으로 정규화한다.

    - HTML 태그 제거 후 엔티티 디코드(순서 중요: 디코드 후 재검사)
    - 제어문자 / BiDi override 제거 (터미널·에디터 스푸핑 방어)
    - 유니코드 NFKC 정규화, 길이 제한
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)

    # 태그 제거 → 엔티티 디코드 → 다시 태그 제거 (이중 인코딩 방어)
    text = _TAG_RE.sub(" ", value)
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)

    text = _CONTROL_RE.sub("", text)
    text = _BIDI_RE.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    text = _WS_RE.sub(" ", text).strip()

    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return text


# ─────────────────────────────────────────────────────────────
# 2. URL defang — 실수 클릭으로 인한 접속 사고 방지
# ─────────────────────────────────────────────────────────────

_HTTP_SCHEME_RE = re.compile(r"^(https?)://", re.IGNORECASE)
_ANY_SCHEME_RE = re.compile(r"^([a-z][a-z0-9+.\-]{0,20}):", re.IGNORECASE)


def defang_url(url: Any) -> str:
    """공격자 인프라 URL 을 클릭 불가능한 형태로 변환한다.

    http://evil.onion/x   →  hxxp://evil[.]onion/x
    javascript:alert(1)   →  javascript[:]alert(1)
    data:text/html,...    →  data[:]text/html,...

    http/https 이외의 스킴(javascript:, data:, vbscript:, file: 등)도
    반드시 무력화한다 — 어떤 렌더러에 넘어가도 실행되지 않도록.
    """
    if not url:
        return ""
    url = sanitize_text(url, max_len=500)

    if _HTTP_SCHEME_RE.match(url):
        url = _HTTP_SCHEME_RE.sub(
            lambda m: ("hxxps" if m.group(1).lower() == "https" else "hxxp") + "://", url
        )
    else:
        # 그 외 스킴은 콜론을 무력화한다 (javascript:, data:, vbscript:, file: …)
        url = _ANY_SCHEME_RE.sub(lambda m: f"{m.group(1)}[:]", url)

    return url.replace(".", "[.]")


def defang_domain(domain: Any) -> str:
    if not domain:
        return ""
    return sanitize_text(domain, max_len=253).replace(".", "[.]")


def is_onion(url: Any) -> bool:
    if not url:
        return False
    return ".onion" in str(url).lower()


# ─────────────────────────────────────────────────────────────
# 3. 도메인 추출 / 정규화
# ─────────────────────────────────────────────────────────────

_DOMAIN_RE = re.compile(
    r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24})\b", re.IGNORECASE
)


def extract_domain(value: Any) -> str:
    """'www.higen.co.kr', 'https://x.co.kr/a' 등에서 등록 도메인을 뽑는다."""
    if not value:
        return ""
    text = sanitize_text(value, max_len=500).lower()
    text = re.sub(r"^[a-z]+://", "", text)
    text = text.split("/")[0].split("?")[0].split("#")[0]
    text = text.split("@")[-1].split(":")[0]
    m = _DOMAIN_RE.search(text)
    if not m:
        return ""
    domain = m.group(1)
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


# ─────────────────────────────────────────────────────────────
# 4. 가상화 환경 탐지 — Tor 모듈 게이트
# ─────────────────────────────────────────────────────────────

_VMWARE_MARKERS = ("vmware", "vmw")


def _run(cmd: list[str], timeout: int = 10) -> str:
    """짧은 시스템 조회 명령 실행. 실패는 조용히 빈 문자열."""
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,  # shell=False 고정: 명령 주입 방지
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def detect_hypervisor() -> dict[str, Any]:
    """실행 환경의 가상화 여부와 벤더를 조사한다.

    반환: {"system", "vendor", "product", "is_vm", "is_vmware", "evidence"[]}
    """
    system = platform.system()
    vendor = product = ""
    evidence: list[str] = []

    if system == "Windows":
        ps = (
            "$cs = Get-CimInstance Win32_ComputerSystem; "
            "$bios = Get-CimInstance Win32_BIOS; "
            "Write-Output ($cs.Manufacturer + '|' + $cs.Model + '|' + $bios.Manufacturer + '|' + $bios.SerialNumber)"
        )
        raw = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=25)
        parts = raw.split("|")
        if len(parts) >= 2:
            vendor, product = parts[0].strip(), parts[1].strip()
            evidence.append(f"Win32_ComputerSystem: {vendor} / {product}")
        if len(parts) >= 4 and parts[2].strip():
            evidence.append(f"Win32_BIOS: {parts[2].strip()} / {parts[3].strip()}")
            vendor = vendor or parts[2].strip()
        # VMware Tools 서비스 존재 여부(보조 증거)
        if os.path.exists(r"C:\Program Files\VMware\VMware Tools\vmtoolsd.exe"):
            evidence.append("VMware Tools 설치 확인 (vmtoolsd.exe)")

    elif system == "Linux":
        for path, label in (
            ("/sys/class/dmi/id/sys_vendor", "sys_vendor"),
            ("/sys/class/dmi/id/product_name", "product_name"),
        ):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    val = fh.read().strip()
                evidence.append(f"{label}: {val}")
                if label == "sys_vendor":
                    vendor = val
                else:
                    product = val
            except OSError:
                pass
        virt = _run(["systemd-detect-virt"])
        if virt:
            evidence.append(f"systemd-detect-virt: {virt}")
            vendor = vendor or virt

    elif system == "Darwin":
        raw = _run(["sysctl", "-n", "machdep.cpu.features"])
        if "VMM" in raw:
            evidence.append("sysctl machdep.cpu.features 에 VMM 플래그")
            vendor = "hypervisor"

    blob = " ".join([vendor, product, " ".join(evidence)]).lower()
    is_vmware = any(m in blob for m in _VMWARE_MARKERS)
    is_vm = is_vmware or any(
        m in blob
        for m in ("virtualbox", "vbox", "qemu", "kvm", "xen", "hyper-v", "microsoft corporation virtual", "parallels", "bhyve")
    )

    return {
        "system": system,
        "vendor": vendor,
        "product": product,
        "is_vm": is_vm,
        "is_vmware": is_vmware,
        "evidence": evidence,
    }


class TorGateError(RuntimeError):
    """Tor 모듈 실행 조건 미충족."""


def assert_tor_allowed(cfg: dict[str, Any], acknowledged: bool) -> dict[str, Any]:
    """Tor 크롤러 실행 전 3중 게이트를 검사한다.

    게이트 1: config.json 의 tor.enabled == true
    게이트 2: --i-understand-the-risk 플래그로 명시적 동의
    게이트 3: require_vmware 가 true 면 VMware 가상머신에서만 허용
    """
    tor_cfg = cfg.get("tor", {}) or {}

    if not tor_cfg.get("enabled"):
        raise TorGateError(
            "게이트1 실패 — config.json 의 tor.enabled 가 false 입니다.\n"
            "  Tor 직접 크롤링은 호스트 PC 에서 절대 켜지 마십시오."
        )

    if not acknowledged:
        raise TorGateError(
            "게이트2 실패 — 위험 고지 동의가 없습니다.\n"
            "  실행 시 --i-understand-the-risk 플래그를 명시해야 합니다."
        )

    env = detect_hypervisor()
    if tor_cfg.get("require_vmware", True):
        if not env["is_vmware"]:
            detail = "\n".join(f"    - {e}" for e in env["evidence"]) or "    - (수집된 증거 없음)"
            raise TorGateError(
                "게이트3 실패 — VMware 가상머신이 아닙니다. 실행을 중단합니다.\n"
                f"  감지된 환경: system={env['system']} vendor={env['vendor']!r} product={env['product']!r}\n"
                f"  근거:\n{detail}\n"
                "  → 이 기능은 스냅샷을 뜬 격리 VMware VM 안에서만 사용하십시오."
            )
    return env


# ─────────────────────────────────────────────────────────────
# 5. 로그 안전 출력
# ─────────────────────────────────────────────────────────────

def safe_log_str(value: Any, max_len: int = 200) -> str:
    """터미널 이스케이프 시퀀스 주입을 막고 로그에 찍을 수 있는 형태로 만든다."""
    text = sanitize_text(value, max_len=max_len)
    return text.encode("unicode_escape").decode("ascii", errors="replace")
