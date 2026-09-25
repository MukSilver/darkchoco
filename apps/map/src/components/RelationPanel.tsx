/**
 * 관계 탭의 오른쪽 패널 — 설계서 4.3.3 · 4.3.6, 피그마 ⑦-8 · ⑦-8e · ⑦-8g.
 *
 *   머리글        TERRITORY · 선택됨 (관계선을 고르면 RELATION · 선택됨)
 *   관계 유형 구성  관계 종류별 근거 사건 수 막대
 *   요약          자동 문장
 *   근거 사건      관계선을 골랐을 때만. 날짜 · 판정 · 규모 · 올라온 곳
 *   관계 연혁      최초 관측 순. 고른 관계는 강조하고 그 자리로 굴린다
 *
 * 섬 간 보기(4.3.3 ②)면 섬 쌍의 관계를 건수 순으로 늘어놓는다. 누르면 보통
 * 관계 탭(①)으로 넘어간다.
 *
 * **근거 사건에 제목이 없다.** 사건 제목에 피해 조직 이름이 들어 있어서
 * 굽기가 안 싣는다 (2026-09-23 결정).
 */

"use client";

import { useEffect, useRef } from "react";

import PanelShell from "./PanelShell";
import { Chip, KindDot } from "./RelBits";
import type { MapLayout } from "@/lib/layout";
import { quarterOfDate } from "@/lib/quarter";
import {
  CONF_CHIP,
  CONF_LABEL,
  KIND_CHIP,
  KIND_LABEL,
  SIZE_LABEL,
  VERDICT_LABEL,
  connectedIslandCount,
  dayText,
  historyOrder,
  historyText,
  kindMix,
  partnerCount,
  selectedText,
  summaryText,
  type RelView,
} from "@/lib/relations";
import type { RelPair } from "./RelationTab";

export type RelationPanelProps = {
  open: boolean;
  onToggle: (open: boolean) => void;
  layout: MapLayout;
  /** 중심 영토의 관계 (`touching`). 섬 간 보기면 그 섬 쌍의 관계 */
  views: RelView[];
  center: string | null;
  selected: string | null;
  onSelect: (relationId: string | null) => void;
  pair: RelPair | null;
  onPairPick: (v: RelView) => void;
};

function quarterLabel(iso: string): string {
  return quarterOfDate(new Date(iso)).replace("-", " ");
}

export default function RelationPanel(p: RelationPanelProps) {
  const byId = new Map(p.layout.territories.map((t) => [t.territoryId, t]));
  const islands = new Map(p.layout.islands.map((i) => [i.islandKey, i]));
  const nameOf = (id: string) => byId.get(id)?.name ?? id;
  const islandOf = (id: string) => byId.get(id)?.islandKey;
  const sel = p.views.find((v) => v.rel.id === p.selected) ?? null;

  const picked = useRef<HTMLLIElement>(null);
  // 설계서 4.3.3 ① 「관계 연혁에서 해당 항목 강조, 그 위치로 스크롤」
  useEffect(() => {
    picked.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [p.selected]);

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
                  className="flex w-full flex-col gap-s2 rounded-[12px] border border-edge bg-card px-s4 py-s3 text-left hover:border-edge-strong"
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
  const mix = kindMix(p.views);
  const total = mix.reduce((s, m) => s + m.count, 0);
  const partners = p.center ? partnerCount(p.views, p.center) : 0;
  const islandN = p.center ? connectedIslandCount(p.views, p.center, islandOf) : 0;
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
        kindLabel: "TERRITORY",
        kindToken: null,
        kindAccent: true,
        stateLabel: c ? "선택됨" : "선택 없음",
        title: c?.name ?? "관계",
        subtitle: c
          ? `${cIsl?.name ?? ""} 섬 · 사건 ${c.metrics.eventCount}건 · 활동도 ${c.metrics.activity} · 연결된 섬 ${islandN}`
          : "이 기준일에 기록된 관계가 없습니다",
      };

  return (
    <PanelShell open={p.open} onToggle={p.onToggle} header={header}>
      <section className="flex flex-col gap-s3">
        <div className="flex items-baseline justify-between">
          <h3 className="text-[13px] font-semibold text-strong">관계 유형 구성</h3>
          <span className="text-[11px] tabular-nums text-label">사건 {total}건</span>
        </div>
        <div className="flex h-[6px] overflow-hidden rounded-full bg-bar-track">
          {mix.map((m) => (
            <div key={m.kind} style={{ width: `${(m.count / total) * 100}%`, background: `var(--t-rel-${m.kind})` }} />
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
          {sel ? selectedText(sel, c.territoryId, p.views, nameOf) : summaryText(c.name, p.views, partners, islandN)}
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
          <ul className="flex flex-col divide-y divide-[var(--t-border-divider)] rounded-[12px] border border-edge bg-card">
            {sel.evidence.map((e) => (
              <li key={e.id} className="flex flex-col gap-[2px] px-s4 py-s2 text-[12px]">
                <span className="flex items-baseline gap-s3">
                  <span className="font-mono tabular-nums text-title">{dayText(e.postedAt)}</span>
                  <span className="min-w-0 flex-1 truncate text-right text-body">{nameOf(e.territoryId)}</span>
                </span>
                <span className="text-[11px] text-label">
                  {VERDICT_LABEL[e.verdict]} · {SIZE_LABEL[e.size]}
                </span>
              </li>
            ))}
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
              return (
                <li
                  key={v.rel.id}
                  ref={on ? picked : undefined}
                  className={[
                    "flex flex-col gap-s2 rounded-[12px] border px-s4 py-s3",
                    on ? "border-[var(--t-accent)] bg-row-selected" : "border-transparent",
                  ].join(" ")}
                >
                  <div className="flex flex-wrap items-center gap-s2">
                    <span
                      aria-hidden
                      className="size-[10px] rounded-full border-2"
                      style={{
                        borderColor: on ? "var(--t-accent)" : "var(--t-info)",
                        background: on ? "var(--t-accent)" : "transparent",
                      }}
                    />
                    <span className="font-mono text-[12px] tabular-nums text-body">
                      {v.first ? quarterLabel(v.first) : "시작 모름"}
                    </span>
                    <Chip tone={KIND_CHIP[v.rel.kind]}>{KIND_LABEL[v.rel.kind]}</Chip>
                    <Chip tone={CONF_CHIP[v.rel.confidence]}>{CONF_LABEL[v.rel.confidence]}</Chip>
                    <span className="flex-1" />
                    <span className="text-[13px] font-semibold tabular-nums" style={{ color: on ? "var(--t-accent)" : "var(--t-text-strong)" }}>
                      {v.count}건
                    </span>
                  </div>
                  <p className="text-[14px] font-semibold text-title">
                    {nameOf(v.rel.from)} → {nameOf(v.rel.to)}
                  </p>
                  <p className="text-[12px] leading-[1.7] text-body">{historyText(v, nameOf)}</p>
                  <button
                    type="button"
                    onClick={() => p.onSelect(on ? null : v.rel.id)}
                    className="self-start text-[12px] hover:underline"
                    style={{ color: "var(--t-web-connection)" }}
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
