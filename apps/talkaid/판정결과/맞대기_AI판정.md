# 맞대기 — AI 판정

    A   opus_어미  (기계번역 OPUS-MT)
    B   qwen1.7b   (로컬 LLM Qwen3-1.7B)
    세트 860439d19151 · 64줄
    판정 Claude 가 매겼다 (2026-09-16). **사람이 스팟체크해서 고치면 된다**

축이 둘이다. **뜻**은 보내도 되는가, **말씨**는 채팅에서 칠 법한가.

    O   그대로 보내도 된다
    ~   통하기는 하는데 모자라다
    X   보내면 안 된다

뜻이 X 인 것은 따로 반박 검증을 한 번 더 거쳤다. 근거에 `[반박: …]` 이
붙은 줄은 처음 X 였다가 완화된 것이다.

---

## 세어 보면

    A 뜻      O 26 (40.6%)   ~ 31 (48.4%)   X  7 (10.9%)
    A 말씨     O 27 (42.2%)   ~ 16 (25.0%)   X 21 (32.8%)
    B 뜻      O 30 (46.9%)   ~ 21 (32.8%)   X 13 (20.3%)
    B 말씨     O 24 (37.5%)   ~ 15 (23.4%)   X 25 (39.1%)

---

## 1
    한국어  Qilin은 자체 운영팀이 직접 공격도 하나, 아니면 순수하게 어피실리에이트에 인프라만 제공하나

    A  뜻[~] 말씨[X]  Is Qilin a direct attack by his team, or is it purely an infrastructure for affiliates.
    B  뜻[X] 말씨[X]  Qilin is either operated by its own team and directly attacks, or simply provides the infrastructure to affiliates.

    근거  A는 「Qilin이 팀에 의한 직접 공격인가」로 조직을 공격 행위 자체로 바꿔 놓았고 「his team」이 누구인지 불명하다. B는 의문문이 「Qilin is either ... or ...」 평서문으로 바뀌어 상대가 답할 이유가 없다. 둘 다 물음표가 없고 A는 an infrastructure 관사 오류까지 있다.

## 2
    한국어  운영자와 어피실리에이트 역할 경계는 어디까지인가

    A  뜻[~] 말씨[O]  What's the boundary between the operator and affiliates?
    B  뜻[~] 말씨[O]  What is the boundary between the operator and affiliates?

    근거  둘 다 「역할」이 빠져 role boundary 인지 영역·관할 경계인지 모호해진다. 말씨는 A의 What's 축약이 채팅체로 자연스럽고 B도 그대로 칠 만하다.

## 3
    한국어  협상과 유출 사이트는 누가 운영하나

    A  뜻[O] 말씨[~]  Who runs negotiations and leak site.
    B  뜻[O] 말씨[X]  Negotiation and leak site is operated by whom?

    근거  뜻은 둘 다 간다. A는 the 가 빠진 leak site 에 마침표로 끝나 질문 표시가 약하다. B는 「is operated by whom?」 수동+후치 의문사에 주술 불일치(Negotiation and leak site is)까지 겹쳐 사람이 안 쓰는 문장이다.

## 4
    한국어  다른 브랜드와 인력이나 코드가 겹친다는 관측이 있는데 사실인가

    A  뜻[~] 말씨[~]  Is it true that there are observations about people and code that overlap with other brands?
    B  뜻[~] 말씨[X]  There's a observation that there's overlap with other brands, staff, or code, is that true?

    근거  A는 「관측이 존재하는 것이 사실인가」로 초점이 옮겨가 정작 겹침 여부를 안 묻는다. B는 「other brands, staff, or code」로 셋을 나열해 「다른 브랜드와 인력·코드가 겹친다」는 관계가 무너지고, a observation 관사 오류와 콤마로 이어붙인 is that true 가 덜컹거린다.

## 5
    한국어  지금도 신규 어피실리에이트를 받고 있나

    A  뜻[O] 말씨[~]  Are you still getting the new affiliates?
    B  뜻[O] 말씨[O]  Are you still getting new affiliates?

    근거  A의 the new affiliates 는 이미 아는 특정 대상을 가리키는 듯 읽혀 군더더기다. B는 관사만 뺀 형태로 채팅에 그대로 칠 수 있다.

## 6
    한국어  수익 배분 비율은 어떻게 되나

    A  뜻[O] 말씨[O]  What's the revenue split ratio?
    B  뜻[O] 말씨[X]  Revenue split ratio is how much?

    근거  뜻은 둘 다 맞다. A는 짧고 곧다. B는 「Revenue split ratio is how much?」로 한국어 어순을 그대로 옮겨 의문문이 비틀렸다.

## 7
    한국어  가입비나 보증금, 추천인 조건이 있나

    A  뜻[O] 말씨[X]  Do you have an entry fee or an deposit or an referral condition?
    B  뜻[O] 말씨[X]  Entry fee, deposit, and referral conditions are there?

    근거  세 항목이 다 살아 뜻은 통한다. A는 an deposit·an referral 관사 오류와 or 반복으로 덜컹거린다. B는 「Entry fee, deposit, and referral conditions are there?」처럼 의문사구를 뒤에 붙여 어순이 한국어식이다.

