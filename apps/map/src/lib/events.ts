/**
 * 사건 목록 — 설계서 4.3.1 · 4.3.2 · 4.3.5 · 4.3.8.
 *
 * 패널 [사건] 탭과 엔티티 탭 「최근 주요 이벤트」가 쓴다.
 *
 * **사건 제목은 새로 짓는다** (2026-09-25 최현서 결정). 노션 자료 제목에 피해
 * 조직 이름이 들어 있어 굽기가 안 싣는다. 대신 분류 칸으로 만든다.
 *
 *     [KR · 유통 · 2026-05-14 · 255GB]
 *      국가  산업 분야  게시 날짜   주장 규모
 *
 * 모르는 조각은 뺀다. 날짜는 늘 있다.
 */

import { inScope } from "./score.ts";
import type { Ev, EvKind } from "./types.ts";

/** 사건 종류 칩 이름 (설계서 2.3) */
export const EV_KIND_LABEL: Record<EvKind, string> = {
  data_post: "데이터 게시",
  claim: "피해 주장",
  sale: "판매",
  access_sale: "접근 구매",
  repost: "재게시",
  official: "공식 발표",
};

/**
 * 칩 색. 피그마 ⑦-4 에서 피해 주장은 danger, 데이터 게시는 warning, 접근 구매는
 * success 칩이다. 판매 · 재게시 · 공식 발표는 시안에 없어 남은 상태색을 나눴다
 */
export const EV_KIND_TONE: Record<EvKind, string> = {
  data_post: "warning",
  claim: "danger",
  sale: "caution",
  access_sale: "success",
  repost: "violet",
  official: "info",
};

/** `255GB` · `1.2TB` · `120만` · `3,400,000건` */
export function sizeText(e: Pick<Ev, "sizeValue" | "sizeUnit">): string | null {
  if (typeof e.sizeValue !== "number" || !e.sizeUnit) return null;
  const n =
    e.sizeUnit === "건"
      ? e.sizeValue.toLocaleString("ko-KR")
      : String(Math.round(e.sizeValue * 100) / 100);
  return `${n}${e.sizeUnit}`;
}

/** 게시 날짜 `2026-05-14`. 노션이 적은 날짜 그대로다 (시간대를 옮기지 않는다) */
export function dayOf(e: Pick<Ev, "postedAt">): string {
  return e.postedAt.slice(0, 10);
}

/** 행 앞머리 `05-14 06:58`. 시각이 없으면 `05-14` */
export function stampOf(e: Pick<Ev, "postedAt">): string {
  const md = e.postedAt.slice(5, 10);
  const hm = /T(\d{2}:\d{2})/.exec(e.postedAt)?.[1];
  return hm ? `${md} ${hm}` : md;
}

/** 사건 제목 — `[KR · 유통 · 2026-05-14 · 255GB]` */
export function eventTitle(e: Ev): string {
  const parts = [e.country, e.industry, dayOf(e), sizeText(e)].filter((x): x is string => !!x);
  return `[${parts.join(" · ")}]`;
}

/** 기간 — 설계서 4.3.2 「7일 / 30일 / 90일 / 전체, 날짜 범위 지정」 */
export type Period =
  | { kind: "days"; days: 7 | 30 | 90 }
  | { kind: "all" }
  | { kind: "range"; from: string; to: string };

export const DEFAULT_PERIOD: Period = { kind: "days", days: 90 };

const DAY = 24 * 60 * 60 * 1000;

/**
 * 기간의 양 끝 (UTC 밀리초). **끝은 기준일 D 다** — 「기준일을 옮긴 상태면 그
 * 날짜까지의 90일」(설계서 4.3.2). 날짜 범위는 그 날 하루를 다 넣는다.
 */
export function periodBounds(p: Period, d: Date): { from: number; to: number } {
  const to = d.getTime();
  if (p.kind === "days") return { from: to - p.days * DAY, to };
  if (p.kind === "all") return { from: -Infinity, to };
  const f = Date.parse(`${p.from}T00:00:00Z`);
  const t = Date.parse(`${p.to}T23:59:59Z`);
  // 거르기는 `from` 을 안 넣는다(`t > from`). 시작일 0시 정각 사건도 들도록 1밀리초 당긴다
  return { from: Number.isNaN(f) ? -Infinity : f - 1, to: Math.min(to, Number.isNaN(t) ? to : t) };
}

/**
 * 기간 안의 사건. **최신순.** 지도에 든 사건만(기준일 전 · 허위 아님 · 반출
 * 제외 아님)이다 — 패널의 사건 수와 같은 규칙이다 (`score.ts` `inScope`).
 */
export function eventsIn(
  events: readonly Ev[],
  d: Date,
  p: Period,
  keep: (e: Ev) => boolean,
): Ev[] {
  const { from, to } = periodBounds(p, d);
  return events
    .filter((e) => keep(e) && inScope(e, d))
    .filter((e) => {
      const t = Date.parse(e.postedAt);
      return t > from && t <= to;
    })
    .sort((a, b) => Date.parse(b.postedAt) - Date.parse(a.postedAt) || a.id.localeCompare(b.id));
}

/** 월별 묶음 `2026-09` (설계서 4.3.2). 들어온 차례(최신순)를 지킨다 */
export function byMonth(events: readonly Ev[]): { month: string; items: Ev[] }[] {
  const out: { month: string; items: Ev[] }[] = [];
  for (const e of events) {
    const m = e.postedAt.slice(0, 7);
    const last = out[out.length - 1];
    if (last && last.month === m) last.items.push(e);
    else out.push({ month: m, items: [e] });
  }
  return out;
}

/** 기간 이름 — 헤더 오른쪽 `90일 · 5건` */
export function periodLabel(p: Period): string {
  if (p.kind === "days") return `${p.days}일`;
  if (p.kind === "all") return "전체";
  return "기간 지정";
}
