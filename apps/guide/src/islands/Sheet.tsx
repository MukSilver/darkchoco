// 대응 한 장. 사고에서 왔으면 case 를 받고, 안내문에서 왔으면 브라우저 저장의 초안을 읽습니다.
// 상태(고른 항목, 완료, 미룬 일)는 이 기기에만 저장합니다.
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { Ico } from "../lib/icons";
import { data, LABEL, RNAME, RICON } from "../lib/data";
import { contributors, josa, levelName, levels, nextOf, pick, ranked, stageOf } from "../lib/rules";
import { isBlankDraft, loadDraft, loadPlan, prefs, saveDraft, savePlan } from "../lib/store";
import { toast } from "../lib/ui";
import { Board, ChipFresh, ChipGate, ChipSpread, Crowd, Effect, GoLinks, How, LinkOf, Timeline, UnitChart, groupOf, hasLink, keysOfAct, tagsOf } from "./parts";
import type { Case, ItemId, Picked } from "../lib/types";

const { stages, actions, risks, groups, weights, when: whens, levelTip, calEvents } = data;

export default function Sheet({ kase = null }: { kase?: Case | null }) {
  const [ready, setReady] = useState(false);
  const [sel, setSel] = useState<Set<ItemId>>(new Set(kase ? kase.confirmed : []));
  const [claimed] = useState<Set<ItemId>>(new Set(kase ? kase.claimed : []));
  const [whenId, setWhenId] = useState<string | null>(null);
  const [ntype, setNtype] = useState<string | null>(null);
  const [done, setDone] = useState<Set<number>>(new Set());
  const [later, setLater] = useState<Set<number>>(new Set());
  const [open, setOpen] = useState<Set<number>>(new Set());
  const [trailAt, setTrailAt] = useState<number | null>(null);
  const [share, setShare] = useState(false);
  const [cal, setCal] = useState(false);
  const [easy, setEasy] = useState(false);
  // 한 번만 쓰는 움직임 표시(프로토타입의 FX). 다시 그리기를 일으키지 않도록 ref 에 두고, 그린 뒤에 비웁니다
  const fx = useRef<{ pop: number | null; opened: number | null; stageEnter: boolean }>({ pop: null, opened: null, stageEnter: false });
  const { pop, opened, stageEnter } = fx.current;
  const enter = useRef(true);
  const lastNext = useRef<number | null | undefined>(undefined);
  const focusNext = useRef(false);
  const src = kase ? "case:" + kase.id : "notice";

  useEffect(() => {
    const p = loadPlan();
    if (kase) {
      // 사고: 이 사고의 저장된 진행이 있으면 그것을, 없으면 사고의 확인 항목을 씁니다
      if (p && p.src === src) { setSel(new Set(p.sel)); setDone(new Set(p.done)); setLater(new Set(p.later || [])); }
    } else {
      // 안내문: 방금 고른 값(초안)이 우선. 초안이 비어 있고 저장된 진행이 있으면 그것을 이어 갑니다 (프로토타입의 #/sheet)
      const d = loadDraft();
      if (isBlankDraft(d) && p && p.src === src) { setSel(new Set(p.sel)); setWhenId(p.when); setNtype(p.ntype); setDone(new Set(p.done)); setLater(new Set(p.later || [])); }
      else {
        setSel(new Set(d.sel)); setWhenId(d.when); setNtype(d.ntype);
        if (d.keepDone && p && p.src === src) { setDone(new Set(p.done)); setLater(new Set(p.later || [])); }
      }
      saveDraft({ ...d, keepDone: true }); // 항목을 다시 고르러 갔다 와도 완료 표시를 이어 갑니다
    }
    setEasy(prefs.easy); setReady(true);
    const onPrefs = () => setEasy(prefs.easy);
    document.addEventListener("guide:prefs", onPrefs);
    return () => document.removeEventListener("guide:prefs", onPrefs);
  }, []);

  const L = useMemo(() => levels(sel, weights), [sel]);
  const st = stageOf(kase ? kase.stageIdx : null, whenId, whens);
  const picked = useMemo(() => pick(actions, sel, L, st.idx, stages), [sel, L, st.idx]);
  const rk = ranked(L);
  const nx = nextOf(picked, done, later);
  const isFake = !!kase && kase.gate === "fake";
  // 다음 할 일이 바뀔 때만 카드가 새로 나타나는 움직임을 주고 초점을 옮깁니다 (프로토타입의 FX.lastNext, focusKey)
  const nxIndex = nx ? nx.index : null;
  const freshNext = lastNext.current !== nxIndex;
  lastNext.current = nxIndex;

  useEffect(() => {
    if (!ready || isFake) return;
    savePlan({ src, sel: [...sel], claimed: [...claimed], when: whenId, ntype, done: [...done], later: [...later] });
  }, [ready, sel, whenId, ntype, done, later]);
  useEffect(() => {
    document.dispatchEvent(new CustomEvent("guide:rendered")); enter.current = false; fx.current = { pop: null, opened: null, stageEnter: false };
    // 다음 할 일 카드에서 누른 단추가 사라졌으면 그 카드의 첫 단추로 초점을 옮깁니다 (프로토타입의 focusKey)
    if (focusNext.current) { focusNext.current = false; if (freshNext) document.querySelector<HTMLElement>("#sec-next .btn, #sec-next button")?.focus({ preventScroll: true }); }
  });

  if (isFake) return (
    <>
      <a class="back" href="/cases/">사고 목록</a>
      <div class="alarm"><h1 tabindex={-1} style="font-size:1.3em; color:var(--danger-ink)">허위로 판정된 사고예요</h1><p>샘플을 확인해 보니 다른 사고의 자료를 다시 쓰거나 꾸며낸 자료였어요. 이 사고를 근거로 한 대응은 안내하지 않아요.</p></div>
      <div class="row"><a class="btn2" href="/notice/1/">안내를 받았다면 여기서 시작하세요</a></div>
    </>
  );

  const toggle = (id: ItemId) => { const s = new Set(sel); s.has(id) ? s.delete(id) : s.add(id); setSel(s); };
  const fromNext = () => { focusNext.current = !!document.activeElement?.closest("#sec-next"); };
  const markDone = (i: number) => {
    fromNext();
    if (done.has(i)) { const d = new Set(done); d.delete(i); setDone(d); toast("완료 표시를 풀었어요."); return; }
    const d = new Set(done); d.add(i); const l = new Set(later); l.delete(i); fx.current.pop = i; setDone(d); setLater(l);
    toast("완료로 표시했어요.", () => { const d2 = new Set(d); d2.delete(i); setDone(d2); });
  };
  const putLater = (i: number) => { fromNext(); const l = new Set(later); l.add(i); setLater(l); toast("나중에 할 일로 미뤘어요. 남은 할 일 목록에 있어요.", () => { const l2 = new Set(l); l2.delete(i); setLater(l2); }); };
  const toggleOpen = (i: number) => { const o = new Set(open); if (o.has(i)) o.delete(i); else { o.add(i); fx.current.opened = i; } setOpen(o); };

  const c = kase;
  const ev = c
    ? `${c.spread === "판매 중" ? "이 자료는 현재 다크웹에서 판매되고 있어요" : c.spread === "무료 공개" ? "이 자료는 현재 다크웹에서 무료로 공개되어 있어요" : c.spread === "재유포" ? "이 자료는 현재 여러 곳에 다시 올라오고 있어요" : "이 자료가 지금 어디까지 퍼졌는지는 아직 확인하지 못했어요"}. ${c.confirmed.length ? `저희가 샘플을 직접 열어 ${c.confirmed.length}개 항목을 확인했어요.` : `샘플에서 확인된 항목은 아직 없어요. 게시글에 적힌 항목 ${c.claimed.length}개를 점선으로 표시했어요. 해당하는 항목을 눌러 주세요.`}`
    : ntype === "maybe" ? "유출 가능성 안내를 받으셨어요. 확정이 아니더라도 아래 대응은 미리 해 두는 편이 안전해요." : `안내문에 적힌 ${sel.size}개 항목을 기준으로 정리했어요.`;
  const blame = <p class="small" style="margin-top:6px">개인정보 유출은 정보를 지키지 못한 회사의 책임이에요. 내 잘못이 아니에요.</p>;

  return (
    <>
      <a class="back" href={c ? "/cases/" : "/notice/3/"}>{c ? "사고 목록" : "항목 다시 선택"}</a>
      <div class="printhead">개인정보 유출 대응 안내, {c ? c.title : "받은 안내문 기준"}</div>
      <div class="stack">
        {c ? <div class="caseline"><span class="ct">{c.title}</span><ChipGate c={c} /><ChipSpread c={c} /><ChipFresh c={c} /></div> : null}
        {rk.length ? <div><h1 tabindex={-1}>지금 가장 주의할 것은<br /><em>{RNAME[rk[0]] + josa(RNAME[rk[0]], "이에요", "예요")}</em></h1><p class="lede" style="color:var(--ink)">{ev}</p>{blame}</div>
          : sel.size ? <div><h1 tabindex={-1}>선택한 항목으로는<br />위험 등급을 정하지 않아요</h1><p class="lede">{ev} 아래 기본 대응은 해 두세요.</p>{blame}</div>
          : <div><h1 tabindex={-1}>유출된 항목을 선택하세요</h1><p class="lede">{ev}</p></div>}
      </div>

      <div class="stack linkscope">
        {rk.length ? (
          <>
            <NextCard nx={nx} picked={picked} later={later} done={done} stIdx={st.idx} sel={sel} easy={easy} cal={cal} setCal={setCal} markDone={markDone} putLater={putLater} fresh={freshNext} />
            <div class="progress noprint">
              <div><h3>대응 {picked.length + 2}개 중 {picked.filter(({ index }) => done.has(index)).length + 2}개 완료</h3><p class="small" style="margin-top:2px">안내를 확인하고 대응 방법을 찾아본 것도 대응이에요. 두 칸은 이미 채워 두었어요.<span class="hov"> 칸에 마우스를 올리면 어떤 일인지 보여요.</span></p></div>
              <Timeline picked={picked} done={done} later={later} compact={false} pop={pop} />
            </div>
          </>
        ) : <p class="note" id="sec-next">{sel.size ? "" : "선택한 항목이 없어도 "}이 세 가지는 해 두세요. 비밀번호 점검, 2단계 인증 켜기, 새 기기 로그인 알림 켜기.</p>}
      </div>

      <Trail st={st} trailAt={trailAt} setTrailAt={(i) => { fx.current.stageEnter = true; setTrailAt(i); }} enter={enter.current} stageEnter={stageEnter} />

      <section class="two linkscope" id="sec-board">
        <Board sel={sel} claimed={claimed} onToggle={toggle} note={"회색 칸은 이번 사고에서 확인되지 않았다는 뜻이에요. 안전하다는 뜻은 아니에요." + (c && c.claimed.length ? " 점선 칸은 게시글에만 적혀 있고 샘플에서는 확인하지 못한 항목이에요. 해당된다면 눌러 주세요." : "")} />
        <div><h2>주의해야 할 위험</h2><p class="small" style="margin-top:4px"><span class="hov">위험에 마우스를 올리면</span><span class="tch">위험을 누르면</span> 관련된 항목과 할 일이 함께 표시돼요.</p>
          <div class="risks">
            {risks.map(({ id: k, label: n }) => {
              const t = picked.filter(({ action }) => action.risk === k), d = t.filter(({ index }) => done.has(index)).length, v = L[k];
              const combo = (k === "phish" && sel.has("name") && sel.has("phone")) || (k === "ident" && sel.has("name") && sel.has("rrn"));
              const reasons = contributors(sel, weights, k).map((i) => LABEL[i]).join(", ");
              return (
                <div class={"rk l" + v} tabIndex={0} data-src={"risk:" + k} data-keys={["risk:" + k, ...contributors(sel, weights, k).map((i) => "item:" + i)].join(" ")}>
                  <span class="ic"><Ico id={RICON[k]} /></span>
                  <span><b>{n}</b><small>{v ? `${reasons} 유출${combo ? ", 함께 유출돼 한 단계 올림" : ""}${t.length ? `, 대응 ${t.length}개 중 ${d}개 완료` : ""}` : "이번 사고와는 관련이 적어요"}</small></span>
                  <span class="lv" data-tip={levelTip[String(Math.min(v, 3))]}>{levelName(v)}<span class="sig" role="img" aria-label={"위험 " + levelName(v)}><i></i><i></i><i></i></span></span>
                </div>
              );
            })}
          </div></div>
      </section>

      <div class="linkscope"><Rest picked={picked} nx={nx} done={done} later={later} open={open} sel={sel} easy={easy} pop={pop} opened={opened} cal={cal} setCal={setCal} markDone={markDone} toggleOpen={toggleOpen} /></div>

      <section class="stack" id="sec-harm"><div><h2>이미 피해가 생겼다면</h2><p class="small" style="margin-top:4px">돈이 빠져나갔거나 내 명의로 무언가가 개설됐다면 위 순서보다 먼저 연락하세요. 거래하는 금융회사 콜센터와 112, 1332 가운데 먼저 연결되는 곳에 지급정지와 피해구제 접수를 요청하면 돼요. 받은 문자와 화면은 지우지 말고 보관하세요.</p></div>
        <div class="nums"><a class="num red" href="tel:112"><b>112</b><span>경찰에 신고하면서 지급정지를 요청하세요.</span></a><a class="num red" href="tel:1332"><b>1332</b><span>금융감독원에서도 지급정지 접수를 받아요.</span></a><a class="num" href="tel:118"><b>118</b><span>무엇부터 할지 모르겠다면 무료로 상담받으세요.</span></a></div>
        <p class="small" style="margin-top:8px">전화로 지급정지를 요청한 뒤에는 경찰서에서 사건사고사실확인원을 받아, 3영업일이 지난 다음 14일 안에 금융회사에 피해구제 신청서를 내면 돼요. 인터넷 사기나 스미싱 피해는 <a href="https://ecrm.police.go.kr/minwon/main" target="_blank" rel="noopener">경찰청 사이버범죄 신고시스템</a>에서도 신고할 수 있어요.</p></section>

      <section class="stack" id="sec-claim"><div><h2>회사에 보상을 요구할 수 있어요</h2><p class="small" style="margin-top:4px">개인정보 유출은 정보를 지키지 못한 회사의 책임이에요. 쉬운 방법부터 차례로 시도해 보세요.</p></div>
        <div class="ladder">
          <div class="rung"><h3>회사에 먼저 문의하기</h3><p>안내문에 적힌 담당 부서에 피해 구제 절차와 보상 계획을 물어보세요.</p></div>
          <div class="rung"><h3>개인정보 분쟁조정 신청하기</h3><p>비용 없이 온라인이나 우편으로 신청할 수 있어요. 공공기관과 일정 규모 이상의 기업은 조정 절차에 반드시 참여해야 해요. 조정이 성립하면 재판상 화해와 같은 효력이 있어요.</p>
            <div class="row noprint">{easy ? <a class="btn2" href="tel:18336972">분쟁조정위원회 1833-6972에 전화하기</a> : <a class="btn2" href="https://www.kopico.go.kr" target="_blank" rel="noopener">개인정보 분쟁조정위원회 바로가기</a>}</div></div>
          <div class="rung"><h3>손해배상 청구하기</h3><p>회사의 잘못으로 유출됐다면 300만 원 이하의 범위에서 배상을 청구할 수 있어요. 손해액을 직접 증명하지 않아도 되지만, 인정 여부와 금액은 법원이 판단해요.</p></div>
        </div></section>

      <section class="stack noprint" id="sec-help"><h2>혼자 하기 어렵다면</h2>
        <div class="row"><button type="button" class="btn2" aria-pressed={share} onClick={() => setShare(!share)}>가족에게 보낼 안내 만들기</button><button type="button" class="btn2" onClick={() => { try { window.print(); } catch { /* 무시 */ } }}><Ico id="print" />인쇄하기</button></div>
        {share ? <ShareBox picked={picked} done={done} sel={sel} /> : null}
      </section>
      {c ? <p class="small">이 자료가 다크웹에서 거쳐 간 경로는 생태계 지도에서 볼 수 있어요.</p> : null}
      <p class="foot">대응 문구와 기관 절차는 검토 중이에요. 체크한 내용은 이 기기에만 저장돼요.</p>
      <MiniBar picked={picked} done={done} nx={nx} show={rk.length > 0} />
    </>
  );
}