## 8
    한국어  어피실리에이트에게 무엇을 제공하나

    A  뜻[O] 말씨[~]  What does it offer to affiliates.
    B  뜻[O] 말씨[O]  What do affiliates get?

    근거  A는 제공 주체를 막연한 it 으로 두고 마침표로 끝나 질문으로 덜 읽힌다. B는 받는 쪽 시점으로 뒤집었지만 묻는 내용은 같고 원어민이 채팅에 칠 어순이다.

## 9
    한국어  내부는 월급형 직원 구조인가, 건별 분배인가

    A  뜻[X] 말씨[X]  Is the inside of the payload structure or is it a handout?
    B  뜻[~] 말씨[~]  Is the inside a salary structure for employees, or a distribution by shift?

    근거  A는 '월급형'을 payload 로 잘못 잡아 「내부가 페이로드 구조인가 유인물인가」라는 딴 문장이 됐고 건별 분배도 handout 으로 사라져 답을 못 받는다. B는 월급 구조 대비는 살렸으나 '건별 분배'를 distribution by shift(교대별)로 바꿔 두 선택지 중 하나가 틀렸고, 말씨는 the inside 가 직역 티가 나지만 의문문 꼴은 성립한다. [반박: B 를 ~ 로 — A는 payload·handout 으로 월급/건별 대비가 통째로 사라져 X 유지. B는 월급 구조 대비가 살아 있고 의문문도 성립해 선택지 하나만 틀린 것이라 ~ 다.]

## 10
    한국어  어피실리에이트에게 요구하는 규칙이나 금지 타깃이 있나

    A  뜻[~] 말씨[~]  Is there a rule or a ban point for affiliates?
    B  뜻[O] 말씨[O]  Are there any rules or prohibited targets for affiliates?

    근거  A는 '금지 타깃'을 ban point 라는 없는 말로 옮겨 두 번째 항목이 안 읽히고 rule 도 단수라 덜컹거린다. B는 rules or prohibited targets 로 둘 다 정확히 옮겼고 짧고 곧아 채팅에 그대로 칠 수 있다.

## 11
    한국어  제외하는 국가나 업종이 있나

    A  뜻[X] 말씨[X]  Is there any country or industry sector.
    B  뜻[O] 말씨[O]  Are there any countries or industries excluded?

    근거  A는 핵심인 '제외하는'이 통째로 빠져 「국가나 업종이 있나」라는 뜻 없는 문장이 됐고 물음표도 없이 마침표로 끝나 질문으로 안 읽힌다. B는 excluded 를 살려 뜻이 그대로 가고 어순도 자연스럽다.

## 12
    한국어  한국 자산운용사 집중 게시는 단일 어피실리에이트 작업인가, 여러 명인가

    A  뜻[~] 말씨[X]  Is Korean asset management firm focused on single affiliates jobs or multiple jobs?
    B  뜻[~] 말씨[X]  Asset management firm concentration posting is a single affiliate work or multiple affiliates?

    근거  A는 주어가 뒤집혀 「자산운용사가 단일 계열사 업무에 집중하나」를 묻는 문장이 됐고 single affiliates jobs 는 수 일치도 관사도 깨졌다. B는 단일 대 복수 대비는 전달하지만 '한국'이 빠졌고, concentration posting is ... or ... ? 는 관사 없는 명사 나열에 평서문 어순이라 어색하다. [반박: A 를 ~ 로 — A는 주어가 뒤집혔어도 한국 자산운용사·집중·단일 대 복수가 다 남았고 의문문이라 상대가 「한 명/여럿」으로 답한다. 어순 문제는 말씨 축이다.]

## 13
    한국어  공통 전산업체 침해로 고객사가 연쇄 감염됐다는 분석에 대한 입장은 무엇인가

    A  뜻[~] 말씨[X]  What is the position of the analysis that a common IT service provider invasion has infected customers in a chain?
    B  뜻[O] 말씨[X]  What is your opinion on the analysis that customers have been infected in a chain reaction due to common IT service provider (전산업체) breaches?

    근거  A는 position of the analysis 로 전치사가 틀려 '너의 입장'이 사라지고 분석 자체의 입장을 묻는 문장이 됐으며 침해를 invasion 으로 쓴 것도 어색하다. B는 what is your opinion on 으로 묻는 대상이 맞지만 괄호에 한국어 (전산업체)가 그대로 남아 있어 그대로 보내면 한국인이라는 게 드러난다. [반박: A 를 ~ 로 — A는 '너의'가 빠져 흐려졌을 뿐 연쇄 감염 분석이라는 물음 대상은 그대로고 invasion 은 말씨 문제라 ~ 다. B의 뜻은 X 가 아니었다.]

## 14
    한국어  왜 하필 한국 금융과 자산운용을 표적했나

    A  뜻[~] 말씨[O]  Why are you targeting Korean finance and assets?
    B  뜻[X] 말씨[~]  Why did we specifically choose Korean finance and asset management as the target?

    근거  A는 자산운용을 assets 로 줄여 범위가 흐려졌지만 질문은 성립하고 Why are you targeting ...? 은 채팅에 칠 법하다. B는 주어가 we 라서 묻는 쪽이 공격 주체가 되는 치명적 뒤집힘이고, 문장 자체는 문법은 맞아도 as the target 이 딱딱하다.

