/**
 * 관계선을 화면이 쓰는 모양으로 묶는다 — 설계서 3.9 · 4.2.3 · 4.3.2 · 4.3.3 · 4.3.6.
 *
 * 세 화면이 같은 관계를 본다. 지도 위 관계선, 패널 [연결] 탭, 관계 탭이다.
 * 설계서 3.9 가 「[연결] 탭 행, 관계선 라벨, 관계 연혁에서 건수가 모두 같아야
 * 한다」고 못 박았으므로 **세 화면이 각자 세지 않고 여기 `relationsAt` 하나만
 * 부른다.** 건수 자체는 `score.ts` 의 `relationCount` 가 센다.
 *
 * 문장을 만드는 함수도 여기 둔다. 설계서가 「자동 문장」이라고만 적었고
 * 피그마 문안을 틀로 삼았다. 노션 설명 칸은 반출 검사에 막혀 있어 안 쓴다.
 */

import { evidenceInScope, relationCount, relationSpan } from "./score.ts";
import type { Confidence, Ev, Relation, RelationKind } from "./types.ts";

/* ────────────────────────────────────────────────────────────────
 * 이름과 색
 * ──────────────────────────────────────────────────────────────── */

/** 관계 종류 차례. 범례와 구성 막대가 이 차례를 쓴다 (설계서 2.3) */
export const KIND_ORDER: RelationKind[] = [
  "affiliate",
  "contact",
  "leak",
  "access",
  "sale",
  "successor",
  "activity",
];

/** 패널 칩 이름. 설계서 2.3 의 한국어 이름이다 */
export const KIND_LABEL: Record<RelationKind, string> = {
  affiliate: "제휴자 모집",
  contact: "공지·연락",
  leak: "데이터 유출",
  access: "접근 공급",
  sale: "데이터 판매",
  successor: "후속",
  activity: "활동",
};

/**
 * 그래프 라벨과 범례 이름. **피그마 ⑦-8 이 영어로 적었다.** 패널 칩은
 * 한국어라 둘을 나눠 둔다. 「Activity」 는 피그마에 없다 — 설계서 5.3 이
 * 「범례에 관계 종류 '활동' 추가」를 시안 할 일로 적어 두었다
 */
export const KIND_NAME: Record<RelationKind, string> = {
  affiliate: "Recruitment",
  contact: "Communication",
  leak: "Data Leak",
  access: "Access Supply",
  sale: "Data Sale",
  successor: "Successor",
  activity: "Activity",
};

/**
 * 패널 칩 색. `tokens.css` 상태색 이름이다. 피그마 ⑦-8 에서 「제휴자 모집」 은
 * danger, 「공지·연락」 은 info 칩이다. 나머지는 선 색과 가장 가까운 상태색이다
 */
export const KIND_CHIP: Record<RelationKind, string> = {
  affiliate: "danger",
  contact: "info",
  leak: "warning",
  access: "success",
  sale: "caution",
  successor: "violet",
  activity: "neutral",
};

export const CONF_LABEL: Record<Confidence, string> = {
  confirmed: "확인됨",
  high: "높은 신뢰",
  estimated: "추정",
};

/** 신뢰도 칩 색. 피그마 ⑦-3 · ⑦-8 에서 뽑았다 */
export const CONF_CHIP: Record<Confidence, string> = {
  confirmed: "success",
  high: "warning",
  estimated: "neutral",
};

/** 신뢰도별 선 모양 — SVG `stroke-dasharray`. 범례와 선이 같은 값을 쓴다 (설계서 2.5) */
export const CONF_DASH: Record<Confidence, string> = {
  confirmed: "",
  high: "7 5",
  estimated: "2 4",
};

/**
 * 근거 사건 목록의 판정 · 규모 이름 (설계서 2.5 · 3.2). 근거 목록은 사건
 * 제목을 안 낸다 — 제목에 피해 조직 이름이 든다 (2026-09-23 결정). 그래서
 * 날짜 · 판정 · 규모 · 올라온 곳만 보인다
 */
export const VERDICT_LABEL: Record<Ev["verdict"], string> = {
  confirmed: "확인됨",
  high: "신뢰성 높음",
  unverified: "검증 전",
  unknown: "미확인",
  low: "신뢰성 낮음",
  false: "허위",
};

export const SIZE_LABEL: Record<Ev["size"], string> = {
  large: "규모 큼",
  medium: "규모 중간",
  small: "규모 작음",
  unknown: "규모 모름",
};

