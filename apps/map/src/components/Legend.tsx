/**
 * 왼쪽 범례 — 폭 `--w-legend`(206px).
 *
 * 설계서에 범례 항목을 정한 절이 따로 없다. 피그마 `⑦-1 섬 지도 (기본)` 에
 * 있는 것을 그대로 옮겼다 — 섬 색 넷, 관계선 신뢰도 셋, 아래 각주다.
 *
 * **색을 `islands.ts` 에서 안 가져온다.** 거기 값은 설계서 2.3 표의 것이고
 * 그 표는 화이트 판 기준이다 (`#877BF3` 따위). 라이트 블랙 판은 같은 섬이
 * 다른 색이라 (`#7666FF`) 판을 타는 토큰을 써야 한다. 굽기가 붙어도
 * 이 부분은 데이터가 아니라 화면 쪽 일이다.
 */

import type { ReactNode } from "react";

import { DARK_ISLANDS, islandToken } from "@/lib/islands";
import { isBaked } from "@/lib/mapData";

/**
 * 섬 목록에서 그대로 만든다. 피그마 범례처럼 넷이다 — 미분류 섬은
 * 2026-09-23 에 없앴다 (`islands.ts`).
 */
const ISLAND_ROWS = DARK_ISLANDS.map((i) => ({
  name: i.name,
  token: islandToken(i.id),
}));

/**
 * 관계선 셋 — 설계서 2.5 의 신뢰도 3단계다.
 * `dash` 는 SVG `stroke-dasharray` 값이고 관계선을 그릴 때 같은 값을 쓴다.
 */
const LINE_ROWS: { name: string; dash: string }[] = [
  { name: "확인됨", dash: "" },
  { name: "높은 신뢰", dash: "7 5" },
  { name: "추정", dash: "2 4" },
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-s3">
      <h3 className="text-[11px] leading-none text-label">{title}</h3>
      {children}
    </section>
  );
}

export default function Legend() {
  return (
    <aside
      className="flex shrink-0 flex-col gap-s6 border-r border-divider bg-panel px-s5 py-s5"
      style={{ width: "var(--w-legend)" }}
    >
      <h2 className="text-[14px] font-semibold leading-none text-title">범례</h2>

      <Section title="섬 색 = 유형">
        <ul className="flex flex-col gap-s3">
          {ISLAND_ROWS.map((r) => (
            <li key={r.token} className="flex items-center gap-s3">
              <span
                aria-hidden
                className="size-[10px] shrink-0 rounded-full"
                style={{
                  background: `var(--t-island-${r.token}-legend, var(--t-island-${r.token}))`,
                }}
              />
              <span className="text-[13px] text-body">{r.name}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="관계선 · 신뢰도 (클릭 시에만 표시)">
        <ul className="flex flex-col gap-s3">
          {LINE_ROWS.map((r) => (
            <li key={r.name} className="flex items-center gap-s3">
              <svg
                aria-hidden
                width="40"
                height="2"
                viewBox="0 0 40 2"
                className="shrink-0 overflow-visible"
              >
                <line
                  x1="0"
                  y1="1"
                  x2="40"
                  y2="1"
                  stroke="var(--t-text-label)"
                  strokeWidth="1.5"
                  strokeDasharray={r.dash || undefined}
                  strokeLinecap="round"
                />
              </svg>
              <span className="text-[13px] text-body">{r.name}</span>
            </li>
          ))}
        </ul>
      </Section>

      <div className="flex-1" />

      {/*
        피그마 문구는 「헥사곤 면적은 사건 수에 비례」였는데 정본 계산에서는
        칸이 사건 지수와 활동도를 합친 점수로 정해져 틀린 말이 됐다.
        「예시 데이터」 문장은 굽기를 안 돌려 예시로 물러섰을 때만 띄운다
        (2026-09-23 최현서 결정)
      */}
      <p className="text-[11px] leading-[1.7] text-label">
        칸이 넓을수록 사건과 활동이 많은 곳입니다. 같은 섬은 같은 색입니다.
        {!isBaked && " 표시된 수치는 예시 데이터입니다."}
      </p>
    </aside>
  );
}
