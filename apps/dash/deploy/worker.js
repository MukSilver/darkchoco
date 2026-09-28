/**
 * 대시보드를 팀에 내주는 Worker.
 *
 * **로컬 PC 가 켜져 있지 않아도 최신을 봅니다.** 예전에는 최현서가 굽고 올려야만
 * 팀원 화면이 갱신됐습니다. 그러면 서버에 올린 뜻이 없습니다 (2026-09-08 지적).
 * 지금은 화면이 열릴 때마다 Worker 가 노션을 직접 읽습니다.
 *
 * ## 하는 일
 *
 *   /data/dash.js    노션을 읽어 화면이 쓰는 데이터를 만들어 냅니다. 60초 캐시.
 *                    게시처 DB 셋은 건수만 담습니다 (2026-09-25, 명부읽기)
 *   /api/review      O/X 를 노션 「검토 여부」 에 쓰고 규칙대로 「DB 반영」 을 맞춥니다
 *   /api/run         GitHub Actions 수집을 시작시킵니다
 *   /api/status      그 실행이 어디까지 갔는지 봅니다
 *   /api/forum-rows  포럼 킷이 낸 칸 값을 수집 DB 에 새 줄로 올립니다 (2026-09-23)
 *
 * 로컬의 `serve.py` · `api.py` · `run_jobs.py` 가 하는 일과 같은 자리입니다.
 * 남의 서버에서는 파이썬이 못 돌고 최현서 PC 의 수집기도 못 부르므로, 수집은
 * GitHub Actions 에 맡기고 여기서는 그 시작과 상태만 다룹니다.
 *
 * ## 무엇을 쓰나
 *
 * 노션에는 **「검토 여부」 와, 그에 딸린 「DB 반영」 둘뿐입니다.** 값은 셋(미검토 ·
 * 사건 O · 사건 X)만 받습니다. 「DB 반영」 은 화면이 정하지 않고 `공개로()` 규칙이
 * 정합니다. 그 밖의 칸도, 줄을 지우는 것도 안 합니다. **줄을 만드는 것은 포럼 사건
 * 하나뿐입니다** — 사람이 화면에서 미리 보고 누를 때만이고, 미검토 · 공개 꺼짐으로 들어갑니다.
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

/**
 * **어느 DB 의 어느 칸을 낼지는 여기가 아니라 `dbs.json` 이 정합니다.**
 *
 * 굽는 쪽(`build.py`)이 같은 파일을 읽습니다. 전에는 칸 목록이 두 코드에 따로
 * 박혀 있어서, 한쪽을 고치고 다른 쪽을 잊으면 로컬과 배포가 다른 화면이 됐습니다.
 * wrangler 가 번들할 때 이 JSON 을 같이 넣습니다.
 */
import 레지스트리 from "../dbs.json";

const 검토값 = new Set(["미검토", "사건 O", "사건 X"]);
const 노션판 = "2025-09-03";

/** 노션 수집 DB 의 데이터 소스 id. `hub/events/push.py` 의 `수집DB` · `dbs.json` 과
 *  같은 값입니다. 이 값만으로는 아무것도 못 읽습니다 — 토큰이 있어야 합니다. */
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
 *
 * **2026-09-13 에 여섯을 넷으로 줄였습니다.** 게시 상태 추적이 수집에 붙었습니다.
 * 단추가 따로 있을 때는 「긁고 나서 추적을 또 눌러야 한다」 를 사람이 외워야 했고,
 * 실제로 추적이 나흘 밤을 안 돌았습니다. `collect.yml` 이 `track.yml` 을
 * `workflow_call` 로 부르므로 워크플로 파일은 둘 다 그대로 있고 각자 혼자서도
 * 돕니다. 화면에서만 하나로 보입니다.
 *
 * `do_track` 은 **누를 때만 켭니다.** 스케줄로 도는 수집에는 안 붙입니다. 추적은
 * 집계처에 요청 한 번이라 하루 한 번이면 충분하고 그것은 track.yml 자기 스케줄이
 * 합니다. 여섯 시간마다 같이 돌면 같은 일을 네 배로 합니다.
 *
 * `노션` 은 **이 일감이 끝났을 때 노션이 달라져 있는가**입니다. 미리보기만
 * false 입니다. 화면은 이 값이 참일 때만 끝나고 나서 다시 읽고, 이 파일에서는
 * 이 값이 참일 때만 캐시를 버립니다. 안 바뀐 것을 다시 읽으면 같은 화면을
 * 받으려고 노션 요청만 한 번 더 나가고, 그 사이에 로그가 지워집니다.
 * **2026-09-22 에 넷을 아홉으로 늘렸습니다.** 수집은 [포럼 · 텔레그램 · 랜섬] 에
 * [명부 · 사건] 을 곱한 여섯 칸인데, 화면에서 누를 수 있는 것이 사건 쪽 둘뿐이었고
 * 명부 셋은 VM 을 켜야만 돌았습니다. 그래서 명부 셋이 전부 비어 있었습니다.
 * `places.yml` 이 생기면서 명부도 여기서 누를 수 있게 됐습니다.
 *
 * `종류` 를 새로 둡니다.
 *
 *     "밖"   GitHub Actions 를 시작시킵니다. `파일` 과 `입력` 이 있어야 합니다
 *     "손"   사람이 화면에서 하는 일입니다. `길` 로 갑니다. dispatch 가 아닙니다
 *
 * **이 칸이 없으면 조용히 엉뚱한 데로 갑니다.** 포럼 사건은 워크플로가 없는데,
 * `파일` 없이 표에 넣으면 `.../workflows/undefined/dispatches` 로 나가고
 * `상태보기()` 는 `|| "collect.yml"` 이라 **다른 워크플로의 지난 실행을** 보여
 * 줍니다. 그래서 두 함수 앞에 관문을 겁니다.
 */