## 15
    한국어  게시가 내려간 피해사가 있나

    A  뜻[X] 말씨[X]  Is there victim organization that she went down?
    B  뜻[X] 말씨[X]  Is there a victim organization that has posted something down?

    근거  A는 원문에 없는 she 가 들어가고 관사도 빠져 「그녀가 쓰러뜨린 피해자」라는 딴 문장이 됐다. B는 '게시가 내려갔다'를 posted something down 으로 옮겨 방향이 뒤집혔고 그 표현 자체가 영어로 뜻이 안 통한다.

## 16
    한국어  실제 피해 규모 주장은 어피실리에이트 산출인가 운영자 집계인가

    A  뜻[~] 말씨[X]  Is the actual damage-scale argument affiliates output or operator count?
    B  뜻[~] 말씨[~]  Actual damage claims are attributed to affiliates or calculated by the operator?

    근거  A는 주장을 argument 로 잘못 골랐지만 계열사 산출 대 운영자 집계 대비는 남는다. 다만 damage-scale argument affiliates output or operator count 는 동사도 관사도 없는 명사 나열이라 사람이 안 쓰는 문장이다. B는 attributed to 가 '산출'보다 약하고 damage claims 가 보험 청구로 읽힐 여지가 있으며, 평서문에 물음표만 붙인 꼴이라 딱딱하다.

## 17
    한국어  초기 접근은 주로 구매인가 직접 침투인가

    A  뜻[~] 말씨[X]  initial access is usually a purchase or is it a direct invasion?
    B  뜻[X] 말씨[X]  Initial access is usually purchased directly or through infiltration.

    근거  A는 구매냐 직접 침투냐 양자택일 구도는 살렸으나 주체(you)가 없고 침투를 invasion으로 옮겨 모호하다. 소문자 시작에 앞 절이 도치되지 않아 'initial access is usually a purchase or is it...' 처럼 덜컹거린다. B는 평서문으로 바뀌었고 'purchased directly or through infiltration' 이라 두 선택지가 모두 구매가 되어 대립 자체가 사라졌다. 물음표도 없어 질문으로 안 읽힌다.

## 18
    한국어  이중 갈취 외에 추가 압박 수단을 쓰나

    A  뜻[O] 말씨[O]  Do you use extra pressure besides double extortion?
    B  뜻[O] 말씨[O]  Double extortion, any other pressure tactics?

    근거  둘 다 이중 갈취 외 추가 압박 수단을 묻는 뜻이 그대로 간다. A는 짧고 곧은 의문문이고, B는 'Double extortion, any other pressure tactics?' 로 채팅에서 실제로 치는 생략형이다.

## 19
    한국어  지불 기한은 어떻게 잡나

    A  뜻[~] 말씨[X]  How do we get payment deadline?
    B  뜻[~] 말씨[O]  When is the payment deadline?

    근거  A는 주어가 we로 뒤집혀 '우리가 어떻게 기한을 받나'가 됐고 set 대신 get, 관사도 빠졌다. B는 'When is the payment deadline?' 이라 기한을 정하는 방식을 묻던 질문이 기한 날짜를 묻는 질문으로 바뀌었다. 다만 B의 영어 자체는 채팅에 그대로 칠 만하다. [반박: A 를 ~ 로 — A는 주어가 흐려졌을 뿐 'how + payment deadline'이 남아 기한을 정하는 방식에 대한 답이 돌아온다. B도 의문문이고 상대가 '보통 72시간' 식으로 답해 원 질문과 겹친다 — 둘 다 어색할 뿐이라 ~.] [반박: B 를 ~ 로 — A는 주어가 흐려졌을 뿐 'how + payment deadline'이 남아 기한을 정하는 방식에 대한 답이 돌아온다. B도 의문문이고 상대가 '보통 72시간' 식으로 답해 원 질문과 겹친다 — 둘 다 어색할 뿐이라 ~.]

## 20
    한국어  암호화 없이 유출 협박만 하는 경우도 있나

    A  뜻[~] 말씨[~]  Is there any chance you're threatening to leak without encryption?
    B  뜻[~] 말씨[X]  Is it possible to have a situation where someone leaks information without encryption and just uses blackmail?

    근거  A는 '그럴 가능성이 있나' 투라 관행을 묻는 질문이 이번 건을 떠보는 추궁처럼 읽히고 '~하는 경우도'의 상시성이 빠졌다. B는 뜻은 통하지만 주체가 someone으로 흐려졌고 'Is it possible to have a situation where...' 가 장황해 채팅에서 쓰는 말이 아니다.

## 21
    한국어  연락처를 얼마나 자주 바꾸나

    A  뜻[O] 말씨[X]  How often do you change your contact
    B  뜻[O] 말씨[O]  How often do you change your contact information?

    근거  뜻은 둘 다 맞다. A는 문장이 'your contact' 에서 끊기고 물음표가 없어 질문으로 안 읽히며 contact가 연락처인지 연락책인지 모호하다. B는 contact information으로 명확하고 물음표까지 있어 그대로 보낼 수 있다.

## 22
    한국어  방탄호스팅을 쓰나

    A  뜻[X] 말씨[X]  Do I write bulletproof hosting?
    B  뜻[~] 말씨[~]  Is bulletproof hosting used?

    근거  A는 주어가 I로 뒤집히고 '쓰나'를 write로 옮겨 '내가 방탄호스팅을 작성하나'라는 말이 안 되는 문장이 됐다. B는 수동태라 뜻은 통하지만 '당신들이 쓰나'라는 상대 지목이 사라졌고, 채팅이라면 Do you use bulletproof hosting? 이 자연스럽다.

