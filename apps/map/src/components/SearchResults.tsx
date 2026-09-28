/**
 * 검색 전체 결과 — 설계서 4.2.2 「전체 결과 (⑦-10d)」, 피그마 ⑦-10d.
 *
 * 검색 창에서 Shift+Enter 를 누르거나 「전체 결과 N건」을 누르면 가운데 화면이
 * 이것으로 바뀐다. 오른쪽 패널은 그대로다.
 *
 *   탭      전체 / 엔티티 / 행위자 / 사건 / 관계 (건수)
 *   필터    섬 · 기간 · 신뢰도 · 정렬(관련도 / 최신순 / 건수순)
 *   묶음    전체 탭에서는 묶음마다 5줄과 「모두 보기」
 *   줄 버튼 엔티티 「지도에서 보기」 · 행위자 「활동 보기」 · 사건 「상세」 · 관계 「관계 탭」
 *
 * 웹 필터는 없다. 지금 찾는 대상이 다크웹 하나뿐이라 거를 것이 없다 — 오픈웹 검색은
 * 오픈웹 팀 몫이다 (피그마 ⑦-10d 에도 없다). 대신 엔티티 · 행위자 줄 아랫줄에 웹을
 * 적는다 (설계서 5.3 「결과 행에 웹 표시」, `SearchRows` `WebTag`). 피해 대상
 * 탭도 없다 (2026-09-23 결정). 사건 「상세」는 보고서 팝업(4.3.4)을 이 화면 위에 연다 —
 * 닫으면 결과 목록으로 돌아온다. 검색 창(자동완성)에서 사건을 고를 때는 팝업을 안 띄우고
 * 지도로 가서 강조만 한다 (설계서 4.2.2 L462 「보고서 팝업은 자동으로 띄우지 않음」).
 */

"use client";

import { useEffect, useRef, useState } from "react";

import { hitKey, rowParts, type SearchCtx } from "./SearchRows";
import { DARK_ISLANDS } from "@/lib/islands";
import { CONF_LABEL } from "@/lib/relations";
import {
  DAYS,
  NO_FILTER,
  SCOPES,
  SORTS,
  filterText,
  narrowed,
  needleOf,
  total,
  type EventHit,
  type Hit,
  type Results,
  type Scope,
  type SearchFilter,
} from "@/lib/search";
import type { Confidence } from "@/lib/types";

/** 전체 탭에서 묶음마다 보이는 줄 */
const PER_BUNDLE = 5;

const BUNDLES: { key: Exclude<Scope, "all">; label: string }[] = [
  { key: "entity", label: "엔티티" },
  { key: "actor", label: "행위자" },
  { key: "event", label: "사건" },
  { key: "rel", label: "관계" },
];

const BUTTON: Record<Hit["kind"], string> = {
  entity: "지도에서 보기",
  actor: "활동 보기",
  event: "상세",
  rel: "관계 탭",
};

const CONFS: (Confidence | null)[] = [null, "confirmed", "high", "estimated"];

/** 필터 단추 하나와 펼친 목록. 바깥을 누르거나 Esc 를 누르면 닫힌다 */
function Menu({
  label,
  value,
  children,
}: {
  label: string;
  value: string;
  children: (close: () => void) => React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  // 열린 동안 Esc 는 메뉴만 닫고 멈춘다. 안 멈추면 page.tsx 의 창 Esc 가 결과 화면 전체를
  // 닫았다 (2026-09-28 코드 분석, `SearchOverlay` 의 Esc 와 같은 까닭). 단추의 onKeyDown 이
  // 아니라 창의 잡기 단계에서 받는다 — 사파리는 단추를 눌러도 초점을 안 옮겨 키가 단추로 안 온다
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const now = document.activeElement;
      const inside = !!wrap.current?.contains(now);
      // 초점이 다른 자리(메뉴를 연 채 Ctrl+K 로 연 검색 창 따위)에 있으면 그쪽 Esc 다
      if (!inside && now && now !== document.body) return;
      e.stopPropagation();
      e.preventDefault();
      // 목록 항목에 있던 초점은 항목이 사라지며 문서 맨 앞으로 빠진다. 단추로 돌려준다
      if (inside) button.current?.focus();
      setOpen(false);
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open]);

  return (
    <div ref={wrap} className="relative">
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-s1 rounded-[10px] border border-edge bg-panel px-s3 py-s2 text-[12px] text-body hover-edge"
      >
        {label}: {value}
        <span aria-hidden className="text-[9px] text-label">
          ▼
        </span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" aria-hidden onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-[calc(100%+4px)] z-40 flex min-w-[140px] flex-col rounded-[10px] border border-edge bg-panel py-s1 shadow-xl">
            {children(() => setOpen(false))}
          </div>
        </>
      )}
    </div>
  );
}