/* ────────────────────────────────────────────────────────────────
 * 활동 관계
 * ──────────────────────────────────────────────────────────────── */

/**
 * 활동 관계(행위자 → 영토)를 사건에서 만든다.
 *
 * 설계서 3.9 가 「활동 관계의 건수는 그 행위자가 그 영토에 올린 사건 수」,
 * 4.3.8 이 「활동한 영토 목록 (관계 종류 '활동')」이라 적었다. **사건에서
 * 나오는 관계다.** 노션 관계선 DB 에도 활동 줄이 있지만 사건에서 나오는 쌍의
 * 일부만 적혀 있다 (2026-09-25 굽기: 사건 11쌍, DB 6쌍).
 *
 * DB 에 같은 쌍이 있으면 그 줄의 번호와 신뢰도를 쓰고 근거만 사건 전부로
 * 바꾼다. DB 에 없는 쌍은 코드가 번호를 매긴다 (설계서 4.3.3 「관계 번호는
 * 코드가 매김」). 신뢰도는 확인됨이다 — 그 행위자가 그 영토에 올린 사건이
 * 곧 근거이고, DB 의 활동 줄도 모두 확인됨이다.
 */
export function withActivity(relations: readonly Relation[], events: readonly Ev[]): Relation[] {
  const byPair = new Map<string, string[]>();
  for (const e of events) {
    if (!e.actorTerritoryId || e.actorTerritoryId === e.territoryId) continue;
    const k = `${e.actorTerritoryId}>${e.territoryId}`;
    const list = byPair.get(k) ?? [];
    list.push(e.id);
    byPair.set(k, list);
  }

  const out: Relation[] = [];
  for (const r of relations) {
    if (r.kind !== "activity") {
      out.push(r);
      continue;
    }
    const k = `${r.from}>${r.to}`;
    const ev = byPair.get(k);
    if (!ev) {
      out.push(r);
      continue;
    }
    out.push({ ...r, evidence: [...new Set([...r.evidence, ...ev])] });
    byPair.delete(k);
  }
  for (const [k, ev] of byPair) {
    const [from, to] = k.split(">");
    out.push({ id: `ACT-${from}-${to}`, from, to, kind: "activity", confidence: "confirmed", evidence: ev });
  }
  return out;
}

/* ────────────────────────────────────────────────────────────────
 * 기준일의 관계
 * ──────────────────────────────────────────────────────────────── */

/** 기준일 D 에 보이는 관계 하나 */
export type RelView = {
  rel: Relation;
  /** n(R) — 설계서 3.9. 근거가 처음부터 없으면 1 */
  count: number;
  /** 처음 · 마지막 본 날 (근거 사건 게시 시각). 근거가 없으면 null */
  first: string | null;
  last: string | null;
  /** D 에 지도에 든 근거 사건. 최근 것이 앞이다 */
  evidence: Ev[];
  /** 근거 사건 없이 명부 「연결된 곳」 칸에서 만든 관계 */
  fromRegistry: boolean;
};

/**
 * 기준일 D 에 그릴 관계. **양 끝이 지도에 있고 건수가 1 이상인 것만.**
 *
 * `present` 는 D 의 지도에 있는 영토 id 다 (칸이 1 이상). 설계서 2.5 가
 * 「제외된 영토가 들어 있는 관계선은 그 영토와 함께 사라진다」고 했고,
 * 3.9 가 건수 0 인 관계(그 분기에는 아직 없던 관계)를 안 그린다.
 */
export function relationsAt(
  relations: readonly Relation[],
  events: readonly Ev[],
  d: Date,
  present: ReadonlySet<string>,
): RelView[] {
  const out: RelView[] = [];
  for (const rel of relations) {
    if (!present.has(rel.from) || !present.has(rel.to)) continue;
    const count = relationCount(rel, events, d);
    if (count === 0) continue;
    const span = relationSpan(rel, events, d);
    const evidence = evidenceInScope(rel, events, d).sort(
      (a, b) => Date.parse(b.postedAt) - Date.parse(a.postedAt),
    );
    out.push({ rel, count, ...span, evidence, fromRegistry: rel.evidence.length === 0 });
  }
  return out;
}

/** 이 영토가 출발이나 도착인 관계 */
export function touching(views: readonly RelView[], id: string): RelView[] {
  return views.filter((v) => v.rel.from === id || v.rel.to === id);
}