function NextCard({ nx, picked, later, done, stIdx, sel, easy, cal, setCal, markDone, putLater, fresh }: {
  nx: Picked | null; picked: Picked[]; later: Set<number>; done: Set<number>; stIdx: number | null; sel: Set<ItemId>; easy: boolean;
  cal: boolean; setCal: (v: boolean) => void; markDone: (i: number) => void; putLater: (i: number) => void; fresh: boolean;
}) {
  if (!nx) return (
    <div class="next enter" id="sec-next"><span class="chip green" style="align-self:flex-start">완료</span><p class="nt">모든 대응을 마쳤어요.</p><p class="why">유출된 정보는 되돌릴 수 없어요. 6개월 뒤에 한 번 더 점검해 주세요.</p>
      <div class="noprint"><div class="row"><button type="button" class="btn2" aria-expanded={cal} onClick={() => setCal(!cal)}><Ico id="cal" />6개월 뒤 점검 일정 넣기</button></div>{cal ? <CalPanel only6 picked={picked} done={done} /> : null}</div></div>
  );
  const { action: a, index: i } = nx, g = groupOf(a.urgency);
  const remaining = picked.filter(({ index }) => !done.has(index)).length;
  return (
    <div class={"next " + a.urgency + (fresh ? " enter" : "")} id="sec-next" data-keys={keysOfAct(a, sel)}>
      <div class="row"><span class={"chip " + g.tone}>{g.label}</span>{later.has(i) ? <span class="chip">미룬 일</span> : null}{stIdx !== null ? <span class="small">{stages[stIdx].name} 단계에서는 이 일을 먼저 하는 게 좋아요</span> : null}</div>
      <p class="nt">{a.title}</p><p class="why">{a.why}</p>
      <div class="meta2">{a.minutes ? <span>약 {a.minutes}분</span> : null}{a.free ? <span>무료</span> : null}<span>관련 항목: {tagsOf(a, sel)}</span>{a.desk && !a.url ? <span>문의처: {a.desk}</span> : null}</div>
      <Effect a={a} /><How a={a} easy={easy} /><GoLinks a={a} easy={easy} />
      <div class="row noprint" style="margin-top:4px"><button type="button" class="btn" onClick={() => markDone(i)}><Ico id="check" />완료했어요</button><LinkOf a={a} easy={easy} />{remaining > 1 ? <button type="button" class="txtbtn" onClick={() => putLater(i)}>나중에 할게요</button> : null}</div>
    </div>
  );
}

