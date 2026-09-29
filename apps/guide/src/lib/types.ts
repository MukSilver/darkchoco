// 설계서 2장의 단위를 그대로 옮긴 타입입니다.

export type ItemId = "name" | "phone" | "email" | "address" | "account" | "rrn" | "finance" | "internal" | "etc";
export type RiskId = "acct" | "phish" | "ident" | "money" | "priv";
export type Urgency = "now" | "today" | "watch";
export type Gate = "ok" | "wait" | "fake";
export type Level = 0 | 1 | 2 | 3;

export interface Item { id: ItemId; label: string }
export interface Risk { id: RiskId; label: string; icon: string }
export interface Group { id: Urgency; label: string; sub: string; tone: string }

/** 등급표. 항목마다 위험별 등급(1 낮음, 2 보통, 3 높음). 없으면 해당 없음 */
export type Weights = Record<ItemId, Partial<Record<RiskId, Level>>>;

export interface Stage {
  idx: number; name: string; sub: string; icon: string;
  who: string; risk: string; dots: number; mix: boolean;
  /** 이 단계에서 먼저 볼 위험 순서 */
  priority: RiskId[];
}

export interface When { id: string; label: string; stageIdx: number | null }

export interface GoLink { label: string; url: string }

export interface Action {
  id: number;
  risk: RiskId;
  urgency: Urgency;
  title: string;
  why: string;
  effect: string | null;
  limit: string | null;
  undo: string | null;
  cond: string | null;
  free: boolean;
  desk: string | null;
  url: string | null;
  minutes: number | null;
  prep: string | null;
  steps: string[];
  alt: string | null;
  go: GoLink[];
  /** 이 중 하나라도 유출되면 조치가 뜸 */
  need: ItemId[];
  /** 화면의 「관련 항목」에 보이는 항목 */
  basis: ItemId[];
}

export interface Case {
  id: number;
  industry: string;
  title: string;
  gate: Gate;
  spread: string;
  freshness: string;
  stageIdx: number | null;
  confirmed: ItemId[];
  claimed: ItemId[];
}

export type Levels = Record<RiskId, Level>;

export interface Picked { action: Action; index: number }

/** 방문자의 진행. 이 기기 브라우저에만 저장. 개인정보 없음 */
export interface Plan {
  src: string;
  sel: ItemId[];
  claimed: ItemId[];
  when: string | null;
  ntype: string | null;
  done: number[];
  later: number[];
  t: number;
}
