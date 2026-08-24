# 킷 다섯을 하나로 합친다.
#
# 각 킷의 본문은 한 글자도 안 바꾼다. 다섯 다 돌아가는 것이고 지금 고치면 위험하다.
# 앞에 판정과 고르는 판만 붙인다. 한 번에 하나만 뜬다.
#
# 껍데기(CHAL·sleep·UI 상자)가 다섯에 겹쳐 있지만 그대로 둔다.
# 껍데기를 뜯는 것은 브라우저에서 이 판이 도는 것을 확인한 뒤에 한다.
import re
from pathlib import Path

B = Path(__file__).resolve().parent
OUT = B / "darkchoco_kit.js"

MODS = [
    ("modForum", "forum_kit.js"),
    ("modQilin", "qilin_kit.js"),
    ("modIndex", "index_kit.js"),
    ("modPhoto", "photo_kit.js"),
    ("modProbe", "probe_generic.js"),
]


def body_of(path: Path) -> str:
    """IIFE 껍데기만 벗긴다. 안은 그대로 둔다."""
    t = path.read_text(encoding="utf-8").rstrip()
    m = re.search(r"\(\(\)\s*=>\s*\{", t)
    assert m, "%s 에서 IIFE 시작을 못 찾음" % path.name
    tail = re.search(r"\}\s*\)\s*\(\s*\)\s*;?\s*$", t)
    assert tail, "%s 에서 IIFE 끝을 못 찾음" % path.name
    inner = t[m.end():tail.start()]
    # 들여쓰기를 두 칸 더
    return "\n".join(("  " + l) if l.strip() else l for l in inner.split("\n"))


HEAD = '''/* 다크초코 통합 킷 v1
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

  const ORDER = ['qilin', 'dirindex', 'forum', 'photo'];
  const BEST = ORDER.filter(k => guess[k])[0] || 'probe';

  /* ── 모듈. 각각 자기 상자를 만든다 ───────────── */
'''

TAIL = '''
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
      err.textContent = NAME[k] + ' 모듈이 멈췄다. 다른 모듈은 멀쩡하다.\\n\\n' + (e && e.stack || e);
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
'''

parts = [HEAD]
for fn, src in MODS:
    body = body_of(B / src)
    parts.append("\n  /* ── %s ── */\n  function %s() {\n%s\n  }\n" % (src, fn, body))
parts.append(TAIL)

OUT.write_text("".join(parts), encoding="utf-8")
print("만듦  %s  %d 자 · %d 줄" % (OUT.name, len(OUT.read_text(encoding='utf-8')),
                                  OUT.read_text(encoding='utf-8').count("\n")))
