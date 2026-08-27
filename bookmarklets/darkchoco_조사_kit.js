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

  const ORDER = ['qilin', 'dirindex', 'photo'];
  const BEST = ORDER.filter(k => guess[k])[0] || 'probe';

  /* ── 모듈. 각각 자기 상자를 만든다 ───────────── */

  /* ── 공통 껍데기 ── */
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
  /* 켜면 상자만 뜬다. 사람이 단추를 눌러 시작한다. 2026-08-27 */
    ta.value = ['킷이 떴다. 아래 단추 중 하나를 누르면 시작한다.', '',
                '  추천    ' + (isDetail ? '이 건 상세' : '이 페이지만'),
                '',
                '「전체 수집」만 요청을 낸다. 쪽을 넘겨 가며 받으므로 시간이 걸린다.',
                '나머지는 열려 있는 문서만 읽는다.'].join('\n');

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
  const NAME = { qilin: '킬린', dirindex: '디렉터리', photo: '증거 사진', probe: '구조 진단' };
  const RUN = { qilin: modQilin, dirindex: modIndex, photo: modPhoto, probe: modProbe };

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
