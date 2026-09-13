# talkaid — 클립보드 번역

    담당    최현서
    만든 날  2026-09-13
    무엇     전역 단축키로 클립보드의 글을 옮긴다. **번역이 이 PC 안에서만 돈다**

유출 게시글에서 확보한 연락처로 게시자와 대화할 때 쓴다.
텔레그램이 주 무대지만 **메일 · Tox · Tor 브라우저에서도 똑같이 된다.**
넷 다 시스템 클립보드를 쓰기 때문이다.

    Ctrl+Alt+1   고른 한국어 → 영어.  보낼 말. 역번역과 검사가 같이 돈다
    Ctrl+Alt+2   고른 외국어 → 한국어.  읽을 말. 영어·중국어를 알아서 가른다
    Ctrl+Alt+3   상용구 목록

**글을 고르고 Ctrl+C · 단축키 · Ctrl+V.** 어디서나 같다.

---

## 안 하는 것

**보내지 않는다.** 클립보드에 놓기만 한다. 붙여넣는 것도 보내는 것도 사람이 한다.
팀 규칙이 「AI 가 문안을 정해 바로 달지 않는다」이고, 전송 경로를 안 만들면 도구가
실수로 보낼 길이 아예 없다.

**밖으로 요청을 보내지 않는다.** 모델을 처음 받을 때만 huggingface.co 에 붙고,
그 뒤로는 인터넷 없이 돈다. 팀 규칙 「번역은 조사 환경 안에서. 외부 서버로 안 나가게」
때문이다. 번역 API 나 봇을 쓰면 원문이 남의 서버로 나간다.

**저수준 키보드 훅을 안 쓴다.** `RegisterHotKey` 로 정해진 조합만 등록한다.
`pynput` 계열은 모든 키 입력을 가로채서 백신이 키로거로 볼 여지가 있다.

---

## 처음 한 번

    python -m pip install ctranslate2 sentencepiece huggingface_hub
    cd apps/talkaid
    python setup.py

모델 셋을 합쳐 약 1.2GB 를 받는다. `~/.cache/huggingface` 에 들어간다.
**GPU 가 필요 없다.** CPU 로 문장 하나에 50~90 ms 다.

### 윈도우에서 걸리는 것

**개발자 모드가 꺼져 있으면 모델 받기가 `WinError 1314` 로 죽는다.**
심볼릭 링크를 못 만들어서다. 도구가 알아서 「링크 대신 복사」로 돌려놓지만,
직접 돌릴 때 걸리면 이렇게 한다.

    set HF_HUB_DISABLE_SYMLINKS=1

### 화면에 있는 글자 (캡처·그림)

**우리가 만들지 않는다.** PowerToys 의 Text Extractor 를 쓴다.

    Win+Shift+T  로 영역을 끌면 글자가 클립보드에 들어간다
    그다음 Ctrl+Alt+2

중국어와 한국어를 읽으려면 언어팩을 깔아야 한다. 관리자 PowerShell 에서:

    Get-WindowsCapability -Online | Where-Object { $_.Name -Like 'Language.OCR*' }
    $c = Get-WindowsCapability -Online | Where-Object { $_.Name -Like 'Language.OCR*zh-CN*' }
    $c | Add-WindowsCapability -Online

---

## 나가면 안 되는 말

**보낼 말(Ctrl+Alt+1)에만 검사가 걸린다.** 걸리면 **클립보드에 안 넣는다.**

    막음   팀·소속 이름 · 협업사 · 공개 계정 · 노션 주소 · 우리 저장소 ·
          내부 케이스 번호(LEAK-nn) · 개인 폴더 경로
    경고   신분을 밝히는 말 · 이메일 · 전화 · 주민번호 꼴 · 번역 안 된 한글

신분을 밝히는 말은 **막지 않고 경고만 한다.** 팀 문서상 기자는 신분을 밝히고
접근하므로 그것이 의도한 문안일 수 있다. 의도했는지는 도구가 판단할 수 없다.

**팀원 실명 목록은 레포에 두지 않는다.** 목록 자체가 개인정보라서다.

    ~/.config/darkchoco/talkaid_block      한 줄에 하나. # 로 시작하면 주석

