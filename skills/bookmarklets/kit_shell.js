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

  /* 끌어서 옮기기. forum_kit 에만 있던 것을 여기로 옮겨 셋도 같이 쓴다.
     상자가 화면을 거의 덮어서 아래를 보려면 옮기거나 접어야 한다. 2026-08-27 */
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
  const onMove = e => { if (!dragging) return;
    box.style.left = (e.clientX - dx) + 'px'; box.style.top = (e.clientY - dy) + 'px'; };
  const onUp = () => { dragging = false; };
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);

  const gone = () => {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    box.remove();
  };

  /* 홈으로. 통합 킷이 `window.__DKHOME` 을 걸어 두면 나온다.
     낱개 킷으로 쓸 때는 돌아갈 데가 없으므로 안 나온다. */
  const homeB = document.createElement('button');
  homeB.textContent = '홈으로';
  homeB.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;background:#234;color:#cde;border:1px solid #467';
  homeB.onclick = () => { const h = window.__DKHOME; gone(); if (h) h(); };

  const stopB = document.createElement('button');
  stopB.textContent = '중단';
  stopB.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;background:#422;color:#fdd;border:1px solid #855';
  stopB.onclick = () => { o.setAbort(true); say('중단 요청. 현재 요청이 끝나면 멈춘다'); };

  const closeB = document.createElement('button');
  closeB.textContent = '닫기';
  closeB.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;background:#422;color:#fdd;border:1px solid #855';
  closeB.onclick = gone;

  /* 최소화. 접어도 상태와 중단은 남긴다.
     걸어다니는 중에 아래 페이지를 보면서 진행을 확인할 때 쓴다. */
  let MINI = false;
  const miniB = document.createElement('button');
  miniB.textContent = '최소화';
  miniB.setAttribute('data-mini', '1');
  miniB.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;background:#333;color:#ddd;border:1px solid #555';
  const KEEP = [grip, st, miniB, stopB, homeB, closeB];
  miniB.onclick = () => {
    MINI = !MINI;
    box.style.inset = MINI ? 'auto 10px 10px auto' : '4%';
    box.style.maxWidth = MINI ? '52vw' : '';
    ta.style.display = MINI ? 'none' : '';
    [...bar.children].forEach(c => { c.style.display = (MINI && KEEP.indexOf(c) < 0) ? 'none' : ''; });
    miniB.textContent = MINI ? '펼치기' : '최소화';
  };

  const mount = (...items) => {
    bar.append(grip, ...items, st, stopB, miniB);
    if (window.__DKHOME) bar.append(homeB);      /* 통합 킷일 때만 */
    bar.append(closeB);
    box.append(bar, ta);
    document.body.appendChild(box);
    box.__gone = gone;
    return box;
  };

  return { box: box, bar: bar, st: st, ta: ta, say: say, put: put,
           mk: mk, inp: inp, grip: grip, stopB: stopB, miniB: miniB,
           homeB: homeB, closeB: closeB, gone: gone, mount: mount };
}
