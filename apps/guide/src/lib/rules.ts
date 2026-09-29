// 설계서 3장의 규칙. 화면과 떼어 둔 순수 함수라 단위 테스트를 붙입니다.
import type { Action, ItemId, Level, Levels, Picked, RiskId, Stage, Urgency, Weights, When } from "./types";

export const RISK_IDS: RiskId[] = ["acct", "phish", "ident", "money", "priv"];
export const DEFAULT_PRIORITY: RiskId[] = ["acct", "phish", "ident", "money", "priv"];
const URGENCY_ORDER: Record<Urgency, number> = { now: 0, today: 1, watch: 2 };

/** 3.1 위험 등급표. 위험마다 가장 높은 등급을 쓰고, 함께 새면 올리는 규칙 둘을 적용합니다. */
export function levels(sel: ReadonlySet<ItemId>, W: Weights): Levels {
  const r: Levels = { acct: 0, phish: 0, ident: 0, money: 0, priv: 0 };
  for (const item of sel) {
    const w = W[item] || {};
    for (const k of Object.keys(w) as RiskId[]) r[k] = Math.max(r[k], w[k] || 0) as Level;
  }
  if (sel.has("name") && sel.has("phone")) r.phish = Math.min(3, r.phish + 1) as Level;
  if (sel.has("name") && sel.has("rrn")) r.ident = 3;
  return r;
}

export const levelName = (v: Level) => (v >= 3 ? "높음" : v === 2 ? "보통" : v === 1 ? "낮음" : "해당 없음");

/** 어떤 항목이 이 위험에 기여했는지 */
export function contributors(sel: ReadonlySet<ItemId>, W: Weights, risk: RiskId): ItemId[] {
  return [...sel].filter((i) => W[i] && W[i][risk]);
}

/** 항목 하나가 걸리는 위험을 등급 높은 순으로 */
export function itemRisks(item: ItemId, W: Weights): RiskId[] {
  const w = W[item] || {};
  return (Object.keys(w) as RiskId[]).sort((a, b) => (w[b] || 0) - (w[a] || 0));
}

/** 등급이 있는 위험을 높은 순으로 */
export function ranked(L: Levels): RiskId[] {
  return RISK_IDS.filter((k) => L[k] > 0).sort((a, b) => L[b] - L[a]);
}

/** 3.4 퍼진 단계. 사고가 있으면 그 사고의 단계, 없으면 받은 시점으로 추정 */
export function stageOf(caseStageIdx: number | null | undefined, whenId: string | null, whens: When[]): { idx: number | null; est: boolean } {
  if (caseStageIdx !== null && caseStageIdx !== undefined) return { idx: caseStageIdx, est: false };
  const w = whens.find((x) => x.id === whenId);
  return { idx: w ? w.stageIdx : null, est: true };
}

/** 3.2 조치 고르기와 3.3 순서. 위험이 낮음 이상이고 필요 항목이 하나라도 유출된 조치만, 시급성 뒤 단계별 위험 순서로 */
export function pick(actions: Action[], sel: ReadonlySet<ItemId>, L: Levels, stageIdx: number | null, stages: Stage[]): Picked[] {
  const pri = stageIdx !== null && stages[stageIdx] ? stages[stageIdx].priority : DEFAULT_PRIORITY;
  return actions
    .map((action, index) => ({ action, index }))
    .filter(({ action }) => L[action.risk] > 0 && action.need.some((x) => sel.has(x)))
    .sort((x, y) => URGENCY_ORDER[x.action.urgency] - URGENCY_ORDER[y.action.urgency] || pri.indexOf(x.action.risk) - pri.indexOf(y.action.risk));
}

/** 3.5 다음 할 일. 완료하지도 미루지도 않은 첫 조치, 없으면 미룬 것 중 첫 조치 */
export function nextOf(picked: Picked[], done: ReadonlySet<number>, later: ReadonlySet<number>): Picked | null {
  return picked.find(({ index }) => !done.has(index) && !later.has(index)) || picked.find(({ index }) => !done.has(index)) || null;
}

/** 진행 칸 수는 조치 수에 2를 더합니다. 안내 확인과 대응 방법 찾아보기는 처음부터 채워 둡니다 */
export function progress(picked: Picked[], done: ReadonlySet<number>): { total: number; finished: number } {
  return { total: picked.length + 2, finished: picked.filter(({ index }) => done.has(index)).length + 2 };
}

/** 항목 이름 뒤에 붙는 조사. 받침이 있으면 앞 것 */
export function josa(word: string, withFinal: string, without: string): string {
  const c = word.charCodeAt(word.length - 1);
  const hasFinal = c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 !== 0;
  return hasFinal ? withFinal : without;
}
