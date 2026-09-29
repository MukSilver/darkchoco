// 여러 화면이 같이 쓰는 조각. 원본 프로토타입의 마크업과 클래스 이름을 그대로 둡니다.
import type { ComponentChildren } from "preact";
import { Ico } from "../lib/icons";
import { data, LABEL, RNAME, GROUP, flow, showFlow } from "../lib/data";
import { itemRisks } from "../lib/rules";
import type { Action, Case, ItemId, Picked, Stage } from "../lib/types";

const { items, stages, gate, spreadTip, groups } = data;

export function tileTip(id: ItemId, on: boolean, cl: boolean) {
  const rs = itemRisks(id, data.weights);
  const base = rs.length ? `유출되면 주의할 위험: ${rs.map((k) => RNAME[k]).join(", ")}` : "위험 등급 계산에는 넣지 않아요. 기본 대응은 안내해요.";
  return (cl ? "게시글에는 적혀 있지만 샘플에서 확인하지 못한 항목이에요. " : "") + base + (on ? ". 누르면 선택이 풀려요." : ". 누르면 유출 항목으로 표시해요.");
}

/** 항목판 아홉 칸 */
export function Board({ sel, claimed, onToggle, note }: { sel: Set<ItemId>; claimed: Set<ItemId>; onToggle: (id: ItemId) => void; note?: string }) {
  return (
    <div>
      <div class="boardhd"><b>{sel.size}</b><span>개 항목 유출</span><span class="small faint">9개 항목 중</span></div>
      <div class="grid9">
        {items.map(({ id, label }) => {
          const on = sel.has(id), cl = claimed.has(id) && !on;
          return (
            <button type="button" class={"tile " + (on ? "on" : cl ? "cl" : "")} aria-pressed={on} data-src={"item:" + id}
              data-keys={["item:" + id, ...itemRisks(id, data.weights).map((k) => "risk:" + k)].join(" ")} data-tip={tileTip(id, on, cl)}
              onClick={() => onToggle(id)}>
              <Ico id={id} /><span>{label}</span>{on ? <span class="tag">유출</span> : cl ? <span class="tag">주장</span> : null}
            </button>
          );
        })}
      </div>
      {note ? <p class="boardnote">{note}</p> : null}
    </div>
  );
}

/** 퍼진 단계 점 넷 (목록용) */
export function MStage({ idx }: { idx: number | null }) {
  if (idx === null) return null;
  const t = stages[idx];
  const parts: ComponentChildren[] = [];
  for (let i = 0; i < 4; i++) {
    if (i) parts.push(<b class={i <= idx ? "p" : ""}></b>);
    parts.push(<i class={i < idx ? "p" : i === idx ? "h" : ""}></i>);
  }
  return <span class="mstage" role="img" aria-label={t.name + " 단계"} data-tip={`${t.name} 단계예요. ${t.sub}.`}>{parts}</span>;
}

export function Crowd({ t, anim }: { t: Stage; anim: boolean }) {
  const dots = [];
  for (let i = 0; i < 60; i++) dots.push(<i style={`--d:${i}`} class={i < t.dots ? (t.mix && i % 3 === 0 ? "b" : "a") : ""}></i>);
  return <div class={"crowd " + (anim ? "anim" : "")} role="img" aria-label="정보를 가진 사람이 늘어나는 정도">{dots}</div>;
}

export const ChipGate = ({ c }: { c: Case }) => <span class={"chip " + gate[c.gate][1]} data-tip={gate[c.gate][2]}>{gate[c.gate][0]}</span>;
export const ChipSpread = ({ c }: { c: Case }) => <span class={"chip " + (c.stageIdx === 1 ? "blue" : c.stageIdx === null ? "" : "orange")} data-tip={spreadTip[c.spread] || ""}>{c.spread === "확인불가" ? "확산 확인 불가" : c.spread}</span>;
export const ChipFresh = ({ c }: { c: Case }) => <span class="chip" data-tip="유출 자료가 처음 올라온 뒤 지난 기간이에요.">{c.freshness}</span>;

