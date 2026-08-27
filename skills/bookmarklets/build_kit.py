# 킷 다섯을 하나로 합친다.
#
# 각 킷의 본문은 한 글자도 안 바꾼다. 다섯 다 돌아가는 것이고 지금 고치면 위험하다.
# 앞에 판정과 고르는 판만 붙인다. 한 번에 하나만 뜬다.
#
# 껍데기(CHAL·sleep·UI 상자)가 다섯에 겹쳐 있지만 그대로 둔다.
# 껍데기를 뜯는 것은 브라우저에서 이 판이 도는 것을 확인한 뒤에 한다.
import argparse
import re
from pathlib import Path

B = Path(__file__).resolve().parent

# 키         함수         파일                검증에서 얼마나 쓰나
MODS = [
    ("forum",    "modForum", "forum_kit.js",     "핵심. ② 재료가 여기서 나온다"),
    ("qilin",    "modQilin", "qilin_kit.js",     "드묾. qilin 유출 사이트에서만"),
    ("dirindex", "modIndex", "index_kit.js",     "드묾. 열린 디렉터리에서만"),
    ("photo",    "modPhoto", "photo_kit.js",     "가끔. 증거 사진"),
    ("probe",    "modProbe", "probe_generic.js", "받침. 판정이 안 될 때. 언제나 들어간다"),
]

# 미리 묶어 둔 조합. 이름으로 부른다
SETS = {
    "검증": ["forum"],                       # 케이스 검증에 쓰는 것
    "조사": ["qilin", "dirindex", "photo"],  # 포럼·사이트 조사에 쓰는 것
    "전부": ["forum", "qilin", "dirindex", "photo"],
}

ALWAYS = "probe"     # 판정이 안 될 때의 받침. 빼지 않는다


def body_of(path: Path) -> str:
    """IIFE 껍데기만 벗긴다. 안은 그대로 둔다.

    `/* @shell */` 표시는 지운다. 공통 껍데기는 맨 앞에 한 번만 둔다.
    모듈마다 넣으면 세 벌이 돼서 줄이는 뜻이 없다.
    """
    t = path.read_text(encoding="utf-8").rstrip().replace("/* @shell */", "")
    m = re.search(r"\(\(\)\s*=>\s*\{", t)
    assert m, "%s 에서 IIFE 시작을 못 찾음" % path.name
    tail = re.search(r"\}\s*\)\s*\(\s*\)\s*;?\s*$", t)
    assert tail, "%s 에서 IIFE 끝을 못 찾음" % path.name
    inner = t[m.end():tail.start()]
    # 들여쓰기를 두 칸 더
    return "\n".join(("  " + l) if l.strip() else l for l in inner.split("\n"))


HEAD = '''/* 다크초코 통합 킷 v1
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
    forum: hit(/showthread\\.php|\\/Thread-|forumdisplay\\.php|\\/Forum-|\\/threads\\/|\\/forums\\//i) >= 4,
    qilin: /\\/site\\/blog\\?uuid=|\\/c\\/[^\\/]+\\/\\d+/.test(H),
    dirindex: /^Index of \\//.test((document.title || '')) ||
              /Parent Directory|\\[To Parent Directory\\]/i.test(TXT) ||
              (!!document.querySelector('pre') && hit(/\\/$/) >= 3),
    photo: document.querySelectorAll('img').length >= 6
  };

  const ORDER = @@ORDER@@;
  const BEST = ORDER.filter(k => guess[k])[0] || 'probe';

  /* ── 모듈. 각각 자기 상자를 만든다 ───────────── */
'''

