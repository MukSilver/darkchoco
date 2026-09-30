# -*- coding: utf-8 -*-
"""키가 실제로 붙는지 확인한다. 값은 화면에 찍지 않는다.

    python scripts/check_keys.py

재순위 키는 아직 없어도 된다. 노션 토큰은 두지 않는다(판 1.6, 노션은 정제 배치가 읽음). 있는 것만 확인하고 없는 것은 「아직 없음」으로 넘어간다.
"""
import os
import sys

# 윈도우 콘솔이 cp949라 한글 밖 문자에서 막힌다. UTF-8로 바꿔 쓴다
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()


def mark(name, ok, note=""):
    print("%-14s %s  %s" % (name, "붙음" if ok else "안 붙음", note))


def check_anthropic():
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        mark("Claude", False, "키가 .env에 없다")
        return
    import anthropic
    try:
        c = anthropic.Anthropic(api_key=key)
        # 가장 싼 호출 — 토큰만 센다. 모델을 부르지 않으므로 값이 들지 않는다
        r = c.messages.count_tokens(
            model="claude-sonnet-5",
            messages=[{"role": "user", "content": "확인"}],
        )
        mark("Claude", True, "토큰 세기 응답 %d" % r.input_tokens)
    except anthropic.AuthenticationError:
        mark("Claude", False, "키가 거절됐다 — 다시 발급해야 한다")
    except anthropic.PermissionDeniedError as e:
        mark("Claude", False, "권한 없음 — 워크스페이스를 확인한다 (%s)" % e.status_code)
    except Exception as e:
        mark("Claude", False, "%s: %s" % (type(e).__name__, str(e)[:80]))


def check_supabase():
    """표준 문서를 받는 곳 (F-01). rag.versions 를 한 줄 읽어 본다."""
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not key:
        mark("Supabase", False, "SUPABASE_URL 과 SUPABASE_SERVICE_KEY 가 없다 — 표준 문서를 받을 수 없다")
        return
    import httpx
    try:
        r = httpx.get(
            url + "/rest/v1/versions",
            params={"select": "version", "order": "version.desc", "limit": 1},
            headers={"apikey": key, "Authorization": "Bearer " + key, "Accept-Profile": "rag"},
            timeout=20,
        )
        if r.status_code == 200:
            rows = r.json()
            mark("Supabase", True, "rag 마지막 판 %s" % (rows[0]["version"] if rows else "없음"))
        else:
            mark("Supabase", False, "HTTP %d" % r.status_code)
    except Exception as e:
        mark("Supabase", False, str(e)[:80])


def check_cohere():
    key = os.getenv("COHERE_API_KEY", "").strip()
    if not key:
        mark("재순위", False, "아직 없음 — 2단계 후반에 붙인다 (OI-25 미결)")
        return
    import httpx
    try:
        r = httpx.post(
            "https://api.cohere.com/v2/rerank",
            headers={"Authorization": "Bearer " + key},
            json={"model": "rerank-v3.5", "query": "확인", "documents": ["확인"], "top_n": 1},
            timeout=30,
        )
        mark("재순위", r.status_code == 200, "HTTP %d" % r.status_code)
    except Exception as e:
        mark("재순위", False, str(e)[:80])


if __name__ == "__main__":
    print("키 확인 — 값은 찍지 않는다\n")
    check_anthropic()
    check_supabase()
    check_cohere()
