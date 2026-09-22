/* 증거 사진 수집 도구 v1
   랜섬웨어 유출 사이트가 피해자 글에 올린 증거 사진을 받는다.
   TITAN, 킬린처럼 썸네일 격자를 쓰는 사이트에서 쓴다.

   **검증에 쓸 것만 받는다.** 기본 20장이고 개수를 직접 정한다.
   요청 간격은 2.5~5초다. 줄이지 마라. 계정과 회선을 셋이 공유한다.
   받은 파일은 VM 안에 둔다. 케이스가 끝나면 지운다.

   먼저 찾기 로 주소를 확인하고, 썸네일이면 원본 주소 확인 으로 규칙을 본 뒤 받는다.
   2026-08-21 다크초코 */
(() => {
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
/* 기본은 크기로 고른다. 주소로 거르지 않는다.

   2026-08-27. 전에는 기본 거르개가 `/uploads/` 였다. 그 조각이 주소에 없는
   이미지 호스트에서는 하나도 안 걸려서 "사진 0개" 가 나왔다.
   imgbb 가 그렇다. 주소가 i.ibb.co/8RYNqm0/1.png 라 uploads 가 없다.

   대신 실제 크기로 고른다. 아이콘과 로고는 작고 증거 사진은 크다.
   주소 조각 칸은 좁힐 때만 쓴다. */
  const MIN = 200;      /* 이보다 작은 것은 아이콘으로 본다 */

  const pick = () => {
    const pat = (patW.__i.value || '').trim();
    const re = pat ? new RegExp(pat, 'i') : null;
    const seen = new Set();
    const out = [];
    document.querySelectorAll('img[src]').forEach(im => {
      const raw = im.getAttribute('src') || '';
      if (!raw) return;
      if (re) {                       /* 칸에 적었으면 그것만 본다 */
        if (!re.test(raw)) return;
      } else {                        /* 안 적었으면 크기로 고른다 */
        const w = im.naturalWidth || im.width || 0;
        const h = im.naturalHeight || im.height || 0;
        if (w < MIN && h < MIN) return;
        if (/^data:/i.test(raw)) return;   /* 인라인 아이콘은 뺀다 */
      }
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
      const all = document.querySelectorAll('img[src]').length;
      L.push('못 찾았다. 이 화면의 img 는 ' + all + '개다.');
      if (!(patW.__i.value || '').trim()) {
        L.push('기본은 ' + MIN + 'px 이상만 고른다. 사진이 그보다 작으면');
        L.push('주소 조각 칸에 파일 이름 조각(png · jpg · 폴더명)을 적고 다시 누른다.');
      } else {
        L.push('주소 조각 칸을 비우면 크기로 고른다. 지금 적힌 것과 안 맞는 듯하다.');
      }
      L.push('접힌 사진이 있으면 먼저 펼치고 다시 누른다.');
    }
    return { md: L.join('\n'), status: '찾음 ' + FOUND.length + '개 · 아직 안 받았다' };
  };

  /* ── 원본 주소 확인. 썸네일을 한 번 눌러 본다 ── */
  const probe = async () => {
    const before = new Set(pick().map(f => f.url));
/* **아무 단추나 누르지 않는다.** pick() 이 증거 사진으로 고른 것 안에서만 찾는다.

   전에는 `document.querySelector('button img, a img, [role="button"] img')` 로
   문서에서 처음 걸리는 것을 확인 없이 눌렀다. 게시판이면 머리글 로고나 도구줄
   아이콘이 먼저 걸린다. 그것이 링크면 누르는 순간 그 주소로 나가고, 구독이나
   읽음 표시처럼 누르면 서버에 남는 링크일 수도 있다 (2026-09-22 고침).

   그래서 셋을 본다 — ① 사진으로 고른 것인가 ② 감싼 것이 다른 쪽으로 나가는
   링크는 아닌가 ③ 사람이 좋다고 했는가. */
    let 찍을것 = null, 감싼것 = null;
    for (const im of document.querySelectorAll('img[src]')) {
      let u;
      try { u = new URL(im.getAttribute('src') || '', location.href).href; }
      catch (e) { continue; }
      if (!before.has(u)) continue;                 /* ① 사진으로 안 고른 것 */
      const w = im.closest('button, a, [role="button"]');
      if (!w) continue;
      if (w.tagName === 'A') {                      /* ② 나가는 링크인가 */
        const h = w.getAttribute('href') || '';
        const 제자리 = !h || /^#/.test(h)
          || /\.(jpe?g|png|gif|webp|bmp)(\?|$)/i.test(h);
        if (!제자리) {
          let 같은쪽 = false;
          try { 같은쪽 = new URL(h, location.href).pathname === location.pathname; }
          catch (e) { 같은쪽 = false; }
          if (!같은쪽) continue;
        }
      }
      찍을것 = im; 감싼것 = w; break;
    }
    if (!찍을것) return { md: '누를 만한 썸네일을 못 찾았다. **사진을 먼저 찾아 본다.**\n'
                          + '찾은 사진 안에 눌러서 열리는 것이 없으면 이 단추는 쓸 일이 없다',
                         status: '실패' };
    const 어디 = 감싼것.getAttribute('href') || 감싼것.getAttribute('aria-label')
               || ('<' + 감싼것.tagName.toLowerCase() + '>');
    if (!confirm('아래를 한 번 누른다. 눌러야 원본 주소가 뜨는지 알 수 있다.\n\n'
                 + '사진   ' + 찍을것.src.slice(0, 110) + '\n'
                 + '감싼 것 ' + String(어디).slice(0, 110) + '\n\n괜찮은가?'))
      return { md: '사람이 그만두었다. 아무것도 누르지 않았다', status: '멈춤' };
    감싼것.click();
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
  /* @shell */
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
})();
