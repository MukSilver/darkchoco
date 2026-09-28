/**
 * 스냅샷 바 — 설계서 4.2.5. 폭 768, 높이 60.
 *
 * **판 1.2 에서 달 단위가 분기 단위로 바뀌었다.** 노브를 옮기면 그 분기
 * 마지막 날까지의 사건으로 다시 센다. 그 날이 곧 `computeMap` 의 기준일 D 다
 * (설계서 3.1). **이번 분기만 오늘까지 본다** — 아직 오지 않은 날이 최근
 * 7일·30일 창에 들어가면 급상승과 변화율이 비어 버린다.
 *
 * 재생은 한 분기씩 넘기고 끝에서 멈춘다. 끝에서 ▶ 를 누르면 첫 분기로 되감고
 * 재생한다 (첫 화면이 끝이다). 타임라인 탭의 재생도 분기 단위라
 * 이제 둘이 같은 간격이지만, 켠 채로 탭을 옮기면 보고 있던 자리를 놓치므로
 * 여전히 탭 전환 때 멈춘다.
 */

"use client";

import { useEffect } from "react";

import PlayGlyph from "./PlayGlyph";
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
  /**
   * 재생 속도 (1 · 2 · 4). 타임라인 탭과 같은 값이다 — 전에는 스냅샷 바가 1초 고정이라 타임라인에서
   * 고른 속도가 여기서는 안 먹었다 (2026-09-28 코드 분석). 없으면 1
   */
  speed?: number;
  onSpeed?: (v: number) => void;
};

/** 1× 재생 간격. 설계서 4.2.5 는 속도를 안 정했다. 타임라인 1× 와 맞춘다 */
const TICK_MS = 1000;
const SPEEDS = [1, 2, 4] as const;

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
  speed = 1,
  onSpeed,
}: SnapshotBarProps) {
  const list = quarterRange(from, to);
  const i = Math.max(0, list.indexOf(value));
  /** 끝(가장 최근 분기)에서 ▶ 를 누르면 첫 분기로 되감고 재생한다 */
  const atEnd = i >= list.length - 1;
  const togglePlay = () => {
    // 첫 화면의 기준일이 끝이라 전에는 ▶ 가 첫 틱에 「끝이다」로 보고 바로 멈췄다
    // (2026-09-28 코드 분석 — 첫 화면에서 ▶ 가 아무 일도 안 함). 타임라인 탭 ▶ 와 같은 규칙이다
    if (!playing && atEnd && list.length > 1) onChange(list[0]);
    onPlaying(!playing);
  };

  useEffect(() => {
    if (!playing) return;
    if (i >= list.length - 1) {
      onPlaying(false);
      return;
    }
    const id = setTimeout(() => onChange(list[i + 1]), TICK_MS / speed);
    return () => clearTimeout(id);
  }, [playing, i, list, onChange, onPlaying, speed]);

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
    // 폭은 768 이 한도이고 가운데가 좁으면 줄어든다. 전에는 768 고정이라 가운데 최소폭을 묶어
    // 1384px 아래 창에서 오른쪽 패널이 잘렸다 (2026-09-28 코드 분석)
    <div
      className="mx-auto flex w-full shrink-0 items-center gap-s5 rounded-[14px] border border-edge bg-card px-s5"
      style={{ maxWidth: "var(--w-snapshot)", height: "var(--h-snapshot)" }}
    >
      <button
        type="button"
        aria-label={playing ? "정지" : atEnd ? "처음부터 재생" : "재생"}
        title={!playing && atEnd ? "처음 분기부터 재생" : undefined}
        onClick={togglePlay}
        className="grid size-[34px] shrink-0 place-items-center rounded-[10px] text-on-accent hover-accent"
        style={{ background: "var(--t-accent)" }}
      >
        {/* 글자(⏸ ▶)는 윈도에서 컬러 이모지가 된다. 타임라인 탭과 같은 그림을 쓴다 */}
        <PlayGlyph kind={playing ? "pause" : "play"} />
      </button>
      {onSpeed && (
        // 재생 속도 — 타임라인 탭과 같은 값 · 같은 모양(펼침). 재생 중에는 테두리가 강조색이다
        <div
          className={[
            "relative h-[30px] shrink-0 rounded-[8px] border",
            playing ? "border-accent" : "border-edge hover:border-edge-strong",
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
      )}

      <div className="shrink-0">
        <div className="text-[9px] tracking-[0.18em] text-label">SNAPSHOT</div>
        <div className="whitespace-nowrap text-[20px] font-semibold leading-tight tabular-nums text-title">
          {value.replace("-", " ")}
        </div>
      </div>

      <div className="min-w-0 flex-1">
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
        className="shrink-0 whitespace-nowrap rounded-[10px] border border-edge px-s4 py-s2 text-[12px] text-body hover-edge disabled:text-disabled"
      >
        기준일로
      </button>
    </div>
  );
}