function Trail({ st, trailAt, setTrailAt, enter, stageEnter }: { st: { idx: number | null; est: boolean }; trailAt: number | null; setTrailAt: (i: number) => void; enter: boolean; stageEnter: boolean }) {
  const known = st.idx !== null, at = trailAt !== null ? trailAt : st.idx, d = at !== null ? stages[at] : null;
  // 들어올 때 막대가 0에서 현재 단계까지 차오릅니다 (프로토타입의 data-w)
  const [grown, setGrown] = useState(false);
  useEffect(() => { const id = requestAnimationFrame(() => setGrown(true)); return () => cancelAnimationFrame(id); }, []);
  const fill = known ? (enter && !grown ? 0 : st.idx! * 25) : 0;
  const title = !known ? "현재 단계는 알 수 없어요" : st.est ? <>내 정보는 <em>{stages[st.idx!].name}</em> 단계일 가능성이 높아요</> : <>내 정보는 지금 <em>{stages[st.idx!].name}</em> 단계예요</>;
  const sub = !known ? "저희가 확인하지 못한 사고는 단계를 추정하지 않아요. 일반적으로는 아래 순서로 퍼져요. 각 단계를 눌러 보세요." : st.est ? "저희가 확인한 사고가 아니어서, 안내를 받은 시점을 기준으로 추정했어요. 추정한 단계는 점선으로 표시해요." : "검증할 때 다크웹에서 직접 확인한 상태예요. 다른 단계를 누르면 그 단계의 설명을 볼 수 있어요.";
  return (
    <section class="band" id="sec-stage"><div class="band-in">
      <div><h2>{title}</h2><p class="small" style="margin-top:4px">{sub}</p></div>
      <div class={"trail " + (st.est ? "est" : "")}><div class="tl"></div>{known ? <div class="tf" style={`width:${fill}%`}></div> : null}
        {stages.map((t, i) => (
          <button type="button" class={"st " + (known && i < st.idx! ? "passed" : "") + " " + (known && i === st.idx ? "here" : "")} aria-pressed={at === i} data-tip={`${t.name}: ${t.sub}. 누르면 이 단계에서 생기는 일을 볼 수 있어요.`} onClick={() => setTrailAt(i)}>
            <span class="dt"><Ico id={t.icon} /></span><b>{t.name}</b><small>{t.sub}</small>{known && i === st.idx ? <span class="now">{st.est ? "추정 단계" : "현재 단계"}</span> : null}
          </button>
        ))}
      </div>
      {d ? (
        <div class={"stagebox " + (stageEnter ? "enter" : "")}>
          <div><h3>누가 가지고 있나요</h3><p style="margin-top:4px">{d.who}</p><Crowd t={d} anim={enter || stageEnter} /><p class="small faint" style="margin-top:8px">정보가 퍼진 정도를 나타낸 그림이에요. 실제 인원과는 다를 수 있어요.</p></div>
          <div><h3>이 단계에서 생기는 일</h3><p style="margin-top:4px">{d.risk}</p>{known && at !== st.idx ? <p class="small" style="margin-top:10px">내 정보는 지금 {stages[st.idx!].name} 단계{st.est ? "로 추정돼요" : "예요"}. <button type="button" style="color:var(--primary-ink); font-weight:700" onClick={() => setTrailAt(st.idx!)}>돌아가기</button></p> : null}</div>
        </div>
      ) : null}
      <UnitChart anim={enter} />
    </div></section>
  );
}

