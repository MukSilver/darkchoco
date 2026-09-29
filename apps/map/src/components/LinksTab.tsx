/**
 * 패널 [연결] 탭 — 설계서 4.3.1 · 4.3.2 · 4.3.3 · 4.3.8, 피그마 ⑦-3.
 *
 *   영토     연결된 엔티티 + 유형 간 연결 요약
 *   행위자   활동한 영토 (관계 종류 「활동」, 행위자 → 영토)
 *   섬       유형 간 연결 요약만
 *
 * 행 동작은 4.3.3 표 그대로다.
 *
 *   한 번 클릭        행 선택. 지도에 그 관계선만 그리고 상대 영토가 떠오른다
 *   같은 행 다시 클릭  선택 해제
 *   더블클릭          관계 탭으로 간다
 *   「관계 보기 ›」    더블클릭과 같다. 마우스를 올린 줄과 고른 줄에서 보인다 (한 번 클릭으로도
 *                     관계 탭에 갈 수 있게 — 2026-09-28 최현서 9번)
 *
 * 건수는 지도 관계선 라벨 · 관계 연혁과 같은 값이다 (설계서 3.9, `relations.ts`).
 */

"use client";

import { useEffect, type ReactNode } from "react";

import { Chip, IslandChip } from "./RelBits";
import { CONF_CHIP, CONF_LABEL, KIND_LABEL, dayText, partnerOf, type IslandPairRow, type RelView } from "@/lib/relations";

/** [연결] 탭에서 고른 행. 지도가 이것만 그린다 */
export type LinkSel =
  | { type: "rel"; id: string }
  | { type: "pair"; from: string; to: string }
  | null;

export type LinksTabProps = {
  mode: "territory" | "actor" | "island";
  /** 고른 영토 id. 섬을 골랐으면 없다 */
  selfId?: string;
  /** 연결된 엔티티 행 (`linkRows`) */
  rows: RelView[];
  /** 유형 간 연결 요약 (`islandPairs`) */
  pairs: IslandPairRow[];
  nameOf: (territoryId: string) => string;
  /** 영토 id → 섬 열쇠 */
  islandOf: (territoryId: string) => string | undefined;
  /** 섬 열쇠 → 이름 · 색 토큰 */
  islandInfo: (key: string) => { name: string; token: string };
  selected: LinkSel;
  onSelect: (s: LinkSel) => void;
  onOpenRel: (v: RelView) => void;
  onOpenPair: (p: IslandPairRow) => void;
  /** 줄에 마우스를 올린 것(뗄 때 null) — 지도에 그 관계선만 잠깐 (v2 6번) */
  onHover?: (s: LinkSel) => void;
};

/** 목록이 사라지면(관계 탭으로 · 선택이 바뀜) 마우스 올림을 비운다 — 사라진 줄은 떼기 신호를 안 보낸다 (검토) */
function useClearHover(onHover?: (s: LinkSel) => void) {
  useEffect(() => () => onHover?.(null), [onHover]);
}

function ym(iso: string | null): string {
  return iso ? iso.slice(0, 7) : "";
}

function Section({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-s3">
      <div className="flex items-baseline justify-between">
        <h3 className="text-[12px] text-label">{title}</h3>
        <span className="text-[11px] tabular-nums text-label">{count}</span>
      </div>
      {children}
    </section>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-[12px] border border-edge bg-card px-s4 py-s4 text-[12px] text-label">
      {children}
    </p>
  );
}

/**
 * 행 하나. 둥근 카드에 칩 줄 · 이름 줄 · 종류와 기간 줄이다 (피그마 ⑦-3).
 * 고른 행은 강조색 테두리다 — 설계서 5.3 이 「[연결] 행 선택 상태」를 시안에
 * 더할 일로 남겼다.
 */
