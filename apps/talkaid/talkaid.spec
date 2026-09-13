# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 설정. **onedir 이다. onefile 이 아니다.**

    .venv\\Scripts\\pyinstaller.exe talkaid.spec --noconfirm

## 왜 onefile 이 아닌가

onefile 은 **실행할 때마다** 임시 폴더에 압축을 푼다. PyInstaller 공식 문서가
대용량에서 비권장한다고 적어 두었고, 180MB 번들에 기동 3.2초라는 사례가 있다.
onedir 은 푸는 일이 없다.

**백신 오탐도 onefile 이 더 심하다.** 런타임 압축 해제가 휴리스틱을 건드린다
(PyInstaller Issue #6754 외 다수). 두 이유가 같은 방향을 가리킨다.

## 왜 UPX 를 끄나

UPX 압축은 오탐을 **악화시킨다** (upx Issue #711). 크기 이득보다 비용이 크다.

## 모델은 안 넣는다

모델이 1.2~2.9GB 다. 넣으면 배포물이 3GB가 되고 모델만 바꿔도 전부 다시 뿌려야 한다.
`huggingface_hub` 가 처음 실행 때 받아 `~/.cache/huggingface` 에 둔다.

## ctranslate2 훅이 없다

`pyinstaller-hooks-contrib` 에 ctranslate2 훅이 없어서 DLL 을 직접 모은다.
`ctranslate2.dll` 과 Intel MKL·oneDNN 이 딸려 있는데 자동으로는 안 잡힌다.
**지은 뒤 깨끗한 PC 에서 반드시 돌려 봐야 한다.**
"""
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

binaries = []
for 이름 in ("ctranslate2", "sentencepiece", "tokenizers"):
    binaries += collect_dynamic_libs(이름)

datas = [
    ("terms.json", "."),
    ("snippets.json", "."),
]

# **바꿔 쓰기 규칙은 스킬 쪽이 정본이다.** 레포에 사본을 두지 않는다 —
# 2026-09-02 에 같은 도구가 세 벌이라 24개 중 13개가 갈렸던 일이 있다.
# 그래서 여기서 정본을 읽어 넣는다. 고칠 때는 정본 한 곳만 고치고 다시 지으면 된다.
#
# 이것을 안 넣으면 exe 로 받은 사람은 규칙 25짝이 통째로 빠진 채 돈다.
# 죽지도 경고하지도 않아서 쓰는 사람이 모른다 (2026-09-13 에 그 상태였다).
정본 = os.path.join("..", "..", "skills", "skills", "darkweb-verify-ko",
                   "tools", "en_style.json")
if os.path.exists(정본):
    datas.append((정본, "."))
else:
    raise SystemExit(
        "en_style.json 을 못 찾았다: %s\n"
        "레포 안에서 지어야 한다. 이것 없이 지으면 바꿔 쓰기가 빠진 exe 가 나온다."
        % os.path.abspath(정본))

# sv_ttk 는 .tcl 파일이 알맹이다. 코드가 아니라 자료라 따로 모아야 한다
datas += collect_data_files("sv_ttk")

a = Analysis(
    ["talkaid.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=["ui", "win", "engine", "guard"],
    hookspath=[],
    excludes=[
        # 안 쓰는데 딸려 오면 수십 MB 다
        "torch", "transformers", "matplotlib", "pandas", "scipy",
        "PIL", "pytest", "IPython",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="talkaid",
    console=False,          # 창이 본체다. 콘솔을 따로 안 띄운다
    upx=False,              # 오탐을 악화시킨다
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name="talkaid",
)