function Rest({ picked, nx, done, later, open, sel, easy, pop, opened, cal, setCal, markDone, toggleOpen }: {
  picked: Picked[]; nx: Picked | null; done: Set<number>; later: Set<number>; open: Set<number>; sel: Set<ItemId>; easy: boolean; pop: number | null; opened: number | null;
  cal: boolean; setCal: (v: boolean) => void; markDone: (i: number) => void; toggleOpen: (i: number) => void;
}) {
  const rest = picked.filter((x) => !nx || x.index !== nx.index);
  if (!rest.length) return null;
  const hasWatch = picked.some(({ action }) => action.urgency === "watch");
  return (
    <section id="sec-rest"><h2>남은 할 일 {rest.filter(({ index }) => !done.has(index)).length}개</h2><p class="small" style="margin-top:4px">항목을 누르면 자세한 설명이 나와요. 마친 일은 왼쪽 네모를 눌러 표시하세요.</p>
      {groups.map((g) => {
        const mine = rest.filter(({ action }) => action.urgency === g.id);
        if (!mine.length) return null;
        return (
          <>
            <div class="grp"><span class={"chip " + g.tone}>{g.label}</span><span>{g.sub}</span></div>
            {mine.map(({ action: a, index: i }) => {
              const dn = done.has(i), op = open.has(i);
              return (
                <div class={"item " + (dn ? "dn" : "")} data-keys={keysOfAct(a, sel)}>
                  <button type="button" class={"cb " + (pop === i ? "pop" : "")} aria-pressed={dn} aria-label={a.title + " 완료 표시"} onClick={() => markDone(i)}></button>
                  <button type="button" class="line" aria-expanded={op} onClick={() => toggleOpen(i)}><span class="t">{a.title}</span>{later.has(i) && !dn ? <span class="chip">미룬 일</span> : null}<span class="mm">{a.minutes ? `약 ${a.minutes}분` : ""}</span><span class="chev"></span></button>
                  {op ? <div class={"detail " + (opened === i ? "enter" : "")}><p>{a.why}</p><p class="small">관련 항목: {tagsOf(a, sel)}</p><Effect a={a} /><How a={a} easy={easy} /><GoLinks a={a} easy={easy} />{hasLink(a, easy) ? <div class="row"><LinkOf a={a} easy={easy} /></div> : null}</div> : null}
                </div>
              );
            })}
            {g.id === "watch" && hasWatch ? <div class="noprint" style="margin-top:12px"><div class="row"><button type="button" class="btn2" aria-expanded={cal} onClick={() => setCal(!cal)}><Ico id="cal" />달력에 점검 일정 넣기</button><span class="small">2주, 1달, 2달, 6개월 뒤 날짜를 알려 드려요.</span></div>{cal ? <CalPanel picked={picked} done={done} /> : null}</div> : null}
          </>
        );
      })}
    </section>
  );
}

