"""
Notion REST API 최소 래퍼 (외부 패키지 없이 표준 라이브러리만 사용).

Notion-Version 은 2025-09-03 을 씁니다.
2025-09-03 부터 데이터베이스가 여러 개의 '데이터 소스(data source)' 를 가질 수 있게
바뀌었고, 스키마 조회와 행 조회가 데이터베이스가 아니라 데이터 소스 단위로 이동했습니다.

  GET  /v1/databases/{db_id}            → data_sources[] 목록
  GET  /v1/data_sources/{ds_id}         → 칼럼 스키마
  POST /v1/data_sources/{ds_id}/query   → 행 조회
  PATCH /v1/pages/{page_id}             → 값 쓰기 (변경 없음)

구버전(2022-06-28)으로 데이터 소스가 2개 이상인 DB 를 조회하면 400 이 납니다.
"""

from __future__ import annotations

import http.client
import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any

# 재시도해야 할 네트워크 오류들. 500개 행을 순차로 쓰는 동안 한 번쯤은
# 반드시 나므로, 여기서 못 잡으면 실행 전체가 죽는다.
TRANSIENT = (
    TimeoutError,
    socket.timeout,
    ConnectionError,
    http.client.HTTPException,
    urllib.error.URLError,
)

API = "https://api.notion.com/v1"
VERSION = "2025-09-03"
LEGACY_VERSION = "2022-06-28"


class NotionError(RuntimeError):
    def __init__(self, message: str, status: int = 0, code: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code


class Notion:
    def __init__(self, token: str, verbose: bool = True, version: str = VERSION):
        if not token:
            raise NotionError("NOTION_TOKEN 이 비어 있습니다. .env 파일을 확인하세요.")
        self.token = token
        self.verbose = verbose
        self.version = version
        self._last = 0.0

    # -- 저수준 -----------------------------------------------------------
    def _request(self, method: str, path: str, body: dict | None = None,
                 retries: int = 6, version: str | None = None) -> dict:
        # Notion rate limit: 평균 3req/s
        gap = time.time() - self._last
        if gap < 0.34:
            time.sleep(0.34 - gap)

        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{API}{path}", data=data, method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": version or self.version,
                "Content-Type": "application/json",
            })
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    self._last = time.time()
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                self._last = time.time()
                payload = exc.read().decode("utf-8", "replace")
                if exc.code == 429 and attempt < retries - 1:
                    wait = float(exc.headers.get("Retry-After", 2)) + 1
                    if self.verbose:
                        print(f"  [notion] 429 rate limit — {wait:.0f}초 대기")
                    time.sleep(wait)
                    continue
                if exc.code in (502, 503, 504) and attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                try:
                    parsed = json.loads(payload)
                    msg = parsed.get("message", payload)
                    code = parsed.get("code", "")
                except Exception:  # noqa: BLE001
                    msg, code = payload, ""
                raise NotionError(f"Notion API {exc.code} {method} {path}\n  {msg}",
                                  exc.code, code) from exc
            except TRANSIENT as exc:
                # 읽기 타임아웃·연결 끊김. 서버가 요청을 받았는지 알 수 없지만
                # PATCH 는 같은 값을 다시 써도 결과가 같으므로 재시도해도 안전하다.
                self._last = time.time()
                if attempt >= retries - 1:
                    raise NotionError(
                        f"Notion 연결 실패 ({type(exc).__name__}): {method} {path}\n"
                        f"  {exc}") from exc
                wait = min(2 ** attempt, 30)
                if self.verbose:
                    print(f"  [notion] 연결 문제({type(exc).__name__}) — "
                          f"{wait}초 후 재시도 {attempt + 1}/{retries - 1}",
                          flush=True)
                time.sleep(wait)
        raise NotionError(f"Notion API 재시도 초과: {method} {path}")

    # -- 데이터베이스 / 데이터 소스 ----------------------------------------
    def database(self, database_id: str) -> dict:
        return self._request("GET", f"/databases/{database_id}")

    def data_sources(self, database_id: str) -> list[dict]:
        """[{'id':…, 'name':…}, …]. DB 가 아니라 데이터 소스 ID 를 줘도 처리한다."""
        try:
            db = self.database(database_id)
        except NotionError as exc:
            if exc.status in (400, 404):
                # 데이터 소스 ID 를 직접 준 경우일 수 있다
                ds = self._request("GET", f"/data_sources/{database_id}")
                return [{"id": ds["id"], "name": _plain(ds.get("name"))
                         or _plain(ds.get("title")) or "(이름 없음)"}]
            raise
        out = []
        for d in db.get("data_sources") or []:
            out.append({"id": d["id"], "name": d.get("name") or "(이름 없음)"})
        if not out:
            # 아주 드물게 data_sources 가 비어 오면 DB 자체를 데이터 소스로 취급
            out = [{"id": database_id, "name": _plain(db.get("title"))}]
        return out

    def data_source(self, ds_id: str) -> dict:
        return self._request("GET", f"/data_sources/{ds_id}")

    def schema(self, ds_id: str) -> dict[str, str]:
        """{칼럼 이름: 타입}"""
        ds = self.data_source(ds_id)
        return {name: prop["type"] for name, prop in ds["properties"].items()}

    def query_all(self, ds_id: str, page_size: int = 100) -> list[dict]:
        pages, cursor = [], None
        while True:
            body: dict[str, Any] = {"page_size": page_size}
            if cursor:
                body["start_cursor"] = cursor
            res = self._request("POST", f"/data_sources/{ds_id}/query", body)
            pages.extend(res.get("results", []))
            if not res.get("has_more"):
                return pages
            cursor = res["next_cursor"]

    def update_page(self, page_id: str, properties: dict) -> dict:
        return self._request("PATCH", f"/pages/{page_id}", {"properties": properties})

    def page(self, page_id: str) -> dict:
        return self._request("GET", f"/pages/{page_id}")


