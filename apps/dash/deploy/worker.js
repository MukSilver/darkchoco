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
 * **팀이 함께 쓰는 비밀번호 하나로 잠급니다.** 브라우저 기본 인증(Basic)이라 처음 열 때
 * 창이 뜨고, 한 번 넣으면 브라우저가 기억합니다. 비밀번호는 Cloudflare 비밀값
 * `DASH_PASSWORD` 에 둡니다.
 *
 * **원래는 Cloudflare Access 로 잠그려 했습니다.** 그런데 Access 는 Cloudflare 에
 * 등록된 도메인에만 걸립니다 — `workers.dev` 주소에는 못 겁니다. 도메인을 사면 그때
 * 옮기면 되고, 그 준비로 Access 헤더도 같이 봅니다. 둘 중 하나만 맞으면 통과합니다.
 *
 * **`DASH_PASSWORD` 가 없으면 아무도 못 들어옵니다.** 비밀값을 깜빡한 채 배포했을 때
 * 화면이 통째로 열려 있는 것보다 낫습니다.
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

/** 글자 수가 같은지부터 보고 한 글자씩 끝까지 본다. 답이 오는 시간으로 비밀번호를
 *  더듬는 것을 막는다. 짧은 비밀번호라 큰 뜻은 없지만 이렇게 두는 것이 맞다. */
function 같나(a, b) {
  if (a.length !== b.length) return false;
  let 다름 = 0;
  for (let i = 0; i < a.length; i++) 다름 |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return 다름 === 0;
}

/** 들어와도 되나. Access 를 거쳤거나 비밀번호가 맞으면 된다. */
function 통과했나(request, env) {
  // 도메인이 생겨 Access 를 걸면 이 헤더가 붙는다. 그때는 비밀번호가 필요 없다.
  if (request.headers.get("Cf-Access-Jwt-Assertion")) return true;

  const 쓸것 = env.DASH_PASSWORD || "";
  // **비밀값이 없으면 아무도 못 들어온다.** 깜빡하고 배포했을 때 통째로 열리는 것보다 낫다.
  if (!쓸것) return false;

  const 인증 = request.headers.get("Authorization") || "";
  if (!인증.startsWith("Basic ")) return false;
  let 푼것;
  try {
    // **atob 만 쓰면 한글 비밀번호가 안 맞는다.** atob 는 바이트를 Latin-1 글자로
    // 돌려주는데, 브라우저는 비ASCII 를 UTF-8 로 인코딩해 보낸다. 바이트로 되돌려
    // UTF-8 로 읽어야 원래 글자가 나온다. 영문만 쓰면 우연히 맞아 안 드러난다.
    const 바이트 = Uint8Array.from(atob(인증.slice(6)), (c) => c.charCodeAt(0));
    푼것 = new TextDecoder("utf-8").decode(바이트);
  } catch {
    return false;
  }
  const 자리 = 푼것.indexOf(":");
  const 온것 = 자리 < 0 ? 푼것 : 푼것.slice(자리 + 1);   // 아이디는 안 본다
  return 같나(온것, 쓸것);
}

/** 브라우저가 비밀번호 창을 띄우게 한다. */
function 물어보기(env) {
  if (!env.DASH_PASSWORD) {
    return json(500, { 오류: "DASH_PASSWORD 가 없습니다. wrangler secret put 으로 넣으십시오" });
  }
  return new Response("비밀번호가 필요합니다.", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="darkchoco", charset="UTF-8"',
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
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

    if (!통과했나(request, env)) return 물어보기(env);

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