function calDesc(picked: Picked[], done: Set<number>) {
  const watch = picked.filter(({ action, index }) => action.urgency === "watch" && !done.has(index)).map(({ action }) => action.title);
  return (watch.length ? "확인할 일: " + watch.join(", ") : "카드 명세서, 본인확인 내역, 모르는 로그인 알림을 확인해요") + ". 자세한 방법은 WEB SCOPE 유출 대응 안내를 보세요.";
}
const pad = (n: number) => String(n).padStart(2, "0");
const at = (n: number) => { const d = new Date(); d.setDate(d.getDate() + n); return d; };
const ymd = (d: Date) => d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate());

function icsFile(picked: Picked[], done: Set<number>) {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+/, "");
  const desc = calDesc(picked, done).replace(/,/g, "\\,");
  let s = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//WEB SCOPE//leak guide//KO\r\nCALSCALE:GREGORIAN\r\n";
  calEvents.forEach((e, k) => { s += `BEGIN:VEVENT\r\nUID:webscope-${stamp}-${k}\r\nDTSTAMP:${stamp}\r\nDTSTART;VALUE=DATE:${ymd(at(e.days))}\r\nDTEND;VALUE=DATE:${ymd(at(e.days + 1))}\r\nSUMMARY:${e.title}\r\nDESCRIPTION:${desc}\r\nBEGIN:VALARM\r\nTRIGGER:PT9H\r\nACTION:DISPLAY\r\nDESCRIPTION:${e.title}\r\nEND:VALARM\r\nEND:VEVENT\r\n`; });
  return s + "END:VCALENDAR\r\n";
}

