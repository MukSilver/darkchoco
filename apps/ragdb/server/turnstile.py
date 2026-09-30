# -*- coding: utf-8 -*-
"""사람 확인 — Cloudflare Turnstile 토큰을 서버에서 검증한다 (설계서 「질문 한 건」 순서 1, 「개발 스택」).

비밀값 TURNSTILE_SECRET 이 비어 있으면 검증을 건너뛴다. 서버 전 개발용이고, /api/status 가 turnstile: false 로 드러낸다.
공개할 때는 반드시 채운다. 토큰과 IP 는 Cloudflare 에만 보내고 기록하지 않는다.
"""
import os

import httpx

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def secret():
    return (os.getenv("TURNSTILE_SECRET") or "").strip()


def enabled():
    return bool(secret())


def verify(token, remote_ip=None, client=None, timeout=5.0):
    """(통과 여부, 이유). 검증이 꺼져 있으면 늘 통과."""
    if not enabled():
        return True, "disabled"
    if not token:
        return False, "missing"
    data = {"secret": secret(), "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        c = client or httpx
        r = c.post(VERIFY_URL, data=data, timeout=timeout)
        body = r.json()
    except Exception:            # 네트워크와 JSON 오류. Cloudflare 가 안 닿으면 사람 확인을 통과시키지 않는다
        return False, "unreachable"
    if body.get("success"):
        return True, "ok"
    return False, ",".join(body.get("error-codes") or ["failed"])
