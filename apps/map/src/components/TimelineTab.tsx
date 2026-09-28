/**
 * 타임라인 탭 — 설계서 4.3.7.
 *
 * 연도 칩으로 시점을 옮기고, 그 시점의 지도와 섬별 누적 추이를 본다.
 * **모든 값이 누적이다.** 그 시점까지의 사건 전부를 센다.
 *
 * **판 1.2 에서 단위가 해에서 분기로 바뀌었다** (설계서 4.3.7 「단위는 분기.
 * 한 해에 4 시점」). 연도 칩은 남아 있고 누르면 그 해 3분기로 간다. 그 해에
 * 3분기가 없으면(첫 해 · 올해) 데이터 안에서 가장 가까운 분기다 (`chipQuarter`).
 * ◀ / ▶▶ 는 한 해씩, 재생은 한 분기씩 옮긴다.
 *
 * 설계서는 「기준 시점은 스냅샷 바와 같은 값」이라고 적었다. 여기서 시점을
 * 옮기면 지도 탭의 기준일도 같이 움직인다.
 *
 * **시점 비교(⑦-9c)** 를 켜면 지도 두 장을 나란히 놓고 오른쪽 열이 변화 요약으로
 * 바뀐다. 연도 칩을 누르면 A → B 차례로 찍히고, 끄면 B 시점 한 장짜리로 돌아온다.
 * 비교 상태는 제목 옆 설명(「시점 비교 · A … ↔ B …」)도 읽어 화면(page)이 들고 있다.
 */

"use client";

import { useEffect, useMemo, type CSSProperties } from "react";

import HexMap from "./HexMap";
import { islandToken } from "@/lib/islands";
import type { MapLayout } from "@/lib/layout";
import { parseQuarter } from "@/lib/quarter";
import type { IslandCode } from "@/lib/types";
import {
  comparePick,
  compareStart,
  diff,
  growth,
  peakOf,
  stepYear,
  thumbBoxes,
  yearCards,
  yearChips,
  type Compare,
  type Diff,
  type Snapshot,
} from "@/lib/timeline";

/** 재생 속도. 설계서 4.3.7 의 1× / 2× / 4× 다. 1× 가 1초에 한 분기 */
const SPEEDS = [1, 2, 4] as const;

export type TimelineTabProps = {
  snaps: Snapshot[];
  /** 지금 보고 있는 분기 (`2026-Q3`) */
  current: string;
  onPick: (q: string) => void;
  /** 시점 비교 상태. 꺼져 있으면 null (설계서 4.3.7 L811-816) */
  compare: Compare | null;
  onCompare: (c: Compare | null) => void;
  playing: boolean;
  onPlaying: (v: boolean) => void;
  speed: number;
  onSpeed: (v: number) => void;
  /** 섬 코드 → 이름 */
  nameOf: (islandId: string) => string;
};

