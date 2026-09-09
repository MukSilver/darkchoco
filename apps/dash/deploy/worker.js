/**
 * 대시보드를 팀에 내주는 Worker.
 *
 * **로컬 PC 가 켜져 있지 않아도 최신을 봅니다.** 예전에는 최현서가 굽고 올려야만
 * 팀원 화면이 갱신됐습니다. 그러면 서버에 올린 뜻이 없습니다 (2026-09-08 지적).
 * 지금은 화면이 열릴 때마다 Worker 가 노션을 직접 읽습니다.
 *
 * ## 세 가지를 합니다
 *
 *   /data/dash.js    노션을 읽어 화면이 쓰는 데이터를 만들어 냅니다. 60초 캐시
 *   /api/review      O/X 를 노션 「검토 여부」 한 칸에 씁니다
 *   /api/run         GitHub Actions 수집을 시작시킵니다
 *   /api/status      그 실행이 어디까지 갔는지 봅니다
 *
 * 로컬의 `serve.py` · `api.py` · `run_jobs.py` 가 하는 일과 같은 자리입니다.
 * 남의 서버에서는 파이썬이 못 돌고 최현서 PC 의 수집기도 못 부르므로, 수집은
 * GitHub Actions 에 맡기고 여기서는 그 시작과 상태만 다룹니다.
 *
 * ## 무엇을 쓰나
 *
 * 노션에는 **「검토 여부」 하나뿐입니다.** 값도 셋(미검토 · 사건 O · 사건 X)만
 * 받습니다. 그 밖의 칸도, 줄을 만들거나 지우는 것도 안 합니다.
 * GitHub 에는 **아래 목록에 있는 워크플로만** 시작시킵니다. 임의 실행은 없습니다.
 * 토큰 둘은 Cloudflare 비밀값에만 있고 브라우저로 안 갑니다.
 *
 * ## 누가 들어오나
 *
 * **팀이 함께 쓰는 비밀번호 하나로 잠급니다.** 브라우저 기본 인증(Basic)이라 처음
 * 열 때 창이 뜨고, 한 번 넣으면 브라우저가 기억합니다. 아이디는 안 봅니다.
 *
 * **원래는 Cloudflare Access 로 잠그려 했습니다.** 그런데 Access 는 Cloudflare 에
 * 등록된 도메인에만 걸립니다 — `workers.dev` 주소에는 못 겁니다. 도메인을 사면 그때
 * 옮기면 되고, 그 준비로 Access 헤더도 같이 봅니다. 둘 중 하나만 맞으면 통과합니다.
 *
 * **`DASH_PASSWORD` 가 없으면 아무도 못 들어옵니다.** 비밀값을 깜빡한 채 배포했을 때
 * 화면이 통째로 열려 있는 것보다 낫습니다.
 *
 * **`wrangler.jsonc` 의 `run_worker_first` 를 지웁니다면 이 파일 전체가 안 돕니다.**
 * 기본값에서는 정적 자산이 Worker 보다 먼저 서빙되어 인증이 통째로 우회됩니다.
 * 2026-09-08 에 실제로 그렇게 열려 있었습니다.
 */

const 검토값 = new Set(["미검토", "사건 O", "사건 X"]);
const 노션판 = "2025-09-03";

/** 노션 수집 DB 의 데이터 소스 id. `hub/events/push.py` 의 `수집DB` 와 같은 값입니다.
 *  이 값만으로는 아무것도 못 읽습니다 — 토큰이 있어야 합니다. */
const 수집DS = "5160ce53-7ce2-4271-879e-06f3ad9957cf";

const 레포 = "MukSilver/darkchoco";

