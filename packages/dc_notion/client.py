"""노션 REST 래퍼. 표준 라이브러리만 씁니다.

dls-observatory 의 것을 그대로 가져왔습니다. 재시도와 속도 제한 처리가
세 벌 중 가장 잘 되어 있어서 그것을 표준으로 삼았습니다.

바뀐 것은 토큰을 받는 방식뿐입니다. 인자로 주지 않으면 dc_notion.token 이
파일과 환경변수를 순서대로 찾습니다.

  · 평균 3req/s 로 스스로 속도를 늦춥니다
  · 429 는 Retry-After 만큼 기다립니다
  · 502·503·504 와 연결 끊김은 지수 백오프로 재시도합니다
"""

from __future__ import annotations

import http.client
import json
import socket
import time
import urllib.error
import urllib.request

from .token import find_token
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
    def __init__(self, token: str | None = None, verbose: bool = True,
                 version: str = VERSION):
        token = token or find_token()
        if not token:
            raise NotionError("노션 토큰이 비어 있습니다.")
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