function CalPanel({ only6 = false, picked, done }: { only6?: boolean; picked: Picked[]; done: Set<number> }) {
  const desc = calDesc(picked, done);
  const evs = calEvents.filter((e) => !only6 || e.days === 180);
  const download = () => {
    try {
      const b = new Blob([icsFile(picked, done)], { type: "text/calendar" }), u = URL.createObjectURL(b), a = document.createElement("a");
      a.href = u; a.download = "유출대응_점검일정.ics"; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(u), 2000);
      toast("점검 일정 파일을 받았어요. 열면 달력에 2주, 1달, 2달, 6개월 뒤 일정이 들어가요.");
    } catch { toast("이 화면에서는 파일을 받을 수 없어요."); }
  };
  return (
    <div class="calp"><p class="small">아래 날짜에 확인할 일을 달력에 넣어 두세요. 달력에 들어가는 것은 할 일 이름뿐이에요.</p>
      <ul class="cald">{evs.map((e) => { const d = at(e.days), u = "https://calendar.google.com/calendar/render?action=TEMPLATE&text=" + encodeURIComponent(e.title) + "&dates=" + ymd(d) + "/" + ymd(at(e.days + 1)) + "&details=" + encodeURIComponent(desc);
        return <li><b>{d.getMonth() + 1}월 {d.getDate()}일, {e.label}</b><span>{e.title}</span><a href={u} target="_blank" rel="noopener">구글 캘린더에 넣기</a></li>; })}</ul>
      <div class="row"><button type="button" class="btn2" onClick={download}><Ico id="cal" />달력 파일 받기</button><span class="small">휴대폰과 컴퓨터의 기본 달력에 한 번에 들어가요.</span></div>
    </div>
  );
}