/**
 * 화면에서 눌러 돌릴 수 있는 것. **여기 있는 것만 됩니다.** 화면은 열쇠만 보냅니다.
 *
 * 로컬 `run_jobs.py` 의 일감표와 같은 구실이지만 목록이 다릅니다. 여기서 돌릴 수
 * 있는 것은 **GitHub Actions 워크플로가 있는 일감뿐**입니다.
 *
 * 2026-09-09 에 「게시 상태 추적」 이 들어왔습니다. `track.py agg` 를 그대로 올린
 * 것이 아니라 `track_push.py` 라는 다른 도구입니다. 저장 자리가 로컬 SQLite 가
 * 아니라 노션 관측 칸이라야 실행마다 새 컨테이너인 곳에서 이력이 이어집니다.
 *
 * `track.py` 의 나머지 둘(사람 관측 넣기 · 보고서)은 로컬에만 있습니다. 앞엣것은
 * 사람이 Tor 로 보고 적는 것이고 뒤엣것은 로컬 표를 읽어 md 를 냅니다.
 */
const 일감표 = {
  수집: {
    이름: "수집 한 바퀴 (텔레그램 + 랜섬)",
    설명: "채널을 훑고 랜섬 집계처를 한 번 봅니다. 몇 분 걸립니다",
    밖: true,
    파일: "collect.yml",
    입력: { do_ransom: "true", do_telegram: "true", push_to_notion: "true" },
  },
  랜섬: {
    이름: "랜섬웨어만",
    설명: "ransomware.live 한국 피해자 한 판",
    밖: true,
    파일: "collect.yml",
    입력: { do_ransom: "true", do_telegram: "false", push_to_notion: "true" },
  },
  텔레그램: {
    이름: "텔레그램만",
    설명: "공개 미리보기가 열린 채널만 봅니다",
    밖: true,
    파일: "collect.yml",
    입력: { do_ransom: "false", do_telegram: "true", push_to_notion: "true" },
  },
  미리보기: {
    이름: "긁기만 하고 노션에 안 올리기",
    설명: "무엇이 올라갈지만 봅니다. 노션에 안 씁니다",
    밖: true,
    파일: "collect.yml",
    입력: { do_ransom: "true", do_telegram: "true", push_to_notion: "false" },
  },
  추적: {
    이름: "게시 상태 추적",
    설명: "랜섬 게시물이 아직 살아 있는지 보고 노션 관측 칸에 적습니다",
    밖: true,
    파일: "track.yml",
    입력: { write_to_notion: "true" },
  },
  추적미리: {
    이름: "게시 상태 추적 — 미리보기",
    설명: "무엇이 바뀔지만 봅니다. 노션에 안 씁니다",
    밖: true,
    파일: "track.yml",
    입력: { write_to_notion: "false" },
  },
};

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

// ── 노션 읽기 ────────────────────────────────────────────────────────────

function _rt(p, 칸) {
  const v = ((p || {})[칸] || {}).rich_text || [];
  return v.map((x) => x.plain_text || "").join("").trim();
}

function _sel(p, 칸) {
  return ((((p || {})[칸] || {}).select) || {}).name || "";
}

function _date(p, 칸) {
  return ((((p || {})[칸] || {}).date) || {}).start || "";
}

/**
 * 노션 수집 DB 를 줄 목록으로. **본문과 개인정보 값은 안 담습니다.**
 * `apps/dash/build.py` 의 `사건()` 과 같은 칸을 같은 이름으로 뽑습니다.
 * 한쪽을 고치면 다른 쪽도 같이 고쳐야 화면이 안 깨집니다.
 */