/**
 * 영토의 [연결] 목록 · 배지 · 지도 선이 쓰는 관계. **행위자는 활동 관계만**이다
 * (설계서 4.3.8 「활동한 영토 목록」). 셋이 같은 목록을 써야 건수가 맞는다 (3.9)
 */
export function linksOf(views: readonly RelView[], id: string, actor: boolean): RelView[] {
  const t = touching(views, id);
  return actor ? t.filter((v) => v.rel.kind === "activity") : t;
}

/** 관계에서 이 영토의 상대 */
export function partnerOf(v: RelView, id: string): string {
  return v.rel.from === id ? v.rel.to : v.rel.from;
}

/**
 * 연결된 엔티티 — [연결] 탭 행이자 관계 탭 노드 (설계서 4.3.2 「이 집합이 곧
 * 관계 탭에서 그리는 노드」). **건수 많은 순**, 같으면 관계 번호 순이다.
 */
export function linkRows(views: readonly RelView[], id: string): RelView[] {
  return touching(views, id).sort((a, b) => b.count - a.count || a.rel.id.localeCompare(b.rel.id));
}

/** 연결된 엔티티 수 — [연결] 탭 배지 (설계서 4.3.2) */
export function partnerCount(views: readonly RelView[], id: string): number {
  return new Set(touching(views, id).map((v) => partnerOf(v, id))).size;
}

/** 연결된 섬 수 — 영토 헤더 (설계서 4.3.2). 상대 영토들의 섬 가짓수다 */
export function connectedIslandCount(
  views: readonly RelView[],
  id: string,
  islandOf: (territoryId: string) => string | undefined,
): number {
  const keys = new Set<string>();
  for (const v of touching(views, id)) {
    const k = islandOf(partnerOf(v, id));
    if (k) keys.add(k);
  }
  return keys.size;
}

/** 영토마다 관계 건수 합. 칩 줄과 기본 중심이 이 값으로 줄 세운다 */
export function relationWeight(views: readonly RelView[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const v of views) {
    m.set(v.rel.from, (m.get(v.rel.from) ?? 0) + v.count);
    m.set(v.rel.to, (m.get(v.rel.to) ?? 0) + v.count);
  }
  return m;
}

function byWeight(views: readonly RelView[], nameOf: (id: string) => string): string[] {
  const w = relationWeight(views);
  return [...w.keys()].sort(
    (a, b) => (w.get(b) ?? 0) - (w.get(a) ?? 0) || nameOf(a).localeCompare(nameOf(b)),
  );
}

/**
 * 관계 탭에 들어올 때의 중심 — 설계서 4.3.6. 지도에서 고른 영토가 없으면
 * 관계 건수가 가장 많은 영토다. 관계가 하나도 없으면 null.
 */
export function defaultCenter(views: readonly RelView[], nameOf: (id: string) => string): string | null {
  return byWeight(views, nameOf)[0] ?? null;
}

/**
 * 중심 엔티티 칩 줄 — 설계서 4.3.6. 관계 건수 상위 6곳이고, **지금 중심이
 * 그 안에 없으면 맨 앞에 붙인다.**
 */
export function centerChips(
  views: readonly RelView[],
  center: string | null,
  nameOf: (id: string) => string,
  n = 6,
): string[] {
  const top = byWeight(views, nameOf).slice(0, n);
  if (center && !top.includes(center)) return [center, ...top];
  return top;
}

/** 관계 유형 구성 — 관계 종류별 근거 사건 수 (설계서 4.3.6). 많은 순 */
export function kindMix(views: readonly RelView[]): { kind: RelationKind; count: number }[] {
  const m = new Map<RelationKind, number>();
  for (const v of views) m.set(v.rel.kind, (m.get(v.rel.kind) ?? 0) + v.count);
  return [...m.entries()]
    .map(([kind, count]) => ({ kind, count }))
    .sort((a, b) => b.count - a.count || KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind));
}

/**
 * 관계 연혁 차례 — **최초 관측 순** (설계서 4.3.6). 근거가 없어 처음 본 날을
 * 모르는 관계는 맨 뒤에 둔다.
 */
export function historyOrder(views: readonly RelView[]): RelView[] {
  return [...views].sort((a, b) => {
    if (a.first && b.first) return Date.parse(a.first) - Date.parse(b.first) || a.rel.id.localeCompare(b.rel.id);
    if (a.first) return -1;
    if (b.first) return 1;
    return b.count - a.count || a.rel.id.localeCompare(b.rel.id);
  });
}

