/**
 * 관계 화면 셋이 같이 쓰는 작은 조각 — 칩, 섬 칩, 팀 로고 마크, 육각 꼭짓점.
 *
 * 패널 [연결] 탭(피그마 ⑦-3)과 관계 탭(⑦-8)의 칩 모양이 같다. 둥근 네모에
 * 옅은 바탕과 테두리, 진한 글자다.
 */

import type { ReactNode } from "react";

/**
 * 상태색 칩. **클래스 이름을 글자 그대로 적는다.** Tailwind 는 소스에서 글자로
 * 보이는 클래스만 만든다. `bg-${tone}-bg` 처럼 이어 붙이면 스타일이 안 생긴다
 */
const TONE: Record<string, string> = {
  danger: "bg-danger-bg text-danger border-danger-edge",
  info: "bg-info-bg text-info border-info-edge",
  warning: "bg-warning-bg text-warning border-warning-edge",
  success: "bg-success-bg text-success border-success-edge",
  caution: "bg-caution-bg text-caution border-caution-edge",
  violet: "bg-violet-bg text-violet border-violet-edge",
  neutral: "bg-neutral-bg text-neutral border-neutral-edge",
};

export function Chip({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-[6px] border px-s2 py-[2px] text-[11px] leading-[16px] ${TONE[tone] ?? TONE.neutral}`}
    >
      {children}
    </span>
  );
}

/**
 * 섬 칩 — 피그마 ⑦-3 「포럼」 · 「텔레그램」 칩. 글자는 섬 색이고 바탕과
 * 테두리는 섬 색을 옅게 섞었다. 시안의 바탕색(`#313143` 따위)이 섬 색을
 * 어두운 바탕에 18% 쯤 섞은 값이다
 */
export function IslandChip({ token, children }: { token: string; children: ReactNode }) {
  const c = `var(--t-island-${token})`;
  return (
    <span
      className="inline-flex shrink-0 items-center rounded-[6px] border px-s2 py-[2px] text-[11px] leading-[16px]"
      style={{
        color: c,
        background: `color-mix(in srgb, ${c} 16%, transparent)`,
        borderColor: `color-mix(in srgb, ${c} 38%, transparent)`,
      }}
    >
      {children}
    </span>
  );
}

/** 관계 종류 점 */
export function KindDot({ kind, size = 8 }: { kind: string; size?: number }) {
  return (
    <span
      aria-hidden
      className="inline-block shrink-0 rounded-full"
      style={{ width: size, height: size, background: `var(--t-rel-${kind})` }}
    />
  );
}

/**
 * 뾰족한 쪽이 위인 육각형 꼭짓점. 지도 칸과 같은 방향이다 (`hex.ts`).
 * SVG `points` 값으로 낸다
 */
export function hexPoints(cx: number, cy: number, r: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 6; i++) {
    const a = ((60 * i - 90) * Math.PI) / 180;
    pts.push(`${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`);
  }
  return pts.join(" ");
}

/**
 * 팀 로고 마크 — 점 넷. 피그마 머리띠 로고가 섬 색 점 넷이다.
 *
 * 설계서 4.3.6 이 행위자 노드를 「로고 대신 상징 마크. 기본은 팀 로고 마크」로
 * 정했다. 행위자 프로필 이미지는 굽기가 안 싣는다
 */
export function TeamMark({ cx, cy, size }: { cx: number; cy: number; size: number }) {
  const r = size * 0.2;
  const g = size * 0.26;
  const dots: [number, number, string][] = [
    [-g, -g, "forum"],
    [g, -g, "ransomware"],
    [-g, g, "telegram"],
    [g, g, "actor"],
  ];
  return (
    <g aria-hidden>
      {dots.map(([dx, dy, t]) => (
        <circle key={t} cx={cx + dx} cy={cy + dy} r={r} fill={`var(--t-island-${t})`} />
      ))}
    </g>
  );
}
