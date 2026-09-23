/**
 * 검색 — 설계서 4.2.2.
 *
 * **여섯 묶음 가운데 엔티티 하나만 채운다.** 나머지는 재료가 없다.
 *
 *   엔티티      됨. 영토 이름과 별칭으로 찾는다
 *   행위자      행위자 DB 를 아직 안 읽는다 (설계서 4.3.8 이 새로 요구한다)
 *   피해 대상   **안 만든다.** 피해 조직 이름을 지도에 안 내기로 했다 (2026-09-23)
 *   사건        사건에 제목이 없다. 제목은 게시글 본문에서 오고 반출 관문이 있다
 *   관계        관계선 DB 가 노션에 없다 (설계서 5.1)
 *
 * 그래서 범위 탭과 섬 필터도 안 만들었다. 묶음이 하나뿐이면 거를 것이 없다.
 * 묶음이 늘면 그때 같이 붙인다.
 *
 * **전체 결과 화면(⑦-10d)도 안 만들었다.** 엔티티만으로는 자동완성에서 다
 * 보인다. 영토가 수십 곳으로 늘면 그때 만든다.
 */

"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { MapLayout, TerritoryShape } from "@/lib/layout";

/** 설계서 4.2.2 — 2글자부터 자동완성 */
const MIN_LEN = 2;
/** 최근 검색 5개 */
const RECENT_MAX = 5;
/** 활동도 급상승 3곳 (설계서 3.8) */
const SURGE_MAX = 3;

export type SearchOverlayProps = {
  layout: MapLayout;
  onClose: () => void;
  /** 고른 영토로 간다. 지도 탭으로 옮기고 그 영토를 고른다 */
  onPick: (territoryId: string) => void;
  /** 최근 검색. 닫으면 이 부품이 사라지므로 부모가 들고 있는다 */
  recent: string[];
  onRecent: (names: string[]) => void;
};

type Hit = {
  t: TerritoryShape;
  /** 0 완전 일치 · 1 앞부분 · 2 중간. 이 순서로 세운다 (설계서 4.2.2) */
  rank: number;
  /** 이름에서 일치한 자리. 굵게 칠하는 데 쓴다 */
  at: number;
  /** 별칭으로 걸렸으면 그 별칭 */
  via?: string;
};

function match(t: TerritoryShape, q: string): Hit | null {
  // 이름과 별칭 둘 다 본다 (설계서 4.2.2 「영토 이름과 별칭」)
  const cand: { s: string; via?: string }[] = [
    { s: t.name },
    ...t.aliases.map((a) => ({ s: a, via: a })),
  ];

  let best: Hit | null = null;
  for (const c of cand) {
    const i = c.s.toLowerCase().indexOf(q);
    if (i < 0) continue;
    // 완전 일치 · 앞부분 · 중간 차례로 센다
    const rank = c.s.toLowerCase() === q ? 0 : i === 0 ? 1 : 2;
    if (!best || rank < best.rank) {
      // 굵게 칠하는 것은 이름에서 걸렸을 때만 한다. 별칭으로 걸렸으면
      // 화면에 뜨는 것이 이름이라 칠할 자리가 없다
      best = { t, rank, at: c.via ? -1 : i, via: c.via };
    }
  }
  return best;
}

/** 이름에서 일치한 자리를 굵게. 설계서 4.2.2 「일치 글자 굵게 표시」 */
function Marked({ text, at, len }: { text: string; at: number; len: number }) {
  if (at < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, at)}
      <span className="font-bold" style={{ color: "var(--t-accent)" }}>
        {text.slice(at, at + len)}
      </span>
      {text.slice(at + len)}
    </>
  );
}

/**
 * **열 때마다 새로 마운트된다.** 부르는 쪽이 `{searching && <SearchOverlay/>}`
 * 로 쓴다. 그래야 입력 내용이 저절로 비워진다 — 설계서 4.2.2 가 「닫으면 입력
 * 내용 삭제」라고 적었다. `open` 을 prop 으로 받아 effect 에서 비우는 쪽은
 * 리액트가 권하지 않는 모양새다.
 *
 * 최근 검색은 그래서 부모가 들고 있는다.
 */
