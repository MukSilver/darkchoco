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
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 무엇을 보일지. 크기순으로 정렬해서 낸다.
# 파이어폭스가 북마크 URL 을 어느 길이에서 막는지 모른다.
# 작은 것부터 끌어다 놓으면 벽이 어디인지 알 수 있다.
KITS = [
    ("darkchoco_검증_kit", "검증 킷", "포럼 + 진단. **케이스 검증에 쓰는 것은 이것이다**", True),
    ("forum_kit", "포럼 킷", "게시판 지도 · 스레드 목록 · 글 본문 · 단서 추출", True),
    ("darkchoco_조사_kit", "조사 킷", "킬린 + 디렉터리 + 증거 사진 + 진단", False),
    ("qilin_kit", "qilin 킷", "qilin 유출 사이트 전용", False),
    ("index_kit", "목록 킷", "포럼 메인에서 게시판 목록과 수치만", False),
    ("photo_kit", "사진 킷", "게시글에 붙은 이미지 받기", False),
    ("probe_generic", "진단", "이 페이지가 어떤 엔진인지만 본다. 요청을 안 낸다", False),
    ("darkchoco_kit", "통합 킷", "다섯 모듈 전부. **길이 때문에 저장이 안 될 수 있다**", False),
]

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
    got.sort(key=lambda x: len(x[0]))       # 작은 것부터. 벽을 찾기 쉽게

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
<p class="sub">아래 단추를 <b>북마크 도구모음으로 끌어다 놓는다.</b> 눌러도 안 된다.<br>작은 것부터 놓여 있다. 저장이 안 되면 <b>그 크기가 벽이다.</b> 초록이 검증용이다.</p>

<div class="step"><ol>
<li><code>Ctrl</code> + <code>Shift</code> + <code>B</code> 로 북마크 도구모음을 켠다</li>
<li><b>① 자리 시험</b>부터 끌어다 놓고 <b>아무 웹페이지에서</b> 눌러 본다</li>
<li>초록 상자가 뜨면 북마클릿 자체는 정상이다. 위에서부터 하나씩 내려간다</li>
<li>어느 것에서 안 되면 <b>그 크기가 벽이다.</b> 그 위 것을 쓴다</li>
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
<b>길이에서도 막힌다.</b> 통합 킷(64,354자)은 저장이 안 되는 것을 확인했다.
정확히 어디가 벽인지는 모른다. 작은 것부터 끌어다 놓으면 알 수 있다.
<b>검증에 필요한 것은 초록 단추 하나뿐이다.</b>
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
