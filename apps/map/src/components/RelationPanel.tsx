/**
 * 관계 탭의 오른쪽 패널 — 설계서 4.3.3 · 4.3.6, 피그마 ⑦-8 · ⑦-8e · ⑦-8g.
 *
 *   머리글        TERRITORY · 선택됨 (중심이 행위자면 ACTOR, 관계선을 고르면 RELATION)
 *   관계 유형 구성  관계 종류별 근거 사건 수 막대
 *   요약          자동 문장
 *   근거 사건      관계선을 골랐을 때만. 사건 줄(종류 칩 · 제목 · 올라온 곳)과 신뢰도 칩
 *   관계 연혁      최초 관측 순. 강조하거나 고른 관계는 강조하고 그 자리로 굴린다
 *
 * **강조와 선택을 가른다** (4.3.3 ①). [연결]에서 넘어와 강조만 된 관계는 연혁에서
 * 강조되고 그 자리로 굴러가지만, 머리글은 TERRITORY 그대로이고 근거 사건도 안
 * 뜬다. 「근거 보기」를 눌러야 고른 것(RELATION, ⑦-8e)이 된다.
 *
 * 섬 간 보기(4.3.3 ②)면 섬 쌍의 관계를 건수 순으로 늘어놓는다. 누르면 보통
 * 관계 탭(①)으로 넘어간다.
 *
 * **근거 사건 제목은 `eventTitle` 이 분류 칸으로 짓는다** (국가 · 산업 · 날짜 · 규모).
 * 자료 제목에는 피해 조직 이름이 들어 굽기가 안 싣는다 (2026-09-23 결정).
 * 사건 줄을 누르면 `onOpenEvent` 를 부른다 — 보고서 팝업(4.3.4) 자리다 (한 번 클릭, 최현서 9번).
 */

"use client";

import { useEffect, useRef, useState } from "react";

import EventRow from "./EventRow";
import PanelShell from "./PanelShell";
import { Chip, KindDot } from "./RelBits";
import type { MapLayout } from "@/lib/layout";
import { quarterOfDate, quarterText } from "@/lib/quarter";
import {
  CONF_CHIP,
  CONF_LABEL,
  KIND_CHIP,
  KIND_LABEL,
  confOfVerdict,
  connectedIslandCount,
  historyOrder,
  historyText,
  kindMix,
  linksOf,
  partnerCount,
  selectedText,
  summaryText,
  type RelView,
} from "@/lib/relations";
import type { Ev } from "@/lib/types";
import type { RelPair } from "./RelationTab";

export type RelationPanelProps = {
  open: boolean;
  onToggle: (open: boolean) => void;
  layout: MapLayout;
  /** 중심 영토의 관계 (`touching`). 섬 간 보기면 그 섬 쌍의 관계 */
  views: RelView[];
  /**
   * 고른 관계선을 찾을 목록 — 관계 탭이 그리는 관계 전부. 2단계로 넓히면 중심에
   * 닿지 않은 선도 고를 수 있어서 `views` 만으로는 못 찾는다
   */
  pool: RelView[];
  center: string | null;
  selected: string | null;
  onSelect: (relationId: string | null) => void;
  /** 강조한 관계선 id — [연결] · 검색 · 섬 간 보기에서 넘어온 관계 (4.3.3 ①) */
  highlight: string | null;
  pair: RelPair | null;
  onPairPick: (v: RelView) => void;
  /** 「추정 관계 포함」을 꺼서 가린 중심의 관계 수. 관계 없음 요약 문안이 갈린다 (⑦-8g) */
  hiddenEst: number;
  /** 근거 사건 누르기 — 보고서 팝업 (설계서 4.3.4 · 4.3.6, 한 번 클릭) */
  onOpenEvent?: (id: string) => void;
};

function quarterLabel(iso: string): string {
  return quarterText(quarterOfDate(new Date(iso)));
}