TAIL = '''
  /* ── 고르는 판 ──────────────────────────────
     작게 뜬다. 하나를 고르면 사라지고 그 모듈이 자기 상자를 만든다. */
  const NAME = @@NAME@@;
  const RUN = @@RUN@@;

  const KEYS = ORDER.concat(['probe']);

  const go = (k) => {
    if (window.__DK) { try { window.__DK.remove(); } catch (e) {} window.__DK = null; }
    try {
      RUN[k]();
    } catch (e) {
      const err = document.createElement('div');
      err.style.cssText = 'position:fixed;inset:10% 20%;z-index:2147483647;background:#111;color:#fdd;border:2px solid #855;padding:12px;font:12px monospace;white-space:pre-wrap;overflow:auto';
      /* 역슬래시를 안 쓴다. TAIL 이 파이썬 문자열이라 겹이 한 번 벗겨지고,
         셸을 거치면 또 벗겨진다. 2026-08-27 에 세 번 물렸다 */
      const NL = String.fromCharCode(10);
      err.textContent = [NAME[k] + ' 모듈이 멈췄다. 다른 모듈은 멀쩡하다.', '',
                         (e && e.stack || e)].join(NL);
      const x = document.createElement('button');
      x.textContent = '닫기';
      x.style.cssText = 'display:block;margin-top:10px;padding:3px 9px;cursor:pointer';
      x.onclick = () => err.remove();
      err.append(x);
      document.body.appendChild(err);
    }
  };

  /* 고르는 판. 접히고 끌어 옮겨진다. 모듈 창에서 「홈으로」 로 다시 부른다 */
  const showPick = () => {
    if (window.__DK) { try { window.__DK.remove(); } catch (e) {} }
    const pick = document.createElement('div');
    pick.style.cssText = 'position:fixed;top:10px;right:10px;z-index:2147483647;background:#111;color:#eee;border:2px solid #666;padding:8px;display:flex;flex-direction:column;gap:6px;font:13px sans-serif;max-width:60vw';
    const line = document.createElement('div');
    line.style.cssText = 'display:flex;gap:6px;align-items:center;flex-wrap:wrap';
    const note = document.createElement('div');
    note.style.cssText = 'font:12px monospace;color:#0f0';
    note.textContent = VER + ' · ' + NAME[BEST] + ' 으로 봤다';

    const grip = document.createElement('span');
    grip.textContent = '\u283F'; grip.title = '끌어서 옮기기';
    grip.style.cssText = 'cursor:move;color:#888;padding:0 4px;user-select:none;font-size:15px';
    let dx = 0, dy = 0, dragging = false;
    grip.onmousedown = e => {
      const r = pick.getBoundingClientRect();
      pick.style.top = r.top + 'px'; pick.style.left = r.left + 'px'; pick.style.right = 'auto';
      dx = e.clientX - r.left; dy = e.clientY - r.top; dragging = true; e.preventDefault();
    };
    const onMove = e => { if (!dragging) return;
      pick.style.left = (e.clientX - dx) + 'px'; pick.style.top = (e.clientY - dy) + 'px'; };
    const onUp = () => { dragging = false; };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    const gone = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      pick.remove();
    };

    const mkB = (label, css) => {
      const b = document.createElement('button');
      b.textContent = label;
      b.style.cssText = 'padding:3px 9px;cursor:pointer;font:12px sans-serif;' + css;
      return b;
    };

    const picks = [];
    KEYS.forEach(k => {
      const hot = (k === BEST);
      const b = mkB(NAME[k], hot ? 'background:#0a4;color:#fff;border:1px solid #0f8;font-weight:bold'
                                 : 'background:#333;color:#ddd;border:1px solid #555');
      b.onclick = () => { gone(); go(k); };
      picks.push(b);
    });

    let mini = false;
    const minB = mkB('최소화', 'background:#333;color:#ddd;border:1px solid #555');
    minB.onclick = () => {
      mini = !mini;
      picks.forEach(b => { b.style.display = mini ? 'none' : ''; });
      note.style.display = mini ? 'none' : '';
      minB.textContent = mini ? '펼치기' : '최소화';
    };

    const closeB = mkB('닫기', 'background:#422;color:#fdd;border:1px solid #855');
    closeB.onclick = gone;

    line.append(grip);
    picks.forEach(b => line.append(b));
    line.append(minB, closeB);
    pick.append(line, note);
    document.body.appendChild(pick);
    window.__DK = pick;
  };

/* 고를 것이 하나뿐이면 판을 건너뛴다. 검증 킷이 그렇다.
   구조 진단은 포럼 창 안에 이미 단추로 있어서 판이 한 겹 더 있을 뜻이 없다.
   그때는 돌아갈 데가 없으므로 __DKHOME 을 안 건다. 모듈에 홈으로가 안 나온다.
   2026-08-27 */
  if (ORDER.length <= 1) {
    go(ORDER[0] || 'probe');
  } else {
    window.__DKHOME = showPick;
    showPick();
  }
})();
'''

KO = {"forum": "포럼", "qilin": "킬린", "dirindex": "디렉터리",
      "photo": "증거 사진", "probe": "구조 진단"}


def build(keys: list[str], out: Path) -> None:
    """고른 모듈만 묶는다. probe 는 언제나 들어간다."""
    keys = [k for k in keys if k != ALWAYS] + [ALWAYS]
    picked = [m for m in MODS if m[0] in keys]
    got = {m[0] for m in picked}
    missing = [k for k in keys if k not in got]
    assert not missing, "모르는 모듈: " + ", ".join(missing)

    shell = (B / "kit_shell.js").read_text(encoding="utf-8")
    assert "function mkShell" in shell, "공통 껍데기를 못 읽었다"

    # 고른 것만 판에 올린다. probe 는 TAIL 이 따로 붙이므로 여기서 뺀다
    order = [k for k, _, _, _ in picked if k != ALWAYS]
    head = HEAD.replace("@@ORDER@@",
                        "[" + ", ".join("'%s'" % k for k in order) + "]")
    tail = TAIL \
        .replace("@@NAME@@",
                 "{ " + ", ".join("%s: '%s'" % (k, KO[k]) for k, _, _, _ in picked) + " }") \
        .replace("@@RUN@@",
                 "{ " + ", ".join("%s: %s" % (k, fn) for k, fn, _, _ in picked) + " }")

    parts = [head, "\n  /* ── 공통 껍데기 ── */\n",
             "\n".join("  " + l if l.strip() else l for l in shell.split("\n")), "\n"]
    for _, fn, src, _ in picked:
        body = body_of(B / src)
        parts.append("\n  /* ── %s ── */\n  function %s() {\n%s\n  }\n" % (src, fn, body))
    parts.append(tail)

    body = "".join(parts)
    out.write_text(body, encoding="utf-8")
    print("만듦  %-24s %7s 자 · %s" % (out.name, format(len(body), ","),
                                     " · ".join(KO[k] for k, _, _, _ in picked)))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="킷을 골라 하나로 묶는다. 파이어폭스가 북마크를 길이에서 막는다")
    ap.add_argument("--only", default="전부",
                    help="묶을 것. 조합 이름(%s) 또는 쉼표로 나눈 모듈 키"
                         % " · ".join(SETS))
    ap.add_argument("--out", help="파일 이름. 안 주면 조합 이름으로")
    a = ap.parse_args()

    if a.only in SETS:
        keys, label = SETS[a.only], a.only
    else:
        keys = [s.strip() for s in a.only.split(",") if s.strip()]
        label = "-".join(keys)
    name = a.out or ("darkchoco_kit.js" if a.only == "전부"
                     else "darkchoco_%s_kit.js" % label)
    build(keys, B / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