/* ────────────────────────────────────────────────────────────────
 * 섬 간 요약 — 설계서 3.9 · 4.3.1 · 4.3.3 ②
 * ──────────────────────────────────────────────────────────────── */

export type IslandPairRow = {
  from: string;
  to: string;
  /** 엔티티 쌍 수 — 그 섬 쌍의 관계 개수 (설계서 3.9) */
  pairs: number;
  /** N(A → B) — 건수 합 */
  count: number;
  /** 건수가 가장 많은 관계 종류 */
  topKind: RelationKind;
  /** 가장 최근 관측. 근거가 없는 관계뿐이면 null */
  last: string | null;
};

/**
 * 이 섬과 **다른 섬** 사이 요약. 방향이 있어 A → B 와 B → A 는 다른 줄이다.
 * 같은 섬 안의 관계(포럼 → 포럼)는 「다른 섬 사이」가 아니라 뺀다 (설계서 4.3.1).
 */
export function islandPairs(
  views: readonly RelView[],
  islandOf: (territoryId: string) => string | undefined,
  islandKey: string,
): IslandPairRow[] {
  const groups = new Map<string, RelView[]>();
  for (const v of views) {
    const a = islandOf(v.rel.from);
    const b = islandOf(v.rel.to);
    if (!a || !b || a === b) continue;
    if (a !== islandKey && b !== islandKey) continue;
    const k = `${a}>${b}`;
    const list = groups.get(k) ?? [];
    list.push(v);
    groups.set(k, list);
  }
  const out: IslandPairRow[] = [];
  for (const [k, list] of groups) {
    const [from, to] = k.split(">");
    let last: string | null = null;
    for (const v of list) {
      if (v.last && (!last || Date.parse(v.last) > Date.parse(last))) last = v.last;
    }
    out.push({
      from,
      to,
      pairs: list.length,
      count: list.reduce((s, v) => s + v.count, 0),
      topKind: kindMix(list)[0].kind,
      last,
    });
  }
  return out.sort((a, b) => b.count - a.count || a.from.localeCompare(b.from) || a.to.localeCompare(b.to));
}

/** 섬 간 보기의 관계 — 출발 섬 A, 도착 섬 B 인 것. 건수 순 (설계서 4.3.3 ②) */
export function pairViews(
  views: readonly RelView[],
  islandOf: (territoryId: string) => string | undefined,
  from: string,
  to: string,
): RelView[] {
  return views
    .filter((v) => islandOf(v.rel.from) === from && islandOf(v.rel.to) === to)
    .sort((a, b) => b.count - a.count || a.rel.id.localeCompare(b.rel.id));
}

/* ────────────────────────────────────────────────────────────────
 * 자동 문장
 * ──────────────────────────────────────────────────────────────── */

/**
 * 받침에 맞는 조사. 한글로 끝나면 받침을 보고, 라틴 글자로 끝나면 읽는 소리를
 * 어림한다 — `Qilin`(킬린) 은 「은」, `Darkforums`(다크포럼스) 는 「는」.
 * 숫자는 한국어로 읽은 끝소리를 본다.
 */
export function josa(word: string, withBatchim: string, without: string): string {
  const ch = word.trim().slice(-1);
  if (!ch) return without;
  const code = ch.charCodeAt(0);
  if (code >= 0xac00 && code <= 0xd7a3) return (code - 0xac00) % 28 ? withBatchim : without;
  if (/[0-9]/.test(ch)) return "013678".includes(ch) ? withBatchim : without;
  // 끝 자음이 받침으로 읽히는 것만 받침으로 친다. `Lockbit`(락빗) · `Club`(클럽) ·
  // `Hack`(핵) 은 받침이고, `Dark`(다크) 처럼 모음을 붙여 읽는 k 는 받침이 아니다
  return /([bplmnt]|ck|ng)$/i.test(word.trim()) ? withBatchim : without;
}

/** `2024년 3월` */
export function monthText(iso: string): string {
  const d = new Date(iso);
  return `${d.getUTCFullYear()}년 ${d.getUTCMonth() + 1}월`;
}

/** `2024-03-18` */
export function dayText(iso: string): string {
  return iso.slice(0, 10);
}

const CONF_SENTENCE: Record<Confidence, string> = {
  confirmed: "관계가 확인되었습니다.",
  high: "신뢰도가 높은 관계이나 확인은 아직 이루어지지 않았습니다.",
  estimated: "추정 관계로, 확인은 아직 이루어지지 않았습니다.",
};

