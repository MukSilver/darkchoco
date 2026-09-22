#!/usr/bin/env python3
"""북마클릿을 끌어다 놓아 설치하는 페이지를 만든다.

    python bookmarklets/build_install_page.py

## 왜 필요한가

파이어폭스와 Tor Browser 는 북마크 편집창의 URL 칸에 `javascript:` 를 넣는 것을 거부한다.
붙여넣어도 저장 버튼을 누르면 원래 값으로 되돌아간다. 자기-XSS 방어다.
주소 칸에 붙여넣으면 `javascript:` 앞부분을 조용히 지운다.

**링크를 끌어다 놓는 경로에는 그 검사가 없다.** 그래서 이 페이지를 만든다.
크롬도 같은 방법으로 된다.

## 쓰는 법

1. 만들어진 `설치.html` 을 브라우저로 연다 (file:// 로 열면 된다)
2. 북마크 도구모음을 켠다 (Ctrl+Shift+B)
3. 페이지의 단추를 도구모음으로 끌어다 놓는다
4. 포럼에서 그 북마크를 누른다

**Tor Browser 는 보안 수준이 Standard 여야 돈다.** Safer 이상이면 JS 가 꺼진다.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 무엇을 보일지. **목록은 build_kit.py 가 들고 있다.** 여기서 또 적지 않는다.
#
# 2026-09-22 전에는 여기에 여덟 줄이 따로 적혀 있었다. 킷을 늘리거나 줄일
# 때마다 build_kit.py 와 이 파일을 둘 다 고쳐야 했고, 한쪽을 빠뜨리면
# 설치 페이지가 없는 파일을 가리켰다.
sys.path.insert(0, str(HERE))
from build_kit import KITS as 킷표, 킷파일           # noqa: E402

KITS = [(킷파일(라벨)[:-3], v["이름"], v["설명"], v["핵심"])
        for 라벨, v in 킷표.items()]

CSS = """
:root{--bg:#0d1117;--sf:#161b22;--ln:#30363d;--ink:#e6edf3;--mut:#8b949e;
      --acc:#6fc8ee;--warn:#f2b45c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);padding:32px 24px;
     font:15px/1.7 'Segoe UI','Malgun Gothic',system-ui,sans-serif}
.wrap{max-width:760px;margin:0 auto}
h1{font-size:24px;margin:0 0 4px;letter-spacing:-.02em}
.sub{color:var(--mut);font-size:14px;margin:0 0 26px}
.step{background:var(--sf);border:1px solid var(--ln);border-radius:10px;
      padding:16px 20px;margin:0 0 24px}
.step ol{margin:0;padding-left:20px}
.step li{margin:4px 0}
.warn{border-color:var(--warn);color:var(--warn)}
.warn b{color:var(--warn)}
.kit{display:flex;align-items:center;gap:16px;padding:13px 0;
     border-top:1px solid var(--ln)}
