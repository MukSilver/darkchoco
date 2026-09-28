/**
 * 검색 창 — 설계서 4.2.2, 피그마 ⑦-10 · ⑦-10a · ⑦-10c.
 *
 * 머리띠 검색창 자리에서 열리고 그 아래로 목록이 펼쳐진다 (피그마). 계산은
 * `lib/search.ts`, 줄 모양은 `SearchRows.tsx` 에 있다.
 *
 *   입력 전 (⑦-10)     범위 탭 · 섬 필터 · 최근 검색 5개 · 활동도 급상승 3곳
 *   자동완성 (⑦-10a)   2글자부터. 엔티티 · 행위자 · 사건 · 관계 차례로 묶음마다 3개
 *   결과 없음 (⑦-10c)  철자가 가까운 이름 3개, 필터가 걸렸으면 「필터 초기화」
 *
 * 피해 대상 묶음은 안 만든다. 피해 조직 이름을 지도에 안 내기로 했다 (2026-09-23).
 * 범위 탭을 하나로 좁히면 그 묶음만 8개까지 보인다.
 *
 * Enter 는 고른 줄(처음에는 맨 위)을 열고, Shift+Enter 는 전체 결과 화면(⑦-10d)을
 * 연다. 결과를 고른 뒤의 동작은 부르는 쪽(`page.tsx`)이 가른다.
 */

"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { hitKey, hitOfRecent, rowParts, type SearchCtx } from "./SearchRows";
import { DARK_ISLANDS } from "@/lib/islands";
import type { MapLayout } from "@/lib/layout";
import {
  SCOPES,
  agoText,
  filterText,
  narrowed,
  nearby,
  needleOf,
  search,
  total,
  NO_FILTER,
  type Hit,
  type Recent,
  type Results,
  type SearchFilter,
} from "@/lib/search";

/** 설계서 4.2.2 — 2글자부터 자동완성 */
const MIN_LEN = 2;
/** 묶음마다 보이는 줄 (4.2.2). 범위를 하나로 좁히면 더 보인다 */
const PER_BUNDLE = 3;
const PER_SCOPE = 8;
/** 활동도 급상승 3곳 (설계서 3.8) */
const SURGE_MAX = 3;

const BUNDLES: { key: keyof Results; label: string }[] = [
  { key: "entity", label: "엔티티" },
  { key: "actor", label: "행위자" },
  { key: "event", label: "사건" },
  { key: "rel", label: "관계" },
];

export type SearchOverlayProps = {
  ctx: SearchCtx;
  /** 활동도 급상승을 뽑는 기준일 지도 */
  layout: MapLayout;
  /** 처음 채워 둘 검색어. 「검색으로 돌아가기」(⑦-10b)가 넘긴다 */
  initialQ: string;
  filter: SearchFilter;
  onFilter: (f: SearchFilter) => void;
  /** 최근 검색. 닫으면 이 부품이 사라지므로 부모가 들고 있는다 */
  recent: Recent[];
  onClearRecent: () => void;
  onClose: () => void;
  onPick: (h: Hit, q: string) => void;
  /** Shift+Enter — 전체 결과 화면 */
  onAll: (q: string) => void;
  /** 같은 일치 단계 안의 차례 (기준일 활동도) */
  weightOf: (id: string) => number;
};

type Row = { key: string; hit: Hit; recent?: Recent };

/**
 * **열 때마다 새로 마운트된다.** 부르는 쪽이 `{open && <SearchOverlay/>}` 로 쓴다.
 * 그래야 입력 내용이 저절로 비워진다 — 설계서 4.2.2 가 「닫으면 입력 내용 삭제」
 * 라고 적었다. 최근 검색과 필터는 그래서 부모가 들고 있는다.
 */