/**
 * 관계 연혁 한 항목의 설명 (설계서 4.3.6). 피그마 ⑦-8 문안을 틀로 삼았다 —
 * 「Qilin은 2024년 3월부터 BreachForums에서 제휴자를 모집해 왔습니다.
 * 관련 사건은 14건 수집되었고, 가장 최근 관측은 2026년 5월입니다.」
 */
export function historyText(v: RelView, nameOf: (id: string) => string): string {
  const a = nameOf(v.rel.from);
  const b = nameOf(v.rel.to);
  const since = v.first ? `${monthText(v.first)}부터 ` : "";
  const subj = `${a}${josa(a, "은", "는")}`;
  const verb: Record<RelationKind, string> = {
    affiliate: `${subj} ${since}${b}에서 제휴자를 모집해 왔습니다.`,
    contact: `${subj} ${since}${b}의 공지·연락 창구로 쓰여 왔습니다.`,
    leak: `${subj} ${since}${b}에 데이터를 유출해 왔습니다.`,
    access: `${subj} ${since}${b}에 접근 권한을 공급해 왔습니다.`,
    sale: `${subj} ${since}${b}에서 데이터를 판매해 왔습니다.`,
    successor: `${b}${josa(b, "은", "는")} ${a}의 뒤를 이은 곳입니다.`,
    activity: `${subj} ${since}${b}에서 활동해 왔습니다.`,
  };
  const facts = v.fromRegistry
    ? "근거 사건 없이 명부의 「연결된 곳」 칸에서 만든 관계입니다."
    : `관련 사건은 ${v.count}건 수집되었고, 가장 최근 관측은 ${monthText(v.last as string)}입니다.`;
  return `${verb[v.rel.kind]} ${facts} ${CONF_SENTENCE[v.rel.confidence]}`;
}

/**
 * 관계 탭 오른쪽 패널의 요약 (설계서 4.3.6 「자동 문장」). 피그마 ⑦-8 문안 —
 * 「BreachForums은 엔티티 4곳, 섬 2곳과 관계가 확인되었습니다. 제휴자 모집
 * 관계가 18건으로 가장 많으며, 관계는 2023년 2월에 처음 관측되어 가장 최근
 * 활동은 2026년 9월에 기록되었습니다.」
 *
 * 「확인되었습니다」 는 쓰지 않는다. 추정 관계가 섞이므로 「있습니다」로 쓴다.
 */
export function summaryText(
  name: string,
  views: readonly RelView[],
  partners: number,
  islands: number,
): string {
  if (views.length === 0) {
    return `${name}${josa(name, "은", "는")} 이 기준일에 기록된 관계가 없습니다.`;
  }
  const top = kindMix(views)[0];
  let first: string | null = null;
  let last: string | null = null;
  for (const v of views) {
    if (v.first && (!first || Date.parse(v.first) < Date.parse(first))) first = v.first;
    if (v.last && (!last || Date.parse(v.last) > Date.parse(last))) last = v.last;
  }
  const head = `${name}${josa(name, "은", "는")} 엔티티 ${partners}곳, 섬 ${islands}곳과 관계가 있습니다.`;
  const mid = `${KIND_LABEL[top.kind]} 관계가 ${top.count}건으로 가장 많`;
  if (!first || !last) return `${head} ${mid}습니다.`;
  return (
    `${head} ${mid}으며, 관계는 ${monthText(first)}에 처음 관측되어 ` +
    `가장 최근 활동은 ${monthText(last)}에 기록되었습니다.`
  );
}

/**
 * 관계선을 골랐을 때의 요약 (피그마 ⑦-8e) — 「선택한 관계 Qilin →
 * BreachForums는 제휴자 모집 14건으로, BreachForums의 관계 중 사건이 가장
 * 많습니다.」
 */
export function selectedText(
  v: RelView,
  center: string,
  views: readonly RelView[],
  nameOf: (id: string) => string,
): string {
  const pair = `${nameOf(v.rel.from)} → ${nameOf(v.rel.to)}`;
  const c = nameOf(center);
  const most = views.every((x) => x === v || x.count < v.count);
  const tail = most ? `으로, ${c}의 관계 중 사건이 가장 많습니다.` : "입니다.";
  return `선택한 관계 ${pair}${josa(nameOf(v.rel.to), "은", "는")} ${KIND_LABEL[v.rel.kind]} ${v.count}건${tail} ${CONF_SENTENCE[v.rel.confidence]}`;
}
