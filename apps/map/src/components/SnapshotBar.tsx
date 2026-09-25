/**
 * 스냅샷 바 — 설계서 4.2.5. 폭 768, 높이 60.
 *
 * **판 1.2 에서 달 단위가 분기 단위로 바뀌었다.** 노브를 옮기면 그 분기
 * 마지막 날까지의 사건으로 다시 센다. 그 날이 곧 `computeMap` 의 기준일 D 다
 * (설계서 3.1). **이번 분기만 오늘까지 본다** — 아직 오지 않은 날이 최근
 * 7일·30일 창에 들어가면 급상승과 변화율이 비어 버린다.
 *
 * 재생은 한 분기씩 넘기고 끝에서 멈춘다. 타임라인 탭의 재생도 분기 단위라
 * 이제 둘이 같은 간격이지만, 켠 채로 탭을 옮기면 보고 있던 자리를 놓치므로
 * 여전히 탭 전환 때 멈춘다.
 */

"use client";

import { useEffect } from "react";

import { labelTicks } from "@/lib/mapui";
import { quarterRange, tickLabel, type QuarterKey } from "@/lib/quarter";

export { quarterEnd as snapshotBasis } from "@/lib/quarter";

export type SnapshotBarProps = {
  /** 눈금 왼쪽 끝 분기, `2024-Q3` */
  from: QuarterKey;
  /** 눈금 오른쪽 끝이자 「기준일로」가 돌아가는 곳 */
  to: QuarterKey;
  /** 지금 고른 분기 */
  value: QuarterKey;
  onChange: (q: QuarterKey) => void;
  playing: boolean;
  onPlaying: (v: boolean) => void;
};

/** 재생 간격. 설계서 4.2.5 는 속도를 안 정했다. 타임라인 1× 와 맞춘다 */
const TICK_MS = 1000;

/** 눈금에 이름표를 몇 개까지 낼까. 분기가 많으면 건너뛴다 */
const MAX_TICKS = 8;

/**
 * 분기 `k` 의 가로 자리. 노브 한가운데가 닿는 자리와 같다 — 노브는 양 끝에서
 * 제 반지름만큼 안쪽까지만 간다. `16px` 은 `globals.css` 의 `--range-knob` 이다
 * (그 변수는 입력 칸 안에만 있어 여기서 못 읽는다)
 */
const tickLeft = (k: number, n: number) =>
  `calc(8px + (100% - 16px) * ${n > 1 ? k / (n - 1) : 0})`;

export default function SnapshotBar({
  from,
  to,
  value,
  onChange,
  playing,
  onPlaying,
}: SnapshotBarProps) {
  const list = quarterRange(from, to);
  const i = Math.max(0, list.indexOf(value));

  useEffect(() => {
    if (!playing) return;
    if (i >= list.length - 1) {
      onPlaying(false);
      return;
    }
    const id = setTimeout(() => onChange(list[i + 1]), TICK_MS);
    return () => clearTimeout(id);
  }, [playing, i, list, onChange, onPlaying]);

  /*
   * 눈금은 분기마다 긋고 이름표만 빽빽하면 건너뛴다 (설계서 4.2.5 「눈금은
   * 분기마다」). 오른쪽 끝은 항상 단다.
   *
   * **이름표를 그 분기 자리에 놓는다.** 전에는 이름표를 양 끝 맞춤으로 늘어놓아
   * 건너뛴 간격이 끝에서 어긋나면 이름표가 제 분기와 떨어져 앉았다. 양 끝 이름표는
   * 피그마 ⑦-1a · ⑦-1b 처럼 줄 끝에 맞추고 가운데 것은 제 눈금 가운데에 앉힌다.
   * 지금 보는 분기는 피그마처럼 굵게 적고, 이름표를 건너뛴 분기면 눈금만 밝힌다
   */
  const n = list.length;
  const labelled = labelTicks(n, MAX_TICKS);

  return (
    <div
      className="mx-auto flex shrink-0 items-center gap-s5 rounded-[14px] border border-edge bg-card px-s5"
      style={{ width: "var(--w-snapshot)", height: "var(--h-snapshot)" }}
    >
      <button
        type="button"
        aria-label={playing ? "정지" : "재생"}
        onClick={() => onPlaying(!playing)}
        className="grid size-[34px] shrink-0 place-items-center rounded-[10px] text-[13px] text-on-accent"
        style={{ background: "var(--t-accent)" }}
      >
        {playing ? "⏸" : "▶"}
      </button>

      <div className="shrink-0">
        <div className="text-[9px] tracking-[0.18em] text-label">SNAPSHOT</div>
        <div className="whitespace-nowrap text-[20px] font-semibold leading-tight tabular-nums text-title">
          {value.replace("-", " ")}
        </div>
      </div>

      <div className="flex-1">
        <input
          type="range"
          min={0}
          max={Math.max(0, list.length - 1)}
          step={1}
          value={i}
          onChange={(e) => onChange(list[Number(e.target.value)])}
          aria-label="기준일"
          className="w-full accent-[var(--t-accent)]"
        />
        <div aria-hidden className="relative mt-[3px] h-[4px]">
          {list.map((q, k) => (
            <span
              key={q}
              className={
                "absolute top-0 h-full w-px -translate-x-1/2 " +
                (k === i ? "bg-title" : "bg-edge-strong")
              }
              style={{ left: tickLeft(k, n) }}
            />
          ))}
        </div>
        <div className="relative mt-[2px] h-[14px] text-[10px] leading-[14px] tabular-nums text-label">
          {labelled.map((k, j) => (
            <span
              key={list[k]}
              className={
                "absolute top-0 whitespace-nowrap " +
                (k === 0 ? "" : k === n - 1 ? "-translate-x-full " : "-translate-x-1/2 ") +
                (k === i ? "font-semibold text-strong" : "")
              }
              style={
                k === 0
                  ? { left: 0 }
                  : k === n - 1
                    ? { left: "100%" }
                    : { left: tickLeft(k, n) }
              }
            >
              {tickLabel(list[k], j === 0 ? undefined : list[labelled[j - 1]])}
            </span>
          ))}
        </div>
      </div>

      <button
        type="button"
        onClick={() => onChange(to)}
        disabled={value === to}
        className="shrink-0 whitespace-nowrap rounded-[10px] border border-edge px-s4 py-s2 text-[12px] text-body disabled:text-disabled"
      >
        기준일로
      </button>
    </div>
  );
}
