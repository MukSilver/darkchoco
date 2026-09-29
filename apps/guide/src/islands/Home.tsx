// 입구. 문 둘과, 저장된 진행이 있으면 이어서 보기 카드
import { useEffect, useState } from "preact/hooks";
import { Ico, Ring } from "../lib/icons";
import { data } from "../lib/data";
import { levels, pick, stageOf } from "../lib/rules";
import { loadPlan, forgetPlan, type Draft, saveDraft } from "../lib/store";
import { toast } from "../lib/ui";
import { MiniTrail, Timeline } from "./parts";
import type { ItemId, Plan } from "../lib/types";

function summary(p: Plan) {
  const c = p.src.startsWith("case:") ? data.cases.find((x) => "case:" + x.id === p.src) : null;
  if (p.src.startsWith("case:") && !c) return null; // 그 사고가 목록에서 빠졌으면 이어 볼 수 없음
  const sel = new Set<ItemId>(p.sel);
  const st = stageOf(c ? c.stageIdx : null, p.when, data.when);
  const picked = pick(data.actions, sel, levels(sel, data.weights), st.idx, data.stages);
  const done = new Set(p.done);
  return { c, tot: picked.length + 2, fin: picked.filter(({ index }) => done.has(index)).length + 2, href: c ? `/cases/${c.id}/` : "/plan/" };
}

export default function Home() {
  const [plan, setPlan] = useState<Plan | null>(null);
  useEffect(() => { setPlan(loadPlan()); }, []);
  const s = plan && plan.sel && plan.sel.length ? summary(plan) : null;
  const sample = [0, 5, 6, 3, 12, 15].map((i) => ({ action: data.actions[i], index: i }));

  return (
    <>
      {s ? (
        <div class="resume">
          <Ring fin={s.fin} tot={s.tot} size={48} />
          <div><b>지난번에 보던 대응 안내가 있어요</b><p class="small">{s.c ? s.c.title : "받은 안내문 기준"}, 대응 {s.tot}개 중 {s.fin}개 완료. 이 기기에만 저장돼 있어요.</p></div>
          <div class="row">
            <a class="btn" href={s.href} onClick={() => { if (!s.c && plan) saveDraft({ sel: plan.sel, when: plan.when, ntype: plan.ntype, keepDone: true } as Draft); }}>이어서 보기</a>
            <button type="button" class="txtbtn" onClick={() => { forgetPlan(); setPlan(null); toast("저장된 기록을 지웠어요."); }}>기록 지우기</button>
          </div>
        </div>
      ) : null}
      <div><h1 tabindex={-1}>개인정보 유출 안내를<br />받으셨나요?</h1><p class="lede">무엇부터 해야 할지 순서대로 알려드려요. 이름이나 전화번호 같은 개인정보는 입력하지 않아요.</p></div>
      <div class="doors">
        <a class="door" href="/notice/1/"><span class="dic"><Ico id="msg" /></span><b>유출 안내 문자나 메일을 받았어요</b><span>안내가 진짜인지 먼저 확인하고, 적힌 내용에 맞춰 할 일을 정리해요.</span><i>안내문으로 시작하기<Ico id="chevR" /></i></a>
        <a class="door" href="/cases/"><span class="dic"><Ico id="news" /></span><b>뉴스로만 소식을 접했어요</b><span>어떤 정보가 유출됐는지 모른다면, 저희가 다크웹에서 직접 확인한 사고에서 찾아볼 수 있어요.</span><i>확인된 사고 찾아보기<Ico id="chevR" /></i></a>
      </div>
      <div class="stack"><h2>이렇게 도와드려요</h2>
        <div class="three">
          <figure><div class="pic"><div class="bubble" style="max-width:190px; font-size:.72em">[○○쇼핑] 개인정보 유출 <u>피해보상금</u> 지급 대상입니다. <u>bit.ly/xxxxx</u></div></div><figcaption><b>사기 문자를 가려내요</b>유출 안내를 흉내 낸 사기 문자가 실제로 돌고 있어요.</figcaption></figure>
          <figure><div class="pic"><MiniTrail /></div><figcaption><b>어디까지 퍼졌는지 보여줘요</b>판매 중인지, 무료로 공개됐는지에 따라 먼저 할 일이 달라져요.</figcaption></figure>
          <figure><div class="pic"><div style="width:100%; max-width:190px"><Timeline picked={sample} done={new Set([0])} later={new Set()} compact /></div></div><figcaption><b>할 일을 하나씩 안내해요</b>온라인 신청이 어렵다면 전화나 방문으로 하는 방법도 알려드려요.</figcaption></figure>
        </div>
      </div>
      <p class="foot">여기서 확인되지 않는다고 해서 안전하다는 뜻은 아니에요.</p>
    </>
  );
}
