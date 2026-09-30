# -*- coding: utf-8 -*-
"""설정 — 값은 전부 .env 에서 읽는다. 코드에 박지 않는다 (CLAUDE.md 「값을 지어내지 않는다」).

아래 기본값 가운데 「첫 값」 이라고 적은 것은 확정한 값이 아니다 (설계서 「보류 및 확정 필요」).
문제집으로 재기 전에 돌려 보려고 둔 출발점이고, 재고 나면 .env 에서 숫자만 바꾼다.
"""
import os

from dotenv import load_dotenv

from . import ROOT

load_dotenv(os.path.join(ROOT, ".env"))


def _s(name, default=""):
    return (os.getenv(name) or default).strip()


def _i(name, default):
    v = _s(name)
    return int(v) if v else default


def _f(name, default):
    v = _s(name)
    return float(v) if v else default


def _b(name, default):
    v = _s(name).lower()
    return default if not v else v in ("1", "true", "yes", "on")


def _path(name, default):
    v = _s(name) or default
    return v if os.path.isabs(v) else os.path.normpath(os.path.join(ROOT, v))


# ── 자리 ──
DATA_DIR = _path("DATA_DIR", "data")
SQLITE_PATH = _path("SQLITE_PATH", os.path.join("data", "ragdb.sqlite"))
INDEX_ROOT = os.path.join(DATA_DIR, "bm25_index")
SNAPSHOT_ROOT = os.path.join(DATA_DIR, "snapshot")
CURRENT = os.path.join(DATA_DIR, "current.txt")
BATCH_LOG = os.path.join(DATA_DIR, "batch_log.jsonl")

# ── 검색 (F-12) ──
CANDIDATE_M = _i("CANDIDATE_M", 100)                 # OI-02 첫 값. 문제집 초안(2026-09-30)에서 50 이면 둘이 빠지고 100 이면 다 듦. 재순위 비용은 100개까지 한 단위
FINAL_K = _i("FINAL_K", 5)                           # OI-02 잠정
KIND_BOOST = _f("KIND_BOOST", 0.1)                   # OI-02 첫 값. 후보 가운데 가장 높은 점수의 몇 배를 더하는지
OFFLINE_FACTOR = _f("OFFLINE_FACTOR", 0.85)          # F-07 처리 1 첫 값. offline 조각의 점수에 곱함. 예비 측정에서 0.7 보다 나았음
EXPANSION_WEIGHT = _f("EXPANSION_WEIGHT", 0.5)       # OI-14 첫 값. 예비 측정과 문제집 초안(2026-09-30)에서 0.3 과 0.5 가 같고 별칭 질문은 0.5 가 나음. 0 이면 꺼짐
EXPANSION_MAX_ITEMS = _i("EXPANSION_MAX_ITEMS", 5)   # OI-15 첫 값
EXPANSION_MAX_FORMS = _i("EXPANSION_MAX_FORMS", 5)   # OI-15 첫 값

# ── 재순위 (F-12 처리 8) ──
RERANK_ENABLED = _b("RERANK_ENABLED", True)
RERANK_MODEL = _s("RERANK_MODEL", "rerank-v3.5")     # OI-25 첫 값
RERANK_TIMEOUT_MS = _i("RERANK_TIMEOUT_MS", 10000)   # OI-21 첫 값. 실측(2026-09-30): 첫 호출 6.7초, 그 뒤 0.3에서 0.5초
RERANK_MIN_SCORE = _f("RERANK_MIN_SCORE", 0.0)       # OI-22. 0 이면 문턱을 쓰지 않음
RERANK_PRICE_PER_SEARCH = _f("RERANK_PRICE_PER_SEARCH", 0.0025)   # 달러. 검색 한 번 값으로 넉넉히 잡은 것

# ── 답변 (F-13) ──
ANSWER_MODEL = _s("ANSWER_MODEL", "claude-sonnet-5")
ANSWER_MAX_TOKENS = _i("ANSWER_MAX_TOKENS", 1024)    # OI-30 초기값
QUESTION_MAX_CHARS = _i("QUESTION_MAX_CHARS", 300)   # OI-30 초기값
PRICE_INPUT = _f("PRICE_INPUT_PER_MTOK", 2.0)
PRICE_OUTPUT = _f("PRICE_OUTPUT_PER_MTOK", 10.0)
PRICE_CACHE_READ = _f("PRICE_CACHE_READ_PER_MTOK", 0.2)
PRICE_CACHE_WRITE = _f("PRICE_CACHE_WRITE_PER_MTOK", 2.5)

# ── 사용량 (F-18) ──
DAILY_BUDGET_USD = _f("DAILY_BUDGET_USD", 3.0)
# 사람별 제한. 0 이면 그 제한을 쓰지 않는다 (2026-09-30 김무근: 사람별 제한 없이, 하루 차단기만)
RATE_CONCURRENT = _i("RATE_CONCURRENT", 0)
RATE_PER_MINUTE = _i("RATE_PER_MINUTE", 0)
RATE_PER_HOUR = _i("RATE_PER_HOUR", 0)

# ── 기록 (F-19, F-20) ──
FINGERPRINT_KEY = _s("FINGERPRINT_KEY")              # 지문 키. 없으면 질문 해시와 재사용 답변을 쓰지 않는다
WORD_FP_MIN_CHARS = _i("WORD_FP_MIN_CHARS", 2)       # OI-27 첫 값
WORD_FP_TTL_DAYS = _i("WORD_FP_TTL_DAYS", 14)
STALE_DAYS = _i("STALE_DAYS", 90)                    # OI-29 첫 값. 확인일이 이보다 오래되면 「오래됨」

# ── 조각 (F-05) ──
MIN_BODY_CHARS = _i("MIN_BODY_CHARS", 40)            # OI-03 첫 값

# ── 열쇠. 값은 여기서만 읽는다 ──
ANTHROPIC_API_KEY = _s("ANTHROPIC_API_KEY")
COHERE_API_KEY = _s("COHERE_API_KEY")
DISCORD_WEBHOOK = _s("DISCORD_WEBHOOK")