function Opt({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      // 마우스 올림은 공통 줄 규칙. 전에는 패널 바탕과 거의 같은 bg-card 라 없는 셈이었다 (최현서 1번)
      className={
        "flex items-center gap-s2 px-s3 py-s1 text-left text-[12px] hover-row " +
        (on ? "font-semibold text-title" : "text-body")
      }
    >
      <span aria-hidden className="w-[10px] text-[10px]" style={{ color: "var(--t-accent)" }}>
        {on ? "✓" : ""}
      </span>
      {children}
    </button>
  );
}

export default function SearchResults({
  ctx,
  q,
  results,
  filter,
  onFilter,
  onPick,
  onOpenEvent,
  onClose,
}: {
  ctx: SearchCtx;
  q: string;
  results: Results;
  filter: SearchFilter;
  onFilter: (f: SearchFilter) => void;
  onPick: (h: Hit) => void;
  /** 사건 「상세」 — 보고서 팝업. 없으면 다른 줄처럼 `onPick` 으로 간다 */
  onOpenEvent?: (h: EventHit) => void;
  /** 「검색 결과 닫기 ×」. 없으면 단추를 안 낸다 */
  onClose?: () => void;
}) {
  const needle = needleOf(q);
  const count = (s: Scope) => (s === "all" ? total(results) : results[s].length);
  const shown = BUNDLES.filter((b) => (filter.scope === "all" || filter.scope === b.key) && results[b.key].length > 0);

  const islandValue = filter.islands.length
    ? filter.islands.length > 2
      ? `${ctx.islandName(filter.islands[0])} 외 ${filter.islands.length - 1}`
      : filter.islands.map(ctx.islandName).join(" · ")
    : "전체";

  const row = (h: Hit) => {
    const p = rowParts(ctx, h, needle);
    return (
      <li key={hitKey(h)} className="flex items-center gap-s3 border-t border-divider px-s5 py-s3 first:border-t-0">
        {p.icon}
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[14px] font-semibold text-strong">{p.title}</span>
          <span className="block truncate text-[12px] tabular-nums text-label">{p.sub}</span>
        </span>
        {h.kind === "event" && p.side}
        <button
          type="button"
          onClick={() => (h.kind === "event" && onOpenEvent ? onOpenEvent(h) : onPick(h))}
          className="shrink-0 rounded-[10px] border border-edge bg-panel px-s3 py-s2 text-[12px] text-body hover:border-accent-edge hover:text-title"
        >
          {BUTTON[h.kind]}
        </button>
      </li>
    );
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-s4">
      {/*
        범위 탭 줄 오른쪽 끝에 「검색 결과 닫기 ×」. 전에는 제목 줄의 화면 탭 자리에 있어서
        결과 화면에서는 화면 탭이 사라졌다 (2026-09-28 코드 분석 — 탭 버튼 자리 고정)
      */}
      <div className="flex shrink-0 items-end gap-s5 border-b border-divider">
      <div role="tablist" aria-label="검색 범위" className="flex gap-s5">
        {SCOPES.map((s) => {
          const on = s.key === filter.scope;
          const n = count(s.key);
          return (
            <button
              key={s.key}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => onFilter({ ...filter, scope: s.key })}
              // 안 고른 탭은 마우스를 올리면 밑줄 자리가 옅게 선다 — 글자색만으로는 안 보였다 (최현서 1번)
              className={
                "-mb-px flex items-baseline gap-s1 border-b-2 pb-s2 text-[14px] " +
                (on ? "font-semibold text-title" : "border-transparent text-label hover:border-edge-strong hover:text-body") +
                (n === 0 && !on ? " opacity-60" : "")
              }
              style={on ? { borderColor: "var(--t-accent)" } : undefined}
            >
              {s.label}
              <span className="text-[11px] tabular-nums text-label">{n}</span>
            </button>
          );
        })}
      </div>
        <div className="flex-1" />
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="mb-s2 shrink-0 whitespace-nowrap rounded-[10px] border border-edge px-s3 py-s1 text-[12px] text-body hover-edge"
          >
            검색 결과 닫기 ×
          </button>
        )}
      </div>

      <div className="flex shrink-0 flex-wrap gap-s2">
        <Menu label="섬" value={islandValue}>
          {() => (
            <>
              <Opt on={filter.islands.length === 0} onClick={() => onFilter({ ...filter, islands: [] })}>
                전체
              </Opt>
              {DARK_ISLANDS.map((isl) => {
                const on = filter.islands.includes(isl.id);
                return (
                  <Opt
                    key={isl.id}
                    on={on}
                    onClick={() =>
                      onFilter({
                        ...filter,
                        islands: on ? filter.islands.filter((x) => x !== isl.id) : [...filter.islands, isl.id],
                      })
                    }
                  >
                    <span
                      aria-hidden
                      className="size-[6px] rounded-full"
                      style={{ background: `var(--t-island-${ctx.token(isl.id)})` }}
                    />
                    {isl.name}
                  </Opt>
                );
              })}
            </>
          )}
        </Menu>
        <Menu label="기간" value={DAYS.find((x) => x.days === filter.days)?.label ?? "전체"}>
          {(close) =>
            DAYS.map((x) => (
              <Opt
                key={x.days}
                on={x.days === filter.days}
                onClick={() => {
                  onFilter({ ...filter, days: x.days });
                  close();
                }}
              >
                {x.label}
              </Opt>
            ))
          }
        </Menu>
        <Menu label="신뢰도" value={filter.conf ? CONF_LABEL[filter.conf] : "전체"}>
          {(close) =>
            CONFS.map((c) => (
              <Opt
                key={c ?? "all"}
                on={c === filter.conf}
                onClick={() => {
                  onFilter({ ...filter, conf: c });
                  close();
                }}
              >
                {c ? CONF_LABEL[c] : "전체"}
              </Opt>
            ))
          }
        </Menu>
        <Menu label="정렬" value={SORTS.find((x) => x.sort === filter.sort)?.label ?? "관련도"}>
          {(close) =>
            SORTS.map((x) => (
              <Opt
                key={x.sort}
                on={x.sort === filter.sort}
                onClick={() => {
                  onFilter({ ...filter, sort: x.sort });
                  close();
                }}
              >
                {x.label}
              </Opt>
            ))
          }
        </Menu>
        <p className="self-center text-[11px] text-label">
          기간은 사건 게시일 · 관계 마지막 본 날, 신뢰도는 관계에 겁니다
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {shown.length === 0 ? (
          <div className="flex flex-col items-center gap-s2 rounded-[14px] border border-edge px-s5 py-s6 text-center">
            <p className="text-[14px] font-semibold text-title">&apos;{q.trim()}&apos;에 대한 결과가 없습니다</p>
            <p className="text-[12px] text-label">필터: {filterText(filter, ctx.islandName)}</p>
            {(narrowed(filter) || filter.scope !== "all") && (
              <button
                type="button"
                onClick={() => onFilter({ ...NO_FILTER, sort: filter.sort })}
                className="mt-s2 rounded-[10px] border border-edge px-s3 py-s2 text-[12px] text-body hover-edge"
              >
                필터 초기화
              </button>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-s4">
            {shown.map((b) => {
              const list = results[b.key] as Hit[];
              const all = filter.scope !== "all";
              return (
                <section key={b.key} className="overflow-hidden rounded-[14px] border border-edge">
                  <div className="flex items-center justify-between border-b border-divider bg-card px-s5 py-s3">
                    <h3 className="text-[13px] text-body">
                      {b.label} <span className="tabular-nums">{list.length}</span>
                    </h3>
                    {!all && (
                      <button
                        type="button"
                        onClick={() => onFilter({ ...filter, scope: b.key })}
                        className="text-[12px] hover:underline"
                        style={{ color: "var(--t-info)" }}
                      >
                        모두 보기 →
                      </button>
                    )}
                  </div>
                  <ul>{(all ? list : list.slice(0, PER_BUNDLE)).map(row)}</ul>
                </section>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
