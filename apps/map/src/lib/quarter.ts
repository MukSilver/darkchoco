/**
 * 분기 다루기 — 설계서 3.1 · 4.2.5 · 4.3.7.
 *
 * **판 1.2 에서 기준일 단위가 달에서 분기로 바뀌었다.** 스냅샷 바 · 타임라인 ·
 * 지도 기준일이 전부 분기를 쓴다. 월별 막대(「사건 수 · 최근 12개월」)만 달
 * 단위로 남는다 — 그 표는 설계서가 안 바꿨다.
 *
 * 분기 열쇠는 `2026-Q3` 꼴 문자열이다. 사전순이 곧 시간순이라 견주기가 쉽다.
 */

import { endOfQuarterUTC, quarterOf } from "./score.ts";

/** `2026-Q3` */
export type QuarterKey = string;

export function quarterKey(year: number, q: number): QuarterKey {
  return `${year}-Q${q}`;
}

export function parseQuarter(k: QuarterKey): { year: number; q: number } {
  const [y, qq] = k.split("-Q");
  return { year: Number(y), q: Number(qq) };
}

/** 그 날짜가 든 분기 */
export function quarterOfDate(d: Date): QuarterKey {
  return quarterKey(d.getUTCFullYear(), quarterOf(d.getUTCMonth() + 1));
}

/** 기준일 D. 「이번 분기는 오늘」 예외가 여기 걸린다 (설계서 3.1) */
export function quarterEnd(k: QuarterKey, today?: Date): Date {
  const { year, q } = parseQuarter(k);
  return endOfQuarterUTC(year, q, today);
}

/** 앞 분기부터 뒤 분기까지 하나씩 */
export function quarterRange(from: QuarterKey, to: QuarterKey): QuarterKey[] {
  const a = parseQuarter(from);
  const b = parseQuarter(to);
  const out: QuarterKey[] = [];
  for (let y = a.year, q = a.q; y < b.year || (y === b.year && q <= b.q); ) {
    out.push(quarterKey(y, q));
    q += 1;
    if (q > 4) {
      q = 1;
      y += 1;
    }
  }
  return out;
}

/**
 * 사건이 걸쳐 있는 분기 범위.
 *
 * 눈금을 고정해 두면 데이터 기간이 바뀔 때마다 앞뒤가 비거나 잘린다.
 */
export function spanOf(
  events: readonly { postedAt: string }[],
): [QuarterKey, QuarterKey] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const e of events) {
    const t = Date.parse(e.postedAt);
    if (Number.isNaN(t)) continue;
    if (t < lo) lo = t;
    if (t > hi) hi = t;
  }
  if (!Number.isFinite(lo)) return ["2024-Q3", "2026-Q3"];
  return [quarterOfDate(new Date(lo)), quarterOfDate(new Date(hi))];
}

/**
 * 눈금 이름표. 연도가 바뀌는 자리에만 연도를 붙인다 (설계서 4.2.5
 * 「연도 경계에 연도 표시」).
 */
export function tickLabel(k: QuarterKey, prev?: QuarterKey): string {
  const { year, q } = parseQuarter(k);
  if (!prev) return `${year} Q${q}`;
  return parseQuarter(prev).year === year ? `Q${q}` : `${year} Q${q}`;
}
