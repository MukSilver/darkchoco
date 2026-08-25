/* 다크초코 통합 킷 v1
 *
 * **이 파일은 손으로 고치지 마라. build_kit.py 가 만든 것이다.**
 * 고칠 자리는 forum_kit.js · qilin_kit.js · index_kit.js · photo_kit.js ·
 * probe_generic.js · kit_shell.js 여섯이다. 고친 뒤 아래를 돌린다.
 *
 *     python bookmarklets/build_kit.py
 *     python bookmarklets/build_bookmarklet.py
 *
 * 킷 다섯을 하나로 합쳤다. 어느 페이지에서 눌러도 된다.
 * 페이지 종류를 판정해 맞는 것을 켜 두고, 아니면 직접 고르면 된다.
 *
 *   포럼        MyBB · XenForo 계열 게시판
 *   킬린        Qilin 유출 사이트
 *   디렉터리     nginx · Apache 열린 목록
 *   증거 사진    썸네일 격자
 *   구조 진단    판정이 안 될 때
 *
 * **한 번에 하나만 뜬다.** 고른 것이 자기 상자를 만든다.
 * 각 모듈은 따로 쓰던 킷의 본문 그대로다. 동작이 바뀌지 않았다.
 *
 * 요청 간격은 모듈 안에서 지킨다. 포럼은 하한 2초다. 줄이지 마라.
 * 계정과 회선을 셋이 공유한다. 한 명이 막히면 셋이 같이 막힌다.
 * 2026-08-24 다크초코 */
