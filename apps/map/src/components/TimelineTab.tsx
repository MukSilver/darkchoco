/**
 * 타임라인 탭 — 설계서 4.3.7.
 *
 * 연도 칩으로 시점을 옮기고, 그 시점의 지도와 섬별 누적 추이를 본다.
 * **모든 값이 누적이다.** 그 시점까지의 사건 전부를 센다.
 *
 * **판 1.2 에서 단위가 해에서 분기로 바뀌었다** (설계서 4.3.7 「단위는 분기.
 * 한 해에 4 시점」). 연도 칩은 남아 있고 누르면 그 해 3분기로 간다.
 *
 * 설계서는 「기준 시점은 스냅샷 바와 같은 값」이라고 적었다. 여기서 시점을
 * 옮기면 지도 탭의 기준일도 같이 움직인다.
 *
 * **시점 비교(⑦-9c)** 를 켜면 지도 두 장을 나란히 놓고 변화 요약을 낸다.
 * 연도 칩을 누르면 A → B 차례로 찍히고, 끄면 B 시점 한 장짜리로 돌아온다.
 */

"use client";

import { useEffect, useMemo, useState } from "react";

import HexMap from "./HexMap";
import { islandToken } from "@/lib/islands";
import type { IslandCode } from "@/lib/types";
import { diff, growth, type Diff, type Snapshot } from "@/lib/timeline";

/** 재생 속도. 설계서 4.3.7 의 1× / 2× / 4× 다. 1× 가 1초에 한 분기 */
const SPEEDS = [1, 2, 4] as const;