## 23
    한국어  압수 이후 재브랜딩 계획이 있나

    A  뜻[O] 말씨[O]  Do you have a plan for rebranding after the seizure?
    B  뜻[X] 말씨[X]  After cooling, is there a rebranding plan?

    근거  A는 압수를 seizure로 정확히 옮겼고 짧은 의문문이라 그대로 보낼 수 있다. B는 압수를 cooling(냉각)으로 잘못 옮겨 압수 이후라는 핵심 조건이 통째로 없어졌고, 'After cooling' 은 상대가 뜻을 짐작할 수도 없다.

## 24
    한국어  과거 다른 그룹명에서 넘어온 인력이나 코드가 있나

    A  뜻[O] 말씨[~]  Do you have any personnel or code from any other group names in the past?
    B  뜻[O] 말씨[~]  Are there any employees or code from a previous group?

    근거  둘 다 과거 그룹에서 넘어온 인력·코드를 묻는 뜻은 간다. A는 personnel이 딱딱하고 'in the past' 가 문장 끝에 붙어 어순이 직역 티가 난다. B는 짧고 매끄럽지만 employees가 기업 말투라 이 판에서는 people이나 members가 맞고, '다른 그룹명(브랜드)' 의 복수 뉘앙스가 a previous group으로 줄었다.

