// 안내문 확인 세 단계. 고른 값은 브라우저 저장으로 다음 단계에 넘깁니다. 주소에는 싣지 않습니다.
import { useEffect, useState } from "preact/hooks";
import { Ico } from "../lib/icons";
import { data } from "../lib/data";
import { emptyDraft, loadDraft, saveDraft, takeFlowReset, type Draft } from "../lib/store";
import { Board } from "./parts";
import type { ItemId } from "../lib/types";

export default function Notice({ step }: { step: 1 | 2 | 3 }) {
  const [d, setD] = useState<Draft>(emptyDraft());
  // 밖에서 들어왔으면 새로 시작하고, 단계 사이를 오가거나 대응 한 장에서 돌아왔으면 고른 값을 이어 갑니다
  useEffect(() => { if (takeFlowReset()) { const v = emptyDraft(); saveDraft(v); setD(v); } else setD(loadDraft()); }, [step]);
  const up = (n: Partial<Draft>) => { const v = { ...d, ...n }; setD(v); saveDraft(v); };
  const sel = new Set<ItemId>(d.sel);
  const suspect = !!d.suspect;

  const bar = (
    <div class="stepper" aria-label={`3단계 중 ${step}단계`}>
      <i class={step >= 1 ? "on" : ""}></i><i class={step >= 2 ? "on" : ""}></i><i class={step >= 3 ? "on" : ""}></i><span>{step} / 3</span>
    </div>
  );

  if (step === 1) return (
    <>
      <div class="stack"><a class="back" href="/">처음으로</a>{bar}</div>
      <div><h1 tabindex={-1}>받은 안내, 진짜일까요?</h1><p class="lede">유출 안내를 흉내 낸 사기 문자가 실제로 돌고 있어요. 받은 문자를 아래 두 예시와 비교해 보세요.</p></div>
      <div class="pair">
        <div><div class="verdict ok"><Ico id="check" />정상적인 안내 예시</div>
          <div class="phone"><div class="from">○○쇼핑 1588-0000</div><div class="bubble">[○○쇼핑] 고객님의 개인정보(이름, 전화번호)가 유출된 사실을 확인하여 알려드립니다. 자세한 내용은 ○○쇼핑 앱의 공지사항에서 확인하실 수 있습니다.</div></div>
          <div class="flags"><div class="flag good"><b>1</b><span>링크 없이 공식 앱이나 홈페이지에서 확인하라고 안내해요.</span></div><div class="flag good"><b>2</b><span>회사 대표번호로 발송됐어요.</span></div></div></div>
        <div><div class="verdict bad"><Ico id="alert" />사기 문자 예시</div>
          <div class="phone"><div class="from">070-0000-0000</div><div class="bubble">[○○쇼핑] 개인정보 유출 <u>피해보상금 30만 원</u> 지급 대상입니다. 아래 링크에서 신청하세요. <u>bit.ly/xxxxx</u></div></div>
          <div class="flags"><div class="flag"><b>1</b><span>보상금이나 환급금을 준다고 해요.</span></div><div class="flag"><b>2</b><span>링크를 누르라고 해요.</span></div><div class="flag"><b>3</b><span>070 번호나 처음 보는 번호로 왔어요.</span></div></div></div>
      </div>
      {suspect ? (
        <div class="alarm" style="animation:enter .25s var(--ease)"><h3>링크를 누르지 말고 먼저 문의하세요</h3><p>개인정보침해 신고센터(118)에서 무료로 상담받을 수 있어요. 받은 문자 내용을 알려주면 진위를 함께 확인해 줘요.</p>
          <div class="row"><a class="btn" href="tel:118">118에 전화하기</a><a class="btn2" href="/notice/2/">그래도 대응 방법 보기</a></div></div>
      ) : (
        <div class="row"><a class="btn" href="/notice/2/">정상적인 안내 같아요</a><button type="button" class="btn2" onClick={() => up({ suspect: true })}>의심스러워요</button></div>
      )}
    </>
  );

  if (step === 2) return (
    <>
      <div class="stack"><a class="back" href="/notice/1/">이전</a>{bar}</div>
      <div><h1 tabindex={-1}>안내문에서 다섯 가지를 확인하세요</h1><p class="lede">회사는 유출 사실을 알릴 때 다음 다섯 가지를 반드시 포함해야 해요. 빠진 내용이 있다면 회사에 문의할 수 있어요.</p></div>
      <div class="letter"><div class="hd">○○쇼핑 개인정보 유출 안내<span>안내문 예시</span></div><div class="lines">
        {[["유출된 항목", "이름, 전화번호처럼 어떤 정보가 유출됐는지 적혀 있어요. 다음 단계에서 이 항목을 선택해요."], ["유출 시점과 경위", "언제, 어떤 경로로 유출됐는지 적혀 있어요."], ["피해를 줄이기 위해 할 수 있는 방법", "비밀번호 변경처럼 내가 직접 할 수 있는 일이에요."], ["회사의 대응 조치와 피해 구제 절차", "회사가 무엇을 하고 있고, 피해를 어떻게 보상받는지 적혀 있어요."], ["신고와 상담을 받는 부서, 연락처", "궁금한 점이나 피해를 알릴 곳이에요."]].map(([h, p], i) => (
          <div class="ln"><span class="n">{i + 1}</span><div><h3>{h}</h3><p>{p}</p></div></div>
        ))}
      </div></div>
      <div class="stack"><h2>안내문에는 어떻게 적혀 있나요?</h2>
        <div class="row">
          {[["sure", "유출됐다고 적혀 있어요"], ["maybe", "유출됐을 가능성이 있다고 적혀 있어요"], ["unk", "잘 모르겠어요"]].map(([id, l]) => (
            <button type="button" class="btn2" aria-pressed={d.ntype === id} onClick={() => up({ ntype: id })}>{l}</button>
          ))}
        </div>
        {d.ntype === "maybe" ? <p class="note" style="animation:enter .22s var(--ease)">2026년 9월 11일부터 회사는 유출이 확정되지 않았더라도 가능성이 있으면 알려야 해요. 다른 사람의 정보가 유출된 것이 확인되어 내 정보도 유출됐을 수 있다는 뜻이에요. 확정이 아니더라도 대응은 미리 해 두는 편이 안전해요.</p> : null}
      </div>
      <div class="row"><a class="btn" href="/notice/3/">다음</a></div>
    </>
  );

  return (
    <>
      <div class="stack"><a class="back" href="/notice/2/">이전</a>{bar}</div>
      <div><h1 tabindex={-1}>안내문에 적힌 유출 항목을 선택하세요</h1><p class="lede">해당하는 항목만 누르면 돼요. 실제 이름이나 번호는 입력하지 않아요.</p></div>
      <div class="linkscope"><Board sel={sel} claimed={new Set()} onToggle={(id) => { const s = new Set(sel); s.has(id) ? s.delete(id) : s.add(id); up({ sel: [...s] }); }} /></div>
      <div class="stack"><div><h2>안내를 받은 지 얼마나 됐나요?</h2><p class="small" style="margin-top:4px">유출된 정보는 시간이 지나면서 판매되거나 무료로 공개되기도 해요. 그에 따라 먼저 할 일이 달라져요.</p></div>
        <div class="when">{data.when.map((w) => <button type="button" class="btn2" aria-pressed={d.when === w.id} onClick={() => up({ when: w.id })}>{w.label}</button>)}</div></div>
      <div class="row"><a class="btn" href="/plan/">대응 방법 보기</a>{sel.size ? null : <span class="small">항목을 하나도 고르지 않으면 기본 대응만 안내해요.</span>}</div>
    </>
  );
}