const 일감표 = {
  // ── 사건 ────────────────────────────────────────────────
  사건전부: {
    무리: "사건",
    이름: "사건 한 바퀴 (텔레그램 + 랜섬 + 게시 상태)",
    설명: "채널과 랜섬 집계처를 훑고, 이어서 게시물이 아직 살아 있는지까지 봅니다",
    종류: "밖",
    밖: true,
    노션: true,
    파일: "collect.yml",
    입력: { do_ransom: "true", do_telegram: "true", push_to_notion: "true", do_track: "true" },
  },
  랜섬사건: {
    무리: "사건",
    이름: "랜섬 사건",
    설명: "ransomware.live 한국 피해자 한 판",
    종류: "밖",
    밖: true,
    노션: true,
    파일: "collect.yml",
    입력: { do_ransom: "true", do_telegram: "false", push_to_notion: "true", do_track: "false" },
  },
  텔레그램사건: {
    무리: "사건",
    이름: "텔레그램 사건",
    설명: "공개 미리보기가 열린 채널만 봅니다",
    종류: "밖",
    밖: true,
    노션: true,
    파일: "collect.yml",
    입력: { do_ransom: "false", do_telegram: "true", push_to_notion: "true", do_track: "false" },
  },
  사건미리보기: {
    무리: "사건",
    이름: "사건 미리보기 — 아무것도 안 씁니다",
    설명: "무엇이 올라가고 무엇이 바뀔지를 함께 봅니다. 노션에 안 씁니다",
    종류: "밖",
    밖: true,
    노션: false,
    파일: "collect.yml",
    입력: { do_ransom: "true", do_telegram: "true", push_to_notion: "false", do_track: "true" },
  },

  // 포럼 사건은 워크플로가 없습니다. 포럼은 로그인과 챌린지가 있어 러너가 대신 못 봅니다.
  // 사람이 포럼에서 킷을 누르고, 킷이 낸 칸 값을 이 화면이 받아 올립니다 (2026-09-23)
  포럼사건: {
    무리: "사건",
    이름: "포럼 사건 올리기",
    설명: "포럼 킷이 낸 칸 값을 받아 미리 보고 수집 DB 에 올립니다. 본문은 안 받습니다",
    종류: "손",
    밖: false,
    노션: true,
    길: "#forum-rows",
  },

  // ── 명부 ────────────────────────────────────────────────
  // 포럼·랜섬은 러너에서 Tor 를 거칩니다. 텔레그램은 t.me 라 안 거칩니다.
  // 잡이 둘로 갈려 있어 `only` 가 그것을 고릅니다
  명부전부: {
    무리: "명부",
    이름: "명부 한 바퀴 (포럼 + 랜섬 + 텔레그램)",
    설명: "명부 셋을 훑어 어디가 살아 있는지 봅니다. 포럼·랜섬은 Tor 를 거칩니다",
    종류: "밖",
    밖: true,
    노션: true,
    파일: "places.yml",
    입력: { only: "all", write_to_notion: "true", limit: "0" },
  },
  포럼명부: {
    무리: "명부",
    이름: "포럼 명부",
    설명: "포럼이 살아 있는지, 회원 수가 얼마인지. Tor 를 거칩니다",
    종류: "밖",
    밖: true,
    노션: true,
    파일: "places.yml",
    입력: { only: "forum", write_to_notion: "true", limit: "0" },
  },
  랜섬명부: {
    무리: "명부",
    이름: "랜섬 명부",
    설명: "랜섬 그룹의 유출 사이트가 살아 있는지. Tor 를 거칩니다",
    종류: "밖",
    밖: true,
    노션: true,
    파일: "places.yml",
    입력: { only: "ransom", write_to_notion: "true", limit: "0" },
  },
  텔레그램명부: {
    무리: "명부",
    이름: "텔레그램 명부",
    설명: "채널이 살아 있는지, 구독자가 몇인지. t.me 라 Tor 를 안 거칩니다",
    종류: "밖",
    밖: true,
    노션: true,
    파일: "places.yml",
    입력: { only: "telegram", write_to_notion: "true", limit: "0" },
  },
  명부미리보기: {
    무리: "명부",
    이름: "명부 미리보기 — 아무것도 안 씁니다",
    설명: "명부 셋을 열어는 보고 노션에만 안 씁니다",
    종류: "밖",
    밖: true,
    노션: false,
    파일: "places.yml",
    입력: { only: "all", write_to_notion: "false", limit: "0" },
  },
};

/**
 * 옛 열쇠. **한 판만 남깁니다.**
 *
 * 이름을 바꾸는 순간, 이미 열려 있는 탭이 옛 열쇠로 `/api/run` 을 부르면
 * 「모르는 일감입니다」 400 을 받습니다. 배포 직후에 팀원이 그것을 봅니다.
 * 2026-09-29 쯤 지웁니다.
 */