(() => {
  const VER = 'darkchoco kit v1';
  if (window.__DK) { try { window.__DK.remove(); } catch (e) {} window.__DK = null; }

  /* ── 어느 페이지인가 ─────────────────────────
     네트워크를 쓰지 않는다. 열려 있는 문서만 본다.
     맞는 것이 없으면 진단으로 보낸다. */
  const A = [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href') || '');
  const H = location.href;
  const TXT = (document.body && document.body.innerText || '').slice(0, 4000);

  const hit = (rx) => A.filter(h => rx.test(h)).length;

  const guess = {
    forum: hit(/showthread\.php|\/Thread-|forumdisplay\.php|\/Forum-|\/threads\/|\/forums\//i) >= 4,
    qilin: /\/site\/blog\?uuid=|\/c\/[^\/]+\/\d+/.test(H),
    dirindex: /^Index of \//.test((document.title || '')) ||
              /Parent Directory|\[To Parent Directory\]/i.test(TXT) ||
              (!!document.querySelector('pre') && hit(/\/$/) >= 3),
    photo: document.querySelectorAll('img').length >= 6
  };

  const ORDER = ['qilin', 'dirindex', 'forum', 'photo'];
  const BEST = ORDER.filter(k => guess[k])[0] || 'probe';

  /* ── 모듈. 각각 자기 상자를 만든다 ───────────── */

  /* ── 공통 껍데기. 세 모듈이 같이 쓴다 ── */
  /* 킷 껍데기. qilin·index·photo 셋이 같이 쓴다.
   *
   * 세 킷의 UI 가 63줄 중 53줄이 같았다. 같은 것을 여기 한 번만 둔다.
   * 다른 10줄은 킷마다 다른 버튼과 입력칸이라 부르는 쪽이 만든다.
   *
   * **forum_kit 과 probe_generic 은 안 쓴다.** 껍데기 모양이 다르다.
   * probe_generic 은 버튼이 하나뿐이고 forum_kit 은 최소화 블록이 다르다.
   * 억지로 맞추면 둘 다 고쳐야 해서 그대로 둔다.
   *
   * BUSY 와 ABORT 는 모듈이 들고 있다. 껍데기는 넘겨받은 함수로만 만진다.
   * 모듈 본문의 수집 반복문이 ABORT 를 직접 읽기 때문이다. 그쪽은 안 건드린다.
   *
   *     const S = mkShell({
   *       busy: () => BUSY,
   *       setBusy: v => { BUSY = v; },
   *       setAbort: v => { ABORT = v; }
   *     });
   *     const say = S.say, put = S.put, mk = S.mk, inp = S.inp;
   *     ...버튼과 입력칸을 만든다...
   *     window.__XK = S.mount(b1, b2, wrap1);
   *
   * mount 는 넘긴 것들 뒤에 상태줄·중단·최소화·닫기를 붙이고 화면에 올린다.
   * 2026-08-25 다크초코 */
  function mkShell(o) {
    const box = document.createElement('div');
    box.style.cssText = 'position:fixed;inset:4%;z-index:2147483647;background:#111;color:#eee;border:2px solid #666;padding:8px;display:flex;flex-direction:column;gap:6px;font:13px sans-serif';
    const bar = document.createElement('div');
    bar.style.cssText = 'display:flex;gap:6px;align-items:center;flex-wrap:wrap';
    const st = document.createElement('span');
    st.style.cssText = 'flex:1;min-width:' + (o.minw || 220) + 'px;color:#0f0;font:12px monospace';
    const ta = document.createElement('textarea');
    ta.style.cssText = 'flex:1;width:100%;background:#000;color:#0f0;font:12px monospace;border:1px solid #444';

    const say = s => { st.textContent = s; };
    const put = s => { ta.value = s; ta.focus(); ta.select(); };

    /* 버튼 공장. 누르면 fn 을 돌리고 결과를 출력칸에 넣는다.
       돌고 있는 중에 또 누르는 것을 막는다. 요청이 겹치면 계정이 막힌다. */
    const mk = (label, fn, hot) => {
      const b = document.createElement('button');
      b.textContent = label;
      b.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;' + (hot ? 'background:#0a4;color:#fff;border:1px solid #0f8;font-weight:bold' : 'background:#333;color:#ddd;border:1px solid #555');
      b.onclick = async () => {
        if (o.busy()) { say('실행 중이다. 끝나거나 중단한 뒤에 누를 것'); return; }
        o.setBusy(true); o.setAbort(false);
        try { const r = await fn(); put(r.md); say(r.status + ' · Ctrl+C'); }
        catch (e) { say('오류 : ' + e); put('오류\n\n' + (e && e.stack || e)); }
        o.setBusy(false);
      };
      return b;
    };

    /* 입력칸 공장. 만든 것의 __i 가 진짜 input 이다. */
    const inp = (label, val, size) => {
      const l = document.createElement('label');
      l.style.cssText = 'display:flex;gap:3px;align-items:center;font:12px sans-serif;color:#aaa';
      const i = document.createElement('input');
      i.value = val; i.size = size;
      i.style.cssText = 'background:#000;color:#0f0;border:1px solid #444;font:12px monospace;width:' + (9 * size) + 'px';
      l.append(document.createTextNode(label), i);
      l.__i = i;
      return l;
    };

    const stopB = document.createElement('button');
    stopB.textContent = '중단';
    stopB.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;background:#422;color:#fdd;border:1px solid #855';
    stopB.onclick = () => { o.setAbort(true); say('중단 요청. 현재 요청이 끝나면 멈춘다'); };

    const closeB = document.createElement('button');
    closeB.textContent = '닫기';
    closeB.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;background:#422;color:#fdd;border:1px solid #855';
    closeB.onclick = () => box.remove();

    /* 최소화. 접어도 상태와 중단은 남긴다.
       걸어다니는 중에 아래 페이지를 보면서 진행을 확인할 때 쓴다. */
    let MINI = false;
    const miniB = document.createElement('button');
    miniB.textContent = '최소화';
    miniB.setAttribute('data-mini', '1');
    miniB.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;background:#333;color:#ddd;border:1px solid #555';
    const KEEP = [st, miniB, stopB, closeB];
    miniB.onclick = () => {
      MINI = !MINI;
      box.style.inset = MINI ? 'auto 10px 10px auto' : '4%';
      box.style.maxWidth = MINI ? '52vw' : '';
      ta.style.display = MINI ? 'none' : '';
      [...bar.children].forEach(c => { c.style.display = (MINI && KEEP.indexOf(c) < 0) ? 'none' : ''; });
      miniB.textContent = MINI ? '펼치기' : '최소화';
    };

    const mount = (...items) => {
      bar.append(...items, st, stopB, miniB, closeB);
      box.append(bar, ta);
      document.body.appendChild(box);
      return box;
    };

    return { box: box, bar: bar, st: st, ta: ta, say: say, put: put,
             mk: mk, inp: inp, stopB: stopB, miniB: miniB, closeB: closeB,
             mount: mount };
  }


  /* ── forum_kit.js ── */
  function modForum() {

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
        BUSY = true; ABORT = false;
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
  /* 켜면 하위 게시판까지 들어가서 목록을 모아 온다. 요청이 늘어나니 기본은 꺼둔다 */
    const cSubs = chk('하위 게시판도', true, '켜면 하위 게시판에 각각 들어가 목록을 모아 온다. 요청이 늘어난다');
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
              if (!r.ok) break;
              const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
              pickScope(doc).els.forEach(e => grab(e, tag, base));
            } catch (e) { break; }
          }
          const got = targets.length - before;
          say(`목록 모으는 중 · ${tag || '이 게시판'} ${pg}쪽 · 새로 ${got}건 · 목록 누적 ${targets.length}건`);
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
  /* 네트워크를 쓰지 않는 것만 자동으로 돌린다. 본문 수집은 버튼을 눌러야 시작한다 */
    (KIND === 'index' ? bTree : KIND === 'list' ? bList : KIND === 'page' ? bPage : bDiag).click();

  }

  /* ── qilin_kit.js ── */
  function modQilin() {

    const VER = 'qilin kit v1';
    if (window.__QK) { try { window.__QK.remove(); } catch (e) {} window.__QK = null; }

    const T = e => (e ? (e.innerText || e.textContent || '') : '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim();
    const HREF = a => (a && a.getAttribute('href')) || '';
    const TODAY = new Date().toISOString().slice(0, 10);
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const CHAL = /cf[-_]chl|cf_chl_opt|Just a moment|Checking your browser|__cf_chl|Attention Required/i;

    const CLUE = {
      onion: /\b[a-z2-7]{16,56}\.onion\b/g,
      tg: /(?:t\.me|telegram\.me)\/[\w+\-\/]+/g,
      btc: /\b(bc1[a-z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b/g,
      xmr: /\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b/g,
      email: /([\w.+-]{1,64})@([\w-]+\.[\w.]{2,})/g,
      host: /\b(?:gofile\.io|mega\.nz|anonfiles?\w*\.com|file\.io|pixeldrain\.com|mediafire\.com|dropbox\.com|qu\.ax)\S*/g,
      size: /\b\d+(?:\.\d+)?\s?(?:GB|TB|MB)\b/gi,
      rows: /\b\d{1,3}(?:,\d{3})+\b/g
    };
    const clues = {};
    const grab = txt => {
      for (const k of Object.keys(CLUE)) {
        const hit = txt.match(CLUE[k]) || [];
        if (hit.length) { clues[k] = clues[k] || new Set(); hit.forEach(v => clues[k].add(v)); }
      }
    };

    const cardsOf = doc => [...doc.querySelectorAll('div[data-key], .item_box')]
      .map(el => (el.classList && el.classList.contains('item_box')) ? (el.closest('[data-key]') || el) : el)
      .filter((el, i, all) => all.indexOf(el) === i);

    const parseCard = el => {
      const uuidA = [...el.querySelectorAll('a[href*="uuid="]')][0];
      const slugA = [...el.querySelectorAll('a[href^="/c/"]')][0];
      const titleA = el.querySelector('.item_box-title') || uuidA;
      const links = [...el.querySelectorAll('a[href]')];
      const zoom = links.find(a => /zoominfo\.com/i.test(HREF(a)));
      const site = links.find(a => /^https?:\/\//i.test(HREF(a)) && !/zoominfo\.com/i.test(HREF(a)));
      const txt = T(el);
      const dateEl = [...el.querySelectorAll('div,span,p')].find(d => d.querySelector('img[src*="clock"]'));
      const dm = (dateEl ? T(dateEl) : txt).match(/\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b/i);
      const pm = txt.match(/(\d+)\s*photos?/i);
      const sector = T(el.querySelector('p.item_box-info'));
      const uuid = (HREF(uuidA).match(/uuid=([0-9a-f-]{8,})/i) || [])[1] || '';
      const slugM = HREF(slugA).match(/^\/c\/([^\/]+)\/(\d+)/);
      return {
        key: el.getAttribute('data-key') || '',
        name: T(titleA),
        sector: sector,
        uuid: uuid,
        slug: slugM ? slugM[1] : '',
        slugN: slugM ? slugM[2] : '',
        site: site ? HREF(site) : '',
        zoom: zoom ? HREF(zoom) : '',
        date: dm ? dm[0] : '',
        photos: pm ? parseInt(pm[1], 10) : null,
        detail: uuid ? '/site/blog?uuid=' + uuid : HREF(slugA)
      };
    };

    const norm = s => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '');

    const dupReport = rows => {
      const out = [];
      const byName = new Map();
      const bySlug = new Map();
      rows.forEach(r => {
        const n = norm(r.name);
        if (n) { byName.set(n, (byName.get(n) || []).concat([r])); }
        if (r.slug) { bySlug.set(r.slug, (bySlug.get(r.slug) || []).concat([r])); }
      });
      const sameName = [...byName.values()].filter(v => v.length > 1);
      const sameSlug = [...bySlug.values()].filter(v => v.length > 1);
      out.push('## 중복 검사');
      out.push('');
      if (!sameName.length && !sameSlug.length) {
        out.push('같은 조직이 두 번 이상 올라온 건이 없다. 이번 범위 안에서만 그렇다.');
        out.push('');
        return out.join('\n');
      }
      sameName.forEach(g => {
        out.push('- 같은 이름 ' + g.length + '건 : ' + g[0].name);
        g.forEach(r => out.push('    ' + (r.date || '날짜없음') + '  uuid=' + (r.uuid || '없음') + '  slug=' + (r.slug || '없음') + (r.slugN ? '/' + r.slugN : '')));
        const u = new Set(g.map(r => r.uuid).filter(Boolean));
        const d = new Set(g.map(r => r.date).filter(Boolean));
        out.push('    판정 : ' + (u.size > 1 ? (d.size > 1 ? '재게시 후보. uuid 도 날짜도 다름' : 'uuid 만 다름. 같은 날') : '같은 uuid. 주소만 여럿'));
      });
      sameSlug.forEach(g => {
        const ns = new Set(g.map(r => r.slugN));
        if (ns.size > 1) { out.push('- 같은 slug 에 번호가 여럿 : ' + g[0].slug + ' -> ' + [...ns].join(', ')); }
      });
      out.push('');
      return out.join('\n');
    };

    const render = (rows, meta) => {
      const L = [];
      L.push('# 킬린 유출 사이트 수집');
      L.push('');
      L.push('- 도구 : ' + VER);
      L.push('- URL : ' + location.href);
      L.push('- 확인 : ' + TODAY + (NAME.value ? ' ' + NAME.value : ''));
      L.push('- ' + meta);
      L.push('- 피해자 ' + rows.length + '건');
      L.push('');
      L.push(dupReport(rows));
      L.push('## 증거가 붙은 건');
      L.push('');
      const withPhoto = rows.filter(r => r.photos > 0);
      if (withPhoto.length) {
        withPhoto.forEach(r => L.push('- ' + r.name + '  ' + r.photos + ' photos  ' + r.detail));
        L.push('');
        L.push('photos 가 파일 목록 캡처면 트리 분석 재료다. 상세를 열어 확인할 것.');
      } else {
        L.push('없음. 이번 범위의 건은 전부 주장뿐이다.');
      }
      L.push('');
      const noSite = rows.filter(r => !r.site).length;
      L.push('## 대상 특정');
      L.push('');
      L.push('- 공식 URL 있음 : ' + (rows.length - noSite) + ' / ' + rows.length);
      L.push('- ZoomInfo 있음 : ' + rows.filter(r => r.zoom).length + ' / ' + rows.length);
      L.push('');
      L.push('공격자가 공식 도메인을 직접 적어준다. 2단계 대상 문자열 일치에 그대로 쓴다.');
      L.push('');
      const ck = Object.keys(clues);
      if (ck.length) {
        L.push('## 추출된 단서');
        L.push('');
        ck.forEach(k => L.push('- ' + k + ' (' + clues[k].size + ') : ' + [...clues[k]].slice(0, 12).join(' · ')));
        L.push('');
      }
      L.push('---- TSV (조직 · 업종 · 날짜 · photos · uuid · slug · 공식URL · ZoomInfo · 상세) ----');
      rows.forEach(r => L.push([r.name, r.sector, r.date, r.photos == null ? '' : r.photos, r.uuid, r.slug + (r.slugN ? '/' + r.slugN : ''), r.site, r.zoom, r.detail].join('\t')));
      return L.join('\n');
    };

    const detail = () => {
      const L = [];
      const body = T(document.body);
      grab(body);
      L.push('# 킬린 상세');
      L.push('');
      L.push('- 도구 : ' + VER);
      L.push('- URL : ' + location.href);
      L.push('- TITLE : ' + document.title);
      L.push('- 확인 : ' + TODAY + (NAME.value ? ' ' + NAME.value : ''));
      L.push('');
      const imgs = [...document.querySelectorAll('img')].map(i => i.getAttribute('src') || '').filter(s => /\/uploads\//.test(s));
      L.push('## 올라온 이미지 ' + imgs.length + '개');
      L.push('');
      imgs.slice(0, 40).forEach(s => L.push('- ' + s));
      L.push('');
      L.push('이미지는 내려받지 않는다. 주소만 기록한다.');
      L.push('');
      const dl = [...document.querySelectorAll('a[href]')].map(a => HREF(a)).filter(h => /\.(zip|rar|7z|tar|gz)(\?|$)|gofile|mega\.nz|torrent/i.test(h));
      L.push('## 다운로드로 보이는 링크 ' + dl.length + '개');
      L.push('');
      L.push(dl.length ? dl.map(h => '- ' + h).join('\n') : '없음');
      L.push('');
      L.push('링크는 존재만 기록한다. 받지 않는다.');
      L.push('');
      const ck = Object.keys(clues);
      if (ck.length) {
        L.push('## 추출된 단서');
        L.push('');
        ck.forEach(k => L.push('- ' + k + ' (' + clues[k].size + ') : ' + [...clues[k]].slice(0, 20).join(' · ')));
        L.push('');
      }
      L.push('## 본문');
      L.push('');
      L.push('```');
      L.push(body.slice(0, 6000));
      L.push('```');
      return { md: L.join('\n'), status: '상세 · 이미지 ' + imgs.length + ' · 단서 ' + ck.length + '종' };
    };

    const looksPath = s => {
      if (!s || s.length > 240) { return false; }
      if (/^https?:\/\//i.test(s)) { return false; }
      if (/\s{2,}/.test(s)) { return false; }
      return /\.[A-Za-z0-9]{1,6}$/.test(s) || /[\\\/]/.test(s);
    };

    const tree = () => {
      const L = [];
      const hits = [];
      const seen = new Set();
      const push = (p, how) => {
        const v = p.replace(/^\.?[\\\/]+/, '').trim();
        if (!v || seen.has(v)) { return; }
        seen.add(v);
        hits.push({ p: v, how: how });
      };
      [...document.querySelectorAll('body *')].forEach(el => {
        if (el.children.length) { return; }
        const t = T(el);
        if (looksPath(t)) { push(t, el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/)[0] : '')); }
      });
      [...document.querySelectorAll('a[href]')].forEach(a => {
        const h = HREF(a);
        const m = h.match(/[?&](?:path|file|f|p)=([^&]+)/i);
        if (m) { try { push(decodeURIComponent(m[1]), 'href 질의'); } catch (e) { push(m[1], 'href 질의'); } }
      });
      const byHow = {};
      hits.forEach(h => { byHow[h.how] = (byHow[h.how] || 0) + 1; });
      L.push('# 파일 목록 뽑기');
      L.push('');
      L.push('- 도구 : ' + VER);
      L.push('- URL : ' + location.href);
      L.push('- 확인 : ' + TODAY + (NAME.value ? ' ' + NAME.value : ''));
      L.push('- 경로로 보이는 것 ' + hits.length + '건');
      L.push('');
      if (!hits.length) {
        L.push('경로가 안 잡혔다. 아래 중 하나다.');
        L.push('');
        L.push('- 파일 목록이 이미지다. 화면을 캡처해서 사람이 읽어야 한다');
        L.push('- 자바스크립트로 나중에 그린다. 다 뜬 뒤 다시 누른다');
        L.push('- 구조가 예상과 다르다. probe_generic 을 돌려 화면을 공유할 것');
        L.push('');
        const imgs = [...document.querySelectorAll('img')].map(i => i.getAttribute('src') || '').filter(Boolean);
        L.push('## 이 화면의 이미지 ' + imgs.length + '개');
        L.push('');
        imgs.slice(0, 30).forEach(s => L.push('- ' + s));
        return { md: L.join('\n'), status: '경로 0건 · 이미지 ' + imgs.length + '개' };
      }
      L.push('## 어디서 나왔나');
      L.push('');
      Object.keys(byHow).sort((a, b) => byHow[b] - byHow[a]).slice(0, 8).forEach(k => L.push('- ' + byHow[k] + '건  ' + k));
      L.push('');
      L.push('한 갈래만 진짜 목록일 수 있다. 아래 경로를 보고 아닌 갈래는 지울 것.');
      L.push('');
      L.push('## tree_scan.py 에 넣을 것');
      L.push('');
      L.push('```');
      hits.forEach(h => L.push(h.p));
      L.push('```');
      L.push('');
      L.push('위 블록만 파일로 저장한 뒤 아래를 돈다.');
      L.push('');
      L.push('    python 06_도구/tools/tree_scan.py <파일> --md 출력.md');
      return { md: L.join('\n'), status: '경로 ' + hits.length + '건 · 갈래 ' + Object.keys(byHow).length };
    };

    const listHere = () => {
      const rows = cardsOf(document).map(parseCard).filter(r => r.name);
      grab(T(document.body));
      return { md: render(rows, '이 쪽만'), status: '목록 ' + rows.length + '건 (이 쪽만)', rows: rows };
    };

    const listAll = async () => {
      const want = Math.max(1, parseInt(MAXP.value, 10) || 3);
      const seen = new Set();
      let rows = cardsOf(document).map(parseCard).filter(r => r.name);
      rows.forEach(r => seen.add(r.uuid || r.name));
      grab(T(document.body));
      let stopped = '';
      for (let p = 2; p <= want; p++) {
        if (ABORT) { stopped = '사용자 중단'; break; }
        say('여러 쪽 모으는 중 ' + p + '/' + want + ' · 누적 ' + rows.length + '건');
        await sleep(2500 + Math.random() * 2500);
        try {
          const res = await fetch('/?page=' + p, { credentials: 'same-origin' });
          const txt = await res.text();
          if (CHAL.test(txt.slice(0, 6000))) { stopped = 'Cloudflare 챌린지. 즉시 멈춤'; break; }
          if (res.status === 429 || res.status === 503) { stopped = 'HTTP ' + res.status + ' 레이트리밋 의심. 즉시 멈춤'; break; }
          if (!res.ok) { stopped = 'HTTP ' + res.status; break; }
          const doc = new DOMParser().parseFromString(txt, 'text/html');
          const got = cardsOf(doc).map(parseCard).filter(r => r.name);
          if (!got.length) { stopped = p + '쪽에서 카드 0건. 마지막 쪽으로 본다'; break; }
          got.forEach(r => { const k = r.uuid || r.name; if (!seen.has(k)) { seen.add(k); rows.push(r); } });
          grab(T(doc.body));
        } catch (e) { stopped = '요청 실패 ' + e; break; }
      }
      return { md: render(rows, '여러 쪽' + (stopped ? ' · 중단 : ' + stopped : ' · ' + want + '쪽까지')), status: '목록 ' + rows.length + '건' + (stopped ? ' · ' + stopped : ''), rows: rows };
    };

    let ABORT = false, BUSY = false;
  
    const S = mkShell({ busy: () => BUSY, setBusy: v => { BUSY = v; }, setAbort: v => { ABORT = v; }, minw: 200 });
    const box = S.box, st = S.st, ta = S.ta;
    const say = S.say, put = S.put, mk = S.mk, inp = S.inp;


    const maxWrap = inp('몇 쪽까지', '3', 3);
    const nameWrap = inp('확인자', '', 7);
    const MAXP = maxWrap.__i;
    const NAME = nameWrap.__i;



    const isDetail = /\/site\/blog\?uuid=|\/c\/[^\/]+\/\d+/.test(location.href);
    const bList = mk('이 페이지만', listHere, !isDetail);
    const bAll = mk('전체 수집', listAll, false);
    const bDetail = mk('이 건 상세', async () => detail(), isDetail);
    const bTree = mk('파일 목록 뽑기', async () => tree(), false);


    /* ── 최소화. 접어도 상태와 중단은 남긴다 ────── */



    window.__QK = S.mount(bList, bAll, bDetail, bTree, maxWrap, nameWrap);

    say(VER + ' · ' + (isDetail ? '상세 페이지로 판정' : '목록 페이지로 판정') + ' · 카드 ' + cardsOf(document).length + '개');
    ta.value = '실행 중';
    (isDetail ? bDetail : bList).click();

  }

  /* ── index_kit.js ── */
  function modIndex() {

    const VER = 'index kit v1';
    if (window.__IK) { try { window.__IK.remove(); } catch (e) {} window.__IK = null; }

    const T = e => (e ? (e.innerText || e.textContent || '') : '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim();
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const GAP = 3.75;   /* 요청 간격 2.5~5초의 가운데. 시간 어림에 쓴다 */
    const dur = s => {
      s = Math.max(0, Math.round(s));
      if (s >= 3600) return Math.floor(s / 3600) + '시간 ' + Math.round((s % 3600) / 60) + '분';
      if (s >= 60) return Math.floor(s / 60) + '분 ' + (s % 60) + '초';
      return s + '초';
    };
    const CHAL = /cf[-_]chl|cf_chl_opt|Just a moment|Checking your browser|__cf_chl|Attention Required/i;
    const MONTH = { Jan: '01', Feb: '02', Mar: '03', Apr: '04', May: '05', Jun: '06',
                    Jul: '07', Aug: '08', Sep: '09', Oct: '10', Nov: '11', Dec: '12' };

    /* 시작 자리. 이 아래로만 걸어다닌다 */
    const ROOT = new URL(location.href.split('?')[0].split('#')[0]);
    if (!ROOT.pathname.endsWith('/')) ROOT.pathname += '/';
    const BASE = ROOT.origin + ROOT.pathname;
    const LABEL = (ROOT.pathname.replace(/\/+$/, '').split('/').pop()) || ROOT.hostname;

    /* ── 크기와 날짜 다듬기 ───────────────────────── */
    const bytesOf = s => {
      const m = /^([\d.]+)\s*([KMGT])?B?$/i.exec((s || '').trim());
      if (!m) return null;
      const n = parseFloat(m[1]);
      const p = { K: 1024, M: 1048576, G: 1073741824, T: 1099511627776 }[(m[2] || '').toUpperCase()];
      return Math.round(p ? n * p : n);
    };
    const dateOf = s => {
      let m = /(\d{2})-([A-Za-z]{3})-(\d{4})\s+(\d{2}:\d{2})/.exec(s || '');   /* nginx */
      if (m) return m[3] + '-' + (MONTH[m[2]] || '00') + '-' + m[1] + ' ' + m[4];
      m = /(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})/.exec(s || '');   /* Apache */
      if (m) return m[1] + ' ' + m[2];
      return '';
    };

    /* ── 인덱스 한 장 읽기 ────────────────────────── */
    const SKIP = /^(\.\.\/?|\/|\?|#)/;
    const parse = (doc, pageUrl) => {
      const out = [];
      const seen = new Set();
      const add = (a, tail, cells) => {
        const raw = a.getAttribute('href') || '';
        if (!raw || SKIP.test(raw) || /^[a-z]+:/i.test(raw) && !/^https?:/i.test(raw)) return;
        if (/[?&]C=[NMSD]|[?&]O=[AD]/.test(raw)) return;   /* Apache 정렬 링크 */
        let u;
        try { u = new URL(raw, pageUrl); } catch (e) { return; }
        if (u.origin !== ROOT.origin) return;
        const full = u.origin + u.pathname;
        if (!full.startsWith(BASE)) return;   /* 위로 올라가지 않는다 */
        if (full === pageUrl || seen.has(full)) return;
        seen.add(full);
        const isDir = u.pathname.endsWith('/');
        let sizeTxt = '', dateTxt = '';
        if (cells) {   /* Apache 표 */
          dateTxt = dateOf(cells[0] || '');
          sizeTxt = (cells[1] || '').trim();
        } else {   /* nginx pre */
          dateTxt = dateOf(tail);
          const m = /(\d[\d.]*\s*[KMGT]?)\s*$/i.exec(tail.replace(/\s+-\s*$/, ''));
          sizeTxt = isDir ? '' : (m ? m[1].trim() : '');
        }
        out.push({
          url: full,
          rel: decodeURIComponent(full.slice(BASE.length)),
          isDir: isDir,
          sizeTxt: isDir ? '' : sizeTxt,
          bytes: isDir ? null : bytesOf(sizeTxt),
          date: dateTxt
        });
      };

      /* Apache 표 먼저 */
      const trs = [...doc.querySelectorAll('table tr')].filter(tr => tr.querySelector('a[href]'));
      if (trs.length) {
        trs.forEach(tr => {
          const tds = [...tr.querySelectorAll('td')].map(T);
          const a = tr.querySelector('a[href]');
          add(a, '', tds.slice(1));
        });
        if (out.length) return out;
      }

      /* nginx pre. 링크 뒤에 오는 글자를 크기와 날짜로 읽는다 */
      const pres = doc.querySelectorAll('pre');
      const scope = pres.length ? pres : [doc.body || doc];
      scope.forEach(pre => {
        const as = [...pre.querySelectorAll('a[href]')];
        as.forEach(a => {
          let tail = '', n = a.nextSibling;
          while (n && !(n.nodeType === 1 && n.tagName === 'A')) {
            tail += n.textContent || '';
            n = n.nextSibling;
          }
          add(a, tail.split('\n')[0] || tail, null);
        });
      });
      return out;
    };

    /* ── 걸어다니기. 디렉터리만 요청한다 ──────────── */
    let ABORT = false, BUSY = false;
    let RESULT = [], STOPPED = '', WALKED = 0, UNOPENED = [], T0 = 0, TOOK = 0;

    const fetchDir = async url => {
      if (!url.endsWith('/')) throw new Error('디렉터리가 아닌 주소는 요청하지 않는다: ' + url);
      const r = await fetch(url, { credentials: 'include' });
      const html = await r.text();
      if (r.status === 403) throw new Error('403. 등급 제한이거나 막혔다');
      if (r.status === 429 || r.status === 503) throw new Error(r.status + '. 즉시 중단한다');
      if (CHAL.test(html)) throw new Error('Cloudflare 확인 화면. 즉시 중단한다');
      if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
      return new DOMParser().parseFromString(html, 'text/html');
    };

    const walk = async (maxDepth, maxReq) => {
      RESULT = []; STOPPED = ''; WALKED = 0; UNOPENED = []; T0 = Date.now(); TOOK = 0;
      const seen = new Set([BASE]);
      const queue = [{ url: BASE, depth: 0 }];
      while (queue.length) {
        if (ABORT) { STOPPED = '사용자 중단'; break; }
        if (WALKED >= maxReq) { STOPPED = '요청 상한 ' + maxReq + ' 도달'; break; }
        const cur = queue.shift();
        let doc;
        try {
          doc = cur.depth === 0 ? document : await fetchDir(cur.url);
          if (cur.depth > 0) { WALKED++; await sleep(2500 + Math.random() * 2500); }
        } catch (e) {
          RESULT.push({ url: cur.url, rel: decodeURIComponent(cur.url.slice(BASE.length)),
                        isDir: true, sizeTxt: '', bytes: null, date: '', err: String(e.message || e) });
          STOPPED = '조회 실패로 중단 : ' + (e.message || e);
          break;
        }
        const rows = parse(doc, cur.url);
        rows.forEach(r => {
          RESULT.push(r);
          if (!r.isDir || seen.has(r.url)) return;
          if (cur.depth + 1 > maxDepth) {
            /* 깊이 상한이다. 있는 줄은 알지만 안을 못 봤다. 반드시 적는다 */
            UNOPENED.push({ rel: r.rel, why: '깊이 상한 ' + maxDepth });
            return;
          }
          seen.add(r.url);
          queue.push({ url: r.url, depth: cur.depth + 1 });
        });
        say('걸어다니는 중 · 요청 ' + WALKED + ' · 모은 것 ' + RESULT.length
            + ' · 남은 폴더 ' + queue.length
            + ' · 지난 ' + dur((Date.now() - T0) / 1000)
            + ' · 최소 ' + dur(queue.length * GAP) + ' 더'
            + (UNOPENED.length ? ' · 안 열어본 ' + UNOPENED.length : ''));
      }
      TOOK = (Date.now() - T0) / 1000;
      /* 멈춰서 큐에 남은 것도 안 열어본 것이다 */
      queue.forEach(q => UNOPENED.push({
        rel: decodeURIComponent(q.url.slice(BASE.length)),
        why: STOPPED || '멈춤'
      }));
      return sum();
    };

    const depthOf = rel => rel.replace(/\/+$/, '').split('/').filter(Boolean).length;
    const deepest = () => RESULT.reduce((a, r) => Math.max(a, depthOf(r.rel)), 0);

    const brief = () => {
      const dirs = RESULT.filter(r => r.isDir).length;
      const bytes = RESULT.reduce((a, r) => a + (r.bytes || 0), 0);
      return '폴더 ' + dirs + ' · 파일 ' + (RESULT.length - dirs)
           + ' · 어림 ' + (bytes / 1048576).toFixed(1) + 'MB'
           + ' · 깊이 ' + deepest() + ' · 요청 ' + WALKED
           + (TOOK ? ' · ' + dur(TOOK) + ' 걸림' : '')
           + (UNOPENED.length ? ' · 안 열어본 폴더 ' + UNOPENED.length + '. 이 숫자는 일부다'
                              : ' · 다 봤다. 깊이가 전체 깊이다')
           + (STOPPED ? ' · ' + STOPPED : '');
    };

    const sum = () => ({ md: paths(), status: brief() });

    /* ── 내보내기 둘. 네트워크를 안 쓴다 ──────────── */
    const paths = () => {
      if (!RESULT.length) return '모은 것이 없다. 먼저 초동분석이나 전체 수집을 누른다';
      /* 맨 앞 # 줄은 tree_scan 이 건너뛴다. 사람이 보라고 붙인다 */
      const L = ['# ' + brief(),
                 '# 수집 ' + new Date().toISOString().slice(0, 16).replace('T', ' ') + ' · ' + BASE];
      UNOPENED.slice(0, 40).forEach(u => L.push('# 안 열어봄  ' + LABEL + '/' + u.rel + '   (' + u.why + ')'));
      if (UNOPENED.length > 40) L.push('# 안 열어본 폴더 ' + (UNOPENED.length - 40) + '개 더 있다. 전체는 크기·날짜 표에');
      L.push('');
      return L.concat(RESULT.map(r => LABEL + '/' + r.rel).sort()).join('\n');
    };
    const tsv = () => {
      if (!RESULT.length) return '모은 것이 없다. 먼저 초동분석이나 전체 수집을 누른다';
      const L = ['경로\t종류\t크기표기\t바이트어림\t날짜'];
      RESULT.slice().sort((a, b) => a.rel.localeCompare(b.rel)).forEach(r => {
        L.push([LABEL + '/' + r.rel, r.isDir ? '폴더' : '파일',
                r.sizeTxt || '', r.bytes == null ? '' : r.bytes, r.date || ''].join('\t'));
      });
      const bytes = RESULT.reduce((a, r) => a + (r.bytes || 0), 0);
      L.push('');
      L.push('# 어림 합계 ' + bytes.toLocaleString() + ' 바이트');
      L.push('# 크기는 서버가 반올림한 값이다. 정확한 바이트가 아니다');
      L.push('# 본 깊이 ' + deepest());
      if (TOOK) L.push('# 걸린 시간 ' + dur(TOOK) + ' · 요청 ' + WALKED + '회');
      if (UNOPENED.length) L.push('# 남은 것을 다 보려면 최소 ' + dur(UNOPENED.length * GAP) + ' 더 든다');
      if (UNOPENED.length) {
        L.push('# 안 열어본 폴더 ' + UNOPENED.length + '. 위 숫자는 일부다');
        L.push('# 아래 주소에서 다시 눌러 이어서 걸어다닌다');
        UNOPENED.forEach(u => L.push('#   ' + LABEL + '/' + u.rel + '   (' + u.why + ')'));
      } else {
        L.push('# 안 열어본 폴더 없음. 전체를 다 봤고 위 깊이가 전체 깊이다');
      }
      L.push('# 수집 ' + new Date().toISOString().slice(0, 16).replace('T', ' ') + ' · ' + BASE);
      if (STOPPED) L.push('# ' + STOPPED);
      return L.join('\n');
    };

    /* ── 화면 ─────────────────────────────────────── */
  
    const S = mkShell({ busy: () => BUSY, setBusy: v => { BUSY = v; }, setAbort: v => { ABORT = v; } });
    const box = S.box, st = S.st, ta = S.ta;
    const say = S.say, put = S.put, mk = S.mk, inp = S.inp;


    const dWrap = inp('깊이', '8', 2);
    const rWrap = inp('요청상한', '200', 4);

    const runWalk = () => walk(Math.max(1, parseInt(dWrap.__i.value, 10) || 8),
                               Math.max(1, parseInt(rWrap.__i.value, 10) || 200));

    /* 초동분석. 요청 수만 묶는다. 너비 우선이라 위쪽 층이 통째로 남는다 */
    const bQuick = mk('초동분석  3분', async () => {
      dWrap.__i.value = '8';
      rWrap.__i.value = '50';
      return runWalk();
    }, true);
    const bWalk = mk('전체 수집', async () => runWalk(), false);
    const bHere = mk('이 폴더만', async () => {
      RESULT = parse(document, BASE); STOPPED = ''; WALKED = 0; UNOPENED = []; TOOK = 0;
      return sum();
    }, false);
    const bPaths = mk('경로 목록', async () => ({ md: paths(), status: 'tree_scan 에 그대로 넣는다' }), false);
    const bTsv = mk('크기·날짜 표', async () => ({ md: tsv(), status: '표 ' + RESULT.length + '줄' }), false);





    /* ── 최소화. 접어도 상태와 중단은 남긴다 ────── */



    window.__IK = S.mount(bQuick, bWalk, bHere, bPaths, bTsv, dWrap, rWrap);

    const n = parse(document, BASE);
    const nd = n.filter(r => r.isDir).length;
    say(VER + ' · ' + LABEL + ' · 이 쪽에 ' + nd + '폴더 '
        + n.filter(r => !r.isDir).length + '파일'
        + (nd ? ' · 깊이 1만 돌아도 최소 ' + dur(nd * GAP) : '')
        + ' · 처음이면 초동분석부터');

  }

  /* ── photo_kit.js ── */
  function modPhoto() {

    const VER = 'photo kit v1';
    if (window.__PK) { try { window.__PK.remove(); } catch (e) {} window.__PK = null; }

    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const CHAL = /cf[-_]chl|cf_chl_opt|Just a moment|Checking your browser|__cf_chl|Attention Required/i;
    const GAP = 3.75;
    const dur = s => {
      s = Math.max(0, Math.round(s));
      if (s >= 60) return Math.floor(s / 60) + '분 ' + (s % 60) + '초';
      return s + '초';
    };

    let ABORT = false, BUSY = false, FOUND = [], GOT = 0, FAIL = [], SIZES = [];
    const kb = n => n >= 1048576 ? (n / 1048576).toFixed(1) + 'MB' : Math.round(n / 1024) + 'KB';

    /* ── 사진 주소 모으기. 네트워크를 안 쓴다 ────── */
    const pick = () => {
      const pat = (patW.__i.value || '').trim();
      const re = pat ? new RegExp(pat, 'i') : /\/uploads?\//i;
      const seen = new Set();
      const out = [];
      document.querySelectorAll('img[src]').forEach(im => {
        const raw = im.getAttribute('src') || '';
        if (!raw || !re.test(raw)) return;
        let u;
        try { u = new URL(raw, location.href).href; } catch (e) { return; }
        if (seen.has(u)) return;
        seen.add(u);
        const r = im.getBoundingClientRect();
        out.push({ url: u, w: im.naturalWidth || 0, h: im.naturalHeight || 0,
                   보임: r.width > 0 && r.height > 0 });
      });
      return out;
    };

    /* 주소 바꾸기. 썸네일과 원본의 규칙이 다를 때 쓴다 */
    const swap = u => {
      const rule = (ruleW.__i.value || '').trim();
      if (!rule || rule.indexOf('->') < 0) return u;
      const [a, b] = rule.split('->').map(s => s.trim());
      return a ? u.split(a).join(b) : u;
    };

    const nameOf = (u, i) => {
      let base = '';
      try { base = decodeURIComponent(new URL(u).pathname.split('/').pop() || ''); } catch (e) {}
      if (!base || base.length > 60) base = 'shot';
      if (!/\.(png|jpe?g|gif|webp|bmp)$/i.test(base)) base += '.png';
      return String(i + 1).padStart(2, '0') + '_' + base;
    };

    const find = async () => {
      FOUND = pick();
      const L = ['# 증거 사진 ' + FOUND.length + '개 · 화면에 보이는 것 '
                 + FOUND.filter(f => f.보임).length,
                 '# ' + location.href,
                 '# 아직 아무것도 받지 않았다. 주소를 확인한 뒤 받기 를 누른다',
                 ''];
      FOUND.forEach((f, i) => L.push(nameOf(swap(f.url), i) + '\t' + swap(f.url)
                                     + (f.w ? '\t' + f.w + 'x' + f.h : '')));
      if (!FOUND.length) {
        L.push('못 찾았다. 주소 조각 칸에 /uploads/ 같은 것을 넣어보거나');
        L.push('접힌 사진이 있으면 먼저 펼친다');
      }
      return { md: L.join('\n'), status: '찾음 ' + FOUND.length + '개 · 아직 안 받았다' };
    };

    /* ── 원본 주소 확인. 썸네일을 한 번 눌러 본다 ── */
    const probe = async () => {
      const before = new Set(pick().map(f => f.url));
      const btn = document.querySelector('button img, a img, [role="button"] img');
      if (!btn) return { md: '누를 만한 썸네일을 못 찾았다', status: '실패' };
      (btn.closest('button, a, [role="button"]') || btn).click();
      await sleep(1200);
      const after = pick();
      const fresh = after.filter(f => !before.has(f.url));
      const big = after.filter(f => f.w >= 900).slice(0, 5);
      const L = ['# 썸네일을 한 번 눌러 본 결과', ''];
      L.push('## 새로 뜬 주소 ' + fresh.length + '개');
      fresh.slice(0, 8).forEach(f => L.push('- ' + f.url + '  ' + f.w + 'x' + f.h));
      L.push('');
      L.push('## 큰 이미지(가로 900 이상) ' + big.length + '개');
      big.forEach(f => L.push('- ' + f.url + '  ' + f.w + 'x' + f.h));
      L.push('');
      L.push('썸네일과 원본 주소가 다르면 **주소 바꾸기** 칸에 규칙을 넣는다.');
      L.push('예   /uploads/p/ -> /uploads/o/');
      L.push('같으면 비워 둔다. 창을 닫고 받기 를 누른다.');
      return { md: L.join('\n'), status: '새 주소 ' + fresh.length + ' · 큰 것 ' + big.length };
    };

    /* ── 받기. 여기만 네트워크를 쓴다 ───────────── */
    const grab = async () => {
      if (!FOUND.length) FOUND = pick();
      if (!FOUND.length) return { md: '받을 것이 없다. 찾기 를 먼저 누른다', status: '없음' };
      const cap = Math.max(1, parseInt(capW.__i.value, 10) || 20);
      const list = FOUND.slice(0, cap);
      GOT = 0; FAIL = []; SIZES = [];
      const T0 = Date.now();

      for (let i = 0; i < list.length; i++) {
        if (ABORT) break;
        const u = swap(list[i].url);
        const nm = nameOf(u, i);
        try {
          const r = await fetch(u, { credentials: 'include' });
          if (r.status === 403) throw new Error('403');
          if (r.status === 429 || r.status === 503) throw new Error(r.status + '. 즉시 중단');
          if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
          const ct = r.headers.get('content-type') || '';
          const blob = await r.blob();
          if (CHAL.test(await blob.slice(0, 2048).text().catch(() => ''))) throw new Error('Cloudflare 화면');
          if (!/^image\//i.test(ct) && blob.size < 200) throw new Error('이미지가 아니다 (' + ct + ')');
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = nm;
          document.body.appendChild(a);
          a.click();
          a.remove();
          setTimeout(() => URL.revokeObjectURL(a.href), 15000);
          SIZES.push({ nm: nm, size: blob.size });
          GOT++;
        } catch (e) {
          FAIL.push(nm + '  ' + (e.message || e));
          if (/429|503|Cloudflare/.test(String(e.message || e))) { ABORT = true; break; }
        }
        const left = list.length - i - 1;
        say('받는 중 ' + (i + 1) + '/' + list.length + ' · 성공 ' + GOT
            + (FAIL.length ? ' · 실패 ' + FAIL.length : '')
            + ' · 지난 ' + dur((Date.now() - T0) / 1000)
            + (left ? ' · 최소 ' + dur(left * GAP) + ' 더' : ''));
        if (left && !ABORT) await sleep(2500 + Math.random() * 2500);
      }

      const took = (Date.now() - T0) / 1000;
      const L = ['# 증거 사진 받기',
                 '# 찾은 것 ' + FOUND.length + ' · 상한 ' + cap + ' · 성공 ' + GOT
                 + ' · 실패 ' + FAIL.length + ' · ' + dur(took) + ' 걸림'
                 + (SIZES.length ? ' · 합계 ' + kb(SIZES.reduce((a, s) => a + s.size, 0))
                    + ' · 평균 ' + kb(SIZES.reduce((a, s) => a + s.size, 0) / SIZES.length) : '')
                 + (ABORT ? ' · 중단' : ''),
                 '# ' + location.href,
                 '# 받은 파일은 VM 안에 둔다. 케이스가 끝나면 지운다',
                 ''];
      if (FOUND.length > cap) {
        L.push('# 상한에 걸려 ' + (FOUND.length - cap) + '개를 안 받았다. 개수를 올리고 다시 누른다');
        L.push('');
      }
      const bySize = {};
      SIZES.forEach(s => { bySize[s.nm] = s.size; });
      list.slice(0, GOT + FAIL.length).forEach((f, i) => {
        const nm = nameOf(swap(f.url), i);
        L.push(nm + '\t' + (bySize[nm] == null ? '실패' : kb(bySize[nm])) + '\t' + swap(f.url));
      });
      const small = SIZES.filter(s => s.size < 30720);
      if (small.length) {
        L.push('');
        L.push('# 30KB 아래가 ' + small.length + '개다. 원본이 아니라 썸네일을 받았을 수 있다');
        L.push('# 원본 주소 확인 을 눌러 주소 규칙을 다시 본다');
      }
      if (FAIL.length) {
        L.push('');
        L.push('## 못 받은 것');
        FAIL.forEach(f => L.push('- ' + f));
      }
      return { md: L.join('\n'),
               status: '성공 ' + GOT + '/' + list.length + (FAIL.length ? ' · 실패 ' + FAIL.length : '')
                       + (SIZES.length ? ' · 합계 ' + kb(SIZES.reduce((a, s) => a + s.size, 0)) : '')
                       + ' · ' + dur(took) + (ABORT ? ' · 중단' : '') };
    };

    /* ── 화면 ─────────────────────────────────────── */
  
    const S = mkShell({ busy: () => BUSY, setBusy: v => { BUSY = v; }, setAbort: v => { ABORT = v; } });
    const box = S.box, st = S.st, ta = S.ta;
    const say = S.say, put = S.put, mk = S.mk, inp = S.inp;


    const capW = inp('몇 장', '20', 3);
    const patW = inp('주소 조각', '', 10);
    const ruleW = inp('주소 바꾸기', '', 16);

    const bFind = mk('찾기', find, true);
    const bProbe = mk('원본 주소 확인', probe, false);
    const bGrab = mk('받기', grab, false);

    /* ── 최소화. 접어도 상태와 중단은 남긴다 ────── */





    window.__PK = S.mount(bFind, bProbe, bGrab, capW, patW, ruleW);

    const n = pick();
    say(VER + ' · 이 쪽에 사진 ' + n.length + '개'
        + (n.length ? ' · 20장이면 최소 ' + dur(Math.min(n.length, 20) * GAP) : '')
        + ' · 찾기 부터');

  }

  /* ── probe_generic.js ── */
  function modProbe() {

    const out = [];
    const r = s => out.push(s);
    const txt = e => (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim();
    const sig = e => e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).slice(0, 3).join('.') : '');
    const chain = e => { const p = []; let n = e, i = 0; for (; n && n !== document.body && i < 6; i++) { p.push(sig(n)); n = n.parentElement; } return p.join(' < '); };
    const A = [...document.querySelectorAll('a[href]')];
    r('# 범용 구조 진단');
    r('- URL : ' + location.href);
    r('- TITLE : ' + document.title);
    r('- 확인 : ' + new Date().toISOString().slice(0, 10));
    r('- 링크 ' + A.length + '개 · 요소 ' + document.querySelectorAll('*').length + '개');
    r('');
    const shape = h => { try { return new URL(h, location.href).pathname.replace(/\/\d+/g, '/N').replace(/\/[0-9a-f]{16,}/gi, '/HEX').replace(/\/[^/]{20,}/g, '/LONG'); } catch (e) { return '?'; } };
    const cnt = new Map();
    A.forEach(a => { const s = shape(a.getAttribute('href')); cnt.set(s, (cnt.get(s) || 0) + 1); });
    r('## 링크 경로 모양 (많은 순 15)');
    [...cnt.entries()].sort((a, b) => b[1] - a[1]).slice(0, 15).forEach(([s, n]) => r('- ' + n + '회  ' + s));
    r('');
    const bag = new Map();
    [...document.querySelectorAll('body *')].forEach(e => { const p = e.parentElement; if (!p) return; const m = bag.get(p) || new Map(); const k = sig(e); m.set(k, (m.get(k) || 0) + 1); bag.set(p, m); });
    const cands = [...bag.entries()].map(([p, m]) => { const top = [...m.entries()].sort((a, b) => b[1] - a[1])[0]; return { p: p, s: top[0], n: top[1] }; }).filter(x => x.n >= 3).sort((a, b) => b.n - a.n).slice(0, 6);
    r('## 반복 블록 후보 (같은 모양 자식 3개 이상)');
    if (!cands.length) r('없음. 자바스크립트로 그리는 페이지일 수 있다');
    cands.forEach(x => r('- ' + x.n + '개 · 자식 ' + x.s + ' · 부모 ' + chain(x.p)));
    r('');
    if (cands.length) {
      const top = cands[0];
      const same = [...top.p.children].filter(c => sig(c) === top.s);
      if (same.length) {
        r('## 반복 블록 하나 outerHTML (1800자)');
        r('```html'); r(same[0].outerHTML.slice(0, 1800)); r('```'); r('');
        r('## 앞 3개 innerText (블록마다 300자)');
        r('```');
        same.slice(0, 3).forEach((c, i) => r((i + 1) + '. ' + txt(c).slice(0, 300)));
        r('```'); r('');
      }
    }
    const cls = new Map();
    document.querySelectorAll('[class]').forEach(e => { if (typeof e.className !== 'string') return; e.className.trim().split(/\s+/).forEach(c => { if (c) cls.set(c, (cls.get(c) || 0) + 1); }); });
    r('## 클래스 빈도 (많은 순 15)');
    if (!cls.size) r('클래스를 안 쓴다');
    [...cls.entries()].sort((a, b) => b[1] - a[1]).slice(0, 15).forEach(([c, n]) => r('- ' + n + '회  .' + c));
    r('');
    const pg = A.filter(a => /page[=/-]\d/i.test(a.getAttribute('href') || '')).map(a => txt(a).slice(0, 8) + ' <- ' + a.getAttribute('href'));
    r('## 페이지네이션');
    r(pg.length ? pg.slice(0, 12).map(s => '- ' + s).join('\n') : '없음');
    r('');
    const body = document.body.innerText || document.body.textContent || '';
    const nums = [...new Set(body.match(/\b\d{1,3}(?:[,.]\d{3})+\b|\b\d+(?:\.\d+)?\s?(?:GB|TB|MB)\b/gi) || [])];
    r('## 규모로 보이는 값 (앞 20)');
    r(nums.length ? nums.slice(0, 20).join(' · ') : '없음');
    r('');
    const dates = [...new Set(body.match(/\b\d{4}-\d{2}-\d{2}\b|\b\d{2}[/.]\d{2}[/.]\d{4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b/gi) || [])];
    r('## 날짜로 보이는 값 (앞 12)');
    r(dates.length ? dates.slice(0, 12).join(' · ') : '없음');
    r('');
    r('## 본문 앞 800자');
    r('```'); r(body.replace(/\s+/g, ' ').trim().slice(0, 800)); r('```');
    const box = document.createElement('div');
    box.style.cssText = 'position:fixed;inset:4%;z-index:2147483647;background:#111;color:#eee;border:2px solid #666;padding:8px;display:flex;flex-direction:column;gap:6px;font:13px sans-serif';
    const bar = document.createElement('div');
    bar.style.cssText = 'display:flex;gap:8px;align-items:center';
    const st = document.createElement('span');
    st.style.cssText = 'flex:1;color:#0f0;font:12px monospace';
    st.textContent = '범용 진단 완료 · 링크 ' + A.length + ' · 반복 블록 후보 ' + cands.length + ' · Ctrl+C';
    const x = document.createElement('button');
    x.textContent = '닫기';
    x.onclick = () => box.remove();
    const ta = document.createElement('textarea');
    ta.style.cssText = 'flex:1;width:100%;background:#000;color:#0f0;font:12px monospace;border:1px solid #444';
    ta.value = out.join('\n');

    /* ── 최소화. 접어도 상태와 중단은 남긴다 ────── */
    let MINI = false;
    const miniB = document.createElement('button');
    miniB.textContent = '최소화';
    miniB.setAttribute('data-mini', '1');
    miniB.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;background:#333;color:#ddd;border:1px solid #555';
    const KEEP = [st, miniB, x];
    miniB.onclick = () => {
      MINI = !MINI;
      box.style.inset = MINI ? 'auto 10px 10px auto' : '4%';
      box.style.maxWidth = MINI ? '52vw' : '';
      ta.style.display = MINI ? 'none' : '';
      [...bar.children].forEach(c => { c.style.display = (MINI && KEEP.indexOf(c) < 0) ? 'none' : ''; });
      miniB.textContent = MINI ? '펼치기' : '최소화';
    };

    bar.append(st, miniB, x);
    box.append(bar, ta);
    document.body.appendChild(box);
    ta.focus();
    ta.select();

  }

  /* ── 고르는 판 ──────────────────────────────
     작게 뜬다. 하나를 고르면 사라지고 그 모듈이 자기 상자를 만든다. */
  const NAME = {
    forum: '포럼', qilin: '킬린', dirindex: '디렉터리',
    photo: '증거 사진', probe: '구조 진단'
  };
  const RUN = {
    forum: modForum, qilin: modQilin, dirindex: modIndex,
    photo: modPhoto, probe: modProbe
  };

  const pick = document.createElement('div');
  pick.style.cssText = 'position:fixed;top:10px;right:10px;z-index:2147483647;background:#111;color:#eee;border:2px solid #666;padding:8px;display:flex;flex-direction:column;gap:6px;font:13px sans-serif;max-width:60vw';
  const line = document.createElement('div');
  line.style.cssText = 'display:flex;gap:6px;align-items:center;flex-wrap:wrap';
  const note = document.createElement('div');
  note.style.cssText = 'font:12px monospace;color:#0f0';
  note.textContent = VER + ' · ' + NAME[BEST] + ' 으로 봤다';

  const go = (k) => {
    pick.remove();
    try {
      RUN[k]();
    } catch (e) {
      const err = document.createElement('div');
      err.style.cssText = 'position:fixed;inset:10% 20%;z-index:2147483647;background:#111;color:#fdd;border:2px solid #855;padding:12px;font:12px monospace;white-space:pre-wrap;overflow:auto';
      err.textContent = NAME[k] + ' 모듈이 멈췄다. 다른 모듈은 멀쩡하다.\n\n' + (e && e.stack || e);
      const x = document.createElement('button');
      x.textContent = '닫기';
      x.style.cssText = 'display:block;margin-top:10px;padding:3px 9px;cursor:pointer';
      x.onclick = () => err.remove();
      err.append(x);
      document.body.appendChild(err);
    }
  };

  ORDER.concat(['probe']).forEach(k => {
    const b = document.createElement('button');
    b.textContent = NAME[k];
    const hot = (k === BEST);
    b.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;' +
      (hot ? 'background:#0a4;color:#fff;border:1px solid #0f8;font-weight:bold'
           : 'background:#333;color:#ddd;border:1px solid #555');
    b.onclick = () => go(k);
    line.append(b);
  });

  const closeB = document.createElement('button');
  closeB.textContent = '닫기';
  closeB.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;background:#422;color:#fdd;border:1px solid #855';
  closeB.onclick = () => pick.remove();
  line.append(closeB);

  pick.append(line, note);
  document.body.appendChild(pick);
  window.__DK = pick;
})();