export function MiniTrail() {
  return (
    <svg viewBox="0 0 200 64" width="200" height="64" aria-hidden="true">
      <line x1="24" y1="26" x2="176" y2="26" style="stroke:var(--line2)" stroke-width="3" stroke-linecap="round" />
      <line x1="24" y1="26" x2="74" y2="26" style="stroke:var(--primary)" stroke-width="3" stroke-linecap="round" />
      <circle cx="24" cy="26" r="7" style="fill:var(--bg);stroke:var(--primary)" stroke-width="2" />
      <circle cx="74" cy="26" r="11" style="fill:var(--primary-fill)" />
      <circle cx="126" cy="26" r="7" style="fill:var(--bg);stroke:var(--line2)" stroke-width="2" />
      <circle cx="176" cy="26" r="7" style="fill:var(--bg);stroke:var(--line2)" stroke-width="2" />
      <text x="74" y="56" text-anchor="middle" font-size="11" font-weight="700" style="fill:var(--primary-ink)">현재 단계</text>
    </svg>
  );
}

/** 진행 막대. 시작 두 칸은 채워 둡니다 */
export function Timeline({ picked, done, later, compact, pop }: { picked: Picked[]; done: Set<number>; later: Set<number>; compact: boolean; pop?: number | null }) {
  const tot = picked.length + 2, fin = picked.filter(({ index }) => done.has(index)).length + 2;
  type Row = { t: string; d: boolean; l?: boolean; i?: number };
  const gs: [string, string, Row[]][] = [["start", "시작", [{ t: "안내 확인", d: true }, { t: "대응 방법 찾아보기", d: true }]]];
  for (const g of groups) gs.push([g.id, g.label, picked.filter(({ action }) => action.urgency === g.id).map(({ action, index }) => ({ t: action.title, d: done.has(index), l: later.has(index), i: index }))]);
  return (
    <div class="tl2" role="img" aria-label={`대응 ${tot}개 중 ${fin}개 완료`}>
      {gs.filter((g) => g[2].length).map(([, name, list]) => (
        <div class="g" style={`flex:${list.length}`}>
          <span class="bars2">{list.map((x) => <i class={(x.d ? "on" : x.l ? "later" : "") + (pop != null && x.i === pop ? " pop" : "")} data-tip={compact ? undefined : x.t + (x.d ? ", 완료" : x.l ? ", 나중에 하기로 함" : ", 아직 안 함")}></i>)}</span>
          {compact ? null : <small><b>{name}</b><span>{list.filter((x) => x.d).length}/{list.length}</span></small>}
        </div>
      ))}
    </div>
  );
}

export function UnitChart({ anim }: { anim: boolean }) {
  if (!showFlow) return null;
  const cls = ["a", "b", "c"], nm = ["판매 중", "무료 공개 또는 재유포", "확인 불가"];
  /* 한 줄에 칸 60개까지만 그립니다. 넘으면 칸 하나가 사고 여러 건을 대신합니다 */
  const MAX = 60;
  const biggest = Math.max(...flow.map(([, ns]) => ns.reduce((a, b) => a + b, 0)));
  const per = Math.max(1, Math.ceil(biggest / MAX));
  let d = 0;
  return (
    <div class="stack" style="gap:12px">
      <h3>저희가 검증한 사고는 이렇게 흘러갔어요</h3>
      <div class="units">
        {flow.map(([lab, ns]) => {
          const tot = ns.reduce((a, b) => a + b, 0), sq: ComponentChildren[] = [];
          ns.forEach((n, k) => { const cells = Math.round(n / per); for (let j = 0; j < cells; j++) sq.push(<i class={cls[k]} style={`--d:${d++}`} data-tip={per === 1 ? `${lab}, ${nm[k]} 1건` : `${lab}, ${nm[k]} ${n}건 중 약 ${per}건`}></i>); });
          return (
            <div class="urow"><span class="lab">{lab}<small>{tot}건</small></span>
              <span class={"usq " + (anim ? "anim" : "")} role="img" aria-label={`${lab} ${tot}건 중 ${ns.map((n, k) => (n ? `${nm[k]} ${n}건` : "")).filter(Boolean).join(", ")}`}>{sq}</span></div>
          );
        })}
      </div>
      <div class="key"><span><i style="background:var(--primary)"></i>판매 중</span><span><i style="background:var(--warn)"></i>무료 공개 또는 재유포</span><span><i style="box-shadow:inset 0 0 0 1.5px var(--control)"></i>확인 불가</span><span>{per === 1 ? "한 칸이 사고 한 건이에요" : `한 칸이 사고 ${per}건이에요`}</span></div>
      <p class="small">저희가 검증한 사고 전체를 1년 기준으로 나눠 지금 상태를 센 것이에요. 시간이 지나면 팔리던 자료가 무료로 풀리기도 해요. 위험이 사라지는 게 아니라 형태가 바뀌어요. 정보 결합 단계는 조사 자료를 바탕으로 설명한 것으로, 위 수치에는 포함되지 않아요.</p>
    </div>
  );
}