const 옛열쇠 = {
  수집: "사건전부",
  랜섬: "랜섬사건",
  텔레그램: "텔레그램사건",
  미리보기: "사건미리보기",
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

/**
 * 노션 속성 하나를 값으로. **칸 이름을 모릅니다. 종류만 봅니다.**
 *
 * `apps/dash/reader.py` 의 `값()` 과 같은 규칙입니다. 언어가 달라 두 벌인데,
 * **어느 칸을 낼지는 `dbs.json` 한 장을 같이 읽어서** 어긋날 자리가 여기뿐입니다.
 * 전에는 칸 목록까지 두 벌이라 한쪽을 고치고 다른 쪽을 잊었습니다.
 *
 * 둘은 따로 다룹니다. `relation` 은 **개수만** — page id 를 그대로 내면
 * 레지스트리 밖 DB 의 줄을 짚는 열쇠가 나갑니다. `people` 은 **찼는지만** —
 * 실명이 들어가는 자리입니다.
 */
function 값(속성) {
  const v = 속성 || {};
  const t = v.type || "";

  if (t === "title") return (v.title || []).map((x) => x.plain_text || "").join("").trim();
  if (t === "rich_text") return (v.rich_text || []).map((x) => x.plain_text || "").join("").trim();
  if (t === "select" || t === "status") return (v[t] || {}).name || "";
  if (t === "multi_select") return (v.multi_select || []).map((x) => x.name || "");
  if (t === "date") return (v.date || {}).start || "";
  if (t === "checkbox") return !!v.checkbox;
  if (t === "number") return v.number;
  if (t === "url") return v.url || "";
  if (t === "unique_id") {
    const u = v.unique_id || {};
    return u.number != null ? `${u.prefix || ""}-${u.number}` : "";
  }
  if (t === "created_time" || t === "last_edited_time") return v[t] || "";

  if (t === "relation") return (v.relation || []).length;
  if (t === "files") return (v.files || []).length;

  if (t === "people" || t === "created_by" || t === "last_edited_by") {
    const 것 = v[t];
    const 있나 = Array.isArray(것) ? 것.length > 0 : !!것;
    return 있나 ? "기입됨" : "미기입";
  }

  // 한 겹 벗겨 다시 봅니다. 안에 든 것이 위의 종류 중 하나입니다
  if (t === "formula") {
    const f = v.formula || {};
    return f.type ? (f[f.type] ?? "") : "";
  }
  if (t === "rollup") {
    const r = v.rollup || {};
    if (r.type === "array") return (r.array || []).map((x) => 값(x));
    return r.type ? (r[r.type] ?? "") : "";
  }

  // **모르는 종류를 지어내지 않습니다.** 빈칸은 화면에 보이므로 사람이 알아챕니다
  return "";
}

/** 실명 선택지를 사람 / 자동 / 미기입 셋으로 접습니다. */
function _사람자동(v) {
  const s = typeof v === "string" ? v.trim() : "";
  if (!s || s === "미기입") return "미기입";
  return s === "자동" ? "자동" : "사람";
}

/** 찼는지만 냅니다. 검증자·기록자·담당자처럼 **실명만 들어가는** 칸입니다. */
function _있없(v) {
  if (typeof v === "string") return v.trim() && v.trim() !== "미기입" ? "기입됨" : "미기입";
  return v ? "기입됨" : "미기입";
}

/** 줄글의 첫 줄만. 검증 요약처럼 1,500자가 넘는 칸이 있습니다. */
function _첫줄(v) {
  return (typeof v === "string" ? v : "").split("\n")[0].slice(0, 120);
}

/** 시각을 KST 날짜로. UTC 15시 이후 글이 하루 앞서지 않게. reader.py 의 _KST날 과 같습니다 */
function _KST날(v) {
  const s = typeof v === "string" ? v.trim() : "";
  if (s.length <= 10) return s;
  // 시간대가 적혀 있을 때만 옮깁니다. 없으면 파이썬처럼 적힌 날을 그대로 씁니다
  if (!/(Z|[+-]\d{2}:?\d{2})$/i.test(s)) return s.slice(0, 10);
  const t = Date.parse(s);
  if (Number.isNaN(t)) return s.slice(0, 10);
  return new Date(t + 9 * 3600 * 1000).toISOString().slice(0, 10);
}

const 접개 = { 사람자동: _사람자동, 있없: _있없, 첫줄: _첫줄, KST날: _KST날 };

/** 노션 페이지 하나를 `dbs.json` 이 적은 대로 옮깁니다. */
function 줄(페이지, 칸들) {
  const p = 페이지.properties || {};
  const out = { id: 페이지.id || "" };
  for (const c of 칸들) {
    let v = 값(p[c.노션]);
    if (c.접기) {
      const f = 접개[c.접기];
      if (!f) throw new Error(`모르는 접기 갈래입니다: ${c.접기} (dbs.json)`);
      v = f(v);
    } else if (c.날짜만 && typeof v === "string") {
      v = v.slice(0, 10);
    }
    out[c.낼] = v;
  }
  return out;
}

/** 레지스트리에서 DB 하나를 꺼냅니다. */
function DB하나(열쇠) {
  const d = (레지스트리.DB || []).find((x) => x.열쇠 === 열쇠);
  if (!d) throw new Error(`dbs.json 에 ${열쇠} 가 없습니다`);
  return d;
}

// ── 게시처 DB 집계 (2026-09-25). reader.py 의 명부셈 과 같습니다 ──
const 확인일갈래 = ["7일 안", "30일 안", "30일 넘음", "빈칸"];
const _날꼴 = /^\d{4}-\d{2}-\d{2}$/;
const _자리표시 = new Set(["미기입", "해당 없음", "없음", "-", "모름", "n/a"]);

function _갈래값(v) {
  return typeof v === "string" && v.trim() ? v.trim() : "빈칸";
}

/** 'YYYY-MM-DD' 를 날 수로. 없는 날(2026-13-45)은 NaN — Date.UTC 가 넘겨 버리므로 되돌려 봅니다 */
function _날수(s) {
  const [y, m, d] = s.split("-").map(Number);
  const t = Date.UTC(y, m - 1, d);
  if (new Date(t).toISOString().slice(0, 10) !== s) return NaN;
  return t / 86400000;
}

function _확인일갈래(v, 오늘) {
  const s = typeof v === "string" ? v.slice(0, 10) : "";
  if (!_날꼴.test(s)) return "빈칸";
  const 며칠 = _날수(오늘) - _날수(s);
  if (Number.isNaN(며칠)) return "빈칸";
  return 며칠 <= 7 ? "7일 안" : 며칠 <= 30 ? "30일 안" : "30일 넘음";
}

/** 한국 관련 유출에 실제로 무엇이 적혀 있나. 자리표시 · 「0건」 뿐인 기계 줄은 안 셉니다 */
function 한국유출있나(v) {
  if (typeof v !== "string") return false;
  // 파이썬 splitlines() 와 같은 줄 경계입니다
  for (const 한줄 of v.split(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/)) {
    const s = 한줄.trim();
    if (!s || _자리표시.has(s.toLowerCase())) continue;
    const 수들 = [...s.matchAll(/(\d[\d,]*)\s*건/g)].map((m) => Number(m[1].replace(/,/g, "")));
    if (수들.length && !수들.some((x) => x)) continue;
    return true;
  }
  return false;
}

/** 게시처 DB 줄들을 **건수로만** 셉니다. 이름 · 주소 · 담당자는 읽지도 않습니다 */
function 명부셈(페이지들, 칸, 오늘) {
  const out = { 줄수: 0, 상태: {}, 조사단계: {}, 확인일: {}, 한국유출: 0, DB반영: 0 };
  for (const k of 확인일갈래) out.확인일[k] = 0;
  for (const pg of 페이지들) {
    const p = pg.properties || {};
    out.줄수 += 1;
    for (const 열쇠 of ["상태", "조사단계"]) {
      const k = _갈래값(값(p[칸[열쇠]]));
      out[열쇠][k] = (out[열쇠][k] || 0) + 1;
    }
    out.확인일[_확인일갈래(값(p[칸.확인일]), 오늘)] += 1;
    if (한국유출있나(값(p[칸.한국유출]))) out.한국유출 += 1;
    if (값(p[칸.DB반영]) === true) out.DB반영 += 1;
  }
  return out;
}

/** 한 번에 읽을 판 수. 100줄씩이라 2000줄입니다. */
const 판상한 = 20;

/**
 * 노션 수집 DB 를 줄 목록으로. **본문과 개인정보 값은 안 담습니다.**
 * `apps/dash/build.py` 의 `사건()` 과 같은 칸을 같은 이름으로 뽑습니다.
 * 한쪽을 고치면 다른 쪽도 같이 고쳐야 화면이 안 깨집니다.
 *
 * `{줄들, 잘림}` 을 냅니다. **잘렸는지를 같이 내는 이유가 있습니다.**
 * 전에는 상한에 닿으면 그냥 멈췄고 화면에 아무 표시가 없었습니다. 로컬은
 * `query_all` 이 끝까지 읽어서 상한이 없으므로, 2000줄을 넘는 날 로컬과
 * 배포가 말없이 다른 화면이 됩니다. 모자란 것을 모르는 쪽이 더 나쁩니다.
 */
async function 사건읽기(token) {
  const 칸들 = DB하나("수집").칸;
  const out = [];
  let cursor = null;
  let 잘림 = false;
  for (let i = 0; i < 판상한; i++) {
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
    // **칸 목록이 여기 없습니다.** `dbs.json` 이 적은 대로 옮깁니다
    for (const row of res.results || []) out.push(줄(row, 칸들));
    if (!res.has_more) break;
    cursor = res.next_cursor;
    // 마지막 판을 다 읽었는데 노션이 아직 더 있다고 합니다. 여기서 멈춥니다
    if (i === 판상한 - 1) 잘림 = true;
  }
  return { 줄들: out, 잘림 };
}

/** 게시처 DB 한 갈래에서 읽을 판 수. 판상한 20 + 8 × 3 갈래 = 44 ≤ 무료 요금제 50 */
const 명부판상한 = 8;

/**
 * 게시처 DB 셋을 **건수로만** 셉니다 (2026-09-25). `apps/dash/build.py` 의 `명부()` 와 같습니다.
 * 줄은 세고 바로 버립니다. 이름 · 주소 · 담당자는 브라우저로 안 갑니다(반출경계표 7-1).
 */
async function 명부읽기(token, 오늘) {
  const m = 레지스트리.명부;
  const 갈래 = [];
  for (const g of m.갈래) {
    const 페이지들 = [];
    let cursor = null;
    let 잘림 = 0;
    for (let i = 0; i < 명부판상한; i++) {
      const body = { page_size: 100 };
      if (cursor) body.start_cursor = cursor;
      const r = await fetch(`https://api.notion.com/v1/data_sources/${g.id}/query`, {
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
      페이지들.push(...(res.results || []));
      if (!res.has_more) break;
      cursor = res.next_cursor;
      if (i === 명부판상한 - 1) 잘림 = 페이지들.length;
    }
    갈래.push({ 열쇠: g.열쇠, 이름: g.이름, 잘림, ...명부셈(페이지들, m.칸, 오늘) });
  }
  return { 오늘, 갈래 };
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
  const { 줄들: 사건, 잘림 } = await 사건읽기(env.NOTION_TOKEN);
  const 검토별 = {};
  for (const e of 사건) 검토별[e.검토 || "미검토"] = (검토별[e.검토 || "미검토"] || 0) + 1;
  // 게시처 DB 집계는 따로 잡습니다. 여기서 죽어도(하위 요청 한도 등) 사건 화면은 보여야 합니다
  let 명부;
  try {
    명부 = await 명부읽기(env.NOTION_TOKEN, 이제(now).slice(0, 10));
  } catch (e) {
    명부 = { 오류: String((e && e.message) || e).slice(0, 200) };
  }
  return {
    구운때: 이제(now) + " (노션에서 방금 읽음)",
    // 상한에 걸려 뒷줄을 못 읽었습니다. 화면이 이것을 보고 경고를 냅니다
    잘림: 잘림 ? 사건.length : 0,
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
      // 워크플로 파일 이름과 입력값은 안 보냅니다. 화면은 열쇠만 씁니다
      일감: Object.keys(일감표).map((k) => ({
        열쇠: k,
        이름: 일감표[k].이름,
        설명: 일감표[k].설명,
        밖: 일감표[k].밖,
        무리: 일감표[k].무리,
        종류: 일감표[k].종류,
        길: 일감표[k].길 || "",
      })),
    },
    요약: { 자리: {}, 자리합: 0, 지도날: "" },
    사건: 사건,
    검토별: 검토별,
    명부: 명부,
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

/**
 * 「검토 여부」 가 전 → 후 로 바뀔 때 「DB 반영」 을 어떻게 하나.
 * true 는 켠다, false 는 끈다, null 은 안 건드린다. (2026-09-23 최현서 결정)
 *
 *     미검토 · 사건 X → 사건 O     켠다
 *     사건 O · 빈칸  → 사건 O     안 건드린다
 *     무엇이든      → 사건 X     끈다
 *     무엇이든      → 미검토     끈다
 *
 * **켜는 것은 사건 O 로 새로 들어갈 때뿐입니다.** 「DB 반영 = 꺼짐」 은 두 뜻입니다 —
 * 아직 검토 전이거나, 사건인데 일부러 안 내보내는 것(옛 「일부러 반출하지 않음」).
 * 이미 사건 O 인 줄에서 O 를 한 번 더 누른 것으로 켜면 뒤엣것이 무너집니다.
 * 빈칸은 화면이 사건 O 로 세므로 사건 O 로 봅니다. 끄는 쪽은 안전한 방향이라 조건이
 * 없습니다.
 *
 * **로컬 `api.py` 에 같은 규칙이 파이썬으로 있습니다.** 한쪽만 고치면 로컬과 배포가
 * 다르게 움직입니다. `packages/tests/test_공개규칙.py` 가 둘을 같은 표로 맞춰 봅니다.
 */
function 공개로(전, 후) {
  if (후 === "사건 X" || 후 === "미검토") return false;
  if (후 === "사건 O" && (전 === "미검토" || 전 === "사건 X")) return true;
  return null;
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

  const 머리 = {
    Authorization: `Bearer ${env.NOTION_TOKEN}`,
    "Notion-Version": 노션판,
    "Content-Type": "application/json",
  };

  // **전 값은 노션에서 읽습니다.** 화면이 보낸 값을 믿으면, 화면이 낡았을 때
  // 일부러 꺼 둔 줄을 켤 수 있습니다. 누르는 속도라 읽기 한 번이 부담이 안 됩니다.
  const g = await fetch(`https://api.notion.com/v1/pages/${page_id}`, { headers: 머리 });
  if (!g.ok) {
    const 몸 = await g.text();
    return json(502, { 오류: `노션 ${g.status}: 지금 값을 못 읽었습니다. ${몸.slice(0, 160)}` });
  }
  const 전줄 = await g.json();
  // **수집 DB 줄이 아니면 안 씁니다.** 「DB 반영」 은 검증 DB 에도 있어서, page id
  // 만 맞으면 남의 DB 의 공개 스위치를 건드릴 수 있습니다. 칸 이름으로 가리면 그쪽에
  // 같은 이름 칸이 생기는 날 뚫리므로 줄의 소속으로 가립니다.
  const 소속 = String(((전줄 && 전줄.parent) || {}).data_source_id || "").replace(/-/g, "").toLowerCase();
  if (소속 !== 수집DS.replace(/-/g, "").toLowerCase()) {
    return json(400, { 오류: "수집 DB 줄이 아닙니다" });
  }
  const 칸 = (전줄 && 전줄.properties) || {};
  if (!칸["검토 여부"] || !칸["DB 반영"]) {
    return json(502, { 오류: "수집 DB 에 「검토 여부」 · 「DB 반영」 칸이 없습니다. 이름이 바뀌었나 봅니다" });
  }
  const 전 = ((칸["검토 여부"].select) || {}).name || "";
  const 전반영 = !!칸["DB 반영"].checkbox;

  const 공개 = 공개로(전, 값);
  const 쓸것 = { "검토 여부": { select: { name: 값 } } };
  if (공개 !== null) 쓸것["DB 반영"] = { checkbox: 공개 };

  // **한 번에 씁니다.** 둘로 나누면 앞엣것만 되고 뒤엣것이 실패했을 때 사건 O 인데
  // 공개가 안 켜진 줄이 남습니다.
  const r = await fetch(`https://api.notion.com/v1/pages/${page_id}`, {
    method: "PATCH",
    headers: 머리,
    body: JSON.stringify({ properties: 쓸것 }),
  });
  if (!r.ok) {
    const 몸 = await r.text();
    // 토큰이 로그나 화면에 안 나오게 앞부분만 돌려줍니다.
    return json(502, { 오류: `노션 ${r.status}: ${몸.slice(0, 200)}` });
  }
  // 눌러서 바뀐 것이 다음 조회에 바로 보이게 캐시를 버립니다.
  캐시 = { 언제: 0, 몸: null };
  return json(200, { ok: true, page_id, 검토: 값, 공개, DB반영: 공개 === null ? 전반영 : 공개 });
}

// ── 포럼 사건 받기 ───────────────────────────────────────────────────────
/*
 * 포럼 킷이 낸 「칸 값」 을 수집 DB 에 올립니다. 수집 여섯 칸 중 마지막 칸인 포럼 사건입니다
 * (2026-09-23 최현서 결정).
 *
 * **킷은 노션에 직접 쓰지 않습니다.** 킷은 포럼 페이지 안에서 돕니다. 그 페이지는 믿을 수
 * 없는 곳이라 비밀번호나 열쇠를 들고 있으면 포럼 쪽 스크립트가 가로챌 수 있습니다. 킷은
 * 값을 넘기기만 하고, 사람이 이 화면에서 미리 보고 누를 때만 여기가 씁니다.
 *
 * **본문은 안 받습니다.** 원문은 킷이 사람 PC 에 파일로만 떨굽니다. 여기 오는 것은 제목 ·
 * 주소 · 게시자 · 날짜 · 게시판 · 한국 신호(도메인 · 한글 · Korea 낱말이 있었나)뿐이고,
 * 모르는 키는 버립니다.
 *
 * **옛 길(kit_in.py → push.py)과 같은 줄을 만듭니다.** UID 를 같은 꼴로 만들어야 두 길로
 * 올린 같은 글이 두 줄이 되지 않습니다. 로컬 `api.py` 가 같은 일을 파이썬으로 하고,
 * `packages/tests/test_포럼사건.py` 가 둘과 `dc_store.Item.uid()` 를 맞춰 봅니다.
 */

// 한 번에 받는 줄. 무료 요금제는 요청 하나에 바깥 요청이 50번까지라, 게시처 재료(포럼 명부 셋 ·
// 선택지 하나로 넷쯤)와 겹침 조회 한 번, 줄마다 만들기 한 번을 더해 그 밑에 둡니다(20줄이면 25번).
// 화면이 이만큼씩 나눠 보냅니다. 포럼 명부가 300줄을 넘으면 읽기가 한 번씩 늡니다
const 포럼줄상한 = 20;
const 포럼본문값 = new Set(["받음", "안 봄", "403"]);

// kit_in.py 의 THREAD_ID 와 같은 차례입니다. 글 번호를 못 뽑으면 주소를 통째로 씁니다
const 글번호꼴 = [/[?&]tid=(\d+)/, /\/threads?\/[^/]*?\.(\d+)/, /[?&]t=(\d+)/,
  /\/topic\/(\d+)/, /\/(\d{3,})\/?$/];

function 포럼글번호(주소, 곳) {
  for (const r of 글번호꼴) {
    const m = 주소.match(r);
    if (m) return `${곳}/${m[1]}`;
  }
  return 주소 || 곳;
}

/** 앞 n 글자. **코드 포인트로 셉니다.** 파이썬 [:n] 과 같아야 UID 가 맞습니다. 이모지가 든
 *  제목을 slice 로 자르면 JS 는 반쪽 글자에서 끊습니다. */
function 앞글자(v, n) {
  return Array.from(String(v || "")).slice(0, n).join("");
}

/** 킷이 보낸 것을 거릅니다. { 줄 } 이나 { 오류 } 를 돌려줍니다. */
function 포럼줄검사(d) {
  if (!d || d.종류 !== "darkchoco-forum-rows" || d.판 !== 1) {
    return { 오류: "포럼 킷이 낸 칸 값이 아닙니다" };
  }
  const 줄들 = Array.isArray(d.줄) ? d.줄 : [];
  if (!줄들.length) return { 오류: "줄이 없습니다" };
  if (줄들.length > 포럼줄상한) return { 오류: `한 번에 ${포럼줄상한}줄까지 받습니다` };
  // 제어 문자를 빈칸으로 바꾸고 앞뒤를 자릅니다. 제목에 줄바꿈이 섞여 오면 노션 제목이 깨집니다
  const 글 = (v, n) => 앞글자((typeof v === "string" ? v : "").replace(/[\u0000-\u001f\u007f]/g, " ").trim(), n);
  const 밖 = [];
  for (const x of 줄들) {
    const 주소 = 글(x && x.URL, 2000);
    let u;
    try { u = new URL(주소); } catch { return { 오류: `주소 꼴이 아닙니다: ${주소.slice(0, 80)}` }; }
    if (u.protocol !== "http:" && u.protocol !== "https:") {
      return { 오류: `http 주소가 아닙니다: ${주소.slice(0, 80)}` };
    }
    const 신호 = (x && x["한국 신호"]) || {};
    const 도메인 = (Array.isArray(신호.도메인) ? 신호.도메인 : [])
      .map((v) => 글(v, 100).toLowerCase())
      .filter((v) => /^[a-z0-9-]+(\.[a-z0-9-]+)*\.kr$/.test(v))
      .slice(0, 10);
    밖.push({
      제목: 글(x.제목, 500),
      URL: 주소,
      곳: u.host,
      게시자: 글(x.게시자, 200),
      날짜: 글(x.날짜, 60),
      게시판: 글(x.게시판, 200),
      본문: 포럼본문값.has(x.본문) ? x.본문 : "안 봄",
      신호: { 도메인, 한글: 신호.한글 === true, korea: 신호.korea === true },
    });
  }
  return { 줄: 밖 };
}

/** UID 재료. `dc_store.Item.uid()` 의 KEY 차례 그대로입니다 — src_id · venue · post_url · actor ·
 *  target_org · title. 포럼 킷 줄은 target_org 가 비고 title 은 120 글자로 잘립니다(kit_in.py). */
function 포럼UID재료(x) {
  return [포럼글번호(x.URL, x.곳), x.곳, x.URL, x.게시자, "", 앞글자(x.제목, 120)]
    .map((v) => String(v).trim().toLowerCase()).join("|");
}

async function 해시16(s) {
  const b = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(s));
  return [...new Uint8Array(b)].map((v) => v.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

/** 한국 관련 근거. 판정기(dc_kr)는 파이썬이라 여기서 못 돌립니다. 킷이 본 신호를 판정기가
 *  쓰는 말투로 적습니다. 포럼 줄은 옛 길에서도 대부분 「미확인」 이었습니다. */
function 포럼근거(신호) {
  const 근거 = [];
  if (신호.도메인.length) 근거.push(`설명문에 한국 도메인 '${신호.도메인[0]}' (검토 필요)`);
  if (신호.korea) 근거.push("설명문에 'korea' 언급 (검토 필요)");
  if (신호.한글) 근거.push("설명문에 한글 포함 (검토 필요)");
  근거.push("사람이 고른 글. 대상 조직은 검토하면서 채운다");
  return 근거.join(" · ");
}

/** 노션 속성. push.py 의 만들기() 가 킷 줄에 내는 칸과 같게 둡니다. */
function 포럼줄속성(x, uid, 오늘) {
  const 글칸 = (v) => ({ rich_text: [{ text: { content: 앞글자(v, 2000) } }] });
  const p = {
    "자료 제목": { title: [{ text: { content: 앞글자(앞글자(x.제목, 120) || "제목 없음", 2000) } }] },
    수집자: { select: { name: "자동" } },
    "검토 여부": { select: { name: "미검토" } },
  };
  if (x.게시자) p["게시자 핸들"] = 글칸(x.게시자);
  p["게시 플랫폼"] = 글칸(x.곳);
  p["원문 URL"] = 글칸(x.URL);
  // push.py 의 _날() 과 같습니다. 포럼 날짜는 대부분 「09-20-2026, 10:15 AM」 꼴이라 안 갑니다
  const 날 = x.날짜;
  if (날.length >= 10 && 날[4] === "-" && 날[7] === "-") {
    p["게시 시각"] = { date: { start: 날 } };
  }
  p["수집일"] = { date: { start: 오늘 } };
  p["게시 성격"] = { select: { name: "확인 못 함" } };
  p["소스"] = { select: { name: "포럼" } };
  p.UID = 글칸(uid);
  p["한국 관련"] = { select: { name: "미확인" } };
  p["한국 관련 근거"] = 글칸(포럼근거(x.신호));
  return p;
}

// ── 게시처 (2026-09-25) ──
// `hub/events/publisher.py` 의 포럼 쪽을 옮긴 것입니다. 포럼 명부의 주소 · 이전 주소 · 어니언
// 주소로 게시 플랫폼(호스트)을 맞추고, 안 되면 이름과 별칭으로 맞춥니다. 못 맞추면 비웁니다.
// **두 벌입니다.** `packages/tests/test_게시처.py` 가 파이썬과 같은 값을 내는지 봅니다
const 포럼명부DS = "a3b4df76-b1f0-4464-9139-1c42ac55bf87";
const 게시처호스트꼴 = /\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+\b/gi;
// t.me 를 열쇠로 쓰면 채널 주소가 전부 한 곳에 붙습니다. 집계처와 블로그 호스팅도 게시처가 아닙니다
const 안쓰는호스트 = new Set(["t.me", "telegram.me", "ransomware.live", "wordpress.com"]);

function 호스트들(s) {
  const 밖 = [];
  // 사람이 명부에 `abc[.]onion` 처럼 적은 주소를 점으로 읽습니다. 파이썬 쪽과 같습니다
  for (const m of String(s || "").split("[.]").join(".").matchAll(게시처호스트꼴)) {
    let h = m[0].toLowerCase();
    if (h.startsWith("www.")) h = h.slice(4);
    if (h.includes(".") && !안쓰는호스트.has(h) && !밖.includes(h)) 밖.push(h);
  }
  return 밖;
}

/** 대소문자 · 공백 · 기호 · 0/o 를 견디는 열쇠. `Cl0p` 와 `clop` 이 같아집니다 */
function 민키(s) {
  return String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "").replace(/0/g, "o");
}

function 속성글자(p, 칸) {
  const v = ((p && p.properties) || {})[칸] || {};
  if (v.type === "title" || v.type === "rich_text") return (v[v.type] || []).map((x) => x.plain_text || "").join("");
  if (v.type === "select" || v.type === "status") return ((v[v.type] || {}).name) || "";
  if (v.type === "url") return v.url || "";
  return "";
}

function 포럼명부표(페이지들) {
  const 표 = { 주소: new Map(), 이름: new Map(), 민: new Map() };
  const 넣기 = (m, k, v) => { if (!m.has(k)) m.set(k, v); };
  for (const p of 페이지들) {
    const 이름 = 속성글자(p, "포럼 이름").trim();
    if (!이름 || 속성글자(p, "담당자") === "자동") continue;
    넣기(표.이름, 이름.toLowerCase(), 이름);
    for (const c of [이름, ...속성글자(p, "이전 이름·별칭").split(/[/·,]/).map((x) => x.trim())]) {
      const k = 민키(c);
      if (k.length >= 4) 넣기(표.민, k, 이름);
    }
    for (const c of ["주소", "이전 주소", "어니언 주소"]) {
      for (const h of 호스트들(속성글자(p, c))) 넣기(표.주소, h, 이름);
    }
  }
  return 표;
}

/** 이미 있는 선택지 중 열쇠가 같은 것이 있으면 그 이름을 씁니다. 같은 곳이 선택지 둘로 갈리지 않게 */
function 선택지맞춤(이름, 선택지) {
  if (!이름 || 선택지.includes(이름)) return 이름;
  const k = 민키(이름);
  // 열쇠가 네 글자보다 짧으면(한글 이름은 빈 글자) 대소문자만 무시하고 통째로 견줍니다
  if (k.length < 4) {
    const 낮춤 = 이름.trim().toLowerCase();
    return 선택지.find((o) => o.trim().toLowerCase() === 낮춤) || 이름;
  }
  return 선택지.find((o) => 민키(o) === k) || 이름;
}

/** 노션 선택지 이름에는 쉼표가 못 들어갑니다. 넣으면 줄 만들기 전체가 거부됩니다 */
function 선택지글(s) {
  return String(s || "").replace(/\s*,\s*/g, " · ").trim();
}

function 포럼게시처칸(표기, 표, 선택지) {
  if (!표) return {};
  let 이름 = "";
  for (const h of 호스트들(표기)) {
    if (표.주소.has(h)) { 이름 = 표.주소.get(h); break; }
  }
  const t = String(표기 || "").trim();
  if (!이름 && 표.이름.has(t.toLowerCase())) 이름 = 표.이름.get(t.toLowerCase());
  if (!이름) 이름 = 표.민.get(민키(t.replace(/\(.*?\)/g, " "))) || "";
  이름 = 앞글자(선택지맞춤(선택지글(이름), 선택지), 100);
  return 이름 ? { 게시처: { select: { name: 이름 } } } : {};
}

/** 포럼 명부 전부와 게시처 선택지. 요청이 네 번쯤이라 한 판에 한 번만 읽습니다 */
async function 게시처재료(머리) {
  const 페이지들 = [];
  let 커서;
  do {
    const r = await fetch(`https://api.notion.com/v1/data_sources/${포럼명부DS}/query`, {
      method: "POST", headers: 머리,
      body: JSON.stringify(커서 ? { page_size: 100, start_cursor: 커서 } : { page_size: 100 }),
    });
    if (!r.ok) throw new Error(`포럼 명부 ${r.status}`);
    const d = await r.json();
    페이지들.push(...(d.results || []));
    커서 = d.has_more ? d.next_cursor : undefined;
  } while (커서);
  const g = await fetch(`https://api.notion.com/v1/data_sources/${수집DS}`, { headers: 머리 });
  if (!g.ok) throw new Error(`수집 DB ${g.status}`);
  const 칸 = (((await g.json()).properties || {}).게시처 || {}).select || {};
  return { 표: 포럼명부표(페이지들), 선택지: (칸.options || []).map((o) => o.name) };
}

async function 포럼사건받기(request, env) {
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
  const 검 = 포럼줄검사(d);
  if (검.오류) return json(400, { 오류: 검.오류 });

  const 머리 = {
    Authorization: `Bearer ${env.NOTION_TOKEN}`,
    "Notion-Version": 노션판,
    "Content-Type": "application/json",
  };
  const 오늘 = 이제(Date.now()).slice(0, 10);
  const 줄들 = [];
  for (const x of 검.줄) 줄들.push({ x, uid: await 해시16(포럼UID재료(x)) });

  // **겹침은 한 번에 봅니다.** UID 가 같거나 원문 URL 이 같으면 이미 있는 글입니다. UID 가
  // 없던 옛 줄은 URL 로만 걸립니다. 사람이 「사건 X」 로 닫은 줄도 여기서 막혀 다시 안 들어갑니다
  const 조건 = 줄들.flatMap(({ x, uid }) => [
    { property: "UID", rich_text: { equals: uid } },
    { property: "원문 URL", rich_text: { equals: x.URL } },
  ]);
  const q = await fetch(`https://api.notion.com/v1/data_sources/${수집DS}/query`, {
    method: "POST",
    headers: 머리,
    body: JSON.stringify({ filter: { or: 조건 }, page_size: 100 }),
  });
  if (!q.ok) {
    const 몸 = await q.text();
    return json(502, { 오류: `노션 ${q.status}: 겹침을 못 봤습니다. 아무것도 안 썼습니다. ${몸.slice(0, 160)}` });
  }
  const 본것 = new Set();
  for (const r of (await q.json()).results || []) {
    const 칸 = r.properties || {};
    for (const k of ["UID", "원문 URL"]) {
      const v = ((칸[k] || {}).rich_text || []).map((t) => t.plain_text || "").join("");
      if (v) 본것.add(v);
    }
  }

  // **게시처는 못 읽어도 줄은 올립니다.** 게시처는 나중에 채울 수 있지만 안 올린 줄은 사람이
  // 다시 킷을 눌러야 합니다
  let 재료 = { 표: null, 선택지: [] };
  try { 재료 = await 게시처재료(머리); } catch { /* 게시처만 비웁니다 */ }

  const 결과 = [];
  let 썼다 = 0;
  for (const { x, uid } of 줄들) {
    if (본것.has(uid) || 본것.has(x.URL)) {
      결과.push({ 제목: 앞글자(x.제목, 80), 결과: "겹침" });
      continue;
    }
    const r = await fetch("https://api.notion.com/v1/pages", {
      method: "POST",
      headers: 머리,
      body: JSON.stringify({
        parent: { type: "data_source_id", data_source_id: 수집DS },
        properties: { ...포럼줄속성(x, uid, 오늘), ...포럼게시처칸(x.곳, 재료.표, 재료.선택지) },
      }),
    });
    if (r.ok) {
      썼다 += 1;
      본것.add(uid);
      본것.add(x.URL);
      결과.push({ 제목: 앞글자(x.제목, 80), 결과: "올림" });
    } else {
      const 몸 = await r.text();
      결과.push({ 제목: 앞글자(x.제목, 80), 결과: `실패 — 노션 ${r.status}: ${몸.slice(0, 120)}` });
    }
  }
  if (썼다) 캐시 = { 언제: 0, 몸: null };
  return json(200, { ok: true, 썼다, 결과 });
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
  if (도나) 줄.push("도는 중입니다. 끝나면 요약이 여기 붙습니다");
  return {
    열쇠,
    돌고있나: 도나,
    줄,
    코드: run.conclusion === "success" ? 0 : (run.conclusion ? 1 : 0),
    끝: run.updated_at || "",
  };
}

/** 워크플로 하나의 마지막 실행을 봅니다.
 *
 *  **어느 파일을 볼지 받아야 합니다.** 전에는 `collect.yml` 로 박혀 있어서,
 *  게시 상태 추적을 돌려도 화면에는 수집의 지난 실행이 떴다. 단추는 맞는 워크플로를
 *  시작시키는데 상태만 딴 데를 보고 있어서 **아무 일도 안 일어난 것처럼 보였다.**
 */
async function 최근실행(env, 파일) {
  const r = await fetch(
    `https://api.github.com/repos/${레포}/actions/workflows/${파일}/runs?per_page=1`,
    { headers: gh머리(env.GH_TOKEN) },
  );
  if (!r.ok) {
    const 몸 = await r.text();
    throw new Error(`GitHub ${r.status}: ${몸.slice(0, 200)}`);
  }
  const d = await r.json();
  return (d.workflow_runs || [])[0] || null;
}

/** 로그에서 **요약에 해당하는 줄만** 골라 냅니다.
 *
 *  GitHub 로그는 줄마다 앞에 시각이 붙고, 실행할 명령이 그대로 한 번 에코됩니다.
 *  그 에코를 안 거르면 **스크립트에 적힌 글이 실제로 일어난 일처럼 보입니다.**
 *  2026-09-12 에 로그에 찍힌 「NOTION_TOKEN 이 없습니다」 를 그 분기를 탄 것으로
 *  읽고 한참 헤맸는데, 실제로는 if 문 본문이 에코된 것이었습니다.
 *
 *  에코된 줄은 GitHub 가 청록 굵게([36;1m)로 칠합니다. 그것으로 가릅니다.
 */
const 요약무늬 = [
  /── 텔레그램 채널 \d+개 ──/,
  // 채널별 줄은 열일곱이라 다 내면 깁니다. **건진 채널만 냅니다.**
  // 「기타」 뿐인 줄은 포럼 공지라 사건이 안 됩니다 (2026-09-13 확인).
  /글 \d+ · 새 것 \d+.*(유출 알림|랜섬 피해자)/,
  // 이것이 뜨면 그 채널은 수동 조사 목록으로 옮겨야 합니다. 이름은 시크릿이라
  // 가려져 나오므로 몇 개인지만 보이고, 어느 것인지는 GitHub 로그를 봅니다.
  /못 봄 — 미리보기가 꺼져 있다/,
  /못 본 채널 \d+개/,
  /요청\s+\d+ · 간격/,
  /긁은 줄 \d+/,
  /items 표 \d+줄 중 \d+줄을 골랐습니다/,
  /\d+줄은 뺐습니다/,
  /노션에 \d+줄이 있습니다/,
  /올릴 것은 \d+줄입니다/,
  /\d+줄을 올렸습니다/,
  /미리보기만 합니다/,
  // 게시 상태 추적 쪽
  /수집 DB 의 랜섬 줄 \d+/,
  /집계처가 보인 uid \d+/,
  /^판정\s/,
  /^건너뜀\s/,
  /바뀐 줄(이 없습니다| \d+)/,
  // **막힌 것을 놓치지 않습니다.** 이 줄들이 없으면 「0줄 올림」 이 「새 것이
  // 없었다」 인지 「못 읽어서 아무것도 안 했다」 인지 화면에서 구분이 안 됩니다.
  /^::(warning|error)::/,
  /집계처를 못 읽었습니다/,
  /^못 받았다/,
  /^줄 0개\./,
  /없어 건너뜁니다/,
  /올릴 표가 없습니다/,
  /표가 안 만들어졌다/,
  // ── 명부 조사 (places.yml) ────────────────────────────────
  // **이름이 든 줄은 일부러 안 넣습니다.** `--요약만` 이 로그에서 한 번 거르지만
  // 여기서도 안 집는 것이 두 겹입니다. 「살펴볼 것 N줄」 은 건수라 괜찮습니다.
  /Tor 를 타고 있습니다/,
  /torrc 세 줄 확인/,
  /tor 준비됨/,
  /아무것도 하지 않고 끝냅니다/,
  /명부 \d+곳을 이음 사전에 담았습니다/,
  /열린 곳 \d+ · 수치까지 본 것 \d+ · 바뀐 줄 \d+/,
  /^상태\s+\S/,
  /썼습니다 — 바뀐 줄 \d+/,
  /미리보기입니다\. --apply/,
  // **문구를 바꾸면 여기도 바꿉니다.** 2026-09-23 에 `run.py` 가 「브라우저가 없어
  // 깊은 판을 건너뜁니다」 를 「깊은 판을 건너뜁니다 — 까닭」 으로 바꾸고 여기를
  // 안 바꿔서, 그 줄이 화면에서 조용히 빠졌습니다. `test_일감표.py` 가 이제 코드가
  // 찍는 문구와 이 무늬를 맞춰 봅니다.
  /깊은 판을 건너뜁니다/,
  /깊은 판을 \d+분에서 끊습니다/,
  // 랜섬 사전 단계. 머리 한 줄만 냅니다 — 달마다 찍는 진행 줄(「1/6 2026-09 312건」)은
  // GitHub 로그에서 도는 중에 보라고 넣은 것이고, 끝난 뒤 요약에는 군더더기입니다
  /집계처에서 피해 \d+달치를 받습니다/,
  /피해 목록 \d+달 중 \d+달을 못 받아/,
  /살펴볼 것 \d+줄/,
  /명부에 없는 이웃 \d+곳/,
];

function 로그에서요약(글) {
  const 밖 = [];
  for (const 날것 of 글.split("\n")) {
    if (날것.includes("[36;1m")) continue;      // 명령 에코. 일어난 일이 아니다
    const x = 날것
      .replace(/^\S+Z\s/, "")                         // 줄머리 시각
      .replace(/\[[0-9;]*m/g, "")               // 남은 색 코드
      .trim();
    if (!x) continue;
    if (요약무늬.some((p) => p.test(x))) 밖.push(x);
  }
  return 밖;
}

/** 실행 하나의 요약. **끝난 뒤에 한 번만 부릅니다.**
 *
 *  화면에는 지금까지 「실행 #7 · success」 만 떴습니다. 정작 알고 싶은 「몇 건
 *  긁어서 몇 줄 올렸나」 는 GitHub 을 열어야 보였습니다.
 *
 *  로그가 수백 KB 라 조회마다 받으면 낭비입니다. 도는 중에는 안 부릅니다.
 *  잡이 여럿이면(수집 + 게시 상태 추적) 차례로 붙입니다.
 */
async function 실행요약(env, run_id) {
  const r = await fetch(
    `https://api.github.com/repos/${레포}/actions/runs/${run_id}/jobs`,
    { headers: gh머리(env.GH_TOKEN) },
  );
  if (!r.ok) return [];
  const d = await r.json();
  const 밖 = [];
  for (const j of d.jobs || []) {
    if (j.conclusion === "skipped") continue;
    const lr = await fetch(
      `https://api.github.com/repos/${레포}/actions/jobs/${j.id}/logs`,
      { headers: gh머리(env.GH_TOKEN) },
    );
    if (!lr.ok) continue;
    const 줄 = 로그에서요약(await lr.text());
    if (줄.length) 밖.push("", `── ${j.name} ──`, ...줄);
  }
  return 밖;
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
  const 날열쇠 = String((d && d.열쇠) || "");
  const 열쇠 = 옛열쇠[날열쇠] || 날열쇠;
  const 일감 = 일감표[열쇠];
  // **목록에 있는 것만 됩니다.** 화면이 보낸 글자로 아무 워크플로나 부르지 않습니다.
  if (!일감) return json(400, { 오류: `모르는 일감입니다: ${열쇠}` });
  // 「손」 일감은 워크플로가 없습니다. 여기로 오면 `일감.파일` 이 undefined 라
  // `.../workflows/undefined/dispatches` 로 나갑니다. 그 전에 막습니다
  if (일감.종류 !== "밖") {
    return json(400, { 오류: `단추로 돌리는 일감이 아닙니다: ${열쇠}` });
  }

  // 이미 도는 중이면 또 시작하지 않습니다. 같은 노션 DB 에 둘이 쓰면 겹침 판정이
  // 어긋납니다. 워크플로 쪽에도 concurrency 가 걸려 있지만 여기서 먼저 막습니다.
  //
  // **누를 그 워크플로를 봅니다.** 전에는 `collect.yml` 만 봐서 두 가지로 틀렸다 —
  // 수집이 도는 중이면 게시 상태 추적까지 막혔고, 게시 상태 추적이 도는 중일 때
  // 또 누르면 안 막혔다. 둘은 concurrency 무리가 서로 달라 따로 봐야 한다.
  let 앞것 = null;
  try {
    앞것 = await 최근실행(env, 일감.파일);
  } catch (e) {
    return json(502, { 오류: String((e && e.message) || e) });
  }
  if (앞것 && 앞것.status !== "completed") {
    return json(409, {
      오류: `이미 도는 중입니다 (실행 #${앞것.run_number}). 끝나면 다시 누르십시오`,
    });
  }

  // **GitHub 이 이 자리에서 간헐적으로 500 을 냅니다.** 2026-09-13 에 똑같은
  // 요청을 네 번 보내 셋이 500, 넷째가 204 였습니다. 본문이 비어 있어 이유를
  // 알 수 없고, 워크플로 파일을 아침에 성공했던 판으로 되돌려도 같았습니다.
  // 사람이 단추를 서너 번 누르게 두지 않고 여기서 다시 걸어 봅니다.
  //
  // **4xx 는 다시 걸지 않습니다.** 입력이 틀렸거나 권한이 없는 것이라 같은
  // 요청을 몇 번 보내도 같습니다. 5xx 만 다시 겁니다.
  let r = null;
  let 몸 = "";
  for (let 판 = 0; 판 < 4; 판 += 1) {
    r = await fetch(
      `https://api.github.com/repos/${레포}/actions/workflows/${일감.파일}/dispatches`,
      {
        method: "POST",
        headers: { ...gh머리(env.GH_TOKEN), "Content-Type": "application/json" },
        body: JSON.stringify({ ref: "main", inputs: 일감.입력 }),
      },
    );
    if (r.ok) break;
    몸 = await r.text();
    if (r.status < 500) break;
    if (판 < 3) await new Promise((풀기) => setTimeout(풀기, 800 * (판 + 1)));
  }
  if (!r || !r.ok) {
    const 상태 = r ? r.status : 0;
    const 꼬리 = 상태 >= 500
      ? " — GitHub 쪽 일시 오류입니다. 네 번 다시 걸어 봤습니다. 잠시 뒤 다시 누르십시오"
      : "";
    return json(502, { 오류: `GitHub ${상태}: ${몸.slice(0, 200)}${꼬리}` });
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
  열쇠 = 옛열쇠[열쇠] || 열쇠;
  // **열쇠가 가리키는 워크플로를 봅니다.** 화면이 열쇠를 안 보내면(첫 그리기 따위)
  // 사건 수집으로 물러섭니다. 목록에 없는 열쇠가 와도 같습니다.
  //
  // **「손」 일감도 물러섭니다.** 워크플로가 없는데 `일감.파일` 을 그냥 쓰면
  // undefined 가 되고, 그러면 옛 코드처럼 엉뚱한 워크플로의 지난 실행을
  // 이 일감의 상태라고 보여 줍니다.
  const 일감 = 일감표[열쇠];
  const 파일 = (일감 && 일감.종류 === "밖" && 일감.파일) || "collect.yml";
  try {
    const run = await 최근실행(env, 파일);
    const s = 실행을상태로(열쇠, run);
    // **이 일감이 노션을 바꾸나.** 화면도 이 값을 보고 다시 읽을지 정합니다.
    // 열쇠를 모르면 바꿨다고 칩니다. 낡은 것을 보이는 쪽이 더 나쁩니다.
    s.노션 = 일감 ? !!일감.노션 : true;
    // 일감이 끝났으면 다음 조회에서 바뀐 것이 보이게 캐시를 버립니다. 수집은 줄이
    // 늘고 게시 상태 추적은 관측 칸이 바뀝니다. 미리보기는 아무것도 안 바꿔
    // 버릴 것이 없습니다. 그때 버리면 같은 화면을 받으려고 노션만 한 번 더 읽습니다.
    if (!s.돌고있나 && s.노션) 캐시 = { 언제: 0, 몸: null };

    // **끝났을 때 한 번만 로그를 받아 요약을 붙입니다.** 도는 중에는 안 받습니다.
    // 요약을 못 받아도 상태는 그대로 보여 줍니다. 로그는 GitHub 에 남아 있습니다.
    if (!s.돌고있나 && run) {
      try {
        const 요약 = await 실행요약(env, run.id);
        if (요약.length) s.줄 = s.줄.concat(요약);
      } catch (e) {
        s.줄 = s.줄.concat("", `요약을 못 읽었습니다: ${String((e && e.message) || e).slice(0, 120)}`);
      }
    }
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
    if (url.pathname === "/api/forum-rows") {
      if (request.method !== "POST") return json(405, { 오류: "POST 로 보내십시오" });
      return 포럼사건받기(request, env);
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