def _plain(rich) -> str:
    if isinstance(rich, str):
        return rich
    return "".join(x.get("plain_text", "") for x in (rich or []))


# --------------------------------------------------------------------------
# 프로퍼티 값 읽기 / 쓰기
# --------------------------------------------------------------------------
def read_value(prop: dict | None) -> Any:
    """Notion 프로퍼티 → 파이썬 값 (비어 있으면 None / [] / '')."""
    if not prop:
        return None
    t = prop.get("type")
    if t == "title":
        return "".join(x.get("plain_text", "") for x in prop["title"]) or None
    if t == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop["rich_text"]) or None
    if t == "select":
        return (prop["select"] or {}).get("name")
    if t == "status":
        return (prop["status"] or {}).get("name")
    if t == "multi_select":
        return [o["name"] for o in prop["multi_select"]]
    if t == "date":
        return (prop["date"] or {}).get("start")
    if t == "checkbox":
        return prop["checkbox"]
    if t == "number":
        return prop["number"]
    if t == "url":
        return prop["url"]
    if t == "people":
        return [p.get("id") for p in prop.get("people", [])]
    if t == "email":
        return prop["email"]
    if t == "phone_number":
        return prop["phone_number"]
    return None


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def build_value(prop_type: str, value: Any) -> dict | None:
    """파이썬 값 → Notion 프로퍼티 payload. 타입이 안 맞으면 None."""
    if value is None or value == "":
        return None

    if prop_type == "rich_text":
        text = str(value)[:1990]
        return {"rich_text": [{"type": "text", "text": {"content": text}}]}
    if prop_type == "title":
        return {"title": [{"type": "text", "text": {"content": str(value)[:1990]}}]}
    if prop_type == "select":
        return {"select": {"name": str(value)[:100]}}
    if prop_type == "status":
        # status 타입은 옵션 자동 생성이 안 되므로 기존 옵션 이름이어야 함
        return {"status": {"name": str(value)[:100]}}
    if prop_type == "multi_select":
        items = value if isinstance(value, (list, tuple, set)) else [value]
        return {"multi_select": [{"name": str(v)[:100]} for v in items if v]}
    if prop_type == "date":
        return {"date": {"start": str(value)}}
    if prop_type == "url":
        return {"url": str(value)}
    if prop_type == "number":
        try:
            return {"number": float(value)}
        except (TypeError, ValueError):
            return None
    if prop_type == "checkbox":
        return {"checkbox": bool(value)}
    if prop_type in ("email", "phone_number"):
        return {prop_type: str(value)}
    return None
