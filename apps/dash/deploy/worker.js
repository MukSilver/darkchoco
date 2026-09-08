/**
 * 대시보드를 팀에 내주는 Worker.
 *
 * 정적 파일(index.html · data/dash.js)을 내주고, 「검토 여부」 한 칸을 노션에 씁니다.
 * 로컬의 `apps/dash/api.py` 가 하는 일과 같습니다. 남의 서버에서는 파이썬이 못 돌아
 * 같은 규칙을 자바스크립트로 옮겼습니다.
 *
 * ## 무엇을 쓰나
 *
 * **「검토 여부」 하나뿐입니다.** 값도 셋(미검토 · 사건 O · 사건 X)만 받습니다.
 * 그 밖의 칸도, 줄을 만들거나 지우는 것도 안 합니다. 토큰은 Cloudflare 비밀값에만
 * 있고 브라우저로 안 갑니다.
 *
 * ## 일감 돌리기는 없습니다
 *
 * 남의 서버는 최현서 PC 의 수집기를 못 돌립니다. 수집은 GitHub Actions 가 여섯 시간마다
 * 하고(`.github/workflows/collect.yml`), 여기는 그 결과를 보고 O/X 를 고르는 자리입니다.
 *
 * ## 누가 들어오나
 *
 * 앞에 **Cloudflare Access** 를 겁니다. 통과한 요청에는 `Cf-Access-Jwt-Assertion`
 * 헤더가 붙습니다. 그 헤더가 없으면 Access 를 안 거친 것이라 막습니다 —
 * Worker 주소로 곧장 오는 길을 닫는 자물쇠입니다.
 *
 * `ACCESS_OPTIONAL` 을 "yes" 로 두면 그 검사를 끕니다. **Access 를 붙이기 전
 * 시험할 때만 씁니다.** 그동안은 주소를 아는 사람이 다 봅니다.
 */

const 검토값 = new Set(["미검토", "사건 O", "사건 X"]);
const 노션판 = "2025-09-03";

function json(코드, d) {
  return new Response(JSON.stringify(d), {
    status: 코드,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

/** Access 를 거쳐 왔나. 헤더가 없으면 자물쇠를 우회한 것이다. */
function 통과했나(request, env) {
  if ((env.ACCESS_OPTIONAL || "") === "yes") return true;
  return !!request.headers.get("Cf-Access-Jwt-Assertion");
}

/** 노션 page id 꼴인가. 32자 16진수(붙임표 허용). */
function 쓸만한id(s) {
  const 민 = String(s || "").replace(/-/g, "");
  return 민.length === 32 && /^[0-9a-f]+$/i.test(민);
}

async function 검토쓰기(request, env) {
  // 다른 웹페이지가 이 주소로 보내는 것을 막습니다(CSRF). 브라우저는 그때 Origin 을 붙입니다.
  const 본 = request.headers.get("Origin");
  if (본) {
    const 여기 = new URL(request.url).origin;
    if (본 !== 여기) return json(403, { 오류: "다른 자리에서 온 요청입니다" });
  }
  if (!(request.headers.get("Content-Type") || "").includes("application/json")) {
    return json(415, { 오류: "json 으로 보내십시오" });
  }
  if (!env.NOTION_TOKEN) {
    return json(500, { 오류: "NOTION_TOKEN 이 없습니다. wrangler secret put 으로 넣으십시오" });
  }

  let d;
  try {
    d = await request.json();
  } catch {
    return json(400, { 오류: "json 이 아닙니다" });
  }
  const page_id = String((d && d.page_id) || "");
  const 값 = String((d && d.검토) || "");
  if (!검토값.has(값)) return json(400, { 오류: `받지 않는 값입니다: ${값}` });
  if (!쓸만한id(page_id)) return json(400, { 오류: "page id 꼴이 아닙니다" });

  const r = await fetch(`https://api.notion.com/v1/pages/${page_id}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${env.NOTION_TOKEN}`,
      "Notion-Version": 노션판,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ properties: { "검토 여부": { select: { name: 값 } } } }),
  });
  if (!r.ok) {
    const 몸 = await r.text();
    // 토큰이 로그나 화면에 안 나오게 앞부분만 돌려줍니다.
    return json(502, { 오류: `노션 ${r.status}: ${몸.slice(0, 200)}` });
  }
  return json(200, { ok: true, page_id, 검토: 값 });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (!통과했나(request, env)) {
      return json(403, { 오류: "Access 를 거치지 않았습니다" });
    }

    if (url.pathname === "/api/review") {
      if (request.method !== "POST") return json(405, { 오류: "POST 로 보내십시오" });
      return 검토쓰기(request, env);
    }
    // 로컬에만 있는 자리들. 여기서는 없다고 알려 줍니다.
    if (url.pathname === "/api/run" || url.pathname === "/api/status") {
      return json(404, {
        오류: "일감 돌리기는 로컬에서만 됩니다. 수집은 GitHub Actions 가 여섯 시간마다 합니다",
      });
    }

    const 답 = await env.ASSETS.fetch(request);
    const h = new Headers(답.headers);
    h.set("X-Robots-Tag", "noindex, nofollow, noarchive");
    h.set("Content-Security-Policy",
      "default-src 'self'; script-src 'self' 'unsafe-inline'; " +
      "style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:");
    h.set("Referrer-Policy", "no-referrer");
    // 구운 데이터가 캐시에 남지 않게 합니다. 여섯 시간마다 바뀝니다.
    if (url.pathname.startsWith("/data/")) h.set("Cache-Control", "no-store");
    return new Response(답.body, { status: 답.status, headers: h });
  },
};
