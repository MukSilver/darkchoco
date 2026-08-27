/* 포럼 조사 통합 도구 — forum kit v1
 * 트리 v3.3 · 하베스터 v6.1 · 낱장 추출 v1.1 · 구조 진단(인덱스+스레드목록)을 하나로 합쳤다.
 * 어느 페이지에서 눌러도 된다. 페이지 종류를 스스로 판정하고 맞는 것을 바로 돌린다.
 *   포럼 메인      → 게시판 트리
 *   스레드 목록    → 스레드 URL 목록 (본문 수집은 버튼을 눌러야 시작한다. 네트워크를 쓰기 때문)
 *   글·공지 한 장  → 본문 추출
 *   판정 실패      → 구조 진단
 * 결과가 0건이면 진단을 자동으로 붙인다. 그 화면을 그대로 공유하면 된다.
 * 여러 명이 같이 쓰므로 확인자 이름은 박아 두지 않는다. 상자의 「확인자」 칸에 적으면 결과에 들어간다.
 * v2.5a — 요청 간격 하한 2초를 넣었다. 전에는 하한이 없어 0.1 을 적으면 0.1 로 돌았다.
 *         2026-08-24 압축본에서 소스를 찾아 레포에 복구하면서 함께 고쳤다.
 * v2.5 — 「목록 몇 쪽까지」와 「본문 최대 몇 건」을 「글 몇 건까지」 하나로 합쳤다. 쪽 넘김은 도구가 알아서 한다.
 * v2.4 — 기본값 조정, 창 옮기기와 최소화, 진행 표시가 무엇을 세는지 밝히도록 수정.
 * v2.3 — showthread.php?tid= 처럼 쿼리로 글을 가리키는 주소에서 쿼리가 잘려 나가던 문제 수정.
 *        포럼이 「없는 글」이라고 답한 경우를 파싱 실패와 구분한다.
 * v2.2 — 정렬이 실제로 먹었는지 결과에서 확인해 알려준다.
 * v2.1 — 용어를 직관적으로 바꾸고 정렬(조회·답글·최신)을 붙였다. 쪽 넘김을 하나로 묶어 하위 게시판에도 같이 먹는다.
 * v2.0 — 목록에서 작성자·답글·조회·날짜를 같이 뽑아 TSV로 낸다. 본문을 안 열고도 규모를 셀 수 있다.
 * v1.9 — 단서에서 BBCode 꼬리를 떼고, 화면에서 ... 로 잘린 주소를 실제 링크로 보강한다.
 * v1.8 — 체크·엑스·무한 아이콘을 ✓ ✗ ∞ 로 바꿔 읽는다. 등급 비교표처럼 그림으로 표시된 칸이 텍스트에서 통째로 사라지던 문제.
 * v1.7 — 「하위 게시판까지」 체크박스. 켜면 하위 게시판에 직접 들어가지 않아도 목록을 한 번에 모은다.
 * v1.6 — 연락 수단 추출 확대. Session · Tox · Matrix · Jabber · 텔레그램 봇 · 자동판매 상점을 따로 뽑는다.
 *        t.me/addlist/코드 처럼 슬래시가 더 붙는 링크가 잘리던 것도 고쳤다.
 * v1.5 — 하위 게시판이 있는 목록 페이지에서 하위 게시판의 스레드·게시물 수까지 표로 뽑는다.
 *        빵부스러기와 하위 게시판을 갈라 놓는다.
 * v1.4 — MyBB 본문에 섞여 들어오던 테마 jQuery 조각 제거. 글쓴이 uid를 이름 옆에 붙인다.
 * v1.3 — 북마크를 갱신해도 같은 페이지에서는 옛 코드가 계속 돌던 문제 수정. 버전이 다르면 옛 상자를 걷어낸다.
 * v1.2 — 상자와 결과에 버전을 표시한다. 어느 빌드가 도는지 확인용.
 *        긴 스레드의 답글 페이지를 목록 페이지로 오해하던 것 수정.
 *        압축본에서 본문 추출이 통째로 실패하던 건에 대비. 추출기가 터져도 선택자를 직접 훑어 본문을 건진다.
 * 2026-08-13 다크초코
 */