export default function TimelineTab({
  snaps,
  current,
  onPick,
  compare,
  onCompare,
  playing,
  onPlaying,
  speed,
  onSpeed,
  nameOf,
}: TimelineTabProps) {
  const at = Math.max(
    0,
    snaps.findIndex((s) => s.ym === current),
  );
  const now = snaps[at];

  const keys = useMemo(() => snaps.map((s) => s.ym), [snaps]);
  /** 연도 칩 — 해마다 그 해 3분기(없으면 가장 가까운 분기) (설계서 4.3.7 L797) */
  const chips = useMemo(() => yearChips(snaps), [snaps]);
  /** 시점별 스냅샷 카드 — 해마다 한 장, 최신이 위 (L807, 피그마 ⑦-9b) */
  const cards = useMemo(() => {
    const list = yearCards(snaps);
    const boxes = thumbBoxes(list.map((c) => c.snap.layout.viewBox));
    return list.map((c, i) => ({ ...c, box: boxes[i] })).reverse();
  }, [snaps]);
  /** 추이 그래프 세로축과 성장 요약 막대가 같은 눈금을 쓴다 (피그마 ⑦-9b 막대 = 축 140 기준) */
  const peak = useMemo(() => peakOf(snaps), [snaps]);
  const info = useMemo(
    () => (id: string) => ({
      name: nameOf(id),
      token: islandToken(id as IslandCode),
    }),
    [nameOf],
  );

  const cmpA = compare ? snaps.find((s) => s.ym === compare.a) : undefined;
  const cmpB = compare ? snaps.find((s) => s.ym === compare.b) : undefined;

  const 변화 = useMemo(
    () => (cmpA && cmpB ? diff(cmpA, cmpB, info) : null),
    [cmpA, cmpB, info],
  );

  /*
   * **비교 중에는 기준 시점이 곧 B 다.** B 를 옮길 때마다 기준 시점도 옮겨 둔다.
   * 그래야 끄거나 탭을 옮겼을 때 따로 맞출 것 없이 B 시점 화면이다 (L816), 옆 패널도
   * B 시점 값을 보인다.
   */
  const toggleCompare = () => {
    if (compare) {
      // 끄면 B 시점 한 장짜리로 돌아간다 (설계서 4.3.7 L816)
      onPick(compare.b);
      onCompare(null);
      return;
    }
    // 처음 켤 때 A 는 3년 전 같은 분기, B 는 최근 분기 (L813)
    const c = compareStart(keys);
    if (!c) return;
    onCompare(c);
    onPick(c.b);
    onPlaying(false);
  };

  /** 연도 칩. 비교 중이면 첫 클릭이 A, 두 번째가 B 다 (L812) */
  const pickYear = (q: string) => {
    if (!compare) {
      onPick(q);
      return;
    }
    const c = comparePick(compare, q);
    onCompare(c);
    onPick(c.b);
  };

  /**
   * 재생 — 한 분기씩 넘기고 끝에서 멈춘다 (설계서 4.3.7).
   *
   * 비교 중에는 안 넘긴다. 두 시점을 견주는 중에 시점이 저절로 움직이면
   * 사람이 무엇을 보고 있는지 놓친다. 단추도 꺼 둔다 (피그마 ⑦-9c).
   */
  useEffect(() => {
    if (!playing || compare) return;
    if (at >= snaps.length - 1) {
      onPlaying(false);
      return;
    }
    const id = setTimeout(() => onPick(snaps[at + 1].ym), 1000 / speed);
    return () => clearTimeout(id);
  }, [playing, compare, at, snaps, speed, onPick, onPlaying]);

  /** 성장 요약. 평소에는 첫 시점 → 지금, 비교 중에는 A → B (L809, 피그마 ⑦-9c) */
  const rows = useMemo(() => {
    if (변화) return growth(변화.a, 변화.b, info);
    return now ? growth(snaps[0], now, info) : [];
  }, [변화, snaps, now, info]);

  if (!now) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-[14px] border border-edge bg-canvas text-[13px] text-label">
        시점을 만들 사건이 없습니다
      </div>
    );
  }

  // ◀ / ▶▶ 는 한 해씩 (L798). 비교 중에는 연도 칩으로만 A · B 를 옮긴다 (피그마 ⑦-9c)
  const prevYear = stepYear(keys, now.ym, -1);
  const nextYear = stepYear(keys, now.ym, 1);
  const last = snaps[snaps.length - 1];
  /** 눈금 이름표를 앉힐 자리 — 연도 칩이 가리키는 분기 */
  const ticks = chips.map((c) => ({ year: c.year, i: keys.indexOf(c.snap.ym) }));
  /** 굵게 낼 해. 평소에는 지금 해, 비교 중에는 A 와 B 의 해 */
  const boldYears = 변화 ? [변화.a.year, 변화.b.year] : [now.year];

  return (
    <div className="flex min-h-0 flex-1 gap-s4 overflow-hidden">
      <div className="flex min-h-0 flex-1 flex-col gap-s4 overflow-y-auto">
        <div className="flex shrink-0 items-center gap-s4">
          <nav
            aria-label="시점 고르기"
            className="flex gap-s1 rounded-[12px] bg-track p-[3px]"
          >
            {chips.map(({ year, snap }) => {
              const marks = compare
                ? [
                    parseQuarter(compare.a).year === year ? "A" : null,
                    parseQuarter(compare.b).year === year ? "B" : null,
                  ].filter(Boolean)
                : [];
              const on = compare ? marks.length > 0 : now.year === year;
              return (
                <button
                  key={year}
                  type="button"
                  aria-current={on ? "page" : undefined}
                  onClick={() => pickYear(snap.ym)}
                  title={
                    compare
                      ? `${compare.next === "a" ? "A" : "B"} 시점으로 찍기 · ${snap.ym}`
                      : snap.ym
                  }
                  className={[
                    "rounded-[10px] px-s4 py-s2 text-center",
                    on ? "bg-selected" : "",
                  ].join(" ")}
                >
                  <div
                    className={
                      "text-[14px] tabular-nums " +
                      (on ? "font-semibold text-strong" : "text-label")
                    }
                  >
                    {year}
                  </div>
                  {/* 비교 중에는 건수 자리에 A · B 를 적는다 (피그마 ⑦-9c) */}
                  <div
                    className={
                      "text-[10px] tabular-nums " +
                      (marks.length ? "font-semibold text-accent" : "text-label")
                    }
                  >
                    {marks.length ? marks.join(" ") : `${snap.events}건`}
                  </div>
                </button>
              );
            })}
          </nav>

          <div className="flex-1" />

          {/*
            재생 단추 줄 — 피그마 ⑦-9b · ⑦-9c, 시트 `07 / 02 Playback Control`.
            30px 네모 단추(모서리 8px) 넷을 6px 씩 띄운다. ◀ · ▶▶ 는 테두리 단추,
            재생은 강조색 채움이다. 꺼진 단추는 통째로 40% 로 흐린다 — ⑦-9c 에서 꺼진
            ◀ 의 테두리 · 그림이 둘 다 바탕과 40% 로 섞인 색이다
          */}
          <div className="flex items-center gap-[6px]">
            <button
              type="button"
              aria-label="1년 전"
              disabled={compare !== null || prevYear === null}
              onClick={() => prevYear && onPick(prevYear)}
              className="grid size-[30px] place-items-center rounded-[8px] border border-edge text-body disabled:opacity-40"
            >
              <Glyph kind="prev" />
            </button>
            <button
              type="button"
              aria-label={playing ? "정지" : at >= snaps.length - 1 ? "처음부터 재생" : "재생"}
              title={!playing && at >= snaps.length - 1 ? "처음 시점부터 재생" : undefined}
              disabled={compare !== null}
              onClick={() => {
                // 끝(가장 최근 시점)에서 누르면 첫 시점으로 되감고 재생한다. 첫 화면이 끝이라
                // 전에는 첫 틱에 「끝이다」로 보고 바로 멈췄다 (2026-09-28 코드 분석). 스냅샷 바와 같은 규칙
                if (!playing && at >= snaps.length - 1 && snaps.length > 1) onPick(snaps[0].ym);
                onPlaying(!playing);
              }}
              className="grid size-[30px] place-items-center rounded-[8px] bg-accent text-on-accent disabled:opacity-40"
            >
              <Glyph kind={playing ? "pause" : "play"} />
            </button>
            <button
              type="button"
              aria-label="1년 후"
              disabled={compare !== null || nextYear === null}
              onClick={() => nextYear && onPick(nextYear)}
              className="grid size-[30px] place-items-center rounded-[8px] border border-edge text-body disabled:opacity-40"
            >
              <Glyph kind="next" />
            </button>
            {/*
              재생 속도 — 피그마는 세 값을 늘어놓지 않고 「2× ▾」 펼침 하나다. 고르는 값과
              동작(1× · 2× · 4×)은 그대로라 브라우저 기본 펼침(select)을 쓴다. 테두리는
              재생 중에만 강조색이다 — ⑦-9b(재생 중)는 붉은 테두리, ⑦-9c(멈춤)는 보통 테두리다
            */}
            <div
              className={[
                "relative h-[30px] rounded-[8px] border",
                playing ? "border-accent" : "border-edge",
              ].join(" ")}
            >
              <select
                aria-label="재생 속도"
                value={speed}
                onChange={(e) => onSpeed(Number(e.target.value))}
                className="h-full cursor-pointer appearance-none rounded-[8px] bg-transparent pl-[9px] pr-[20px] text-[12px] tabular-nums text-body"
              >
                {SPEEDS.map((v) => (
                  <option key={v} value={v} className="bg-panel text-body">
                    {v}×
                  </option>
                ))}
              </select>
              <span
                aria-hidden
                className="pointer-events-none absolute right-[8px] top-1/2 -translate-y-1/2 text-[8px] text-body"
              >
                ▾
              </span>
            </div>
            <button
              type="button"
              onClick={toggleCompare}
              disabled={snaps.length < 2}
              aria-pressed={compare !== null}
              className="flex items-center gap-s2 text-[12px] disabled:text-disabled"
            >
              <span
                aria-hidden
                className="relative h-[16px] w-[30px] rounded-full transition-colors"
                style={{
                  background: compare
                    ? "var(--t-accent)"
                    : "var(--t-surface-track)",
                }}
              >
                <span
                  className="absolute top-[2px] size-[12px] rounded-full bg-white transition-all"
                  style={{ left: compare ? 16 : 2 }}
                />
              </span>
              <span className={compare ? "text-strong" : "text-label"}>
                시점 비교
              </span>
            </button>
          </div>
        </div>

        {변화 ? (
          <div className="grid shrink-0 grid-cols-2 gap-s4">
            <SideMap mark="A" snap={변화.a} />
            <SideMap mark="B" snap={변화.b} />
          </div>
        ) : (
        <section className="relative flex min-h-[340px] shrink-0 flex-col rounded-[14px] border border-edge bg-canvas p-s5">
          <header className="z-10 flex shrink-0 items-center gap-s3">
            <h2 className="text-[15px] font-semibold text-title">
              Historical Map
            </h2>
            <Chip label="사건" value={`${now.events}건`} />
            {/* 한 해 앞 같은 분기와 견준다 (L806). 첫 해는 견줄 시점이 없어 안 낸다 */}
            {now.delta !== null && (
              <Chip
                label="전년 대비"
                value={
                  now.delta === 0
                    ? "0"
                    : `${now.delta > 0 ? "▲" : "▼"} ${Math.abs(now.delta)}`
                }
                tone={now.delta > 0 ? "up" : now.delta < 0 ? "down" : undefined}
              />
            )}
            {now.fresh !== null && <Chip label="신규" value={String(now.fresh)} />}
          </header>

          <span
            aria-hidden
            className="pointer-events-none absolute left-s5 top-[54px] text-[46px] font-bold leading-none tabular-nums"
            style={{ color: "var(--t-border-card)", opacity: 0.55 }}
          >
            {now.ym}
          </span>

          <div className="min-h-0 flex-1">
            <HexMap layout={now.layout} />
          </div>

          {playing && (
            <div
              className="absolute bottom-[66px] left-s5 flex items-center gap-s2 rounded-full px-s4 py-s2 text-[12px] text-on-accent"
              style={{ background: "var(--t-accent)" }}
            >
              <span aria-hidden className="size-[6px] rounded-full bg-white" />
              재생 중 · {speed}× · {now.ym}
              {at < snaps.length - 1 && ` → ${snaps[at + 1].ym}`}
            </div>
          )}

          <TimeSlider
            at={at}
            count={snaps.length}
            onChange={(i) => onPick(snaps[i].ym)}
            ticks={ticks}
            boldYears={boldYears}
          />
        </section>
        )}

        <div className="grid shrink-0 grid-cols-[1fr_320px] gap-s4">
          <TrendChart
            snaps={snaps}
            at={at}
            peak={peak}
            ticks={ticks}
            boldYears={boldYears}
            nameOf={nameOf}
            band={
              변화
                ? [
                    keys.indexOf(변화.a.ym),
                    keys.indexOf(변화.b.ym),
                  ]
                : undefined
            }
          />

          <section className="rounded-[14px] border border-edge bg-card px-s5 py-s4">
            <h3 className="text-[12px] font-semibold text-strong">
              성장 요약 ·{" "}
              {변화
                ? `${변화.a.ym} → ${변화.b.ym}`
                : `${snaps[0].ym} → ${now.ym}`}
            </h3>
            <ul className="mt-s4 flex flex-col gap-s4">
              {rows.map((r) => (
                <li key={r.islandId} className="flex flex-col gap-s2">
                  <div className="flex items-baseline gap-s2">
                    <span className="flex-1 text-[12px] font-semibold text-strong">
                      {r.name}
                    </span>
                    <span className="text-[11px] tabular-nums text-label">
                      {r.from}→{r.to}
                    </span>
                    {r.rate !== null && r.rate !== 0 && (
                      <span
                        className="text-[11px] tabular-nums"
                        style={{
                          color:
                            r.rate > 0
                              ? "var(--t-trend-up)"
                              : "var(--t-trend-down)",
                        }}
                      >
                        {r.rate > 0 ? "▲" : "▼"}
                        {Math.abs(Math.round(r.rate))}%
                      </span>
                    )}
                  </div>
                  {/*
                    막대 둘을 겹친다 — 어두운 쪽이 처음, 밝은 쪽이 지금이다 (피그마 ⑦-9b).
                    길이는 추이 그래프 세로축과 같은 눈금이라 재생하면 자라는 것이 보인다
                  */}
                  <div className="relative h-[5px] overflow-hidden rounded-full bg-bar-track">
                    <div
                      className="absolute inset-y-0 left-0 rounded-full"
                      style={{
                        width: `${pctOf(r.to, peak)}%`,
                        background: `var(--t-island-${r.token})`,
                      }}
                    />
                    <div
                      className="absolute inset-y-0 left-0 rounded-full"
                      style={{
                        width: `${pctOf(Math.min(r.from, r.to), peak)}%`,
                        background: `var(--t-island-${r.token})`,
                        filter: "brightness(0.7)",
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>

      <aside className="flex w-[240px] shrink-0 flex-col gap-s3 overflow-y-auto">
        {/* 비교 중에는 이 열이 변화 요약이다 (피그마 ⑦-9c) */}
        {변화 ? (
          <ChangeSummary d={변화} />
        ) : (
          <>
            <h3 className="shrink-0 text-[12px] font-semibold text-strong">
              시점별 스냅샷
            </h3>
            {cards.map((c) => {
              const on = c.year === now.year;
              // 지금 시점보다 뒤의 해는 흐리게 둔다 (피그마 ⑦-9b 재생 중 2025 · 2026 카드)
              const later = c.year > now.year;
              return (
                <button
                  key={c.year}
                  type="button"
                  onClick={() => onPick(c.snap.ym)}
                  aria-current={on ? "true" : undefined}
                  className={[
                    "flex shrink-0 items-center gap-s3 rounded-[12px] border p-s2 pr-s4 text-left",
                    on ? "border-accent bg-row-selected" : "border-edge bg-card",
                    later ? "opacity-50" : "",
                  ].join(" ")}
                >
                  <Thumb layout={c.snap.layout} viewBox={c.box} />
                  <span className="min-w-0">
                    <span
                      className={
                        "block text-[14px] tabular-nums " +
                        (on ? "font-semibold text-accent" : "text-strong")
                      }
                    >
                      {c.snap.ym}
                    </span>
                    <span className="mt-s1 block text-[11px] tabular-nums text-label">
                      {c.snap.events}건
                      {c.snap.delta !== null &&
                        c.snap.delta !== 0 &&
                        ` · ${c.snap.delta > 0 ? "▲" : "▼"}${Math.abs(c.snap.delta)}`}
                      {c.snap.ym === last.ym && " · 현재"}
                    </span>
                  </span>
                </button>
              );
            })}
          </>
        )}
      </aside>
    </div>
  );
}

/**
 * 재생 단추 그림 (피그마 ⑦-9b · ⑦-9c).
 *
 * **글자(◀ ▶ ⏸)를 쓰지 않는다.** ⏸ · ▶ 는 윈도에서 컬러 이모지로 바뀌어 피그마의
 * 흰 도형과 달라진다. 크기는 ⑦-9b 에서 읽었다 — 삼각형 폭 6px(▶▶ 는 둘을 3px 띄움),
 * 일시정지 막대 약 4px 둘을 1.5px 띄움
 */
function Glyph({ kind }: { kind: "prev" | "play" | "pause" | "next" }) {
  const w = kind === "next" ? 16 : 12;
  return (
    <svg aria-hidden width={w} height="12" viewBox={`0 0 ${w} 12`} fill="currentColor">
      {kind === "prev" && <path d="M9 2.5v7L3 6z" />}
      {kind === "play" && <path d="M3.5 2v8L10 6z" />}
      {kind === "pause" && (
        <>
          <rect x="1.5" y="2" width="3.75" height="8" rx="0.5" />
          <rect x="6.75" y="2" width="3.75" height="8" rx="0.5" />
        </>
      )}
      {kind === "next" && (
        <>
          <path d="M0.5 2.5v7L6.5 6z" />
          <path d="M9.5 2.5v7L15.5 6z" />
        </>
      )}
    </svg>
  );
}

/**
 * 스냅샷 카드의 섬 썸네일 (피그마 ⑦-9b, 컴포넌트 시트 「Snapshot List Item」).
 * 섬 테두리 경로만 섬 색으로 채운다. viewBox 를 카드끼리 맞춰 해마다 자라는 것이 보인다
 */
function Thumb({ layout, viewBox }: { layout: MapLayout; viewBox: string }) {
  return (
    <span
      aria-hidden
      className="block h-[44px] w-[60px] shrink-0 rounded-[8px] bg-track p-[4px]"
    >
      <svg viewBox={viewBox} className="block size-full">
        {layout.islands.map((i) => (
          <path
            key={i.islandKey}
            d={i.outline}
            fill={`var(--t-island-${i.token})`}
          />
        ))}
      </svg>
    </span>
  );
}

/**
 * 슬라이더 모양. 트랙 4px, 노브 16px 고리.
 *
 * 크롬 계열은 지나온 구간을 트랙 배경 그라디언트로 칠한다 — 노브 자리를 `--fill`
 * 로 받는다. 파이어폭스는 `::-moz-range-progress` 가 알아서 칠한다.
 */
const SLIDER = [
  "block h-[16px] w-full cursor-pointer appearance-none bg-transparent",
  "[&::-webkit-slider-runnable-track]:h-[4px] [&::-webkit-slider-runnable-track]:rounded-full",
  "[&::-webkit-slider-runnable-track]:bg-[linear-gradient(to_right,var(--t-accent)_var(--fill),var(--t-surface-track)_var(--fill))]",
  "[&::-webkit-slider-thumb]:-mt-[6px] [&::-webkit-slider-thumb]:box-border [&::-webkit-slider-thumb]:size-[16px]",
  "[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full",
  "[&::-webkit-slider-thumb]:border-[3px] [&::-webkit-slider-thumb]:border-accent [&::-webkit-slider-thumb]:bg-panel",
  "[&::-moz-range-track]:h-[4px] [&::-moz-range-track]:rounded-full [&::-moz-range-track]:bg-track",
  "[&::-moz-range-progress]:h-[4px] [&::-moz-range-progress]:rounded-full [&::-moz-range-progress]:bg-accent",
  "[&::-moz-range-thumb]:box-border [&::-moz-range-thumb]:size-[16px] [&::-moz-range-thumb]:rounded-full",
  "[&::-moz-range-thumb]:border-[3px] [&::-moz-range-thumb]:border-accent [&::-moz-range-thumb]:bg-panel",
].join(" ");

/**
 * 시점 슬라이더 (피그마 ⑦-9b, 컴포넌트 시트 「Snapshot bar」).
 *
 * 강조색으로 지나온 구간을 칠하고 노브는 16px 고리(속은 패널색)다. 브라우저
 * 기본 모양은 판마다 색이 달라 토큰을 못 탄다.
 *
 * 눈금 이름표는 연도만, 연도 칩이 가리키는 분기 자리에 둔다. 분기 스무 개에
 * 이름표를 다 달면 글자가 붙는다. 노브 중심은 양 끝에서 반지름(8px)만큼 안쪽이라
 * 이름표 자리도 같은 식으로 잡는다.
 */
function TimeSlider({
  at,
  count,
  onChange,
  ticks,
  boldYears,
}: {
  at: number;
  count: number;
  onChange: (i: number) => void;
  ticks: { year: number; i: number }[];
  boldYears: number[];
}) {
  const frac = (i: number) => (count <= 1 ? 0 : i / (count - 1));
  const knob = (f: number) => `calc(8px + ${f} * (100% - 16px))`;
  return (
    <div className="z-10 mt-s3 shrink-0">
      <input
        type="range"
        min={0}
        max={Math.max(0, count - 1)}
        step={1}
        value={at}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label="시점"
        style={{ "--fill": knob(frac(at)) } as CSSProperties}
        className={SLIDER}
      />
      <div className="relative mt-s1 h-[14px] text-[10px] tabular-nums">
        {ticks.map((t, k) => {
          const bold = boldYears.includes(t.year);
          // 양 끝 이름표는 가운데 맞춤하면 틀 밖으로 나가 끝에 붙인다
          const edge = k === 0 ? "first" : k === ticks.length - 1 ? "last" : "mid";
          return (
            <span
              key={t.year}
              className={[
                "absolute top-0 whitespace-nowrap",
                edge === "first" ? "left-0" : edge === "last" ? "right-0" : "-translate-x-1/2",
                bold ? "font-semibold text-strong" : "text-label",
              ].join(" ")}
              style={edge === "mid" ? { left: knob(frac(t.i)) } : undefined}
            >
              {t.year}
            </span>
          );
        })}
      </div>
    </div>
  );
}

/** 비교 모드의 지도 한 장. A 와 B 를 나란히 놓는다 (피그마 ⑦-9c) */
function SideMap({ mark, snap }: { mark: "A" | "B"; snap: Snapshot }) {
  return (
    <section className="relative flex min-h-[340px] flex-col rounded-[14px] border border-edge bg-canvas p-s5">
      <header className="z-10 flex shrink-0 items-center gap-s3">
        <span
          className="grid size-[20px] place-items-center rounded-[6px] text-[11px] font-bold text-on-accent"
          style={{ background: "var(--t-accent)" }}
        >
          {mark}
        </span>
        <span className="whitespace-nowrap text-[15px] font-semibold tabular-nums text-title">
          {snap.ym}
        </span>
        <Chip label="사건" value={`${snap.events}건`} />
      </header>

      <span
        aria-hidden
        className="pointer-events-none absolute left-s5 top-[46px] text-[34px] font-bold leading-none tabular-nums"
        style={{ color: "var(--t-border-card)", opacity: 0.5 }}
      >
        {snap.ym}
      </span>

      <div className="min-h-0 flex-1">
        <HexMap layout={snap.layout} />
      </div>
    </section>
  );
}

/** 「변화 · A → B」 요약 (설계서 4.3.7 시점 비교) */
function ChangeSummary({ d }: { d: Diff }) {
  return (
    <section className="flex flex-col gap-s3">
      <h3 className="shrink-0 text-[12px] font-semibold text-strong">
        변화 · {d.a.ym} → {d.b.ym}
      </h3>

      <div className="shrink-0 rounded-[14px] border border-edge bg-card px-s5 py-s4">
        <div className="text-[11px] text-label">누적 사건</div>
        <div
          className="mt-s1 text-[30px] font-bold leading-none tabular-nums"
          style={{
            color:
              d.deltaEvents >= 0 ? "var(--t-accent)" : "var(--t-trend-down)",
          }}
        >
          {d.deltaEvents >= 0 ? "+" : ""}
          {d.deltaEvents}건
        </div>
        <div className="mt-s2 text-[11px] tabular-nums text-label">
          {d.a.events} → {d.b.events}
          {d.times !== null && ` · ×${d.times.toFixed(1)}`}
        </div>
      </div>

      <ul className="flex shrink-0 flex-col gap-s2">
        {d.islands.map((i) => (
          <li
            key={i.islandId}
            className="flex items-center gap-s3 rounded-[12px] border border-edge bg-card px-s4 py-s3"
          >
            <span
              aria-hidden
              className="size-[8px] shrink-0 rounded-full"
              style={{
                background: `var(--t-island-${i.token}-legend, var(--t-island-${i.token}))`,
              }}
            />
            <span className="flex-1 text-[12px] font-semibold text-strong">
              {i.name}
            </span>
            <span className="text-[11px] tabular-nums text-label">
              {i.from}→{i.to}
            </span>
            {i.delta !== 0 && (
              <span
                className="text-[11px] font-semibold tabular-nums"
                style={{
                  color:
                    i.delta > 0
                      ? "var(--t-trend-up)"
                      : "var(--t-trend-down)",
                }}
              >
                {i.delta > 0 ? "+" : ""}
                {i.delta}
              </span>
            )}
          </li>
        ))}
      </ul>

      {d.fresh.length > 0 && (
        <div className="shrink-0 rounded-[12px] border border-edge bg-card px-s4 py-s3">
          <div className="text-[11px] text-label">
            신규 엔티티 ({d.a.ym} 이후)
          </div>
          <p className="mt-s2 text-[12px] leading-[1.7] text-body">
            {d.fresh.join(" · ")}
          </p>
        </div>
      )}
    </section>
  );
}

/** 막대 길이 (%). 눈금은 추이 그래프 세로축과 같다 */
function pctOf(v: number, peak: number): number {
  return Math.round((v / Math.max(1, peak)) * 100);
}

function Chip({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "up" | "down";
}) {
  return (
    <span className="rounded-[8px] bg-card px-s3 py-[3px] text-[11px]">
      <span className="text-label">{label} </span>
      <span
        className="font-semibold tabular-nums"
        style={{
          color:
            tone === "up"
              ? "var(--t-trend-up)"
              : tone === "down"
                ? "var(--t-trend-down)"
                : "var(--t-text-strong)",
        }}
      >
        {value}
      </span>
    </span>
  );
}

/**
 * 섬별 누적 사건 추이 — 설계서 4.3.7 L808 의 선 그래프.
 *
 * 세로선이 지금 보고 있는 시점이다. 비교 중에는 A · B 두 줄과 그 사이 음영이다.
 *
 * **섬 넷을 다 그린다.** 전에는 한 번도 사건이 없던 섬을 뺐는데, 설계서가 「섬 4개
 * 선 그래프」라 0건 섬도 바닥선으로 둔다 (피그마 ⑦-9b 범례 넷).
 */
function TrendChart({
  snaps,
  at,
  peak,
  ticks,
  boldYears,
  nameOf,
  band,
}: {
  snaps: Snapshot[];
  at: number;
  peak: number;
  /** 연도 이름표 자리. 슬라이더와 같다 */
  ticks: { year: number; i: number }[];
  boldYears: number[];
  nameOf: (id: string) => string;
  /** 시점 비교 중이면 A~B 구간을 음영으로 덮는다 (설계서 4.3.7) */
  band?: [number, number];
}) {
  const W = 620;
  const H = 180;
  const PAD = { l: 34, r: 12, t: 12, b: 22 };

  // 섬 목록 차례 그대로 (`Snapshot.byIsland`). 0건 섬도 든다
  const ids = Object.keys(snaps[0]?.byIsland ?? {});
  const max = peak;
  const x = (i: number) =>
    PAD.l +
    (snaps.length <= 1
      ? 0
      : (i / (snaps.length - 1)) * (W - PAD.l - PAD.r));
  const y = (v: number) => H - PAD.b - (v / max) * (H - PAD.t - PAD.b);
  /** 세로선과 큰 점을 찍을 시점. 평소에는 지금, 비교 중에는 A · B */
  const marks = band && band[0] >= 0 && band[1] >= 0 ? band : [at];

  return (
    <section className="rounded-[14px] border border-edge bg-card px-s5 py-s4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-[12px] font-semibold text-strong">
          섬별 누적 사건 추이
        </h3>
        <ul className="flex gap-s4">
          {ids.map((id) => (
            <li key={id} className="flex items-center gap-s2 text-[11px]">
              <span
                aria-hidden
                className="size-[7px] rounded-full"
                style={{
                  background: `var(--t-island-${islandToken(id as IslandCode)})`,
                }}
              />
              <span className="text-label">{nameOf(id)}</span>
            </li>
          ))}
        </ul>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="mt-s3 w-full" role="img"
           aria-label="섬별 누적 사건 추이">
        {[0, max / 2, max].map((v) => (
          <g key={v}>
            <line
              x1={PAD.l}
              y1={y(v)}
              x2={W - PAD.r}
              y2={y(v)}
              stroke="var(--t-border-divider)"
            />
            <text
              x={PAD.l - 6}
              y={y(v) + 3}
              fontSize={9}
              textAnchor="end"
              fill="var(--t-text-label)"
            >
              {Math.round(v)}
            </text>
          </g>
        ))}

        {marks.length === 2 && (
          <rect
            x={x(Math.min(...marks))}
            y={PAD.t}
            width={Math.abs(x(marks[1]) - x(marks[0]))}
            height={H - PAD.t - PAD.b}
            fill="var(--t-accent)"
            opacity={0.12}
          />
        )}

        {marks.map((i, k) => (
          <line
            // A 와 B 가 같은 시점일 수 있어 자리 번호를 열쇠로 쓴다
            key={k}
            x1={x(i)}
            y1={PAD.t}
            x2={x(i)}
            y2={H - PAD.b}
            stroke="var(--t-accent)"
            strokeWidth={1}
          />
        ))}

        {ids.map((id) => {
          const pts = snaps.map((s, i) => [x(i), y(s.byIsland[id] ?? 0)]);
          const color = `var(--t-island-${islandToken(id as IslandCode)})`;
          return (
            <g key={id}>
              <polyline
                points={pts.map(([a, b]) => `${a},${b}`).join(" ")}
                fill="none"
                stroke={color}
                strokeWidth={2}
                strokeLinejoin="round"
              />
              {pts.map(([a, b], i) => {
                const big = marks.includes(i);
                return (
                  <circle
                    key={i}
                    cx={a}
                    cy={b}
                    r={big ? 4 : 2.5}
                    fill={big ? color : "var(--t-surface-card)"}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                );
              })}
            </g>
          );
        })}

        {/* 연도 이름표 — 연도 칩이 가리키는 분기 자리. 슬라이더 눈금과 같다 */}
        {ticks.map((t) => {
          const bold = boldYears.includes(t.year);
          return (
            <text
              key={t.year}
              x={x(t.i)}
              y={H - 6}
              fontSize={9}
              textAnchor="middle"
              fontWeight={bold ? 700 : 400}
              fill={bold ? "var(--t-text-strong)" : "var(--t-text-label)"}
            >
              {t.year}
            </text>
          );
        })}
      </svg>
    </section>
  );
}