없으면 그 검사를 **「못 봄」** 으로 적는다. 없음과 못 봄은 다르다.

**걸린 값을 화면에 찍지 않는다.** 무엇이 몇 건 걸렸는지만 낸다. 로그가 곧 반출이다.

---

## 기계번역을 믿지 않는 법

**스무 문장 중 넷의 뜻이 틀렸다** (2026-09-13 실측). 그래서 장치를 셋 두었다.

**하나. 문장을 나눠서 넣는다.** 효과가 가장 크다.

    합쳐서   I want to make sure that I understand that there are more than one million files.
             (질문이 사라지고 두 뜻이 뭉갰다)
    나눠서   I want to make sure that what I understand is right.
             You're saying there are more than one million files?

**둘. 도메인 용어를 자리표로 뺀다.** `terms.json` 에 있다.

    어피실리에이트   efisilite  →  affiliates
    업종            karma      →  industry sector

쓰다가 깨지는 말을 보면 `terms.json` 에 한 줄 더한다. 코드는 안 고친다.

**셋. 역번역을 같이 낸다. 이것이 핵심이다.**

    한국어   게시가 내려간 피해사가 있나요?
    영어     Is there victim organization that she went down?
    역번역   **그녀가 쓰러뜨린 피해자가 있습니까?**   ← 여기서 틀린 것을 안다

**역번역을 반드시 읽는다.** 그러라고 창을 띄워 둔다. 트레이로 숨기지 않는다.

### 사람이 도와야 하는 것

압축된 한국어는 모델이 못 푼다. 원문을 풀어 쓰면 결과가 좋아진다.

    피해사        →  피해 회사
    업종          →  산업 분야
    게시가 내려간   →  게시물이 삭제된

---

## 대화 중에 번역을 덜 쓰는 법

가장 빠른 것은 **미리 만들어 두는 것**이다.

    대화 전   질문지를 통째로 옮겨 번호 목록으로 들고 들어간다.
             스킬의 references/talk-en.md 와 tools/en_style.py 가 그것을 한다
    대화 중   Ctrl+Alt+3 의 상용구.  맞장구 · 되묻기 · 시간 벌기 · 마무리
    그다음    Ctrl+Alt+1.  즉석에서 생긴 말만

`snippets.json` 은 번역을 안 거친다. 그래서 0 ms 다. 쓰다 보면 늘어난다.

---

## 파일

    engine.py       모델과 파이프라인.  윈도우가 아니어도 돈다
    guard.py        나가면 안 되는 말.  0 ms
    talkaid.py      상주와 단축키.  **윈도우 전용**
    setup.py        모델 받기와 확인
    terms.json      도메인 용어
    snippets.json   상용구
    tests/          python tests/test_engine.py · python tests/test_guard.py

바꿔 쓰기 규칙은 **여기 사본을 두지 않는다.** 스킬의
`skills/skills/darkweb-verify-ko/tools/en_style.json` 을 그대로 본다.
2026-09-02 에 같은 도구가 세 벌이라 24개 중 13개가 갈렸던 일이 있다.

---

## 쓰는 모델

전부 CTranslate2 int8 이고 CPU 에서 돈다.

| 방향 | 모델 | 크기 | 문장 하나 |
|---|---|---|---|
| ko → en | `gaudi/opus-mt-ko-en-ctranslate2` | 160 MB | 52 ms |
| en → ko | `eskara1398/opus-mt-tc-big-en-ko-ct2` | 845 MB | 90 ms |
| zh → en | `gaudi/opus-mt-zh-en-ctranslate2` | 160 MB | 50 ms |

중국어에서 한국어로 곧장 가는 OPUS-MT 모델이 없어서 **영어를 거친다.**

**전부 제3자가 올린 변환본이다.** CTranslate2 의 `model.bin` 은 pickle 이 아니라
코드가 실행되지는 않지만, 잘못 변환된 것이 실제로 있었다 —
`ooeoeo/opus-mt-tc-big-en-ko-ct2-float16` 은 어휘 대응이 어긋나 알아볼 수 없는 글자가
나온다. 모델을 바꿀 때는 **반드시 몇 문장 돌려 보고 정한다.**