function ShareBox({ picked, done, sel }: { picked: Picked[]; done: Set<number>; sel: Set<ItemId> }) {
  const top = picked.filter(({ index }) => !done.has(index)).slice(0, 3);
  let t = `개인정보 유출 안내를 받았을 때 이 순서대로 하시면 돼요.\n\n유출된 항목: ${[...sel].map((i) => LABEL[i]).join(", ")}\n\n`;
  top.forEach(({ action: a }, n) => { t += `${n + 1}. ${a.title}\n${a.alt ? `   ${a.alt}\n` : a.desk ? `   문의처: ${a.desk}\n` : ""}`; });
  t += "\n문자에 있는 링크는 누르지 마세요.\n잘 모르겠으면 118(개인정보침해 신고센터)에 전화해서 물어보세요. 상담은 무료예요.";
  const copy = () => { const ta = document.getElementById("sharetxt") as HTMLTextAreaElement; const fb = () => { ta.select(); toast("글을 길게 눌러 복사해 주세요."); }; try { navigator.clipboard.writeText(t).then(() => toast("복사했어요. 카카오톡이나 문자에 붙여 넣으세요."), fb); } catch { fb(); } };
  const canShare = typeof navigator !== "undefined" && !!(navigator as Navigator & { share?: unknown }).share;
  return (
    <div class="stack" style="gap:8px; animation:enter .22s var(--ease)"><label class="small" for="sharetxt">복사해서 카카오톡이나 문자로 보내세요. 개인정보는 포함되어 있지 않아요.</label><textarea id="sharetxt" readOnly value={t}></textarea>
      <div class="row"><button type="button" class="btn" onClick={copy}>복사하기</button>{canShare ? <button type="button" class="btn2" onClick={() => { try { navigator.share({ title: "개인정보 유출 대응 안내", text: t }).catch(() => { }); } catch { /* 무시 */ } }}><Ico id="share" />공유하기</button> : null}</div></div>
  );
}