/* 조치 상세 조각 */
export function How({ a, easy }: { a: Action; easy: boolean }) {
  if (easy && a.alt) return <div class="how"><h3>전화나 방문으로 하는 방법</h3><p style="margin-top:4px">{a.alt}</p></div>;
  if (a.steps.length) return (
    <div class="how"><h3>신청 방법</h3>{a.prep ? <p class="small" style="margin-top:2px">준비물: {a.prep}</p> : null}
      <ol>{a.steps.map((x) => <li>{x}</li>)}</ol>{a.alt ? <p class="small" style="margin-top:8px">온라인 신청이 어렵다면 {a.alt}</p> : null}</div>
  );
  if (a.prep) return <p class="small">준비물: {a.prep}</p>;
  return a.alt ? <p class="small">{a.alt}</p> : null;
}

export function Effect({ a }: { a: Action }) {
  const rows: ComponentChildren[] = [];
  if (a.cond) rows.push(<div class="c"><b>이럴 때만 해당해요</b><p>{a.cond}</p></div>);
  if (a.effect) rows.push(<div class="e"><b>하고 나면 이렇게 달라져요</b><p>{a.effect}</p></div>);
  if (a.limit) rows.push(<div class="l"><b>이건 안 막혀요</b><p>{a.limit}</p></div>);
  if (a.undo) rows.push(<div class="o"><b>다시 풀려면</b><p>{a.undo}</p></div>);
  return rows.length ? <div class="fx">{rows}</div> : null;
}

export function GoLinks({ a, easy }: { a: Action; easy: boolean }) {
  const list = easy ? a.go.filter((g) => g.url.startsWith("tel:")) : a.go;
  if (!list.length) return null;
  return (
    <div class="go noprint"><span class="gol">바로 가는 곳</span>
      {list.map((g) => { const tel = g.url.startsWith("tel:"); return <a class="btn2 gob" href={g.url} target={tel ? undefined : "_blank"} rel={tel ? undefined : "noopener"}>{g.label}</a>; })}
    </div>
  );
}

/** 창구 바로가기 단추가 나오는지. 쉬운 보기에서는 전화가 아닌 링크를 숨깁니다 */
export const hasLink = (a: Action, easy: boolean) => !!(a.desk && a.url) && !(easy && a.alt && !a.url!.startsWith("tel:"));
export function LinkOf({ a, easy }: { a: Action; easy: boolean }) {
  if (!hasLink(a, easy)) return null;
  const tel = a.url!.startsWith("tel:");
  return <a class="btn2" href={a.url!} target={tel ? undefined : "_blank"} rel={tel ? undefined : "noopener"}>{tel ? a.desk + "에 전화하기" : a.desk + " 바로가기"}</a>;
}

export const tagsOf = (a: Action, sel: Set<ItemId>) => a.basis.filter((x) => sel.has(x)).map((x) => LABEL[x]).join(", ");
export const keysOfAct = (a: Action, sel: Set<ItemId>) => ["risk:" + a.risk, ...a.need.filter((x) => sel.has(x)).map((x) => "item:" + x)].join(" ");
export const groupOf = (u: string) => GROUP[u];