export type TimelineTabProps = {
  snaps: Snapshot[];
  /** 지금 보고 있는 분기 (`2026-Q3`) */
  current: string;
  onPick: (q: string) => void;
  /** 연도 칩. 그 해 3분기로 간다 (설계서 4.3.7) */
  onPickYear: (y: number) => void;
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
  onPickYear,
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

  /** 연도 칩은 그 해 분기 넷을 묶어 보인다 (설계서 4.3.7) */
  const years = useMemo(() => [...new Set(snaps.map((s) => s.year))], [snaps]);

  /**
   * 시점 비교 — 설계서 4.3.7.
   *
   * **처음 켤 때 A 는 3년 전, B 는 최근이다.** 설계서가 그렇게 정했다.
   * 데이터가 3년치가 안 되면 첫 시점을 A 로 쓴다.
   */
  const [cmp, setCmp] = useState<{ a: string; b: string } | null>(null);
  const cmpA = cmp ? snaps.find((s) => s.ym === cmp.a) : undefined;
  const cmpB = cmp ? snaps.find((s) => s.ym === cmp.b) : undefined;

  const toggleCompare = () => {
    if (cmp) {
      // 끄면 B 시점 한 장짜리로 돌아간다 (설계서 4.3.7)
      onPick(cmp.b);
      setCmp(null);
      return;
    }
    if (snaps.length < 2) return;
    const last = snaps[snaps.length - 1];
    // 「A = 3년 전 같은 분기」 (설계서 4.3.7). 한 해가 4 시점이라 12 앞이다
    const want = Math.max(0, snaps.length - 1 - 12);
    setCmp({ a: snaps[want].ym, b: last.ym });
    onPlaying(false);
  };

  /** 비교 중에 칩을 누르면 A 를 옮긴다. 이미 A 인 자리면 A·B 를 맞바꾼다 */
  const pickQuarter = (q: string) => {
    if (!cmp) {
      onPick(q);
      return;
    }
    if (q === cmp.a) setCmp({ a: cmp.b, b: q });
    else setCmp({ a: q, b: cmp.b === q ? cmp.a : cmp.b });
  };

  const 변화 = useMemo(
    () =>
      cmpA && cmpB
        ? diff(cmpA, cmpB, (id) => ({
            name: nameOf(id),
            token: islandToken(id as IslandCode),
          }))
        : null,
    [cmpA, cmpB, nameOf],
  );

  /**
   * 재생 — 한 분기씩 넘기고 끝에서 멈춘다 (설계서 4.3.7).
   *
   * 비교 중에는 안 넘긴다. 두 시점을 견주는 중에 시점이 저절로 움직이면
   * 사람이 무엇을 보고 있는지 놓친다.
   */
  useEffect(() => {
    if (!playing || cmp) return;
    if (at >= snaps.length - 1) {
      onPlaying(false);
      return;
    }
    const id = setTimeout(() => onPick(snaps[at + 1].ym), 1000 / speed);
    return () => clearTimeout(id);
  }, [playing, cmp, at, snaps, speed, onPick, onPlaying]);

  const rows = useMemo(
    () =>
      growth(snaps, at, (id) => ({
        name: nameOf(id),
        token: islandToken(id as IslandCode),
      })),
    [snaps, at, nameOf],
  );

  if (!now) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-[14px] border border-edge bg-canvas text-[13px] text-label">
        시점을 만들 사건이 없습니다
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 gap-s4 overflow-hidden">
      <div className="flex min-h-0 flex-1 flex-col gap-s4 overflow-y-auto">
        <div className="flex shrink-0 items-center gap-s4">
          <nav
            aria-label="시점 고르기"
            className="flex gap-s1 rounded-[12px] bg-track p-[3px]"
          >
            {years.map((y) => {
              const mine = snaps.filter((s) => s.year === y);
              const total = mine[mine.length - 1]?.events ?? 0;
              const marks = cmp
                ? mine
                    .map((s) =>
                      s.ym === cmp.a ? "A" : s.ym === cmp.b ? "B" : null,
                    )
                    .filter(Boolean)
                : [];
              const on = cmp
                ? marks.length > 0
                : mine.some((s) => s.ym === current);
              return (
                <button
                  key={y}
                  type="button"
                  aria-current={on ? "page" : undefined}
                  onClick={() => onPickYear(y)}
                  className={[
                    "rounded-[10px] px-s4 py-s2 text-center",
                    on ? "bg-selected" : "",
                  ].join(" ")}
                  style={
                    marks.length
                      ? { outline: "1px solid var(--t-accent)" }
                      : undefined
                  }
                >
                  <div
                    className={
                      "text-[14px] tabular-nums " +
                      (on ? "font-semibold text-strong" : "text-label")
                    }
                  >
                    {y}
                  </div>
                  <div
                    className="text-[10px] tabular-nums"
                    style={{
                      color: marks.length
                        ? "var(--t-accent)"
                        : "var(--t-text-label)",
                    }}
                  >
                    {marks.length ? marks.join(" ") : `${total}건`}
                  </div>
                </button>
              );
            })}
          </nav>

          <div className="flex-1" />

          <div className="flex items-center gap-s3">
            <button
              type="button"
              aria-label="이전 시점"
              disabled={at === 0}
              onClick={() => onPick(snaps[at - 1].ym)}
              className="grid size-[30px] place-items-center rounded-full border border-edge text-[11px] text-body disabled:text-disabled"
            >
              ◀
            </button>
            <button
              type="button"
              aria-label={playing ? "정지" : "재생"}
              onClick={() => onPlaying(!playing)}
              className="grid size-[34px] place-items-center rounded-[10px] text-[13px] text-on-accent"
              style={{ background: "var(--t-accent)" }}
            >
              {playing ? "⏸" : "▶"}
            </button>
            <button
              type="button"
              aria-label="다음 시점"
              disabled={at >= snaps.length - 1}
              onClick={() => onPick(snaps[at + 1].ym)}
              className="grid size-[30px] place-items-center rounded-full border border-edge text-[11px] text-body disabled:text-disabled"
            >
              ▶▶
            </button>
            <div
              className="flex items-center rounded-[10px] border"
              style={{ borderColor: "var(--t-accent)" }}
            >
              {SPEEDS.map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => onSpeed(v)}
                  className={
                    "px-s3 py-[4px] text-[11px] tabular-nums " +
                    (v === speed ? "font-semibold text-strong" : "text-label")
                  }
                >
                  {v}×
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={toggleCompare}
              disabled={snaps.length < 2}
              aria-pressed={cmp !== null}
              className="flex items-center gap-s2 text-[12px] disabled:text-disabled"
            >
              <span
                aria-hidden
                className="relative h-[16px] w-[30px] rounded-full transition-colors"
                style={{
                  background: cmp
                    ? "var(--t-accent)"
                    : "var(--t-surface-track)",
                }}
              >
                <span
                  className="absolute top-[2px] size-[12px] rounded-full bg-white transition-all"
                  style={{ left: cmp ? 16 : 2 }}
                />
              </span>
              <span className={cmp ? "text-strong" : "text-label"}>
                시점 비교
              </span>
            </button>
          </div>
        </div>

        {변화 ? (
          <div className="grid shrink-0 grid-cols-[1fr_1fr_300px] gap-s4">
            <SideMap mark="A" snap={변화.a} />
            <SideMap mark="B" snap={변화.b} />
            <ChangeSummary d={변화} />
          </div>
        ) : (
        <section className="relative flex min-h-[340px] shrink-0 flex-col rounded-[14px] border border-edge bg-canvas p-s5">
          <header className="z-10 flex shrink-0 items-center gap-s3">
            <h2 className="text-[15px] font-semibold text-title">
              Historical Map
            </h2>
            <Chip label="사건" value={`${now.events}건`} />
            {now.delta !== null && (
              <Chip
                label="전년 대비"
                value={`${now.delta >= 0 ? "▲" : "▼"} ${Math.abs(now.delta)}`}
                tone={now.delta >= 0 ? "up" : "down"}
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

          <div className="z-10 mt-s3 shrink-0">
            <input
              type="range"
              min={0}
              max={Math.max(0, snaps.length - 1)}
              step={1}
              value={at}
              onChange={(e) => onPick(snaps[Number(e.target.value)].ym)}
              aria-label="시점"
              className="w-full accent-[var(--t-accent)]"
            />
            <div className="mt-s1 flex justify-between text-[10px] tabular-nums text-label">
              {snaps.map((s, i) => (
                <span
                  key={s.ym}
                  className={s.ym === current ? "font-semibold text-strong" : ""}
                >
                  {/* 연도가 바뀌는 자리에만 연도를 붙인다 (설계서 4.2.5) */}
                  {i === 0 || snaps[i - 1].year !== s.year
                    ? `${s.year} Q${s.q}`
                    : `Q${s.q}`}
                </span>
              ))}
            </div>
          </div>
        </section>
        )}

        <div className="grid shrink-0 grid-cols-[1fr_320px] gap-s4">
          <TrendChart
            snaps={snaps}
            at={변화 ? snaps.findIndex((s) => s.ym === 변화.b.ym) : at}
            nameOf={nameOf}
            band={
              변화
                ? [
                    snaps.findIndex((s) => s.ym === 변화.a.ym),
                    snaps.findIndex((s) => s.ym === 변화.b.ym),
                  ]
                : undefined
            }
          />

          <section className="rounded-[14px] border border-edge bg-card px-s5 py-s4">
            <h3 className="text-[12px] font-semibold text-strong">
              성장 요약 · {snaps[0].ym} → {now.ym}
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
                  <div className="h-[5px] overflow-hidden rounded-full bg-bar-track">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${pct(r.to, rows)}%`,
                        background: `var(--t-island-${r.token})`,
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
        <h3 className="shrink-0 text-[12px] font-semibold text-strong">
          시점별 스냅샷
        </h3>
        {[...snaps].reverse().map((s) => {
          const on = s.ym === current;
          return (
            <button
              key={s.ym}
              type="button"
              onClick={() => pickQuarter(s.ym)}
              className={[
                "shrink-0 rounded-[12px] border px-s4 py-s3 text-left",
                on ? "bg-row-selected" : "border-edge bg-card",
              ].join(" ")}
              style={on ? { borderColor: "var(--t-accent)" } : undefined}
            >
              <div
                className={
                  "text-[14px] tabular-nums " +
                  (on ? "font-semibold" : "text-strong")
                }
                style={on ? { color: "var(--t-accent)" } : undefined}
              >
                {s.ym}
              </div>
              <div className="mt-s1 text-[11px] tabular-nums text-label">
                {s.events}건
                {s.delta !== null && ` · ▲${s.delta}`}
                {s.ym === snaps[snaps.length - 1].ym && " · 현재"}
              </div>
            </button>
          );
        })}
      </aside>
    </div>
  );
}

/** 비교 모드의 지도 한 장. A 와 B 를 나란히 놓는다 (피그마 ⑦-9c) */
function SideMap({ mark, snap }: { mark: "A" | "B"; snap: Snapshot }) {
  return (
    <section className="relative flex min-h-[300px] flex-col rounded-[14px] border border-edge bg-canvas p-s5">
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
    <section className="flex flex-col gap-s3 overflow-y-auto">
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

function pct(v: number, rows: { to: number }[]): number {
  const max = Math.max(1, ...rows.map((r) => r.to));
  return Math.round((v / max) * 100);
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
 * 섬별 누적 사건 추이 — 설계서 4.3.7 의 선 그래프.
 *
 * 세로선이 지금 보고 있는 시점이다.
 */
function TrendChart({
  snaps,
  at,
  nameOf,
  band,
}: {
  snaps: Snapshot[];
  at: number;
  nameOf: (id: string) => string;
  /** 시점 비교 중이면 A~B 구간을 음영으로 덮는다 (설계서 4.3.7) */
  band?: [number, number];
}) {
  const W = 620;
  const H = 180;
  const PAD = { l: 34, r: 12, t: 12, b: 22 };

  const ids = useMemo(() => {
    const s = new Set<string>();
    for (const sn of snaps) {
      for (const k of Object.keys(sn.byIsland)) {
        if (sn.byIsland[k] > 0) s.add(k);
      }
    }
    return [...s];
  }, [snaps]);

  const max = Math.max(
    1,
    ...snaps.flatMap((s) => ids.map((k) => s.byIsland[k] ?? 0)),
  );
  const x = (i: number) =>
    PAD.l +
    (snaps.length <= 1
      ? 0
      : (i / (snaps.length - 1)) * (W - PAD.l - PAD.r));
  const y = (v: number) => H - PAD.b - (v / max) * (H - PAD.t - PAD.b);

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

        {band && band[0] >= 0 && band[1] >= 0 && (
          <rect
            x={x(Math.min(...band))}
            y={PAD.t}
            width={Math.abs(x(band[1]) - x(band[0]))}
            height={H - PAD.t - PAD.b}
            fill="var(--t-accent)"
            opacity={0.12}
          />
        )}

        {(band ?? [at]).map((i) => (
          <line
            key={i}
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
              {pts.map(([a, b], i) => (
                <circle
                  key={i}
                  cx={a}
                  cy={b}
                  r={i === at ? 4 : 2.5}
                  fill={i === at ? color : "var(--t-surface-card)"}
                  stroke={color}
                  strokeWidth={1.5}
                />
              ))}
            </g>
          );
        })}

        {snaps.map((s, i) =>
          // 분기가 촘촘하면 연도 바뀌는 자리와 고른 자리에만 이름표를 낸다
          i === 0 || snaps[i - 1].year !== s.year || i === at ? (
            <text
              key={s.ym}
              x={x(i)}
              y={H - 6}
              fontSize={9}
              textAnchor="middle"
              fontWeight={i === at ? 700 : 400}
              fill={i === at ? "var(--t-text-strong)" : "var(--t-text-label)"}
            >
              {i === at ? `${s.year} Q${s.q}` : String(s.year)}
            </text>
          ) : null,
        )}
      </svg>
    </section>
  );
}