async function 사건읽기(token) {
  const out = [];
  let cursor = null;
  // **끝없이 돌지 않게 상한을 둡니다.** 100줄씩 스무 번이면 2000줄입니다.
  for (let i = 0; i < 20; i++) {
    const body = { page_size: 100 };
    if (cursor) body.start_cursor = cursor;
    const r = await fetch(`https://api.notion.com/v1/data_sources/${수집DS}/query`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Notion-Version": 노션판,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const 몸 = await r.text();
      throw new Error(`노션 ${r.status}: ${몸.slice(0, 200)}`);
    }
    const res = await r.json();
    for (const row of res.results || []) {
      const p = row.properties || {};
      const 제목 = ((p["자료 제목"] || {}).title || [])
        .map((x) => x.plain_text || "").join("").trim();
      const 번호 = (p["사건 ID"] || {}).unique_id || {};
      out.push({
        id: row.id || "",
        번호: 번호.number != null ? `${번호.prefix || ""}-${번호.number}` : "",
        제목: 제목,
        대상: _rt(p, "대상 조직"),
        자리: _rt(p, "게시 플랫폼"),
        핸들: _rt(p, "게시자 핸들"),
        url: _rt(p, "원문 URL"),
        검토: _sel(p, "검토 여부"),
        소스: _sel(p, "소스"),
        한국: _sel(p, "한국 관련"),
        근거: _rt(p, "한국 관련 근거"),
        성격: _sel(p, "게시 성격"),
        국가: _sel(p, "국가"),
        규모: _rt(p, "주장 규모"),
        상태: _sel(p, "상태"),
        수집자: _sel(p, "수집자"),
        게시: _date(p, "게시 시각").slice(0, 10),
        수집일: _date(p, "수집일").slice(0, 10),
        발견: _date(p, "발견일").slice(0, 10),
        관측시각: _date(p, "관측 시각").slice(0, 16),
        게시상태: _sel(p, "게시 상태"),
        웹: _sel(p, "웹에 올림"),
      });
    }
    if (!res.has_more) break;
    cursor = res.next_cursor;
  }
  return out;
}

/**
 * 화면이 그대로 쓰는 `window.DASH` 를 만듭니다.
 *
 * **「수집 표」 절은 서버판에 안 냅니다.** 그 숫자는 최현서 PC 의 SQLite 를 센 것이라
 * 여기서는 셀 수가 없습니다. 0 을 내면 「표가 비었다」 로 읽혀 더 나쁩니다.
 * `서버: true` 를 보고 화면이 그 절 대신 다른 문구를 냅니다.
 */
function 이제(now) {
  // KST 로 적습니다. 팀이 다 한국에 있고 노션 날짜도 KST 로 적혀 있습니다.
  return new Date(now + 9 * 3600 * 1000).toISOString().slice(0, 16).replace("T", " ");
}

async function 데이터만들기(env, now) {
  const 사건 = await 사건읽기(env.NOTION_TOKEN);
  const 검토별 = {};
  for (const e of 사건) 검토별[e.검토 || "미검토"] = (검토별[e.검토 || "미검토"] || 0) + 1;
  return {
    구운때: 이제(now) + " (노션에서 방금 읽음)",
    제어판: {
      서버: true,
      표: "GitHub Actions (여섯 시간마다)",
      표있음: true,
      줄수: 사건.length,
      관측: 0,
      마지막수집: "",
      소스별: {},
      실행: [],
      설정: [],
      명령: [],
      일감: Object.keys(일감표).map((k) => ({
        열쇠: k,
        이름: 일감표[k].이름,
        설명: 일감표[k].설명,
        밖: 일감표[k].밖,
      })),
    },
    요약: { 자리: {}, 자리합: 0, 지도날: "" },
    사건: 사건,
    검토별: 검토별,
    노션읽음: true,
  };
}

/** 노션을 매 요청마다 읽지 않게 잠깐 들고 있습니다. 여섯 시간마다 바뀌는 데이터라
 *  1분이면 충분하고, 여러 사람이 같이 볼 때 노션 쪽 요청이 확 줄어듭니다. */
let 캐시 = { 언제: 0, 몸: null };
const 캐시초 = 60;