## 25
    한국어  지불하지 않으면 데이터를 제3의 포럼이나 마켓에 재판매하나

    A  뜻[~] 말씨[~]  If you don't pay for it, do you give the data to the third forum or to the market?
    B  뜻[X] 말씨[X]  If you don't pay, you'll have to sell the data to a third forum or market.

    근거  A는 의문문은 지켰으나 「재판매」를 give(무상 제공)로 바꿔 핵심인 판매 여부가 빠졌고 「제3의 포럼」이 the third forum(세 번째 포럼)이 됐다. B는 의문문이 평서문 명령조(you'll have to sell)가 되어 상대가 답할 자리가 없고, 파는 주체도 상대에게 떠넘겨졌다.

## 26
    한국어  삭제된 게시물의 데이터도 여전히 보유하고 있나

    A  뜻[~] 말씨[O]  Do you still have the data for the deleted items?
    B  뜻[~] 말씨[X]  Deleted posts still have their data still owned.

    근거  A는 짧은 의문문으로 자연스러우나 「게시물」을 deleted items로 뭉개 유출 사이트 게시글인지 파일인지 모호하다. B는 Deleted posts still have their data still owned 로 주어가 뒤집혀 게시물이 데이터를 보유한다는 뜻이 됐고, still 이 두 번 겹친 비문에 물음표도 없다. [반박: B 를 ~ 로 — 문법은 깨졌지만 삭제 게시물 데이터를 아직 보유하냐는 내용은 그대로 남아 상대가 못 알아볼 정도는 아니다. 어색함이지 뜻의 오류가 아니다.]

## 27
    한국어  과거 컬렉션과 데이터가 겹치거나 소스로 쓴 적이 있나

    A  뜻[~] 말씨[X]  Have you ever had past collections and data overlap or write them as sources?
    B  뜻[O] 말씨[~]  Have you ever had the past collection and data overlap or used it as a source?

    근거  A는 「소스로 쓴」의 쓰다를 write 로 직역해 뒷절이 무의미해졌고, had ... overlap or write 로 동사 시제가 어긋난 비문이다. B는 used it as a source 로 뒷절을 살려 뜻이 통하나 the past collection and data overlap 어순이 덜컹거린다.

## 28
    한국어  잠깐 시간 되나요?

    A  뜻[O] 말씨[O]  Can I have a moment?
    B  뜻[X] 말씨[X]  Okay, time?

    근거  A는 채팅에서 그대로 칠 만한 짧은 의문문이다. B는 Okay, time? 이라는 두 단어 파편이라 시간이 되냐는 요청 자체가 사라졌고 상대가 무슨 말인지 못 알아본다.

## 29
    한국어  글 봤습니다. 몇 가지 물어봐도 될까요?

    A  뜻[~] 말씨[O]  I read it. Can I ask you a few questions?
    B  뜻[~] 말씨[X]  I saw the post. Several questions can be asked, can't they?

    근거  A는 「글」을 it 으로 받아 무엇을 봤는지 지시 대상이 빠졌지만 허락을 구하는 질문 형태와 말씨는 자연스럽다. B는 첫 문장은 정확하나 뒷문장이 Several questions can be asked, can't they? 라는 수동+부가의문으로, 허락 요청이 동의 확인처럼 비틀렸고 채팅에서 쓰지 않는 어투다.

## 30
    한국어  답 주셔서 고맙습니다.

    A  뜻[O] 말씨[O]  Thank you for your response.
    B  뜻[O] 말씨[~]  Thank you for your answer.

    근거  둘 다 감사 뜻은 그대로다. A의 Thank you for your response 는 무난하고, B의 for your answer 는 대화 맥락에서 덜 쓰는 조합이라 약간 번역투로 읽힌다.

## 31
    한국어  알겠습니다.

    A  뜻[~] 말씨[X]  Yes, sir.
    B  뜻[O] 말씨[O]  Okay.

    근거  A의 Yes, sir 는 원문에 없는 상하관계와 복종 뉘앙스를 더해 군대·경찰 말투로 들리고, 범죄 운영자 상대 채팅에서는 비꼬는 것으로 읽힐 수 있다. B의 Okay 는 알겠다는 뜻과 채팅 말씨가 모두 맞다.

## 32
    한국어  이해했습니다.

    A  뜻[O] 말씨[O]  I get it.
    B  뜻[O] 말씨[O]  I understand.

    근거  A의 I get it 과 B의 I understand 모두 이해했다는 뜻이 그대로 가고 채팅에서 바로 칠 수 있는 문장이다.

## 33
    한국어  그럴 만하네요.

    A  뜻[~] 말씨[O]  Well, that's worth it.
    B  뜻[O] 말씨[O]  That makes sense.

    근거  A는 「납득된다」를 "worth it"(가치가 있다)로 바꿔 뜻이 달라졌다. 말씨는 채팅체로 자연스럽다. B는 뜻과 말씨 모두 맞다. [반박: A 를 ~ 로 — 「그럴 만하네요」는 「이해된다」는 맞장구인데 A의 "that's worth it"은 「가치가 있다」로 읽혀 뜻이 어긋난다. 다만 질문이 아니라 짧은 맞장구라 상대가 답을 못 하게 되지는 않고, 「그럴 만하다」에 원래 「할 만하다」는 뜻도 있어 완전한 오역으로 단정하기 애매하다. 조사가 망가지는 수준은 아니므로 X 가 아니라 ~ 다.]

## 34
    한국어  네, 말이 되네요.

    A  뜻[O] 말씨[O]  Yeah, that makes sense.
    B  뜻[~] 말씨[~]  Yes, that's right.

    근거  A는 "Yeah, that makes sense."로 「말이 되네요」의 납득을 그대로 옮겼다. B의 "that's right"는 논리적 납득이 아니라 사실 확인 동의로 읽혀 어긋나고, Yes 쪽이라 채팅보다 딱딱하다.

## 35
    한국어  그 부분을 좀 더 설명해 주실 수 있나요?

    A  뜻[~] 말씨[O]  Can you explain that part for me?
    B  뜻[O] 말씨[O]  Can you explain that part a bit more?

    근거  A는 「좀 더」(a bit more)가 빠져 이미 한 설명에 덧붙여 달라는 뉘앙스가 사라졌다. 말씨는 둘 다 짧고 자연스럽고, B는 "a bit more"까지 살렸다.

## 36
    한국어  제가 이해한 게 맞는지 확인하고 싶습니다.

    A  뜻[O] 말씨[~]  I want to make sure that what I understand is right.
    B  뜻[O] 말씨[O]  I want to check if I understand it correctly.

    근거  둘 다 뜻은 맞다. A의 "make sure that what I understand is right"는 관계절이 겹쳐 장황한 번역투다. B는 "check if I understand it correctly"로 간결하다.

## 37
    한국어  정확히 어떤 뜻인가요?

    A  뜻[O] 말씨[O]  What exactly does that mean?
    B  뜻[O] 말씨[X]  Exactly what meaning does it have?

    근거  뜻은 둘 다 통한다. B의 "Exactly what meaning does it have?"는 한국어 어순을 그대로 옮긴 비틀린 의문문이라 원어민이 쓰지 않는다. A는 관용적 어순이다.

## 38
    한국어  그건 어디서 나온 건가요?

    A  뜻[O] 말씨[O]  Where did that come from?
    B  뜻[O] 말씨[O]  Where did that come from?

    근거  A와 B가 같은 문장이고, "Where did that come from?"은 출처를 묻는 채팅체 그대로다.

## 39
    한국어  그건 어떻게 아시나요?

    A  뜻[O] 말씨[O]  How do you know that?
    B  뜻[O] 말씨[O]  How do you know that?

    근거  A와 B가 같은 문장이고, "How do you know that?"은 짧고 곧아 그대로 칠 수 있다.

## 40
    한국어  다시 말씀해 주시겠어요? 문장이 깨졌습니다.

    A  뜻[~] 말씨[~]  Can you repeat that? The sentence was broken.
    B  뜻[~] 말씨[X]  Again, please tell me? The sentence is broken.

    근거  둘 다 "The sentence is/was broken"이라 문자가 깨졌다는 뜻이 아니라 비문이라는 말로 읽혀 모호하다(garbled 쪽이 맞다). 앞 문장은 A의 "Can you repeat that?"이 자연스럽고, B의 "Again, please tell me?"는 어순이 부서진 의문문이다.

## 41
    한국어  방금 말씀하신 것과 앞에서 하신 말씀이 안 맞는 것 같은데요.

    A  뜻[~] 말씨[~]  I don't think you're right about what you just said and what you said.
    B  뜻[X] 말씨[X]  Just what you said and what I said before seems not to match.

    근거  A는 「두 말이 서로 안 맞는다」는 모순 지적을 「네 말이 틀렸다(you're not right)」는 단정으로 바꿨고, 뒤의 what you said 에 「앞에서」가 없어 같은 말을 두 번 가리켜 헛돈다. B는 뒤를 what I said before 로 해서 화자 자신의 말과 대조하는 것으로 주체가 뒤집혔고, Just what you said / seems not to match 는 어순이 직역이라 사람이 안 쓴다 [반박: A 를 ~ 로 — A는 두 발언을 같이 지목한 신빙성 도전이라 해명을 끌어내므로 뜻이 흐려진 정도다. B는 대조 대상이 화자 자신의 말로 바뀌어 지적이 엉뚱한 곳을 겨눈다]

## 42
    한국어  잠시만요.

    A  뜻[~] 말씨[~]  Excuse me.
    B  뜻[O] 말씨[O]  Just a moment.

    근거  A의 Excuse me 는 「잠시만요(기다려 달라)」가 아니라 주의를 끌거나 불쾌감을 드러내는 말로 읽혀 뜻이 모호하다. B의 Just a moment 는 대기 요청으로 정확하고 채팅에 그대로 칠 만하다

## 43
    한국어  잠깐만요, 확인해 볼게요.

    A  뜻[O] 말씨[O]  Wait, let me check it out.
    B  뜻[O] 말씨[~]  Just a moment, I'll check it over.

    근거  A의 Wait, let me check it out 은 뜻과 말씨 모두 자연스러운 채팅체다. B는 뜻은 같지만 check it over 가 「꼼꼼히 검토하다」쪽이라 짧게 확인하는 상황과 어긋나고, Just a moment 와 겹쳐 한 박자 딱딱하다

## 44
    한국어  알아보고 다시 말씀드리겠습니다.

    A  뜻[~] 말씨[~]  I'll figure it out and I'll tell you again.
    B  뜻[~] 말씨[~]  I'll remember and say it again.

    근거  원문은 「알아본 뒤 다시 연락드리겠다(get back to you)」인데 A는 tell you again 이라 「같은 말을 되풀이하겠다」로 읽힐 여지가 있고 I'll 을 두 번 반복해 덜컹거린다. B는 알아보다를 remember 로 옮겨 「기억했다가 다시 말하겠다」가 되어 약속의 내용 자체가 바뀌었다 [반박: B 를 ~ 로 — B의 remember는 알아본다는 내용을 깎지만 나중에 다시 말하겠다는 닫는 인사 기능은 남아 상대가 잘못 움직이지 않는다]

## 45
    한국어  죄송합니다, 타자가 느립니다.

    A  뜻[~] 말씨[~]  Sorry, typing is slow.
    B  뜻[X] 말씨[O]  I'm sorry, someone else is feeling bad.

    근거  A는 소유격이 없는 typing is slow 라 「내 타자가 느리다」가 아니라 회선이나 시스템이 느리다는 뜻으로도 읽힌다. B는 타자를 다른 사람으로, 느리다를 기분이 안 좋다로 잘못 읽어 전혀 다른 문장이 됐다(문장 자체는 영어로는 매끄럽다)

## 46
    한국어  몇 분만 주세요.

    A  뜻[O] 말씨[O]  Give me a few minutes.
    B  뜻[X] 말씨[O]  How many minutes?

    근거  A의 Give me a few minutes 는 요청 그대로다. B는 「몇 분만 달라」는 요청을 How many minutes? 라는 되묻기로 뒤집어 상대가 시간을 답해야 하는 상황이 된다(짧은 채팅체이긴 하다)

## 47
    한국어  말씀하기 어려우면 괜찮습니다.

    A  뜻[~] 말씨[O]  It's okay if it's hard to talk.
    B  뜻[X] 말씨[X]  Speaking is difficult for me.

    근거  A는 뜻이 대체로 통하나 주어가 없어 hard to talk 가 「대화하기 곤란한 상황」으로도 읽혀 「답 안 해도 된다」는 배려가 흐려진다. B는 difficult for me 로 어려운 쪽이 상대가 아니라 화자가 되어 뜻이 뒤집혔고, Speaking is difficult for me 는 교과서 문장투다

## 48
    한국어  알겠습니다, 그건 넘어가죠.

    A  뜻[O] 말씨[O]  Okay, let's move on.
    B  뜻[~] 말씨[~]  Okay, that's okay. Let's move on.

    근거  A의 Okay, let's move on 은 짧고 곧아 그대로 보낼 만하다. B는 원문에 없는 that's okay 를 넣어 「괜찮다고 봐준다」는 뉘앙스가 붙었고 Okay 가 연달아 두 번 나와 군더더기로 읽힌다

## 49
    한국어  사려는 게 아닙니다.

    A  뜻[~] 말씨[O]  I'm not buying it.
    B  뜻[~] 말씨[O]  I don't want to.

    근거  A "I'm not buying it"은 문자 그대로 구매 거절로도 읽히지만 영어 관용구로는 「못 믿겠다」가 더 강해 상대가 반박으로 오해할 수 있다(말씨는 짧고 채팅투). B "I don't want to"는 목적어 buy 가 통째로 빠져 「사려는 게 아니다」가 「하기 싫다」로 바뀌었다. [반박: B 를 ~ 로 — B "I don't want to"는 목적어가 빠졌지만 구매 제안에 대한 생략 응답으로 읽혀 「안 산다」가 전달된다. 단독 첫마디면 모호해질 뿐이니 X 가 아니라 ~ 다. A 는 원래 X 가 아니라 건드리지 않는다.]

## 50
    한국어  대가로 드릴 수 있는 것이 없습니다.

    A  뜻[X] 말씨[O]  There's nothing you can give in return.
    B  뜻[X] 말씨[X]  There's nothing I can drill with the bail.

    근거  A 는 주어가 뒤집혔다 — 「내가 줄 것이 없다」가 "There's nothing you can give in return"(네가 줄 게 없다)이 됐다. 문장 자체는 자연스럽다. B 는 「대가」를 bail(보석), 「드릴」을 drill(뚫다)로 받아 뜻이 사라진 무의미 문장이다.

## 51
    한국어  그건 말씀드릴 수 없습니다.

    A  뜻[~] 말씨[O]  I can't say that.
    B  뜻[O] 말씨[O]  That's something I can't tell you.

    근거  A "I can't say that"은 상대(you)가 빠져 「그 말을 할 수는 없다」로도 읽히는 모호함이 있으나 거절로는 통하고 말씨는 채팅투다. B "That's something I can't tell you"는 비공개 거절이 정확히 가고 어순도 자연스럽다.

## 52
    한국어  그 부분은 이야기하지 않겠습니다.

    A  뜻[O] 말씨[O]  I'm not going to talk about that.
    B  뜻[O] 말씨[X]  That part I won't tell you.

    근거  A "I'm not going to talk about that"은 화제 거부가 그대로 가고 실제 채팅에 칠 법한 문장이다. B 는 뜻은 같지만 "That part I won't tell you"로 목적어를 앞으로 뺀 직역 어순이라 원어민이 쓰지 않는 덜컹거리는 문장이다.

## 53
    한국어  여기까지입니다. 시간 내 주셔서 고맙습니다.

    A  뜻[O] 말씨[O]  That's it. Thank you for your time.
    B  뜻[~] 말씨[X]  Here it is. Time you've given me, thank you.

    근거  A "That's it. Thank you for your time"은 마무리 인사로 정확하고 자연스럽다. B 는 「여기까지입니다」를 물건을 건네는 "Here it is"로 잘못 옮겼고, "Time you've given me, thank you"는 어순이 깨진 직역이다. [반박: B 를 ~ 로 — B "Here it is"는 어색하지만 뒤에 붙은 시간 감사 인사가 마무리라는 것을 살려 줘 사인오프로 읽힌다. 질문도 아니어서 답을 막지 않으니 ~ 다. A 는 원래 X 가 아니다.]

## 54
    한국어  더 있으면 다시 연락드리겠습니다.

    A  뜻[~] 말씨[O]  I'll call you back when we have more.
    B  뜻[~] 말씨[~]  There's more, I'll call you back.

    근거  A 는 뜻이 통하나 텔레그램 채팅에서 "call you back"은 전화 뉘앙스라 get back to you 가 맞고, 「더 있으면」을 when 으로 바꿔 조건이 약해졌다. B 는 조건절이 통째로 빠져 "There's more"로 더 있다고 단정해 버렸고 접속사 없이 이어 붙여 끊긴다. [반박: B 를 ~ 로 — B 는 조건절이 빠져 단정이 됐지만 「다시 연락하겠다」는 본래 기능은 그대로 전달돼 조사가 망가지지 않는다. 뉘앙스 손실이라 ~ 다. A 는 원래 X 가 아니다.]

## 55
    한국어  게시가 내려간 피해사가 있나요?

    A  뜻[X] 말씨[X]  Is there victim organization that she went down?
    B  뜻[X] 말씨[O]  Is there a victim organization that has posted something?

    근거  A 는 관사가 빠지고 없는 주어 she 가 들어가 "that she went down"이 되어 뜻이 무너졌다. B 는 문법과 말씨는 자연스러운 의문문이지만 「게시가 내려간」이 "has posted something"(게시를 올린)으로 정반대가 됐다.

## 56
    한국어  제외하는 국가나 업종이 있나요?

    A  뜻[X] 말씨[X]  Is there any country or industry sector.
    B  뜻[O] 말씨[O]  Are there any countries or industries excluded?

    근거  A 는 핵심어 「제외하는」이 통째로 빠져 「국가나 업종이 있나」가 됐고, 마침표로 끝나 질문으로 읽히지 않으며 수 일치도 어색하다. B "Are there any countries or industries excluded?"는 제외 조건이 살아 있고 그대로 칠 만한 의문문이다.

## 57
    한국어  지불 기한은 어떻게 잡나요?

    A  뜻[~] 말씨[X]  How do we get payment deadline?
    B  뜻[~] 말씨[X]  Payment deadline how to set?

    근거  A는 주체가 we 로 뒤집혀 「우리가 기한을 어떻게 받나」가 됐다. 상대가 기한을 어떻게 정하는지 묻는 원문과 다르고 a/the 도 없다. B 는 Payment deadline how to set 으로 주어와 동사가 없는 어순 붕괴라 누가 정하는지 모호하고 채팅에서도 비문으로 읽힌다. [반박: A 를 ~ 로 — A는 주어가 we 로 흔들려도 지불 기한을 묻는 의문문이 유지되고 상대가 낼 답이 곧 원하는 사실이라 X 가 아니라 ~ 다. 주어 어색함은 말씨 축 몫이다.]

## 58
    한국어  지금도 신규 어피실리에이트를 받고 있나요?

    A  뜻[O] 말씨[~]  Are you still getting the new affiliates?
    B  뜻[O] 말씨[O]  Are you still getting new affiliates?

    근거  뜻은 둘 다 간다. A 의 the new affiliates 는 이미 언급된 특정 신규 어피를 가리키는 것처럼 읽혀 덜컹거린다. B 는 관사를 빼 Are you still getting new affiliates? 로 그대로 칠 만하다.

## 59
    한국어  제가 이해한 것이 맞는지 확인하고 싶습니다. 파일 백만 개가 넘는다는 주장이 맞나요?

    A  뜻[O] 말씨[~]  I want to make sure that what I understand is right. You're saying there are more than one million files?
    B  뜻[O] 말씨[~]  I want to check if I understand it correctly. Is the claim that there are over a million files correct?

    근거  둘 다 확인 요청과 백만 건 주장을 다 옮겼다. A 의 뒷문장 You're saying there are more than one million files? 는 채팅투로 좋으나 앞문장 make sure that what I understand is right 가 장황하다. B 의 Is the claim that ... correct? 는 설문지 문어체라 실시간 대화에서 딱딱하다.

## 60
    한국어  운영자와 어피실리에이트의 역할 경계는 어디까지이고, 어피실리에이트에게 무엇을 제공하나요?

    A  뜻[O] 말씨[X]  What's the role boundary between the operator and affiliates, and what does it provide for affiliates.
    B  뜻[~] 말씨[X]  What is the boundary between the operator and affiliates, and what does affiliates provide?

    근거  B 는 뒷절이 what does affiliates provide 로 제공 주체가 어피실리에이트로 뒤집혔다. 원문은 운영자가 어피에게 무엇을 주느냐다. 수 일치도 does affiliates 로 깨졌다. A 는 뜻은 맞지만 물음표가 없어 진술로 읽히고 role boundary 가 직역 티가 난다. [반박: B 를 ~ 로 — B 뒷절은 does/affiliates 수 불일치로 주어가 확정되지 않아 방향이 모호하고, 앞절이 멀쩡한 데다 어느 쪽에 답했는지가 답변에 드러나 한 턴 손해에 그친다.]

## 61
    한국어  왜 하필 그 업종을 골랐는지 물어봐도 될까요?

    A  뜻[O] 말씨[X]  Can I ask why you picked that industry sector.
    B  뜻[~] 말씨[O]  Why did you choose that industry sector?

    근거  A 는 물어봐도 될까요까지 살렸으나 물음표가 없어 질문으로 안 읽힌다. B 는 짧고 곧아 채팅투는 좋은데 양해를 구하는 틀이 사라져 왜 그 업종을 골랐냐는 직설 추궁이 됐다. 상대가 방어할 여지가 커진다.

## 62
    한국어  게시글은 봤습니다. 다만 규모가 주장과 안 맞는 것 같아서요. 어디서 나온 숫자인가요?

    A  뜻[~] 말씨[X]  I've seen post. I just don't think the scale fits the argument. Where did that come from?
    B  뜻[O] 말씨[~]  I've seen the post. But the size seems to not match what's being claimed. Where did the number come from?

    근거  A 는 주장을 argument 로 옮겨 논쟁이라는 뜻이 되고 마지막 Where did that come from 이 숫자를 안 가리켜 무엇을 묻는지 흐려진다. I've seen post 는 관사가 빠져 덜컹거린다. B 는 세 조각을 다 옮겼고 the number 도 짚었다. 다만 seems to not match 는 doesn't seem to match 가 자연스럽다.

## 63
    한국어  저희는 이 건이 다른 사건과 이어져 있는지 보고 있습니다. 혹시 같은 자료를 전에 다른 곳에 올리신 적이 있나요?

    A  뜻[~] 말씨[O]  We're looking at whether this is connected to another case. Have you posted the same data before?
    B  뜻[O] 말씨[X]  We are looking into whether this case is connected to another one. Do you ever put the same data in another place before?

    근거  A 는 다른 곳에 가 빠져 같은 자료를 전에 올린 적 있냐는 질문이 돼, 다른 포럼·마켓 재게시라는 핵심을 못 짚는다. 말씨는 두 문장 다 자연스럽다. B 는 in another place before 로 조건은 살렸지만 Do you ever put ... before? 라 현재형과 before 가 충돌하는 비문이다.

## 64
    한국어  답을 강요하려는 것은 아닙니다. 다만 공개된 분석과 어긋나는 부분이 있어서 확인하고 싶었습니다.

    A  뜻[~] 말씨[X]  I'm not trying to force the answer. I just wanted to make sure that there was something out there that was against public analysis.
    B  뜻[~] 말씨[~]  It's not required to force an answer. But there are parts that don't match the published analysis, so I wanted to check it out.

    근거  A 는 뒷문장에서 인과가 뒤집혀 「공개 분석에 반하는 무언가가 존재하는지 확인하고 싶었다」가 됐다. 어긋나는 부분이 있어서 확인한다는 원문과 다르고 something out there that was against 가 장황하다. B 는 뒷문장이 정확하지만 첫 문장이 It's not required to force an answer 라 행위자가 사라져 「답을 강요할 필요는 없다」로 읽힌다. [반박: A 를 ~ 로 — 이 줄은 질문이 아니라 해명 문장이고 A 에도 공개 분석과 어긋난다는 요지와 확인 의도가 둘 다 남아 있어 인과가 흐릿할 뿐이다.]