export default function SearchOverlay({
  layout,
  onClose,
  onPick,
  recent,
  onRecent,
}: SearchOverlayProps) {
  const [q, setQ] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const hits = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (needle.length < MIN_LEN) return [];
    return layout.territories
      .map((t) => match(t, needle))
      .filter((h): h is Hit => h !== null)
      .sort(
        (a, b) =>
          a.rank - b.rank || b.t.metrics.activity - a.t.metrics.activity,
      );
  }, [layout, q]);

  /** 활동도 급상승 — 설계서 3.8 의 `surge7d` 가 큰 순서 */
  const surging = useMemo(
    () =>
      [...layout.territories]
        .filter((t) => t.metrics.surge7d > 0)
        .sort((a, b) => b.metrics.surge7d - a.metrics.surge7d)
        .slice(0, SURGE_MAX),
    [layout],
  );

  /** 결과가 없을 때 「이것을 찾으셨나요?」 — 앞 두 글자가 같은 것 */
  const nearby = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (needle.length < MIN_LEN || hits.length > 0) return [];
    return layout.territories
      .filter((t) => t.name.toLowerCase().startsWith(needle.slice(0, 2)))
      .slice(0, 3);
  }, [layout, q, hits.length]);

  const go = (t: TerritoryShape) => {
    onRecent([t.name, ...recent.filter((x) => x !== t.name)].slice(0, RECENT_MAX));
    onPick(t.territoryId);
    onClose();
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => Math.min(hits.length - 1, c + 1));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(0, c - 1));
    }
    if (e.key === "Enter" && hits[cursor]) go(hits[cursor].t);
  };

  const needle = q.trim().toLowerCase();

  return (
    <div
      className="fixed inset-0 z-50 flex justify-center pt-[72px]"
      style={{ background: "rgb(0 0 0 / 45%)" }}
      onClick={onClose}
    >
      <div
        className="flex h-fit max-h-[70vh] w-[560px] flex-col overflow-hidden rounded-[14px] border border-edge bg-panel shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center gap-s3 border-b border-divider px-s5 py-s4">
          <span aria-hidden className="text-[13px] text-label">
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
            className="flex-1 bg-transparent text-[14px] text-title outline-none placeholder:text-disabled"
          />
          <kbd className="rounded bg-kbd px-s2 py-[2px] text-[10px] text-label">
            Esc
          </kbd>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {needle.length < MIN_LEN ? (
            <div className="flex flex-col gap-s5 px-s5 py-s4">
              {recent.length > 0 && (
                <section>
                  <h3 className="text-[11px] text-label">최근 검색</h3>
                  <ul className="mt-s3 flex flex-wrap gap-s2">
                    {recent.map((r) => (
                      <li key={r}>
                        <button
                          type="button"
                          onClick={() => setQ(r)}
                          className="rounded-[8px] border border-edge px-s3 py-[3px] text-[12px] text-body"
                        >
                          {r}
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section>
                <h3 className="text-[11px] text-label">
                  활동도 급상승 · 지난 7일
                </h3>
                {surging.length === 0 ? (
                  <p className="mt-s3 text-[12px] text-label">
                    지난 7일에 늘어난 곳이 없습니다
                  </p>
                ) : (
                  <ul className="mt-s3 flex flex-col gap-s1">
                    {surging.map((t) => (
                      <li key={t.territoryId}>
                        <button
                          type="button"
                          onClick={() => go(t)}
                          className="flex w-full items-center gap-s3 rounded-[8px] px-s3 py-s2 text-left hover:bg-card"
                        >
                          <span
                            aria-hidden
                            className="size-[8px] shrink-0 rounded-full"
                            style={{
                              background: `var(--t-island-${t.token})`,
                            }}
                          />
                          <span className="flex-1 text-[13px] text-body">
                            {t.name}
                          </span>
                          <span
                            className="text-[11px] tabular-nums"
                            style={{ color: "var(--t-trend-up)" }}
                          >
                            ▲{Math.round(t.metrics.surge7d * 10) / 10}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <p className="text-[11px] leading-[1.7] text-label">
                지금은 엔티티(포럼 · 랜섬웨어 그룹 · 텔레그램 채널)만 찾습니다.
                행위자 · 사건 · 관계는 재료가 아직 없습니다.
              </p>
            </div>
          ) : hits.length === 0 ? (
            <div className="flex flex-col gap-s3 px-s5 py-s5">
              <p className="text-[13px] text-body">찾은 것이 없습니다</p>
              {nearby.length > 0 && (
                <>
                  <p className="text-[11px] text-label">이것을 찾으셨나요?</p>
                  <ul className="flex flex-wrap gap-s2">
                    {nearby.map((t) => (
                      <li key={t.territoryId}>
                        <button
                          type="button"
                          onClick={() => go(t)}
                          className="rounded-[8px] border border-edge px-s3 py-[3px] text-[12px] text-body"
                        >
                          {t.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          ) : (
            <ul>
              <li className="flex items-center justify-between px-s5 pb-s2 pt-s4">
                <span className="text-[11px] text-label">엔티티</span>
                <span className="text-[11px] tabular-nums text-label">
                  {hits.length}
                </span>
              </li>
              {hits.map((h, i) => {
                const on = i === cursor;
                const m = h.t.metrics;
                return (
                  <li key={h.t.territoryId}>
                    <button
                      type="button"
                      onMouseEnter={() => setCursor(i)}
                      onClick={() => go(h.t)}
                      className={
                        "flex w-full items-center gap-s3 px-s5 py-s3 text-left " +
                        (on ? "bg-row-selected" : "")
                      }
                    >
                      <span
                        aria-hidden
                        className="size-[10px] shrink-0 rounded-full"
                        style={{ background: `var(--t-island-${h.t.token})` }}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13px] font-semibold text-strong">
                          <Marked
                            text={h.t.name}
                            at={h.at}
                            len={needle.length}
                          />
                        </span>
                        <span className="block text-[11px] tabular-nums text-label">
                          활동도 {m.activity} · 사건 {m.eventCount}건
                          {h.via && ` · 별칭 ${h.via}`}
                        </span>
                      </span>
                      <span className="shrink-0 rounded-[6px] bg-card px-s2 py-[2px] text-[11px] tabular-nums text-label">
                        {m.eventCount}건
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="flex shrink-0 gap-s5 border-t border-divider px-s5 py-s3 text-[11px] text-label">
          <span>↵ 지도에서 열기</span>
          <span>↑↓ 고르기</span>
          <span>Esc 닫기</span>
        </div>
      </div>
    </div>
  );
}