.kit:last-child{border-bottom:1px solid var(--ln)}
.kit.core{background:#10241d}
.kit.core .bm{background:#54c79e}
.bm{flex:none;display:inline-block;padding:9px 18px;border-radius:8px;
    background:var(--acc);color:#08121a;font-weight:700;text-decoration:none;
    cursor:grab;white-space:nowrap}
.bm:active{cursor:grabbing}
.desc{min-width:0}
.desc b{display:block;font-size:14.5px}
.desc span{color:var(--mut);font-size:13px}
.size{margin-left:auto;color:var(--mut);font-size:12px;
      font-variant-numeric:tabular-nums;white-space:nowrap}
code{background:#0b0f14;border:1px solid var(--ln);border-radius:4px;
     padding:1px 5px;font-size:13px}
"""


# 북마클릿이 아예 도는지 가르는 시험용. 길이가 짧아 어디서도 저장된다.
# 이것도 안 되면 길이 문제가 아니라 브라우저가 북마클릿 자체를 막는 것이다.
TINY = ("javascript:(()=>{const d=document.createElement('div');"
        "d.style.cssText='position:fixed;top:10px;right:10px;z-index:2147483647;"
        "background:#0a4;color:#fff;padding:10px 14px;font:14px sans-serif;"
        "border:2px solid #0f8';d.textContent='북마클릿 정상 · '+location.host;"
        "d.onclick=()=>d.remove();document.body.appendChild(d);"
        "setTimeout(()=>d.remove(),6000)})();")


def build() -> str:
    got = [(TINY, "① 자리 시험", "**여기부터 해보세요.** 눌러서 초록 상자가 뜨면 "
                              "북마클릿 자체는 도는 것이다. 6초 뒤 사라진다", True)]
    for stem, name, desc, core in KITS:
        f = HERE / (stem + ".bookmarklet.txt")
        if f.exists():
            got.append((f.read_text(encoding="utf-8").strip(), name, desc, core))
    # 자리 시험이 맨 앞, 그 다음이 핵심 킷이다. 전에는 크기순이었는데
    # 킷이 여덟이던 시절 「어느 길이에서 막히는지」 를 찾으려던 것이다.
    # 둘만 남아 그 뜻이 없어졌고, 쓰는 순서대로 놓는 편이 낫다
    got.sort(key=lambda x: (not x[3], len(x[0])))

    rows = []
    for code, name, desc, core in got:
        # 굵게 표시할 자리를 살린다. 나머지는 그대로 이스케이프한다
        d = html.escape(desc).replace("**", "\x00")
        while "\x00" in d:
            d = d.replace("\x00", "<b>", 1).replace("\x00", "</b>", 1)
        rows.append(
            '<div class="kit%s">'
            '<a class="bm" href="%s" onclick="return false">%s</a>'
            '<span class="desc"><b>%s</b><span>%s</span></span>'
            '<span class="size">%s자</span>'
            "</div>"
            % (" core" if core else "", html.escape(code, quote=True),
               html.escape(name), html.escape(name), d, format(len(code), ",")))

    return """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>다크초코 킷 설치</title><style>%s</style></head><body><div class="wrap">
<h1>다크초코 킷 설치</h1>
<p class="sub">아래 단추를 <b>북마크 도구모음으로 끌어다 놓는다.</b> 눌러도 안 된다.<br>킷은 둘이다. <b>포럼 글을 읽을 때는 초록 것</b>을 쓰고, 유출 사이트·열린 디렉터리·증거 사진은 다른 하나를 쓴다.</p>

<div class="step"><ol>
<li><code>Ctrl</code> + <code>Shift</code> + <code>B</code> 로 북마크 도구모음을 켠다</li>
<li><b>① 자리 시험</b>부터 끌어다 놓고 <b>아무 웹페이지에서</b> 눌러 본다</li>
<li>초록 상자가 뜨면 북마클릿 자체는 정상이다. 이어서 킷 둘을 끌어다 놓는다</li>
<li>자리 시험은 되는데 킷이 안 되면 길이 문제가 아니다. 다른 원인을 본다</li>
</ol>
<b>① 자리 시험도 안 되면</b> 길이 문제가 아니다.
북마크를 누를 때 주소창에 <code>javascript:</code> 가 잠깐 보이는지,
아무 반응이 없는지 알려 달라. 원인이 갈린다.
</div>

<div class="step warn">
<b>URL 칸에 붙여넣는 방법은 안 된다.</b>
파이어폭스와 Tor Browser 는 북마크 URL 칸의 <code>javascript:</code> 를 거부하고
저장할 때 원래 값으로 되돌린다. 주소 칸에 붙여넣으면 앞부분을 조용히 지운다.
끌어다 놓는 경로에는 그 검사가 없다.
<br><br>
<b>Tor Browser 는 보안 수준이 Standard 여야 돈다.</b>
Safer 이상이면 JS 가 꺼져서 눌러도 아무 일이 안 일어난다.
킷을 쓸 때만 내리고 평소에는 올려 두는 편이 낫다.
<br><br>
<b>길이에서도 막힌다.</b> 전에 모듈 다섯을 한 벌로 묶은 킷(73,767자)이
저장이 안 되는 것을 확인했다. 2026-09-22 에 그것을 둘로 갈랐고
<b>지금 둘 다 6만 자 아래다.</b> 그래서 길이 벽에 안 걸린다.
자리 시험은 되는데 킷이 안 되면 길이가 아니라 다른 문제다.
</div>
%s
<div class="step" style="margin-top:24px">
<b>안 되면</b> 개발자도구로도 된다.
<code>F12</code> → 콘솔 → <code>allow pasting</code> 을 직접 타이핑하고 Enter →
<code>javascript:</code> 를 뺀 코드를 붙여넣고 Enter.
</div>
</div></body></html>
""" % (CSS, "\n".join(rows))


def main() -> int:
    out = HERE / "설치.html"
    body = build()
    out.write_text(body, encoding="utf-8")
    n = body.count('class="kit')
    print("%s  킷 %d개  %d자" % (out, n, len(body)))
    print("브라우저로 열어 단추를 북마크 도구모음으로 끌어다 놓는다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