/** 따라오는 진행 막대의 내용. 보이고 숨기는 것은 ui.ts 가 스크롤 위치로 정합니다 */
function MiniBar({ picked, done, nx, show }: { picked: Picked[]; done: Set<number>; nx: Picked | null; show: boolean }) {
  useEffect(() => {
    const m = document.getElementById("mini"); if (!m) return;
    if (!show) { m.innerHTML = ""; return; }
    const tot = picked.length + 2, fin = picked.filter(({ index }) => done.has(index)).length + 2;
    const r = 30 / 2 - 3, c = 2 * Math.PI * r, f = fin / tot;
    m.innerHTML = `<div class="mini-in"><svg class="ring" viewBox="0 0 30 30" aria-hidden="true"><circle cx="15" cy="15" r="${r}" fill="none" stroke="var(--line)" stroke-width="4"/><circle cx="15" cy="15" r="${r}" fill="none" stroke="var(--ok-fill)" stroke-width="4" stroke-linecap="round" stroke-dasharray="${(c * f).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 15 15)"/></svg><div class="mt"><b>대응 ${tot}개 중 ${fin}개 완료</b><small></small></div><button type="button" class="btn" data-jump="sec-next">다음 할 일 보기</button></div>`;
    m.querySelector("small")!.textContent = nx ? "다음: " + nx.action.title : "모든 대응을 마쳤어요";
  }, [picked, done, nx, show]);
  return null;
}