export default function SearchOverlay({
  ctx,
  layout,
  initialQ,
  filter,
  onFilter,
  recent,
  onClearRecent,
  onClose,
  onPick,
  onAll,
  weightOf,
}: SearchOverlayProps) {
  const [q, setQ] = useState(initialQ);
  const [cursor, setCursor] = useState(0);
  // 최근 검색 시각 배지의 「지금」. 열 때 한 번 잡는다 — 창을 연 채 몇 분이 흘러도 배지가 안 바뀐다
  const [now] = useState(() => Date.now());
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputRef.current?.select();
  }, []);

  const needle = needleOf(q);
  const typed = needle.length >= MIN_LEN;

  const results = useMemo(
    () => (typed ? search(ctx.ix, q, filter, weightOf) : null),
    [ctx.ix, q, filter, weightOf, typed],
  );

  /** 활동도 급상승 — 설계서 3.8 의 `surge7d` 가 큰 순서 */
  const surging = useMemo(
    () =>
      [...layout.territories]
        .filter((t) => t.metrics.surge7d > 0)
        .sort((a, b) => b.metrics.surge7d - a.metrics.surge7d)
        .slice(0, SURGE_MAX),
    [layout],
  );

  const per = filter.scope === "all" ? PER_BUNDLE : PER_SCOPE;
  const bundles = results
    ? BUNDLES.filter((b) => filter.scope === "all" || filter.scope === b.key)
        .map((b) => ({ ...b, all: results[b.key] as Hit[] }))
        .filter((b) => b.all.length > 0)
    : [];
  const shownTotal = results
    ? filter.scope === "all"
      ? total(results)
      : (results[filter.scope] as Hit[]).length
    : 0;

  const near = useMemo(
    () => (typed && shownTotal === 0 ? nearby(ctx.ix, q) : []),
    [ctx.ix, q, typed, shownTotal],
  );

  // 화살표로 오가는 줄. 입력 전에는 최근 검색과 급상승, 입력 뒤에는 보이는 결과
  const rows: Row[] = [];
  if (!typed) {
    for (const r of recent) {
      const hit = hitOfRecent(ctx.ix, r);
      if (hit) rows.push({ key: `recent:${hitKey(hit)}`, hit, recent: r });
    }
    for (const t of surging) {
      const e = ctx.ix.byId.get(t.territoryId);
      if (e) rows.push({ key: `surge:${e.id}`, hit: { kind: "entity", e, m: { rank: 0, at: -1 } } });
    }
  } else if (shownTotal > 0) {
    for (const b of bundles) for (const h of b.all.slice(0, per)) rows.push({ key: hitKey(h), hit: h });
  } else {
    for (const e of near) rows.push({ key: `near:${e.id}`, hit: { kind: "entity", e, m: { rank: 0, at: -1 } } });
  }
  const at = Math.min(cursor, Math.max(0, rows.length - 1));

  useEffect(() => {
    listRef.current?.querySelector(`[data-row="${at}"]`)?.scrollIntoView({ block: "nearest" });
  }, [at]);

  /** 칩을 눌러도 입력칸에 포커스를 둔다 — 입력 · 화살표 · Enter · Esc 가 계속 입력칸에서 먹는다 */
  const keepFocus = (e: React.MouseEvent) => e.preventDefault();

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      // 창 쪽 Esc(선택 해제 · 전체 결과 닫기)까지 가지 않게 여기서 멈춘다. 안 멈추면 React 가
      // 이 키에서 상태를 바로 반영해, 새로 걸린 창 듣개가 같은 Esc 를 한 번 더 받는다
      e.stopPropagation();
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor(Math.min(rows.length - 1, at + 1));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor(Math.max(0, at - 1));
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (e.shiftKey) {
        if (typed) onAll(q);
        return;
      }
      if (rows[at]) onPick(rows[at].hit, typed ? q : "");
    }
  };

  const toggleIsland = (id: (typeof DARK_ISLANDS)[number]["id"]) =>
    onFilter({
      ...filter,
      islands: filter.islands.includes(id) ? filter.islands.filter((x) => x !== id) : [...filter.islands, id],
    });

  /** 한 줄. 버튼 하나다 */
  const line = (row: Row, i: number, side?: React.ReactNode, sub?: React.ReactNode) => {
    const p = rowParts(ctx, row.hit, typed ? needle : "");
    const on = i === at;
    return (
      <li key={row.key}>
        <button
          type="button"
          data-row={i}
          onMouseEnter={() => setCursor(i)}
          onClick={() => onPick(row.hit, typed ? q : "")}
          className={"flex w-full items-center gap-s3 px-s5 py-s2 text-left " + (on ? "bg-row-selected" : "")}
        >
          {p.icon}
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-semibold text-strong">
              {row.recent ? row.recent.label : p.title}
            </span>
            <span className="block truncate text-[11px] tabular-nums text-label">
              {sub ?? (row.recent ? row.recent.sub : p.sub)}
            </span>
          </span>
          {side ?? p.side}
          {on && typed && (
            <kbd className="shrink-0 rounded bg-kbd px-s1 py-[1px] text-[10px] text-label" aria-hidden>
              ↵
            </kbd>
          )}
        </button>
      </li>
    );
  };

  let i = -1;
  const next = () => (i += 1);

  return (
    <>
      <div className="fixed inset-0 z-40" aria-hidden onClick={onClose} />
      <div className="absolute inset-0 z-50">
        {/* 닫힌 검색창(`AppHeader`)과 같은 8px 네모. 테두리만 강조색이다 (피그마 ⑦-10a) */}
        <div
          className="flex h-full items-center gap-s2 rounded-[8px] border bg-input px-s4"
          style={{
            borderColor: "var(--t-accent)",
            boxShadow: "0 0 0 3px color-mix(in srgb, var(--t-accent) 20%, transparent)",
          }}
        >
          <span aria-hidden className="text-[12px] text-label">
            ⌕
          </span>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setCursor(0);
            }}
            onKeyDown={onKey}
            placeholder="노드 · 키워드 · 엔티티 검색"
            aria-label="검색"
            className="min-w-0 flex-1 bg-transparent text-[13px] text-title outline-none placeholder:text-disabled"
          />
          <kbd className="rounded bg-kbd px-s2 py-[2px] text-[10px] text-label">Esc</kbd>
        </div>

        <div className="absolute right-0 top-[calc(100%+8px)] flex max-h-[72vh] w-[480px] flex-col overflow-hidden rounded-[14px] border border-edge bg-panel shadow-2xl">
          <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto py-s2">
            {!typed ? (
              <>
                <div className="flex flex-col gap-s2 px-s5 pb-s3 pt-s2">
                  <div role="group" aria-label="범위" className="flex flex-wrap gap-s1">
                    {SCOPES.map((s) => {
                      const on = s.key === filter.scope;
                      return (
                        <button
                          key={s.key}
                          type="button"
                          aria-pressed={on}
                          onMouseDown={keepFocus}
                          onClick={() => onFilter({ ...filter, scope: s.key })}
                          // 안 고른 칩은 마우스를 올리면 바탕이 트랙 색으로 뜬다. 글자색만 바뀌어서는
                          // 패널 위 bg-card 칩이 달라 보이지 않았다 (2026-09-28 최현서 1번)
                          className={
                            "rounded-full px-s3 py-[3px] text-[12px] " +
                            (on ? "bg-title font-semibold text-panel" : "bg-card text-body hover-row hover:text-title")
                          }
                        >
                          {s.label}
                        </button>
                      );
                    })}
                  </div>
                  <div role="group" aria-label="섬 필터" className="flex flex-wrap gap-s1">
                    {DARK_ISLANDS.map((isl) => {
                      const on = filter.islands.includes(isl.id);
                      return (
                        <button
                          key={isl.id}
                          type="button"
                          aria-pressed={on}
                          onMouseDown={keepFocus}
                          onClick={() => toggleIsland(isl.id)}
                          // 범위 칩처럼 마우스를 올리면 바탕이 트랙 색으로 뜨고 글자가 밝다. 테두리 칩이라
                          // 테두리도 진해지는 `hover-edge` 다. 고른 칩은 다시 누르면 풀려서 테두리를
                          // 강조색으로 올린다. 전에는 hover 가 없었다 (최현서 1번)
                          className={
                            "flex items-center gap-s1 rounded-full border px-s3 py-[2px] text-[12px] " +
                            (on
                              ? "border-accent-edge bg-accent-subtle text-title hover:border-accent"
                              : "border-edge text-body hover-edge")
                          }
                        >
                          <span
                            aria-hidden
                            className="size-[6px] rounded-full"
                            style={{ background: `var(--t-island-${ctx.token(isl.id)})` }}
                          />
                          {isl.name}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {rows.some((r) => r.recent) && (
                  <section>
                    <div className="flex items-center justify-between px-s5 pb-s1 pt-s2">
                      <h3 className="text-[11px] text-label">최근 검색</h3>
                      <button type="button" onClick={onClearRecent} className="text-[11px] text-label hover:text-title">
                        전체 삭제
                      </button>
                    </div>
                    <ul>
                      {rows
                        .filter((r) => r.recent)
                        .map((r) =>
                          line(
                            r,
                            next(),
                            <span className="shrink-0 rounded-[6px] border border-edge px-s2 py-[1px] text-[11px] tabular-nums text-label">
                              {agoText(r.recent!.at, now)}
                            </span>,
                          ),
                        )}
                    </ul>
                  </section>
                )}

                <section>
                  <h3 className="px-s5 pb-s1 pt-s3 text-[11px] text-label">활동도 급상승 · 지난 7일</h3>
                  {surging.length === 0 ? (
                    <p className="px-s5 pb-s2 text-[12px] text-label">지난 7일에 늘어난 곳이 없습니다</p>
                  ) : (
                    <ul>
                      {rows
                        .filter((r) => !r.recent)
                        .map((r) => {
                          const t = surging.find((x) => x.territoryId === (r.hit.kind === "entity" ? r.hit.e.id : ""));
                          const e = r.hit.kind === "entity" ? r.hit.e : null;
                          return line(
                            r,
                            next(),
                            <span
                              className="shrink-0 rounded-[6px] border border-edge px-s2 py-[1px] text-[11px] tabular-nums"
                              style={{ color: "var(--t-trend-up)" }}
                            >
                              ▲ {Math.round((t?.metrics.surge7d ?? 0) * 10) / 10}
                            </span>,
                            e ? `${ctx.islandName(e.islandId)} · 활동도 ${t?.metrics.activity ?? 0}` : undefined,
                          );
                        })}
                    </ul>
                  )}
                </section>
              </>
            ) : shownTotal > 0 ? (
              bundles.map((b) => (
                <section key={b.key}>
                  <div className="flex items-center justify-between px-s5 pb-s1 pt-s3">
                    <h3 className="text-[11px] text-label">{b.label}</h3>
                    <span className="text-[11px] tabular-nums text-label">{b.all.length}</span>
                  </div>
                  <ul>{b.all.slice(0, per).map((h) => line({ key: hitKey(h), hit: h }, next()))}</ul>
                </section>
              ))
            ) : (
              <div className="flex flex-col">
                <div className="flex flex-col items-center gap-s2 px-s5 pb-s4 pt-s5 text-center">
                  <span aria-hidden className="text-[16px] text-label">
                    ⌕
                  </span>
                  <p className="text-[14px] font-semibold text-title">&apos;{q.trim()}&apos;에 대한 결과가 없습니다</p>
                  <p className="text-[12px] text-label">철자를 확인하거나 섬 · 기간 필터를 해제해 보세요</p>
                </div>
                {near.length > 0 && (
                  <section>
                    <h3 className="px-s5 pb-s1 text-[11px] text-label">이것을 찾으셨나요?</h3>
                    <ul>{rows.map((r) => line(r, next()))}</ul>
                  </section>
                )}
              </div>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-s4 border-t border-divider px-s5 py-s2 text-[11px] text-label">
            {!typed ? (
              <>
                <span>⌘K 열기</span>
                <span>↑↓ 이동</span>
                <span>↵ 선택</span>
                <span>Esc 닫기</span>
              </>
            ) : shownTotal > 0 ? (
              <>
                <span>↵ 지도에서 열기</span>
                <button type="button" onClick={() => onAll(q)} className="hover:text-title">
                  ⇧↵ 전체 결과 {shownTotal}건
                </button>
                <span>Esc 닫기</span>
                {(narrowed(filter) || filter.scope !== "all") && (
                  <span className="ml-auto truncate">필터 적용 중</span>
                )}
              </>
            ) : (
              <>
                <span className="truncate">필터: {filterText(filter, ctx.islandName)}</span>
                {(narrowed(filter) || filter.scope !== "all") && (
                  <button
                    type="button"
                    onMouseDown={keepFocus}
                    onClick={() => onFilter({ ...NO_FILTER, sort: filter.sort })}
                    className="shrink-0 hover:text-title"
                  >
                    필터 초기화
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