(() => {
  const VER = 'forum kit v2.5';
/* 같은 페이지에서 다시 눌렀을 때. 버전이 같으면 있던 상자를 다시 보여주고, */
/* 다르면 옛 상자를 걷어내고 새 코드로 다시 뜬다. 이게 없으면 북마크를 갱신해도 */
/* 페이지를 새로 열기 전까지 옛 코드가 계속 돌아 갱신이 먹은 줄 모르게 된다 */
  if (window.__FK) {
    if (window.__FK.ver === VER) { window.__FK.open(); return; }
    try { window.__FK.destroy(); } catch (e) {}
    window.__FK = null;
  }

  /* ================= 공통 ================= */
  const NB = / /g;
  const C = s => (s || '').replace(NB, ' ').replace(/\s+/g, ' ').trim();
  const CL = el => el ? (el.innerText || el.textContent).replace(NB, ' ').replace(/\n{3,}/g, '\n\n').replace(/[ \t]+/g, ' ').trim() : '';
  const N = s => { if (s == null) return null; const m = String(s).replace(/[,\s]/g, '').match(/^\d+$/); return m ? parseInt(m[0], 10) : null; };
  const A = a => a.href || a.getAttribute('href') || ''; /* MyBB SEO 링크는 상대주소다. 브라우저가 푼 절대주소로 본다 */
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const TODAY = new Date().toISOString().slice(0, 10);
  const fmt = n => n == null ? '' : n.toLocaleString();
  const path = e => { const p = []; let c = e, d = 0;
    while (c && c !== document.body && d < 5) {
      p.push(c.tagName.toLowerCase() + (c.id ? '#' + c.id : '') +
        (c.className && typeof c.className === 'string' ? '.' + c.className.trim().split(/\s+/).slice(0, 3).join('.') : ''));
      c = c.parentElement; d++;
    } return p.join(' ← '); };

/* 게시판 링크. /forums/db-leaks/ 처럼 숫자 없는 커스텀 슬러그도 게시판이다 */
  const F_PAT = /\/Forum-|\/forums\/[^\/?#]+\/?(?:$|[?#])|\/forums\/[^\/]+\.\d+|forumdisplay\.php\?fid=|\/forum-\d+/i;
  const F_SKIP = /\/threads?[-\/]|\/posts?\/|\/page-\d|[?&]page=|mark-read|\/watch\b|\/latest\b|\/unread\b|action=|\/members?\/|whats-new|\/post-\d|sortby=|datecut=|[?&]order=|[?&]prefix=/i;
/* 스레드 링크. misc.php?action=whoposted&tid= 가 tid= 때문에 통과하던 것을 막는다 */
/* announcements.php?fid=39&aid=7 처럼 aid가 뒤에 오는 경우도 잡는다 */
  const T_HIT = /\/Thread-|thread-\d+|[?&]tid=\d+|\/threads\/|\/Announcement-|announcements\.php\?[^#]*[?&]?aid=\d+/i;
  const T_SKIP = /action=(lastpost|newpost|thread_|nextnewest|nextoldest|whoposted)|[?&]page=|#pid|\/post-\d+|\/unread|\/latest|\/misc\.php|\/printthread/i;
  const SUBSEL = '.forum-subforums, .node-subNodeFlatList, .subforums, .subforum_list, .forums__subforum, .subforum';
  const isForum = a => F_PAT.test(A(a)) && !F_SKIP.test(A(a)) && !!C(a.textContent);
  const isThread = a => T_HIT.test(A(a)) && !T_SKIP.test(A(a));
  const inSub = a => !!a.closest(SUBSEL);
  const key = u => u.split('#')[0].split('?')[0].replace(/\/$/, '');

  /* 스레드 링크가 모이는 가장 작은 조상을 찾는다. 사이드바 위젯을 피하기 위한 것 */
  const SCOPE_SEL = '.structItemContainer, .structItemContainer-group, #threadslist, table.tborder tbody, .p-body-main .block-body';
  const countIn = els => { const s = new Set();
    els.forEach(e => e.querySelectorAll && [...e.querySelectorAll('a[href]')].filter(isThread).forEach(a => s.add(key(A(a)))));
    return s.size; };
  const autoScope = (doc, pick) => {
    const cand = [...doc.querySelectorAll('a[href]')].filter(pick);
    if (cand.length < 3) return null;
    const sco = new Map();
    cand.forEach(a => { let e = a.parentElement, d = 0;
      while (e && e !== doc.body && d < 12) { sco.set(e, (sco.get(e) || 0) + 1); e = e.parentElement; d++; } });
/* 기준을 넘는 것 중 가장 작은 것. 큰 것부터 고르면 사이드바까지 품는 조상이 뽑힌다 */
    const best = [...sco.entries()].filter(([, n]) => n >= Math.max(3, cand.length * 0.5))
      .sort((a, b) => a[0].querySelectorAll('*').length - b[0].querySelectorAll('*').length || b[1] - a[1])[0];
    return best ? [best[0]] : null;
  };
  const pickScope = doc => {
    if (!cfg.scoped) return { els: [doc], how: '전체(영역 제한 끔)' };
    const fixed = [...doc.querySelectorAll(SCOPE_SEL)];
    const auto = autoScope(doc, isThread);
    const nf = fixed.length ? countIn(fixed) : 0;
    const na = auto ? countIn(auto) : 0;
/* 공지·고정글 표는 본문 목록과 떨어져 있는 경우가 많아 두 영역을 합친다. 중복은 뒤에서 걸러진다 */
    if (na > nf) return { els: auto.concat(fixed), how: `자동 탐색 ${na}건 + 고정 선택자 ${nf}건 합침` };
    if (nf) return { els: fixed, how: `고정 선택자 ${fixed.length}개 영역 ${nf}건` };
    return { els: [doc], how: '영역 못 찾음. 전체에서 수집' };
  };

  /* ================= 페이지 판정 ================= */
  const links = [...document.querySelectorAll('a[href]')];
  const fLinks = links.filter(isForum);
  const tLinks = links.filter(isThread);
  const uF = new Set(fLinks.map(a => key(A(a)))).size;
  const uT = new Set(tLinks.map(a => key(A(a)))).size;
  const BODY_SEL = '.post_body, [id^="pid_"], article.message .bbWrapper, .message-body';
  const nBody = document.querySelectorAll(BODY_SEL).length;
  const KIND = nBody ? 'page' : (uT >= 5 && uT >= uF) ? 'list' : uF >= 5 ? 'index' : 'unknown';
  const KNAME = { index: '포럼 메인 (게시판 목록)', list: '스레드 목록', page: '글 · 공지 한 장', unknown: '판정 실패' };

  /* ================= 화면 ================= */
  let ABORT = false, BUSY = false;
/* 못 가져온 URL 과 사유. 결과 꼬리에 낸다.
   이게 없으면 요청이 막힌 게시판과 글이 없는 게시판이 결과에서 같아 보인다. */
  const FAILED = [];
  const box = document.createElement('div');
  box.style.cssText = 'position:fixed;inset:4%;z-index:2147483647;background:#111;color:#eee;border:2px solid #666;padding:8px;display:flex;flex-direction:column;font:13px sans-serif;gap:6px';
  const row1 = document.createElement('div'); row1.style.cssText = 'display:flex;gap:6px;align-items:center;flex-wrap:wrap';
  const row2 = document.createElement('div'); row2.style.cssText = 'display:flex;gap:10px;align-items:center;flex-wrap:wrap;font:12px sans-serif;color:#aaa';
  const st = document.createElement('span'); st.style.cssText = 'flex:1;min-width:220px;color:#0f0;font:12px monospace';
  const ta = document.createElement('textarea');
  ta.style.cssText = 'flex:1;width:100%;background:#000;color:#0f0;font:12px monospace;border:1px solid #444';
  const say = s => { st.textContent = s; try { console.log('[fk] ' + s); } catch (e) {} };
  const put = s => { ta.value = s; ta.focus(); ta.select(); };

  const mkBtn = (label, fn, hot) => {
    const b = document.createElement('button');
    b.textContent = label;
    b.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;' +
      (hot ? 'background:#0a4;color:#fff;border:1px solid #0f8;font-weight:bold' : 'background:#333;color:#ddd;border:1px solid #555');
    b.onclick = async () => {
      if (BUSY) { say('실행 중이다. 끝나거나 중단한 뒤에 누를 것'); return; }
      BUSY = true; ABORT = false; FAILED.length = 0;
      try { await fn(); } catch (e) { say('오류 : ' + e); put('오류\n\n' + (e && e.stack || e)); }
      BUSY = false;
    };
    return b;
  };
  const num = (label, val, w, tip) => {
    const wrap = document.createElement('label'); wrap.style.cssText = 'display:flex;gap:3px;align-items:center';
    if (tip) wrap.title = tip;
    const i = document.createElement('input'); i.value = val; i.size = w || 3;
    i.style.cssText = 'background:#000;color:#0f0;border:1px solid #444;font:12px monospace;width:' + ((w || 3) * 9) + 'px';
    wrap.append(document.createTextNode(label), i); wrap.__i = i; return wrap;
  };
  const chk = (label, on, tip) => {
    const wrap = document.createElement('label'); wrap.style.cssText = 'display:flex;gap:3px;align-items:center;cursor:pointer';
    if (tip) wrap.title = tip;
    const i = document.createElement('input'); i.type = 'checkbox'; i.checked = !!on;
    wrap.append(i, document.createTextNode(label)); wrap.__i = i; return wrap;
  };
  const sel = (label, opts, tip) => {
    const wrap = document.createElement('label'); wrap.style.cssText = 'display:flex;gap:3px;align-items:center';
    if (tip) wrap.title = tip;
    const i = document.createElement('select');
    i.style.cssText = 'background:#000;color:#0f0;border:1px solid #444;font:12px sans-serif';
    opts.forEach(([v, t]) => { const o = document.createElement('option'); o.value = v; o.textContent = t; i.append(o); });
    wrap.append(document.createTextNode(label), i); wrap.__i = i; return wrap;
  };
/* 쪽수와 건수를 따로 두면 서로 어긋난다. 「몇 건」 하나로 정하고 쪽수는 도구가 알아서 넘긴다 */
  const iN = num('글 몇 건까지', 60, 5,
    '이번에 다룰 글의 총 개수. 목록은 이 수가 찰 때까지 쪽을 넘기고, 본문도 이만큼만 받는다. '
    + '하위 게시판을 켜면 게시판별로 나눠 가진다. 전수를 받으려면 9999처럼 큰 수를 넣으면 마지막 쪽에서 알아서 멈춘다');
  const iDelay = num('요청 간격(초)', '2.5~5', 7, '요청 사이 대기 시간. 줄이지 말 것. 공유 계정이라 차단되면 셋이 같이 막힌다. 2초 밑으로는 안 내려간다');
/* 여러 명이 같이 쓰는 도구라 이름은 박아 두지 않는다. 비워 두면 결과에 확인자 줄이 안 들어간다 */
  const iWho = num('확인자 이름', '', 8, '비워 두면 결과에 확인자 줄이 안 들어간다');
  const iSort = sel('정렬', [['', '게시판 기본순'], ['views', '조회 많은 순'], ['replies', '답글 많은 순'], ['lastpost', '최신순']],
    '정렬을 고르면 목록을 그 순서로 다시 받아 온다. 전수를 못 받을 때 위에서부터 중요한 것만 건지는 방법이다');
  const cMask = chk('개인정보 가리기', false, '켜면 샘플로 보이는 줄을 생략하고 이메일·전화를 가린다. 기본은 원문 그대로다');
  const cScope = chk('사이드바 빼기', true, '글 목록 영역 안의 링크만 본다. 끄면 인기글 위젯까지 섞인다');
/* 켜면 하위 게시판까지 들어가서 목록을 모아 온다. 요청이 늘어나니 기본은 꺼둔다.
   2026-08-27. 주석은 꺼둔다고 적었는데 코드가 true 였다. 코드를 주석에 맞췄다. */
  const cSubs = chk('하위 게시판도', false, '켜면 하위 게시판에 각각 들어가 목록을 모아 온다. 요청이 늘어난다');
  const WHO = () => C(iWho.__i.value);
  const stamp = () => TODAY + (WHO() ? ' ' + WHO() : '');
  const cfg = { get n() { return Math.max(1, N(iN.__i.value) || 60); },
                get mask() { return cMask.__i.checked; },
                get scoped() { return cScope.__i.checked; },
                get subs() { return cSubs.__i.checked; },
                get sort() { return iSort.__i.value; } };
/* 3 처럼 한 숫자만 적어도 되고 2.5~5 처럼 범위로 적어도 된다 */
  /* 하한 2초. 기본값 2.5초의 80% 다. 더 줄이면 계정과 회선이 막힌다.
     셋이 같이 쓰므로 한 명이 막히면 셋이 같이 막힌다.
     입력칸에 더 작은 값을 적어도 여기서 올려 잡는다. */
  const FLOOR = 2000;
  const wait = () => {
    const v = (iDelay.__i.value || '').trim();
    const r = v.match(/([\d.]+)\s*[~\-]\s*([\d.]+)/);
    const one = !r && v.match(/^([\d.]+)$/);
    let a = (r ? parseFloat(r[1]) : one ? parseFloat(one[1]) : 2.5) * 1000;
    let b = (r ? parseFloat(r[2]) : one ? parseFloat(one[1]) : 5) * 1000;
    if (!(a > 0)) a = 2500;
    if (!(b > 0)) b = 5000;
    a = Math.max(FLOOR, a);
    b = Math.max(a, b);
    return sleep(a + Math.random() * (b - a));
  };

  const bTree = mkBtn('게시판 지도', () => run(modTree), KIND === 'index');
  const bList = mkBtn('글 목록', () => run(() => modList(false)), KIND === 'list');
  const bHarv = mkBtn('본문 받기', () => run(() => modList(true)));
  const bPage = mkBtn('이 글 본문', () => run(modPage), KIND === 'page');
  const bDiag = mkBtn('구조 진단', () => run(modDiag), KIND === 'unknown');
/* 이 둘은 실행 중에도 눌려야 하므로 BUSY 가드를 타지 않는다 */
  const plain = (label, fn) => { const b = document.createElement('button'); b.textContent = label;
    b.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;background:#422;color:#fdd;border:1px solid #855';
    b.onclick = fn; return b; };
  const bStop = plain('중단', () => { ABORT = true; say('중단 요청. 현재 건이 끝나면 멈춘다'); });
  const bClose = plain('닫기', () => box.remove());

/* 끌어서 옮기기. 붙잡는 손잡이를 따로 둔다 */
  const grip = document.createElement('span');
  grip.textContent = '⠿'; grip.title = '끌어서 옮기기';
  grip.style.cssText = 'cursor:move;color:#888;padding:0 4px;user-select:none;font-size:15px';
  let dx = 0, dy = 0, dragging = false;
  grip.onmousedown = e => {
    const r = box.getBoundingClientRect();
    box.style.inset = ''; box.style.left = r.left + 'px'; box.style.top = r.top + 'px';
    box.style.width = r.width + 'px'; box.style.height = r.height + 'px';
    dx = e.clientX - r.left; dy = e.clientY - r.top; dragging = true; e.preventDefault();
  };
  const onMove = e => { if (!dragging) return; box.style.left = (e.clientX - dx) + 'px'; box.style.top = (e.clientY - dy) + 'px'; };
  const onUp = () => { dragging = false; };
  document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);

/* 최소화. 설정과 결과는 그대로 두고 머리줄만 남긴다 */
  let mini = false, prevH = '', prevB = '';
  const bMin = plain('최소화', () => {
    mini = !mini;
    row2.style.display = mini ? 'none' : 'flex';
    ta.style.display = mini ? 'none' : '';
    if (mini) { prevH = box.style.height; prevB = box.style.bottom; box.style.height = 'auto'; box.style.bottom = 'auto'; }
    else { box.style.height = prevH; box.style.bottom = prevB; }
    bMin.textContent = mini ? '펼치기' : '최소화';
  });
  row1.append(grip, bTree, bList, bHarv, bPage, bDiag, st, bStop, bMin, bClose);
  row2.append(iN, iSort, iDelay, iWho, cMask, cScope, cSubs);
  box.append(row1, row2, ta);

  const run = async fn => {
    say('실행 중');
    const r = await fn();
    let out = r.md;
/* 아무것도 못 찾으면 진단을 붙여 준다. 이 화면을 그대로 공유하면 된다 */
    if (r.empty) { out += '\n\n' + '='.repeat(50) + '\n0건이라 구조 진단을 붙였다. 이 화면을 그대로 공유할 것\n' + '='.repeat(50) + '\n\n' + (await modDiag()).md; }
    put(out);
    say(r.status + (r.empty ? ' · 진단 첨부됨' : '') + ' · Ctrl+C');
  };

  /* ===== 게시판 링크 하나의 스레드·게시물 수를 읽는다. 트리와 목록에서 같이 쓴다 ===== */
  const byLabel = t => {
/* 콜론 있는 "Threads: 123" 형태를 먼저 본다. 없으면 "123 THREADS" 형태 */
    const thC = t.match(/(?:threads?|주제|스레드)\s*:\s*([\d,]+)/i);
    const poC = t.match(/(?:posts?|messages?|게시물)\s*:\s*([\d,]+)/i);
/* 한국어는 라벨이 앞에 온다. 이걸 안 보면 「주제 120 게시물 3,400」에서 120을 게시물로 잘못 읽는다 */
    const thK = t.match(/(?:주제|스레드|글\s?수)\s+([\d,]+)/);
    const poK = t.match(/(?:게시물|답글|댓글)\s+([\d,]+)/);
/* 라벨 뒤에 곧바로 숫자가 붙는 테마가 있어 \b 대신 「알파벳이 아니면 끝」으로 본다. 1774THREADS7439POSTS 같은 경우 */
    const thS = t.match(/([\d,]+)\s*(?:threads?|주제|스레드)(?![a-z])/i);
    const poS = t.match(/([\d,]+)\s*(?:posts?|messages?|게시물|글)(?![a-z])/i);
    return [N(thC && thC[1]) ?? N(thK && thK[1]) ?? N(thS && thS[1]),
            N(poC && poC[1]) ?? N(poK && poK[1]) ?? N(poS && poS[1])];
  };
  const countsOf = a => {
    let el = a, th = null, po = null, how = 'none', blocked = false;
    for (let i = 0; i < 7; i++) {
      const p = el.parentElement;
      if (!p || p === document.body) break;
/* 하위 게시판 링크는 그 행의 소유가 아니므로 blocked 판정에서 뺀다 */
      if ([...p.querySelectorAll('a[href]')].some(x => x !== a && isForum(x) && !inSub(x))) { blocked = true; break; }
      el = p;
      const [t, o] = byLabel(C(el.innerText || el.textContent));
      if (t != null || o != null) { th = t; po = o; how = 'label'; break; }
    }
    if (th == null && po == null) {
      const tr = a.closest('tr');
      if (tr) {
        const nums = [...tr.children]
          .filter(td => ![...td.querySelectorAll('a[href]')].some(x => x !== a && isForum(x)))
          .map(td => N(C(td.textContent))).filter(v => v != null);
        if (nums.length >= 2) { th = nums[0]; po = nums[1]; how = 'td'; }
        else if (nums.length === 1) { po = nums[0]; how = 'td1'; }
      }
    }
    return { th, po, how, blocked };
  };
/* 빵부스러기 링크는 하위 게시판이 아니다 */
  const BC = '.breadcrumb, .breadcrumb__main, .breadcrumb__bit, nav, .p-breadcrumbs, #breadcrumb';
  const isCrumb = a => !!a.closest(BC);

  /* ================= 1. 게시판 트리 ================= */
  const modTree = () => {
    const seen = new Map();
    fLinks.forEach(a => {
      const { th, po, how, blocked } = countsOf(a);
      const name = C(a.textContent), sub = inSub(a);
      const isCat = (!sub && th == null && po == null && blocked);
/* 카테고리 헤더가 첫 하위 게시판 URL을 그대로 쓰는 테마가 있어 카테고리는 이름으로 키를 잡는다 */
      const k = isCat ? 'cat::' + name : key(A(a));
      const rec = { depth: isCat ? 1 : (sub ? 3 : 2), name, threads: th, posts: po,
                    url: isCat ? '' : A(a), how: isCat ? 'cat' : (sub ? 'sub' : how) };
      if (!seen.has(k)) seen.set(k, rec);
      else if (seen.get(k).posts == null && po != null) seen.set(k, rec);
    });
    const rows = [...seen.values()];
    const boards = rows.filter(r => r.depth === 2);
    if (!rows.length) return { md: `# ${location.hostname} 게시판 트리\n\n게시판을 못 찾았다. 포럼 메인(인덱스) 페이지인지 확인할 것.\n`, status: '게시판 0개', empty: true };

    const totalPosts = boards.reduce((a, r) => a + (r.posts || 0), 0); /* 하위(3)는 상위에 합산돼 있으므로 뺀다 */
    const pct = p => (p && totalPosts) ? ((p / totalPosts) * 100).toFixed(1) + '%' : '';
    const miss = boards.filter(r => r.posts == null);
    const eng = document.querySelector('.node--forum, .node--category') ? 'xenforo'
              : /\/forums\/[^\/]+\.\d+/.test(location.href + document.body.innerHTML.slice(0, 4000)) ? 'xenforo(table)' : 'mybb';
    const wrong = boards.length === 0 || uT > boards.length * 4;

    let md = `# ${location.hostname} 게시판 트리\n\n${VER} · 엔진 ${eng} · 확인 ${stamp()} · ${new Date().toISOString()}\n`;
    if (wrong) md += `\n주의 — 스레드 링크가 ${uT}개다. 스레드 목록 페이지에서 돌렸을 수 있다. 포럼 메인에서 다시 볼 것.\n`;
    md += `\n링크 ${rows.length}개 (카테고리 ${rows.length - boards.length} · 게시판 ${boards.length}) · 게시물 합계 ${fmt(totalPosts)}`;
    md += miss.length ? ` · 수치 못 읽음 ${miss.length}개\n\n` : `\n\n`;
    md += `| 깊이 | 게시판 | 스레드 | 게시물 | 비중 | URL |\n|---|---|---|---|---|---|\n`;
    rows.forEach(r => md += `| ${r.depth} | ${'　'.repeat(Math.max(0, r.depth - 1))}${r.name} | ${fmt(r.threads)} | ${fmt(r.posts)} | ${pct(r.posts)} | ${r.url.replace(/^https?:\/\/[^\/]+/, '')} |\n`);
    if (miss.length) md += `\n수치 못 읽은 것 — ` + miss.map(r => r.name).join(', ') + `\n`;
    const top = boards.filter(r => r.posts).sort((a, b) => b.posts - a.posts).slice(0, 15);
    md += `\n## 게시물 많은 순\n\n| 게시판 | 스레드 | 게시물 | 스레드당 |\n|---|---|---|---|\n`;
    top.forEach(r => md += `| ${r.name} | ${fmt(r.threads)} | ${fmt(r.posts)} | ${(r.threads && r.posts) ? (r.posts / r.threads).toFixed(1) : ''} |\n`);
    let tsv = '깊이\t게시판\t스레드\t게시물\tURL\n';
    rows.forEach(r => tsv += `${r.depth}\t${r.name}\t${r.threads ?? ''}\t${r.posts ?? ''}\t${r.url}\n`);
    window.__TREE = rows;
    return { md: md + '\n\n---- TSV ----\n' + tsv,
             status: `게시판 지도 · ${eng} · 게시판 ${boards.length}개` + (miss.length ? ` · 미독 ${miss.length}` : ' · 전부 읽음') + (wrong ? ' · 페이지 의심' : '') };
  };

  /* ================= 2. 스레드 목록 · 본문 수집 ================= */
  const RE = {
    email: /([\w.+-]{1,64})@([\w-]+\.[\w.]{2,})/g,
    phoneKR: /\b01[016789][-. ]?\d{3,4}[-. ]?\d{4}\b/g,
    phoneIntl: /\+\d{1,3}[-. ]?\(?\d{2,4}\)?[-. ]?\d{3,4}[-. ]?\d{3,4}\b/g,
    rrn: /\b\d{6}[-]\d{7}\b/g,
    btc: /\b(bc1[a-z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b/g,
    xmr: /\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b/g,
    eth: /\b0x[a-fA-F0-9]{40}\b/g,
    onion: /\b[a-z2-7]{16,56}\.onion\b/g,
/* addlist/코드처럼 슬래시가 더 붙는 형태까지 잡는다. 전에는 t.me/addlist에서 잘렸다 */
    tg: /(?:t\.me|telegram\.me)\/[\w+\-\/]+/g,
/* 다크웹 판매글의 표준 연락 수단. 텔레그램만 보면 절반을 놓친다 */
    session: /\b05[0-9a-f]{64}\b/gi,
    tox: /\b[0-9A-F]{76}\b/g,
    matrix: /@[\w.\-]+:[\w.\-]+\.[a-z]{2,}/gi,
    jabber: /\b[\w.\-]+@(?:xmpp|jabber|exploit|thesecure|creep)[\w.\-]*\.[a-z]{2,}/gi,
/* 자동판매 상점. 합법 결제 플랫폼을 끼고 파는 경로다 */
    shop: /\b[\w.\-]+\.(?:sellix\.(?:cx|io)|bgng\.io|pw|app)\/?\S*|\bsellix\.[a-z]{2,}\S*/gi,
    bot: /@\w*_?[Bb][Oo][Tt]\b/g,
    host: /\b(?:gofile\.io|mega\.nz|anonfiles?\w*\.com|file\.io|pixeldrain\.com|mediafire\.com|dropbox\.com|qu\.ax|biteblob\.com|justpaste\.it|pastebin\.com|paste\.pm|pomf2\.lain\.la)\S*/g,
    ip: /\b(?:\d{1,3}\.){3}\d{1,3}\b/g,
    pct: /\b\d{1,2}(?:\.\d+)?\s*%/g,
    money: /(?:\$|USD|EUR|€)\s?[\d,]+(?:\.\d+)?|\b[\d,]+\s?(?:USD|EUR|BTC|XMR)\b/gi
  };
  const found = { wallet: new Set(), onion: new Set(), tg: new Set(), session: new Set(), tox: new Set(),
                  matrix: new Set(), jabber: new Set(), shop: new Set(), bot: new Set(), host: new Set(), ip: new Set() };
  const isSample = ln => { const t = ln.trim();
    if (t.length < 8) return false;
    if (t.split(/[:|;,\t]/).filter(Boolean).length < 3) return false;
    return /@|\d{6,}|[a-f0-9]{16,}/i.test(t); };
/* BBCode 꼬리와 끝의 잡문자를 떼어낸다. dbmarket.app[/COLOR] 같은 것이 그대로 들어오던 문제 */
  const tidy = v => String(v).replace(/\[\/?[A-Za-z][^\]]*\]/g, '').replace(/\[[^\]]*$/, '')
                             .replace(/[)\]\s.,;:'"]+$/, '').trim();
  const scan = raw => {
    for (const k of ['btc', 'xmr', 'eth']) (raw.match(RE[k]) || []).forEach(v => found.wallet.add(tidy(v)));
    (raw.match(RE.onion) || []).forEach(v => found.onion.add(tidy(v)));
    for (const k of ['tg', 'session', 'tox', 'matrix', 'jabber', 'shop', 'bot', 'host', 'ip'])
      (raw.match(RE[k]) || []).forEach(v => { const t = tidy(v); if (t) found[k].add(t); });
  };
  const proc = raw => {
    scan(raw);
    if (!cfg.mask) return raw; /* 기본은 원문 그대로. 검증에 샘플이 필요하기 때문 */
    const out = []; let runc = 0;
    for (const ln of raw.split('\n')) {
      if (isSample(ln)) { runc++; continue; }
      if (runc) { out.push(`<샘플로 판단해 ${runc}줄 생략>`); runc = 0; }
      out.push(ln);
    }
    if (runc) out.push(`<샘플로 판단해 ${runc}줄 생략>`);
    return out.join('\n').replace(RE.rrn, '<주민번호형>').replace(RE.email, '***@$2')
      .replace(RE.phoneKR, '<전화>').replace(RE.phoneIntl, '<전화>');
  };
  const CHL = /cf[-_]chl|cf_chl_opt|Just a moment|Checking your browser|__cf_chl|Attention Required/i;
/* DOMParser로 만든 문서는 브라우저마다 innerText 동작이 갈린다. 터지면 textContent로 떨어진다 */
  const S = el => { if (!el) return '';
    try { return CL(el); }
    catch (e) { try { return (el.textContent || '').replace(NB, ' ').replace(/\n{3,}/g, '\n\n').replace(/[ \t]+/g, ' ').trim(); } catch (e2) { return ''; } } };
/* MyBB 본문 첫 줄에 테마의 jQuery 조각이 섞여 들어온다. 지우되 거기 든 uid는 따로 챙긴다 */
  const JQ = /^\s*\$\(\s*["'][^)]*\)\s*\.\w+\([^\n]*\);?\s*$/gm;
  const strip = t => t.replace(JQ, '').replace(/^\s*\n/, '').trim();
  const uidOf = el => { const m = (el.innerHTML || '').match(/action=profile&(?:amp;)?uid=(\d+)/i); return m ? m[1] : null; };
  const EX = {
    mybb: doc => [...doc.querySelectorAll('div.post, [id^="post_"]')].map(el => {
      const u = uidOf(el);
      const nm = S(el.querySelector('.post_author .largetext, .post_author strong, .largetext')) ||
                 S(el.querySelector('.post_author')).split('\n')[0] || '?';
      return { author: nm + (u ? ` (uid ${u})` : ''),
               date: S(el.querySelector('.post_date, .post_head .smalltext')) || '?',
               body: strip(S(el.querySelector('.post_body, [id^="pid_"]')) || S(el)),
/* MyBB가 긴 주소를 화면에서 ... 로 줄여 보여준다. 실제 href를 따로 챙겨 단서로 쓴다 */
               hrefs: [...el.querySelectorAll('a[href]')].map(a => a.href) };
    }),
    xenforo: doc => [...doc.querySelectorAll('article.message, .message--post')].map(el => {
      const tm = el.querySelector('time[datetime]');
      return { author: el.getAttribute('data-author') || S(el.querySelector('.message-name .username, .username')) || '?',
               date: tm ? tm.getAttribute('datetime') : S(el.querySelector('.message-attribution-main')) || '?',
               body: S(el.querySelector('.bbWrapper, .message-body')),
               hrefs: [...el.querySelectorAll('.bbWrapper a[href], .message-body a[href]')].map(a => a.href) };
    })
  };
/* 추출기가 통째로 터져도 본문은 건진다. 선택자만 직접 훑는 최후 수단 */
  const RAW = doc => [...doc.querySelectorAll('.post_body, [id^="pid_"], .bbWrapper, .message-body')]
    .map(el => ({ author: '?', date: '?', body: strip(S(el)) })).filter(p => p.body);
  const engOf = d => d.querySelector('article.message, .message--post') ? 'xenforo'
                  : d.querySelector('div.post, [id^="post_"]') ? 'mybb' : null;

  const modList = async withBodies => {
    const t0 = Date.now();
    const seen = new Set(), targets = [];
/* 목록 행에서 작성자·답글·조회·날짜를 같이 뽑는다. 본문을 안 열고도 셀 수 있게 하려는 것 */
    const rowOf = a => { let e = a;
      for (let i = 0; i < 8 && e.parentElement; i++) { e = e.parentElement;
        if (/^(tr|li)$/i.test(e.tagName) || /structItem|inline_row|threadbit/i.test(e.className || '')) return e; }
      return null; };
    const metaOf = a => {
      const r = rowOf(a); if (!r) return {};
      const au = [...r.querySelectorAll('a[href]')]
        .find(x => /\/User-|member\.php\?action=profile|\/members\/|finduser/i.test(x.href || ''));
      const t = C(r.innerText || r.textContent);
/* 숫자 칸을 훑는다. 표면 열, 아니면 행 전체에서 천단위 숫자를 줍는다 */
      let nums = [...r.children].map(c => N(C(c.textContent))).filter(v => v != null);
      if (nums.length < 2) nums = (t.match(/\b\d{1,3}(?:,\d{3})*\b/g) || []).map(N).filter(v => v != null);
      const dm = t.match(/(Today|Yesterday|\d{4}-\d{2}-\d{2}|[A-Z][a-z]{2}\s\d{1,2},\s\d{4})/);
      return { author: au ? C(au.textContent) : '', replies: nums[0] ?? null, views: nums[1] ?? null, date: dm ? dm[1] : '' };
    };
/* 쿼리로 글을 가리키는 주소가 있다. showthread.php?tid=194121 에서 ?tid= 를 떼면 글이 사라진다. */
/* 중복 판정에만 쓰는 열쇠와 실제로 받아올 주소를 갈라 놓는다 */
    const idKey = u => {
      const m = u.match(/[?&](tid|aid|pid)=(\d+)/i);
      return m ? u.split('?')[0].toLowerCase() + '#' + m[1].toLowerCase() + m[2]
               : u.split('#')[0].split('?')[0].replace(/\/$/, '').toLowerCase();
    };
    const grab = (doc, tag, base) => { for (const a of doc.querySelectorAll('a[href]')) {
      if (!isThread(a)) continue;
      let abs; try { abs = new URL(a.getAttribute('href'), base || location.href).href.split('#')[0]; } catch (e) { continue; }
      const k = idKey(abs); if (seen.has(k)) continue;
      seen.add(k); targets.push(Object.assign({ url: abs, title: (tag ? `[${tag}] ` : '') + C(a.textContent), tag: tag || '' }, metaOf(a)));
    } };
/* 목록 주소 만들기. 정렬을 고르면 그 순서로 다시 받는다 */
    const listUrl = (base, pg, sort) => {
      const xf = base.includes('/forums/');
      let u = base.replace(/[?#].*$/, '').replace(/\/$/, ''); const q = [];
      if (sort) {
        if (xf) q.push('order=' + (sort === 'views' ? 'view_count' : sort === 'replies' ? 'reply_count' : 'last_post_date'), 'direction=desc');
        else q.push('datecut=9999', 'prefix=0', 'sortby=' + sort, 'order=desc');
      }
      if (pg > 1) { if (xf) u += '/page-' + pg; else q.push('page=' + pg); }
      return u + (q.length ? '?' + q.join('&') : '');
    };
/* 한 게시판에서 할당된 건수가 찰 때까지 쪽을 넘긴다. 새 글이 안 늘면 마지막 쪽으로 보고 멈춘다 */
    const crawl = async (base, tag, live, quota) => {
      const start = targets.length;
      for (let pg = 1; pg <= 500 && !ABORT; pg++) {
        if (targets.length - start >= quota) break;
        const before = targets.length;
        if (pg === 1 && live && !cfg.sort) {
          pickScope(document).els.forEach(e => grab(e));
        } else {
          try {
            await wait();
            const r = await fetch(listUrl(base, pg, cfg.sort), { credentials: 'same-origin' });
/* 2026-08-27. 여기에 챌린지와 레이트리밋 검사가 없었다. qilin_kit 에는 있었다.
   챌린지 페이지가 200 으로 오면 파싱이 0건이 되어 마지막 쪽으로 읽혔고,
   429 를 받아도 다음 쪽을 계속 두드렸다. 실패가 결과에도 안 남아
   "글 없는 게시판" 과 구별되지 않았다. 셋이 계정을 같이 쓴다. */
            if (r.status === 429 || r.status === 503) {
              FAILED.push(`${listUrl(base, pg, cfg.sort)} — HTTP ${r.status} 레이트리밋 의심. 즉시 멈춤`);
              ABORT = true; break;
            }
            if (!r.ok) { FAILED.push(`${listUrl(base, pg, cfg.sort)} — HTTP ${r.status}`); break; }
            const txt = await r.text();
            if (CHL.test(txt.slice(0, 6000))) {
              FAILED.push(`${listUrl(base, pg, cfg.sort)} — 챌린지 화면. 즉시 멈춤`);
              ABORT = true; break;
            }
            const doc = new DOMParser().parseFromString(txt, 'text/html');
            pickScope(doc).els.forEach(e => grab(e, tag, base));
          } catch (e) {
            FAILED.push(`${listUrl(base, pg, cfg.sort)} — ${e && e.message || '요청 실패'}`);
            break;
          }
        }
        const got = targets.length - before;
        say(`목록 모으는 중 · ${tag || '이 게시판'} ${pg}쪽 · 새로 ${got}건 · 목록 누적 ${targets.length}건`);
        if (ABORT) break;
        if (pg > 1 && got === 0) break; /* 더 안 늘면 끝. 전수로 돌릴 때의 안전장치 */
      }
/* 할당보다 많이 담겼으면(한 쪽에 여러 건이라) 잘라 낸다 */
      const over = (targets.length - start) - quota;
      if (over > 0) targets.splice(targets.length - over, over);
    };
/* 하위 게시판을 수치까지 읽는다. 상위 게시판의 스레드 수는 하위를 포함한 값이라 */
/* 이걸 빼지 않으면 규모를 잘못 읽는다. bf.st Announcements 857이 하위 847을 포함한 값이었던 것과 같다 */
    const selfKey = key(location.href);
    const subs = [], crumbs = [], oseen = new Set();
    fLinks.forEach(a => {
      const u = key(A(a)); if (u === selfKey || oseen.has(u)) return; oseen.add(u);
      const nm = C(a.textContent);
      if (isCrumb(a)) { crumbs.push(`${nm} → ${u}`); return; }
      const { th, po } = countsOf(a);
      subs.push({ nm, u, th, po });
    });
    const subTh = subs.reduce((x, r) => x + (r.th || 0), 0);
    const subPo = subs.reduce((x, r) => x + (r.po || 0), 0);
    const sc = pickScope(document);
    say('목록 영역 : ' + sc.how);
/* 하위 게시판을 함께 볼 때는 건수를 게시판 수로 나눠 고르게 담는다 */
    const boardsN = 1 + (cfg.subs ? subs.length : 0);
    const quota = Math.max(1, Math.ceil(cfg.n / boardsN));
    if (boardsN > 1) say(`${cfg.n}건을 게시판 ${boardsN}곳에 나눠 각 ${quota}건씩 모은다`);
    await crawl(location.href, '', true, quota);

/* 같은 게시판 주소의 페이지 링크만 센다. 긴 스레드의 답글 페이지(Thread-xxx?page=2)를 목록 페이지로 오해하던 것을 막는다 */
    const basePath = location.pathname.replace(/\/$/, '');
    const pgN = Math.max(0, ...links.filter(a => { try { return new URL(A(a)).pathname.replace(/\/$/, '') === basePath; } catch (e) { return false; } })
      .map(a => { const m = A(a).match(/page[=\-\/](\d+)/i); return m ? parseInt(m[1], 10) : 0; }));

    let listMd = `# ${location.hostname} 글 목록\n\n${VER}\n출처 : ${location.href}`
      + (cfg.sort ? `\n정렬 : ${{ views: '조회 많은 순', replies: '답글 많은 순', lastpost: '최신순' }[cfg.sort]}` : '')
      + `\n영역 : ${sc.how}\n확인 : ${stamp()}\n대상 ${targets.length}건\n`;
    if (!withBodies) listMd += `\n>> 여기까지는 제목과 URL뿐이다. 본문과 답글이 필요하면 위 초록색 「본문 받기」 버튼을 누를 것.\n`
      + `>> ${targets.length}건 × 간격 2.5~5초라 ${Math.max(1, Math.ceil(targets.length * 3.75 / 60))}분쯤 걸린다. 다 끝난 뒤에 복사할 것.\n`;
    if (pgN > 1) {
      listMd += `\n참고 — 이 게시판 목록은 ${pgN}쪽까지 있다. 지금은 ${targets.length}건만 모았다. 더 필요하면 「글 몇 건까지」를 올릴 것.\n`;
      if (pgN > 20) listMd += `한 쪽에 20건쯤이면 이 게시판 전체는 ${fmt(pgN * 20)}건 안팎이다. `
        + `전부 받는 것은 현실적이지 않다. 정렬을 걸어 위에서부터 필요한 만큼만 받는 편이 낫다.\n`;
    }
    if (subs.length) {
      listMd += `\n## 이 게시판의 하위 게시판 ${subs.length}개\n\n| 게시판 | 스레드 | 게시물 | URL |\n|---|---|---|---|\n`;
      subs.forEach(r => listMd += `| ${r.nm} | ${fmt(r.th)} | ${fmt(r.po)} | ${r.u.replace(/^https?:\/\/[^\/]+/, '')} |\n`);
      if (subTh || subPo) listMd += `| 하위 합계 | ${fmt(subTh)} | ${fmt(subPo)} | |\n`;
      listMd += `\n상위 게시판의 스레드·게시물 수는 하위를 포함한 값이다. 이 게시판만의 규모를 보려면 위 합계를 빼야 한다.\n`
        + (cfg.subs ? `「하위 게시판도」가 켜져 있어 아래에서 하위 목록도 같이 받는다.\n`
                      : `하위 게시판 글은 여기서 안 잡힌다. 「하위 게시판도」를 켜면 한 번에 돈다.\n`);
    }
    if (crumbs.length) listMd += `\n지나온 경로 (빵부스러기)\n` + crumbs.map(o => '- ' + o).join('\n') + '\n';
/* 하위 게시판까지 켜져 있으면 각 하위 게시판 목록도 받아 온다. 네 번 들어갈 것을 한 번에 끝내려는 것 */
    let subGot = 0;
    if (cfg.subs && subs.length) {
      const before = targets.length;
      for (const sb of subs) { if (ABORT) break; await crawl(sb.u, sb.nm, false, quota); }
      subGot = targets.length - before;
      listMd += `\n하위 게시판 ${subs.length}곳을 돌아 ${subGot}건을 더 모았다. 목록에 [게시판명]으로 표시된다.\n`;
    } else if (subs.length) {
      listMd += `\n하위 게시판 목록은 아직 안 받았다. 「하위 게시판도」를 켜고 다시 누르면 네 곳을 한 번에 돈다.\n`;
    }
    listMd = listMd.replace(/^대상 \d+건$/m, `대상 ${targets.length}건`);
    listMd += `\n` + targets.map((t, i) => `${i + 1}. ${t.title}\n   ${t.url}`).join('\n') + '\n';
/* 정렬을 걸었으면 실제로 그 순서로 왔는지 확인한다. 포럼이 요청을 무시해도 화면에는 티가 안 나기 때문 */
    if (cfg.sort === 'views' || cfg.sort === 'replies') {
      const kf = cfg.sort, lab = kf === 'views' ? '조회수' : '답글 수';
      const groups = {};
      targets.forEach(t => { const g = t.tag || '이 게시판'; (groups[g] = groups[g] || []).push(t[kf]); });
      const bad = [], ok = [];
      for (const [g, arr] of Object.entries(groups)) {
        const v = arr.filter(x => x != null);
        if (v.length < 3) continue;
        let desc = true;
        for (let i = 1; i < v.length; i++) if (v[i] > v[i - 1]) { desc = false; break; }
        (desc ? ok : bad).push(g);
      }
      if (bad.length) listMd += `\n정렬 확인 — ${bad.join(' · ')}에서 ${lab}가 내림차순이 아니다. `
        + `포럼이 정렬 요청을 무시했을 수 있다. 아래 표의 ${lab} 열을 눈으로 볼 것.\n`;
      else if (ok.length) listMd += `\n정렬 확인 — ${lab} 내림차순이 맞다 (${ok.length}개 게시판).\n`;
      else listMd += `\n정렬 확인 — ${lab}를 못 읽어 확인하지 못했다. 표의 ${lab} 열이 비어 있는지 볼 것.\n`;
    }
/* 표 계산용. 엑셀이나 노션에 그대로 붙여 셀 수 있다 */
    listMd += `\n---- TSV (게시판 · 제목 · 작성자 · 답글 · 조회 · 날짜 · URL) ----\n`;
/* 내가 붙인 [게시판명]만 떼고 [PAKISTAN] 같은 원래 제목의 국가 태그는 남긴다. 그게 셀 거리다 */
    listMd += targets.map(t => [t.tag || '',
      (t.tag && (t.title || '').startsWith(`[${t.tag}] `)) ? t.title.slice(t.tag.length + 3) : (t.title || ''),
      t.author || '', t.replies ?? '', t.views ?? '', t.date || '', t.url].join('\t')).join('\n') + '\n';
    if (!targets.length) return { md: listMd, status: '0건', empty: true };
    if (!withBodies) { bHarv.style.background = '#0a4'; bHarv.style.color = '#fff'; bHarv.style.border = '1px solid #0f8'; bHarv.style.fontWeight = 'bold';
      return { md: listMd, status: `글 목록 ${targets.length}건 모음. 본문이 필요하면 초록색 「본문 받기」를 누를 것` }; }

    put(listMd);
    const total = targets.length;
    const out = [`# ${location.hostname} 수집\n\n${VER}\n출처 목록 : ${location.href}\n확인 : ${stamp()} · ${new Date().toISOString()}\n대상 ${targets.length}건 (수집 ${total}건) · 마스킹 ${cfg.mask ? 'ON' : 'OFF(원문)'}\n`];
    const fails = [], gated = [];
    let n = 0, streak = 0;
    for (const t of targets) {
      if (ABORT) { out.push('\n> 사용자 중단\n'); break; }
      n++;
      say(`본문 받는 중 ${n}/${total}건 (목록 ${targets.length}건 중) · ${Math.round((Date.now() - t0) / 1000)}초 · ${t.title.slice(0, 34)}`);
      try {
        const res = await fetch(t.url, { credentials: 'same-origin' });
        const html = await res.text();
/* 차단(중단해야 함)과 권한 거부(기록하고 계속)를 가른다 */
        const bad = CHL.test(html.slice(0, 6000)) ? 'Cloudflare 챌린지 페이지'
                  : (res.status === 429 || res.status === 503) ? `HTTP ${res.status} 레이트리밋 의심` : null;
        if (bad) { out.push(`\n> 중단. ${bad}. 이후 요청은 보내지 않았다.\n`); fails.push(`${t.url} : ${bad}`);
                   say(`중단. ${bad}. 간격을 늘리고 시간을 두고 다시 시도할 것`); ABORT = true; break; }
        if (res.status === 403) {
          out.push(`\n---\n\n## ${t.title}\n\n- URL : ${t.url}\n- 상태 : 403 접근 권한 없음 (등급 제한 또는 삭제·이동)\n- 확인 : ${stamp()}\n`);
          gated.push(`${t.title} : ${t.url}`); streak = 0; await wait(); continue;
        }
        if (!res.ok) { fails.push(`${t.url} : HTTP ${res.status}`);
                       if (++streak >= 3) { say('연속 3회 실패. 중단'); ABORT = true; break; } await wait(); continue; }
        streak = 0;
        const doc = new DOMParser().parseFromString(html, 'text/html');
        const eng = engOf(doc);
        const title = CL(doc.querySelector('.thread_head .subject, .p-title-value, h1')) || t.title;
        out.push(`\n---\n\n## ${title}\n\n- URL : ${t.url}\n- 엔진 : ${eng || '판별실패'}\n- 확인 : ${stamp()}\n`);
        if (!eng) {
/* 포럼이 「없는 글」이라고 답한 경우와 우리가 구조를 못 읽은 경우를 가른다 */
          const msg = (CL(doc.body) || '').match(/(specified thread does not exist|announcement specified is invalid|no longer available|do not have permission|not have access)/i);
          if (msg) {
            out.push(`\n> 포럼이 「${msg[1]}」라고 답했다. 주소가 잘못됐거나 권한이 없다.\n`);
            fails.push(`${t.url} : ${msg[1]}`);
          } else {
            out.push('\n> 구조를 못 읽었다. 덤프\n\n```\n' + (doc.body ? CL(doc.body).slice(0, 1200) : '') + '\n```\n');
            fails.push(`${t.url} : parse`);
          }
        }
        else {
          let posts = [];
          try { posts = EX[eng](doc).filter(p => p.body); }
          catch (e) { posts = RAW(doc); fails.push(`${t.url} : 추출기 오류(${e}) → 최후 수단으로 ${posts.length}건 건짐`); }
          if (!posts.length) { posts = RAW(doc); if (!posts.length) fails.push(`${t.url} : empty`); }
          posts.forEach((p, i) => {
            if (p.hrefs && p.hrefs.length) scan(p.hrefs.join('\n')); /* 잘리지 않은 주소로 단서를 보강한다 */
            out.push(`\n### ${i === 0 ? '원문' : '답글 ' + i}  ${p.author}  ${p.date}\n\n\`\`\`\n${proc(p.body)}\n\`\`\`\n`);
          });
        }
      } catch (e) { fails.push(`${t.url} : ${e}`); }
      await wait();
    }
    const dump = (label, set) => set.size ? `\n### ${label} (${set.size})\n\n` + [...set].map(v => '- ' + v).join('\n') + '\n' : '';
    const clues = dump('지갑 주소', found.wallet) + dump('onion', found.onion) + dump('텔레그램', found.tg) +
                  dump('텔레그램 봇', found.bot) + dump('Session ID', found.session) + dump('Tox ID', found.tox) +
                  dump('Matrix', found.matrix) + dump('Jabber/XMPP', found.jabber) +
                  dump('자동판매 상점', found.shop) + dump('파일 호스팅', found.host) + dump('IP', found.ip);
    if (clues) out.push('\n---\n\n## 추출된 단서\n' + clues);
    if (gated.length) out.push('\n## 등급 제한으로 못 본 글 (' + gated.length + ')\n\n' + gated.map(g => '- ' + g).join('\n') +
      '\n\n> 6번 확인 못 한 것에 접근 권한 없음으로 기록할 것\n');
    if (fails.length) out.push('\n## 못 가져온 것\n\n' + fails.map(f => '- ' + f).join('\n') + '\n');
/* 숫자가 줄어든 것처럼 보이지 않게 목록과 본문을 갈라 적는다 */
    const why = [];
    if (ABORT) why.push('중단됨');

    if (fails.length) why.push(`실패 ${fails.length}건`);
    if (gated.length) why.push(`권한 없음 ${gated.length}건`);
    out.splice(1, 0, `\n## 수집 요약\n\n- 목록에 모인 글 : ${targets.length}건\n`
      + `- 본문을 받은 글 : ${n}건${n < targets.length ? ` (나머지 ${targets.length - n}건은 안 받음)` : ''}\n`
      + (why.length ? `- 이유 : ${why.join(' · ')}\n` : '')
      + `- 걸린 시간 : ${Math.round((Date.now() - t0) / 1000)}초\n`);
    window.__OUT = out.join('');
    return { md: window.__OUT,
             status: `본문 ${n}건 받음 (목록 ${targets.length}건 중)` + (why.length ? ` · ${why.join(' · ')}` : '')
                     + ` · ${Math.round((Date.now() - t0) / 1000)}초` };
  };

  /* ===== 체크·엑스·무한 기호는 아이콘이라 텍스트로 안 나온다. 잠깐 글자로 바꿔 놓고 읽는다 ===== */
  const ICON_SEL = 'i,svg,img,span[class*="fa-"],span[class*="icon"]';
  const symOf = el => {
    const cn = el.className;
    const c = ((typeof cn === 'string' ? cn : (cn && cn.baseVal) || '') + ' ' +
               (el.getAttribute('title') || '') + ' ' + (el.getAttribute('alt') || '') + ' ' +
               (el.getAttribute('aria-label') || '')).toLowerCase();
    if (/infinit/.test(c)) return '∞';
    if (/(check|tick|circle-check|thumbs-up)/.test(c) && !/uncheck/.test(c)) return '✓';
    if (/(times|xmark|x-mark|close|remove|cross|ban|circle-xmark|thumbs-down)/.test(c)) return '✗';
    return null;
  };
/* 읽는 동안만 바꾸고 반드시 되돌린다. 남의 페이지를 건드리는 것이라 예외가 나도 복구한다 */
  const withSymbols = fn => {
    const undo = [];
    try {
      document.querySelectorAll(ICON_SEL).forEach(el => {
        const sym = symOf(el); if (!sym) return;
        const t = document.createTextNode(sym);
        el.parentNode.insertBefore(t, el);
        const old = el.style.display; el.style.display = 'none';
        undo.push(() => { t.remove(); el.style.display = old; });
      });
      return fn(undo.length);
    } finally { undo.forEach(f => { try { f(); } catch (e) {} }); }
  };

  /* ================= 3. 낱장 본문 ================= */
  const modPage = () => withSymbols(nIcon => {
    const title = C(document.querySelector('.thread_head .subject, .p-title-value, h1, .thead strong')?.textContent) || document.title;
    const cands = [];
    const push = (sel, how) => document.querySelectorAll(sel).forEach(el => { const t = CL(el); if (t.length > 80) cands.push({ how, t, el }); });
    push('.post_body, [id^="pid_"]', 'mybb-post'); /* MyBB 게시글 */
    push('article.message .bbWrapper, .message-body', 'xenforo'); /* XenForo */
    push('table.tborder td.trow1, table.tborder td.trow2', 'mybb-announcement'); /* MyBB 공지 (스레드가 아닌 정적 안내) */
    push('#content, .content, main, article', 'generic');
    const uniq = [];
    cands.sort((a, b) => a.t.length - b.t.length).forEach(c => { if (!uniq.some(u => c.el.contains(u.el))) uniq.push(c); });
    const bodies = uniq.length ? uniq : cands.slice(0, 1);
    if (!bodies.length) return { md: `# ${title}\n\n- URL : ${location.href}\n\n본문을 못 찾았다.\n`, status: '본문 0블록', empty: true };

    const whole = bodies.map(b => b.t).join('\n');
    const clue = {};
    for (const [k, re] of Object.entries(RE)) { const m = [...new Set(whole.match(re) || [])]; if (m.length) clue[k] = m; }
    delete clue.email; delete clue.phoneKR; delete clue.phoneIntl; delete clue.rrn;
    const LABEL = { btc: 'BTC 지갑', xmr: 'XMR 지갑', eth: 'ETH 지갑', onion: 'onion', tg: '텔레그램',
                    bot: '텔레그램 봇', session: 'Session ID', tox: 'Tox ID', matrix: 'Matrix', jabber: 'Jabber/XMPP',
                    shop: '자동판매 상점', host: '파일 호스팅', ip: 'IP', pct: '퍼센트(수수료 후보)', money: '금액' };

/* 내 계정·세션이 드러나는 링크는 뽑지 않는다. 공유 계정이라 하나 노출되면 셋이 다 걸린다 */
    const ALWAYS = /logout|logoutkey|usercp|\/alerts|my_post_key|markread|action=getdaily|\/credits\.php|private\.php(?!\?action=send)/i;
    const myUid = (document.body.innerHTML.match(/finduserthreads&(?:amp;)?uid=(\d+)/i) || [])[1] || null;
    const mine = h => myUid && new RegExp('uid=' + myUid + '\\b').test(h);
    let cut = 0;
    const ls = [...new Set(links.filter(a => { const h = a.getAttribute('href') || '';
        const bad = ALWAYS.test(h) || mine(h); if (bad) cut++; return !bad; })
      .map(a => `${C(a.textContent).slice(0, 40)} → ${a.getAttribute('href')}`)
      .filter(s => s && !/^\s*→/.test(s)))].slice(0, 40);

    let md = `# ${title}\n\n- URL : ${location.href}\n- 도구 : ${VER}\n- 확인 : ${stamp()}\n- 추출 방식 : ${[...new Set(bodies.map(b => b.how))].join(', ')}\n\n## 본문\n\n`;
    bodies.forEach((b, i) => { md += (bodies.length > 1 ? `### 블록 ${i + 1} (${b.how})\n\n` : '') + '```\n' + b.t + '\n```\n\n'; });
    if (Object.keys(clue).length) { md += `## 추출된 단서\n\n`;
      for (const [k, v] of Object.entries(clue)) md += `- ${LABEL[k] || k} : ${v.join(' · ')}\n`; }
    md += `\n## 페이지 내 링크 (앞 40${cut ? ' · 계정·세션 링크 ' + cut + '개 제외' : ''})\n\n` + ls.map(l => '- ' + l).join('\n') + '\n';
    if (nIcon) md += `\n아이콘 ${nIcon}개를 기호로 바꿔 읽었다 (✓ 있음 · ✗ 없음 · ∞ 무제한). 원래는 그림이라 텍스트에 안 나온다.\n`;
    return { md, status: `이 글 본문 · ${bodies.length}블록 ${whole.length}자 · 단서 ${Object.keys(clue).length}종` + (nIcon ? ` · 아이콘 ${nIcon}개 복원` : '') };
  });

  /* ================= 4. 구조 진단 ================= */
  const modDiag = async () => {
    const L = [], add = s => L.push(s);
    add(`# 구조 진단\n`);
    add(`- 도구 : ${VER}`);
    add(`- URL : ${location.href}`);
    add(`- TITLE : ${document.title}`);
    add(`- 확인 : ${stamp()}`);
    add(`- 판정 : ${KNAME[KIND]}  (게시판 링크 ${uF} · 스레드 링크 ${uT} · 본문 블록 ${nBody})\n`);

    const SELS = ['table.tborder', 'table.tborder tbody', 'table.tborder tr', '.forumbit_depth1', '.forumbit_depth2',
      '.node--forum', '.node--category', '.forums__bit', '.threadlist', '.thread_list', '#threadslist',
      '.structItemContainer', '.structItem', '.inline_row', '.threads__list', '.post_body', 'article.message',
      'div.post', '#content', 'main'];
    add('## 선택자별 매칭 개수\n');
    SELS.forEach(s => { const n = document.querySelectorAll(s).length; if (n) add(`- ${s} → ${n}`); });
    add('');

    const section = (label, arr, pick) => {
      add(`## ${label} (${arr.length}개)\n`);
      if (!arr.length) { add('없음\n'); return; }
      const cand = autoScope(document, pick);
      const sco = new Map();
      arr.forEach(a => { let e = a.parentElement, d = 0;
        while (e && e !== document.body && d < 12) { sco.set(e, (sco.get(e) || 0) + 1); e = e.parentElement; d++; } });
      const best = [...sco.entries()].filter(([, n]) => n >= Math.max(3, arr.length * 0.5))
        .sort((a, b) => a[0].querySelectorAll('*').length - b[0].querySelectorAll('*').length || b[1] - a[1]).slice(0, 5);
      add('컨테이너 후보 (작은 순)\n');
      best.forEach(([e, n]) => add(`- ${n}개 · ${path(e)}`));
      if (cand) add(`\n자동 선택 : ${path(cand[0])}`);
      let row = arr[0];
      for (let i = 0; i < 8 && row.parentElement; i++) {
        row = row.parentElement;
        if (/^(tr|li)$/i.test(row.tagName) || /structItem|inline_row|forumbit|node/i.test(row.className || '')) break;
      }
      add(`\n행 하나 outerHTML (1800자)\n\n\`\`\`html\n${row.outerHTML.slice(0, 1800)}\n\`\`\`\n`);
      add(`행 innerText\n\n\`\`\`\n${CL(row).slice(0, 300)}\n\`\`\`\n`);
      add('링크 앞 15개\n');
      [...new Set(arr.map(a => key(A(a))))].slice(0, 15).forEach((u, i) => add(`${i + 1}. ${u}`));
      add('');
    };
    section('게시판으로 보이는 링크', fLinks, isForum);
    section('스레드로 보이는 링크', tLinks, isThread);

    add('## 본문 후보 선택자\n');
    ['.post_body', '[id^="pid_"]', 'article.message .bbWrapper', '.message-body',
     'table.tborder td.trow1', 'table.tborder td.trow2'].forEach(s => {
      const els = [...document.querySelectorAll(s)];
      if (els.length) add(`- ${s} → ${els.length}개 · 최대 ${Math.max(...els.map(e => CL(e).length))}자`);
    });
    add('');
    const pg = links.filter(a => /page=\d|\/page-\d|page\/\d/i.test(A(a)))
      .map(a => C(a.textContent).slice(0, 12) + ' ← ' + a.getAttribute('href')).slice(0, 8);
    add('## 페이지네이션 링크\n');
    add(pg.length ? pg.map(s => '- ' + s).join('\n') : '없음');
    add('');
    const nums = [...new Set(((document.body.innerText || document.body.textContent).match(/\b\d{1,3}(?:,\d{3})+\b/g) || []))].slice(0, 20);
    add('## 페이지 내 천단위 숫자 (앞 20)\n');
    add(nums.length ? nums.join(' · ') : '없음');
    return { md: L.join('\n'), status: `구조 진단 완료 · ${KNAME[KIND]}` };
  };

  /* ================= 시작 ================= */
  document.body.appendChild(box);
  window.__FK = { ver: VER, open: () => { if (!document.body.contains(box)) document.body.appendChild(box); }, destroy: () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); box.remove(); } };
  say(`${VER} · ${KNAME[KIND]}으로 판정 · 게시판 ${uF} · 스레드 ${uT} · 본문 ${nBody}`);
  ta.value = '실행 중';
/* 켜면 상자만 뜬다. 무엇을 할지는 사람이 단추로 고른다.

   2026-08-27. 전에는 판정한 모듈을 자동으로 눌렀다. 두 가지가 나빴다.
   하나, 목록 페이지에서 눌리던 modList 안에 fetch 가 둘 있어서 켜기만 해도
   쪽을 넘겨 가며 요청이 나갔다. 셋이 계정을 같이 쓰므로 한 명이 막히면 셋이 막힌다.
   둘, 켜는 것과 도는 것이 섞여 있어서 상자가 안 뜰 때 설치 문제인지
   모듈 문제인지 구별이 안 됐다.
   추천 단추는 초록으로 강조된다. 그것을 누르면 전과 같다. */
  ta.value = ['킷이 떴다. 아래 단추 중 하나를 누르면 시작한다.', '',
              '  추천    ' + ({ index: '게시판 지도', list: '글 목록',
                                page: '이 글 본문' }[KIND] || '구조 진단'),
              '',
              '「글 목록」과 「본문 받기」는 요청을 낸다. 간격을 확인하고 누를 것.',
              '나머지는 열려 있는 문서만 읽는다.'].join('\n');
})();