export default function RelationPanel(p: RelationPanelProps) {
  const byId = new Map(p.layout.territories.map((t) => [t.territoryId, t]));
  const islands = new Map(p.layout.islands.map((i) => [i.islandKey, i]));
  const nameOf = (id: string) => byId.get(id)?.name ?? id;
  const islandOf = (id: string) => byId.get(id)?.islandKey;
  const sel = p.pool.find((v) => v.rel.id === p.selected) ?? null;

  const picked = useRef<HTMLLIElement>(null);
  // 설계서 4.3.3 ① 「관계 연혁에서 해당 항목 강조, 그 위치로 스크롤」
  useEffect(() => {
    picked.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [p.selected, p.highlight]);

  // 근거 사건 한 번 누름 — 그 줄을 강조한다 (4.3.3 「한 번은 미리보기」). 고른
  // 관계선이 바뀌면 저절로 풀리도록 관계선 id 를 같이 적어 둔다
  const [evPick, setEvPick] = useState<{ rel: string; ev: string } | null>(null);
  const evOn = evPick && evPick.rel === p.selected ? evPick.ev : null;

  /* ── 섬 간 보기 ─────────────────────────────────────── */

  if (p.pair) {
    const a = islands.get(p.pair.from)?.name ?? "";
    const b = islands.get(p.pair.to)?.name ?? "";
    const total = p.views.reduce((s, v) => s + v.count, 0);
    return (
      <PanelShell
        open={p.open}
        onToggle={p.onToggle}
        header={{
          kindLabel: "ISLAND PAIR",
          kindToken: null,
          kindAccent: true,
          stateLabel: "섬 간 보기",
          title: `${a} → ${b}`,
          subtitle: `엔티티 ${p.views.length}쌍 · ${total}건`,
        }}
      >
        <section className="flex flex-col gap-s3">
          <div className="flex items-baseline justify-between">
            <h3 className="text-[13px] font-semibold text-strong">엔티티 쌍</h3>
            <span className="text-[11px] text-label">건수 순</span>
          </div>
          <ul className="flex flex-col gap-s3">
            {p.views.map((v) => (
              <li key={v.rel.id}>
                <button
                  type="button"
                  onClick={() => p.onPairPick(v)}
                  className="flex w-full flex-col gap-s2 rounded-[12px] border border-edge bg-card px-s4 py-s3 text-left hover:border-edge-strong hover:bg-track"
                >
                  <span className="flex items-center gap-s2">
                    <Chip tone={KIND_CHIP[v.rel.kind]}>{KIND_LABEL[v.rel.kind]}</Chip>
                    <Chip tone={CONF_CHIP[v.rel.confidence]}>{CONF_LABEL[v.rel.confidence]}</Chip>
                    <span className="flex-1" />
                    <span className="text-[13px] font-semibold tabular-nums text-strong">{v.count}건</span>
                  </span>
                  <span className="text-[14px] font-semibold text-title">
                    {nameOf(v.rel.from)} <span className="font-normal text-label">→</span> {nameOf(v.rel.to)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </PanelShell>
    );
  }

  /* ── 보통 관계 탭 ───────────────────────────────────── */

  const c = p.center ? byId.get(p.center) : undefined;
  const cIsl = c ? islands.get(c.islandKey) : undefined;
  // 행위자 머리글은 설계서 4.3.8 「ACTOR · 선택됨, 핸들, 사건 수·활동도·활동 영토 수」
  const actor = cIsl?.islandId === "ACTOR";
  const mix = kindMix(p.views);
  const total = mix.reduce((s, m) => s + m.count, 0);
  const partners = p.center ? partnerCount(p.views, p.center) : 0;
  const islandN = p.center ? connectedIslandCount(p.views, p.center, islandOf) : 0;
  // 활동 영토 수 — 행위자 [연결] 탭과 같게 활동 관계만 센다 (4.3.8)
  const actorN = p.center && actor ? partnerCount(linksOf(p.views, p.center, true), p.center) : 0;
  const history = historyOrder(p.views);

  const header = sel
    ? {
        kindLabel: "RELATION",
        kindToken: null,
        kindAccent: true,
        stateLabel: "선택됨",
        title: c?.name ?? "",
        subtitle: `선택한 관계 ${nameOf(sel.rel.from)} → ${nameOf(sel.rel.to)} · ${KIND_LABEL[sel.rel.kind]}`,
      }
    : {
        kindLabel: actor ? "ACTOR" : "TERRITORY",
        kindToken: null,
        kindAccent: true,
        stateLabel: c ? "선택됨" : "선택 없음",
        title: c?.name ?? "관계",
        subtitle: !c
          ? "이 기준일에 기록된 관계가 없습니다"
          : actor
            ? `${cIsl?.name ?? "행위자"} 섬 · 사건 ${c.metrics.eventCount}건 · 활동도 ${c.metrics.activity} · 활동 영토 ${actorN}곳`
            : `${cIsl?.name ?? ""} 섬 · 사건 ${c.metrics.eventCount}건 · 활동도 ${c.metrics.activity} · 연결된 섬 ${islandN}`,
      };

  /** 올라온 곳. 행위자 사건이면 「행위자 → 영토」 — 패널 [사건] 탭과 같다 */
  const whereOf = (e: Ev) =>
    e.actorTerritoryId && byId.has(e.actorTerritoryId)
      ? `${nameOf(e.actorTerritoryId)} → ${nameOf(e.territoryId)}`
      : nameOf(e.territoryId);

  return (
    <PanelShell open={p.open} onToggle={p.onToggle} header={header}>
      <section className="flex flex-col gap-s3">
        <div className="flex items-baseline justify-between">
          <h3 className="text-[13px] font-semibold text-strong">관계 유형 구성</h3>
          <span className="text-[11px] tabular-nums text-label">사건 {total}건</span>
        </div>
        {/* 중심이나 기준일이 바뀌면 칸 길이가 번져 바뀐다 — 전에는 딱 바뀌었다 (최현서 1번) */}
        <div className="flex h-[6px] overflow-hidden rounded-full bg-bar-track">
          {/* 칸은 자리 순서로 잇는다 — 종류로 이으면 차례가 바뀔 때 옮겨진 칸만 전환 없이 붙어 합이
              잠깐 100% 가 아니었다 (2026-09-28 검토). 색도 같이 번진다 */}
          {mix.map((m, i) => (
            <div
              key={i}
              className="transition-[width,background-color] duration-[var(--dur-base)] ease-[var(--ease-out)]"
              style={{ width: `${(m.count / total) * 100}%`, background: `var(--t-rel-${m.kind})` }}
            />
          ))}
        </div>
        {mix.length > 0 && (
          <ul className="flex flex-wrap gap-x-s4 gap-y-s2">
            {mix.map((m) => (
              <li key={m.kind} className="flex items-center gap-s2 text-[12px] text-body">
                <KindDot kind={m.kind} />
                {KIND_LABEL[m.kind]}
                <span className="tabular-nums text-label">{m.count}건</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {c && (
        <p className="rounded-[12px] border border-edge bg-card px-s4 py-s4 text-[12px] leading-[1.75] text-body">
          {sel
            ? selectedText(sel, c.territoryId, p.views, nameOf)
            : summaryText(c.name, p.views, partners, islandN, p.hiddenEst)}
        </p>
      )}

      {sel && sel.fromRegistry && sel.rel.note && (
        <section className="flex flex-col gap-s3">
          <h3 className="text-[13px] font-semibold text-strong">명부 「연결된 곳」 원문</h3>
          <p className="break-all rounded-[12px] border border-edge bg-card px-s4 py-s3 font-mono text-[12px] leading-[1.6] text-body">
            {sel.rel.note}
          </p>
        </section>
      )}

      {sel && !sel.fromRegistry && (
        <section className="flex flex-col gap-s3">
          <div className="flex items-baseline justify-between">
            <h3 className="text-[13px] font-semibold text-strong">근거 사건</h3>
            <span className="text-[11px] tabular-nums text-label">최근 순 · {sel.evidence.length}건</span>
          </div>
          <ul className="flex flex-col gap-s1">
            {sel.evidence.map((e) => {
              // 사건 판정을 신뢰도 칩으로 (설계서 2.3). 허위는 칩이 없다
              const conf = confOfVerdict(e.verdict);
              return (
                <li key={e.id}>
                  {/* 한 번 누르기 · Enter 는 EventRow 가 받는다 — 그 줄을 강조하고 팝업을 연다
                      (2026-09-28 최현서 9번). 신뢰도 칩은 칩 줄 오른쪽 끝 자리(`side`)에 둔다 —
                      전에는 줄 위에 띄워서 칩이 늘면 첫 줄 칩과 겹쳤다 */}
                  <EventRow
                    e={e}
                    where={whereOf(e)}
                    on={evOn === e.id}
                    onClick={() => setEvPick(evOn === e.id ? null : { rel: sel.rel.id, ev: e.id })}
                    onOpen={
                      p.onOpenEvent
                        ? () => {
                            setEvPick({ rel: sel.rel.id, ev: e.id });
                            p.onOpenEvent?.(e.id);
                          }
                        : undefined
                    }
                    side={conf ? <Chip tone={CONF_CHIP[conf]}>{CONF_LABEL[conf]}</Chip> : undefined}
                  />
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-s3">
        <div className="flex items-baseline justify-between">
          <h3 className="text-[13px] font-semibold text-strong">관계 연혁</h3>
          <span className="text-[11px] tabular-nums text-label">최초 관측 순 · {history.length}건</span>
        </div>
        {history.length === 0 ? (
          <div className="flex flex-col items-center gap-s1 rounded-[12px] border border-edge bg-card px-s4 py-s5 text-center">
            <p className="text-[13px] font-semibold text-title">기록된 관계 연혁이 없습니다</p>
            <p className="text-[11px] text-label">관계가 관측되면 최초 관측 순으로 표시됩니다</p>
          </div>
        ) : (
          <ol className="flex flex-col gap-s3">
            {history.map((v) => {
              const on = v.rel.id === p.selected;
              // 고른 것이 없을 때만 강조가 산다 — 관계 탭 그래프와 같다
              const lit = on || (!sel && v.rel.id === p.highlight);
              return (
                <li
                  key={v.rel.id}
                  ref={lit ? picked : undefined}
                  className={[
                    "flex flex-col gap-s2 rounded-[12px] border px-s4 py-s3",
                    lit ? "border-[var(--t-accent)] bg-row-selected" : "border-transparent",
                  ].join(" ")}
                >
                  <div className="flex flex-wrap items-center gap-s2">
                    <span
                      aria-hidden
                      className="size-[10px] rounded-full border-2"
                      style={{
                        borderColor: lit ? "var(--t-accent)" : "var(--t-info)",
                        background: lit ? "var(--t-accent)" : "transparent",
                      }}
                    />
                    <span className="font-mono text-[12px] tabular-nums text-body">
                      {v.first ? quarterLabel(v.first) : "시작 모름"}
                    </span>
                    <Chip tone={KIND_CHIP[v.rel.kind]}>{KIND_LABEL[v.rel.kind]}</Chip>
                    <Chip tone={CONF_CHIP[v.rel.confidence]}>{CONF_LABEL[v.rel.confidence]}</Chip>
                    <span className="flex-1" />
                    <span className="text-[13px] font-semibold tabular-nums" style={{ color: lit ? "var(--t-accent)" : "var(--t-text-strong)" }}>
                      {v.count}건
                    </span>
                  </div>
                  <p className="text-[14px] font-semibold text-title">
                    {nameOf(v.rel.from)} → {nameOf(v.rel.to)}
                  </p>
                  <p className="text-[12px] leading-[1.7] text-body">{historyText(v, nameOf)}</p>
                  {/*
                    글자 단추의 공통 마우스 올림(`hover-seg`) — 전에는 밑줄만 그어졌다. 글자색을 인라인
                    style 로 주면 hover 클래스가 못 이겨서 클래스로 옮겼다. 안쪽 여백만큼 바깥을 당겨
                    글자 자리는 그대로다 (2026-09-28 코드 분석, 최현서 1번)
                  */}
                  <button
                    type="button"
                    onClick={() => p.onSelect(on ? null : v.rel.id)}
                    className="-mx-s1 self-start rounded-[6px] px-s1 text-[12px] text-web-connection hover-seg hover:underline"
                  >
                    {on ? "선택 해제" : "근거 보기"}
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </PanelShell>
  );
}