async function 데이터내기(env, now) {
  if (!env.NOTION_TOKEN) {
    return new Response(
      "window.DASH={오류:'NOTION_TOKEN 이 없습니다. wrangler secret put 으로 넣으십시오'};",
      { status: 200, headers: { "Content-Type": "application/javascript; charset=utf-8", "Cache-Control": "no-store" } },
    );
  }
  if (캐시.몸 && now - 캐시.언제 < 캐시초 * 1000) {
    return new Response(캐시.몸, {
      headers: {
        "Content-Type": "application/javascript; charset=utf-8",
        "Cache-Control": "no-store",
        "X-Dash-Cache": "hit",
      },
    });
  }
  let 몸;
  try {
    const d = await 데이터만들기(env, now);
    몸 = "window.DASH=" + JSON.stringify(d) + ";";
    캐시 = { 언제: now, 몸: 몸 };
  } catch (e) {
    // **옛 것이라도 있으면 그것을 냅니다.** 노션이 잠깐 안 될 때 화면이 통째로
    // 비는 것보다 낫습니다. 아무것도 없으면 화면에 이유를 보입니다.
    if (캐시.몸) {
      return new Response(캐시.몸, {
        headers: {
          "Content-Type": "application/javascript; charset=utf-8",
          "Cache-Control": "no-store",
          "X-Dash-Cache": "stale",
        },
      });
    }
    const 말 = String((e && e.message) || e).replace(/[\\'"]/g, " ");
    몸 = "window.DASH={오류:'노션을 못 읽었습니다: " + 말 + "'};";
  }
  return new Response(몸, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Dash-Cache": "miss",
    },
  });
}

// ── 노션 쓰기 ────────────────────────────────────────────────────────────

/** 다른 웹페이지가 이 주소로 보내는 것을 막습니다(CSRF). 브라우저는 그때 Origin 을 붙입니다. */
function 남의자리인가(request) {
  const 본 = request.headers.get("Origin");
  if (!본) return false;
  return 본 !== new URL(request.url).origin;
}

async function 검토쓰기(request, env) {
  if (남의자리인가(request)) return json(403, { 오류: "다른 자리에서 온 요청입니다" });
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
  // 눌러서 바뀐 것이 다음 조회에 바로 보이게 캐시를 버립니다.
  캐시 = { 언제: 0, 몸: null };
  return json(200, { ok: true, page_id, 검토: 값 });
}

// ── GitHub Actions 돌리기 ────────────────────────────────────────────────

function gh머리(token) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    // GitHub 은 User-Agent 가 없으면 403 을 냅니다.
    "User-Agent": "darkchoco-dash",
  };
}

/** 최근 실행 하나를 화면이 아는 모양으로 바꿉니다.
 *  화면은 `{열쇠, 돌고있나, 줄, 코드, 끝}` 을 기다립니다 (index.html 상태그리기). */
function 실행을상태로(열쇠, run) {
  if (!run) {
    return { 열쇠, 돌고있나: false, 줄: ["최근 실행이 없습니다"], 코드: 0, 끝: "" };
  }
  const 도나 = run.status !== "completed";
  const 줄 = [
    `실행 #${run.run_number} · ${run.status}${run.conclusion ? " · " + run.conclusion : ""}`,
    `시작 ${run.run_started_at || run.created_at || ""}`,
    `무엇 ${run.display_title || run.name || ""}`,
    `자세히 ${run.html_url || ""}`,
  ];
  if (도나) 줄.push("도는 중입니다. GitHub 쪽이라 화면에 로그는 안 옵니다");
  return {
    열쇠,
    돌고있나: 도나,
    줄,
    코드: run.conclusion === "success" ? 0 : (run.conclusion ? 1 : 0),
    끝: run.updated_at || "",
  };
}

async function 최근실행(env) {
  const r = await fetch(
    `https://api.github.com/repos/${레포}/actions/workflows/collect.yml/runs?per_page=1`,
    { headers: gh머리(env.GH_TOKEN) },
  );
  if (!r.ok) {
    const 몸 = await r.text();
    throw new Error(`GitHub ${r.status}: ${몸.slice(0, 200)}`);
  }
  const d = await r.json();
  return (d.workflow_runs || [])[0] || null;
}

