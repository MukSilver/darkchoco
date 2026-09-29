// 사고 목록. 업종 거르기는 브라우저 안에서 합니다. 목록 자체는 빌드 때 HTML로 들어갑니다.
import { useEffect, useState } from "preact/hooks";
import { Ico } from "../lib/icons";
import { data, LABEL } from "../lib/data";
import { ChipFresh, ChipGate, ChipSpread, MStage } from "./parts";

export default function CaseList({ industry = "" }: { industry?: string }) {
  const [ind, setInd] = useState(industry);
  const fromUrl = () => new URLSearchParams(location.search).get("ind") || "";
  // 업종은 주소(?ind=)에 실어 뒤로 가기로 되돌릴 수 있게 합니다 (프로토타입의 #/list/업종)
  useEffect(() => { setInd(fromUrl()); const pop = () => setInd(fromUrl()); window.addEventListener("popstate", pop); return () => window.removeEventListener("popstate", pop); }, []);
  const inds = [...new Set(data.cases.map((c) => c.industry))];
  const rows = data.cases.filter((c) => !ind || c.industry === ind);
  const choose = (v: string) => { if (v === ind) return; setInd(v); history.pushState(null, "", v ? `?ind=${encodeURIComponent(v)}` : location.pathname); };

  return (
    <>
      <a class="back" href="/">처음으로</a>
      <div><h1 tabindex={-1}>저희가 확인한 유출 사고</h1><p class="lede">다크웹에서 샘플을 직접 열어 확인한 사고예요. 회사 이름 대신 업종과 자료 종류로 표시해요. 뉴스에서 본 업종을 선택해 보세요.</p></div>
      <div class="stack">
        <div class="inds" role="group" aria-label="업종">
          <button type="button" class="ind" aria-pressed={!ind} onClick={() => choose("")}>전체</button>
          {inds.map((i) => <button type="button" class="ind" aria-pressed={ind === i} onClick={() => choose(i)}>{i}</button>)}
        </div>
        {rows.length ? (
          <div class="cases">
            {rows.map((c) => (
              <a class="case" href={`/cases/${c.id}/`}>
                <span class="ct">{c.title}</span><span class="go" aria-hidden="true"><Ico id="chevR" /></span>
                <span class="meta"><ChipGate c={c} /><ChipSpread c={c} /><ChipFresh c={c} /><MStage idx={c.stageIdx} />
                  <span class="icons" data-tip={"확인된 항목: " + (c.confirmed.map((i) => LABEL[i]).join(", ") || "없음") + (c.claimed.length ? ". 게시글에만 적힌 항목: " + c.claimed.map((i) => LABEL[i]).join(", ") : "")}>
                    {c.confirmed.map((i) => <Ico id={i} />)}{c.claimed.filter((i) => !c.confirmed.includes(i)).map((i) => <span class="c"><Ico id={i} /></span>)}
                  </span></span>
              </a>
            ))}
          </div>
        ) : (
          <div class="empty"><h3>이 업종에서 확인된 사고는 아직 없어요</h3><p class="small">확인되지 않았다고 해서 안전하다는 뜻은 아니에요. 받은 안내문이 있다면 항목을 직접 골라 시작하세요.</p>
            <div class="row"><button type="button" class="btn2" onClick={() => choose("")}>전체 보기</button><a class="btn2" href="/notice/3/">항목 선택하기</a></div></div>
        )}
      </div>
      <div class="note">찾는 사고가 없다면 안내문에 적힌 항목을 직접 선택해 시작할 수 있어요. <a class="more" href="/notice/3/">항목 선택하기 ›</a></div>
      <p class="foot">파란 아이콘은 확인된 유출 항목이고, 흐린 아이콘은 게시글에만 적힌 항목이에요.</p>
    </>
  );
}