function Row({
  on,
  onClick,
  onOpen,
  onHover,
  chips,
  count,
  title,
  meta,
}: {
  on: boolean;
  onClick: () => void;
  onOpen: () => void;
  onHover?: (on: boolean) => void;
  chips: ReactNode;
  count: number;
  title: ReactNode;
  meta: string;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={on}
      onClick={onClick}
      onDoubleClick={onOpen}
      onMouseEnter={onHover ? () => onHover(true) : undefined}
      onMouseLeave={onHover ? () => onHover(false) : undefined}
      onKeyDown={(e) => {
        if (e.key === "Enter") onOpen();
        if (e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className={[
        "group relative flex cursor-pointer select-none flex-col gap-s2 rounded-[12px] border px-s4 py-s4 outline-none",
        "focus-visible:ring-2 focus-visible:ring-[var(--t-accent)]",
        // 마우스 올림은 공통 규칙(`hover-edge`)에 맞춰 바탕도 한 단계 밝힌다 (최현서 1 · 9번)
        on ? "border-[var(--t-accent)] bg-accent-subtle" : "border-edge bg-card hover:border-edge-strong hover:bg-track",
      ].join(" ")}
    >
      <div className="flex items-center gap-s2">
        {chips}
        <span className="flex-1" />
        <span className="text-[14px] font-semibold tabular-nums text-strong">{count}건</span>
      </div>
      <div className="text-[14px] font-semibold text-title">{title}</div>
      <span className="truncate font-mono text-[11px] text-label">{meta}</span>
      {/* 줄 위에 겹쳐 띄운다. 자리를 차지하면 기간 글씨가 잘린다 */}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onOpen();
        }}
        // 고른 줄에서도 보인다 — 한 번 눌러 고른 뒤 한 번 더 누르면 관계 탭이다. 더블클릭을 몰라도
        // 한 번 클릭으로 갈 수 있게 (2026-09-28 최현서 9번). 마우스를 안 올린 줄에서는 설계서
        // 4.3.3 L604 대로 숨긴다
        // 고른 줄에서는 흐름 안(줄 오른쪽 아래)에 놓는다 — 줄 위에 띄우면 기간 줄 끝(최근 관측 월)을
        // 늘 가렸다 (2026-09-28 검토). 마우스만 올린 줄은 전처럼 위에 띄운다
        className={[
          "rounded-[6px] border px-s2 py-[2px] text-[11px] text-title transition-opacity hover:border-edge-strong",
          on
            ? "self-end border-accent-edge bg-accent-subtle"
            : "absolute bottom-s3 right-s3 border-transparent bg-card opacity-0 focus-visible:opacity-100 group-hover:opacity-100",
        ].join(" ")}
      >
        관계 보기 ›
      </button>
    </div>
  );
}

function Arrow({ from, to }: { from: string; to: string }) {
  return (
    <>
      {from} <span className="font-normal text-label">→</span> {to}
    </>
  );
}

export default function LinksTab(p: LinksTabProps) {
  useClearHover(p.onHover);
  const relRows = p.mode === "actor" ? p.rows.filter((v) => v.rel.kind === "activity") : p.rows;
  const partners = p.selfId ? new Set(relRows.map((v) => partnerOf(v, p.selfId as string))).size : 0;

  const relList =
    p.mode === "island" ? null : (
      <Section title={p.mode === "actor" ? "활동한 영토" : "연결된 엔티티"} count={partners}>
        {relRows.length === 0 ? (
          <Empty>
            {p.mode === "actor" ? "이 기준일에 활동한 영토가 없습니다." : "이 기준일에 연결된 엔티티가 없습니다."}
          </Empty>
        ) : (
          relRows.map((v) => {
            const other = partnerOf(v, p.selfId as string);
            const isl = p.islandOf(other);
            const info = isl ? p.islandInfo(isl) : null;
            const on = p.selected?.type === "rel" && p.selected.id === v.rel.id;
            return (
              <Row
                key={v.rel.id}
                on={on}
                onClick={() => p.onSelect(on ? null : { type: "rel", id: v.rel.id })}
                onOpen={() => p.onOpenRel(v)}
                onHover={p.onHover ? (h) => p.onHover?.(h ? { type: "rel", id: v.rel.id } : null) : undefined}
                chips={
                  <>
                    {info && <IslandChip token={info.token}>{info.name}</IslandChip>}
                    <Chip tone={CONF_CHIP[v.rel.confidence]}>{CONF_LABEL[v.rel.confidence]}</Chip>
                  </>
                }
                count={v.count}
                title={<Arrow from={p.nameOf(v.rel.from)} to={p.nameOf(v.rel.to)} />}
                meta={
                  v.fromRegistry
                    ? `${KIND_LABEL[v.rel.kind]} · 근거 사건 없음`
                    : `${KIND_LABEL[v.rel.kind]} · ${ym(v.first)} → ${ym(v.last)}`
                }
              />
            );
          })
        )}
      </Section>
    );

  // 행위자는 활동한 영토만 적는다 (설계서 4.3.8)
  const pairList =
    p.mode === "actor" ? null : (
      <Section title="유형 간 연결 · 요약" count={p.pairs.length}>
        {p.pairs.length === 0 ? (
          <Empty>이 기준일에 다른 섬과 이어진 관계가 없습니다.</Empty>
        ) : (
          p.pairs.map((r) => {
            const on = p.selected?.type === "pair" && p.selected.from === r.from && p.selected.to === r.to;
            return (
              <Row
                key={`${r.from}>${r.to}`}
                on={on}
                onClick={() => p.onSelect(on ? null : { type: "pair", from: r.from, to: r.to })}
                onOpen={() => p.onOpenPair(r)}
                onHover={p.onHover ? (h) => p.onHover?.(h ? { type: "pair", from: r.from, to: r.to } : null) : undefined}
                chips={
                  <>
                    <Chip tone="neutral">유형 간</Chip>
                    <span className="text-[11px] tabular-nums text-label">엔티티 {r.pairs}쌍</span>
                  </>
                }
                count={r.count}
                title={<Arrow from={p.islandInfo(r.from).name} to={p.islandInfo(r.to).name} />}
                meta={`${KIND_LABEL[r.topKind]}${r.last ? ` · 최근 ${dayText(r.last)}` : ""}`}
              />
            );
          })
        )}
      </Section>
    );

  return (
    <>
      {relList}
      {pairList}
    </>
  );
}