async function 돌리기(request, env) {
  if (남의자리인가(request)) return json(403, { 오류: "다른 자리에서 온 요청입니다" });
  if (!env.GH_TOKEN) {
    return json(500, {
      오류: "GH_TOKEN 이 없습니다. wrangler secret put GH_TOKEN 으로 넣으십시오",
    });
  }
  let d;
  try {
    d = await request.json();
  } catch {
    return json(400, { 오류: "json 이 아닙니다" });
  }
  const 열쇠 = String((d && d.열쇠) || "");
  const 일감 = 일감표[열쇠];
  // **목록에 있는 것만 됩니다.** 화면이 보낸 글자로 아무 워크플로나 부르지 않습니다.
  if (!일감) return json(400, { 오류: `모르는 일감입니다: ${열쇠}` });

  // 이미 도는 중이면 또 시작하지 않습니다. 같은 노션 DB 에 둘이 쓰면 겹침 판정이
  // 어긋납니다. 워크플로 쪽에도 concurrency 가 걸려 있지만 여기서 먼저 막습니다.
  let 앞것 = null;
  try {
    앞것 = await 최근실행(env);
  } catch (e) {
    return json(502, { 오류: String((e && e.message) || e) });
  }
  if (앞것 && 앞것.status !== "completed") {
    return json(409, {
      오류: `이미 도는 중입니다 (실행 #${앞것.run_number}). 끝나면 다시 누르십시오`,
    });
  }

  const r = await fetch(
    `https://api.github.com/repos/${레포}/actions/workflows/${일감.파일}/dispatches`,
    {
      method: "POST",
      headers: { ...gh머리(env.GH_TOKEN), "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main", inputs: 일감.입력 }),
    },
  );
  if (!r.ok) {
    const 몸 = await r.text();
    return json(502, { 오류: `GitHub ${r.status}: ${몸.slice(0, 200)}` });
  }
  return json(200, {
    열쇠,
    돌고있나: true,
    코드: 0,
    끝: "",
    줄: [
      `${일감.이름} 을 GitHub Actions 에 맡겼습니다`,
      "실행이 목록에 뜨기까지 몇 초 걸립니다",
      "로그는 GitHub 쪽에 있습니다. 아래 주소로 볼 수 있습니다",
      `https://github.com/${레포}/actions/workflows/${일감.파일}`,
    ],
  });
}

async function 상태보기(request, env) {
  if (!env.GH_TOKEN) return json(500, { 오류: "GH_TOKEN 이 없습니다" });
  let 열쇠 = "";
  try {
    열쇠 = String(((await request.json()) || {}).열쇠 || "");
  } catch {
    열쇠 = "";
  }
  try {
    const run = await 최근실행(env);
    const s = 실행을상태로(열쇠, run);
    // 수집이 끝났으면 다음 조회에서 새 줄이 보이게 캐시를 버립니다.
    if (!s.돌고있나) 캐시 = { 언제: 0, 몸: null };
    return json(200, s);
  } catch (e) {
    return json(502, { 오류: String((e && e.message) || e), 돌고있나: false, 줄: [] });
  }
}

// ── 들어오는 것 가르기 ───────────────────────────────────────────────────

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (!통과했나(request, env)) return 물어보기(env);

    if (url.pathname === "/api/review") {
      if (request.method !== "POST") return json(405, { 오류: "POST 로 보내십시오" });
      return 검토쓰기(request, env);
    }
    if (url.pathname === "/api/run") {
      if (request.method !== "POST") return json(405, { 오류: "POST 로 보내십시오" });
      return 돌리기(request, env);
    }
    if (url.pathname === "/api/status") {
      if (request.method !== "POST") return json(405, { 오류: "POST 로 보내십시오" });
      return 상태보기(request, env);
    }

    // **구운 파일 대신 노션에서 방금 읽은 것을 냅니다.** 정적 자산에도 같은 이름의
    // 파일이 있지만 여기서 가로채므로 안 나갑니다. 로컬 serve.py 에서는 그 파일이
    // 그대로 쓰입니다.
    if (url.pathname === "/data/dash.js") {
      return 데이터내기(env, Date.now());
    }

    const 답 = await env.ASSETS.fetch(request);
    const h = new Headers(답.headers);
    h.set("X-Robots-Tag", "noindex, nofollow, noarchive");
    h.set("Content-Security-Policy",
      "default-src 'self'; script-src 'self' 'unsafe-inline'; " +
      "style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:");
    h.set("Referrer-Policy", "no-referrer");
    return new Response(답.body, { status: 답.status, headers: h });
  },
};
