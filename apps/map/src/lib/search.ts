/**
 * 검색 계산 — 설계서 4.2.2, 피그마 ⑦-10 · ⑦-10a · ⑦-10c · ⑦-10d.
 *
 * 검색 창(`SearchOverlay`)과 전체 결과 화면(`SearchResults`)이 같은 계산을 쓴다.
 * 노션도 화면도 안 부른다.
 *
 *   묶음        무엇으로 찾나
 *   엔티티      영토 이름과 별칭. 행위자 섬 영토도 여기 든다
 *   행위자      행위자 섬 영토의 핸들과 다른 이름(별칭). 엔티티 쪽에도 같이 나온다 (4.2.2)
 *   사건        찾은 엔티티 · 행위자의 사건 (연관 검색 한 단계)
 *   관계        찾은 엔티티 · 행위자가 출발이나 도착인 관계 (연관 검색 한 단계)
 *   피해 대상   **안 만든다.** 피해 조직 이름을 지도에 안 낸다 (2026-09-23 결정)
 *
 * 사건에는 글자로 찾을 이름이 없다. 제목이 「국가 · 산업 분야 · 날짜 · 규모」이고
 * 설계서 검색어 표에도 사건 칸이 없다. 사건과 관계는 찾은 대상에 딸려 나온다.
 * 두 단계(찾은 영토와 관계가 있는 다른 영토의 사건)는 안 낸다 (4.2.2 연관 검색).
 *
 * **기준일과 무관하게 전체 기간에서 찾는다** (4.2.2). 한 번이라도 지도에 나온 영토가
 * 대상이다 — 어느 분기에도 안 나온 영토(2.5 로 빠진 곳)는 뺀다. 허위 · 반출 제외
 * 사건과, 그런 사건만 근거인 관계도 뺀다.
 */

import { CONF_LABEL } from "./relations.ts";
import { relationCount, relationSpan } from "./score.ts";
import type { QuarterKey } from "./quarter.ts";
import type { Confidence, Ev, IslandCode, Relation } from "./types.ts";

/* ────────────────────────────────────────────────────────────────
 * 필터
 * ──────────────────────────────────────────────────────────────── */

/** 범위 탭 (⑦-10 · ⑦-10d). 피해 대상은 뺐다 */
export type Scope = "all" | "entity" | "actor" | "event" | "rel";

export const SCOPES: { key: Scope; label: string }[] = [
  { key: "all", label: "전체" },
  { key: "entity", label: "엔티티" },
  { key: "actor", label: "행위자" },
  { key: "event", label: "사건" },
  { key: "rel", label: "관계" },
];

/** 정렬 (⑦-10d) — 관련도 / 최신순 / 건수순 */
export type Sort = "relevance" | "recent" | "count";

/** 기간 필터. 0 은 전체, 나머지는 데이터 기준 시각에서 거슬러 센 날 수 */
export type Days = 0 | 30 | 90 | 365;

export const DAYS: { days: Days; label: string }[] = [
  { days: 0, label: "전체" },
  { days: 30, label: "최근 30일" },
  { days: 90, label: "최근 90일" },
  { days: 365, label: "최근 1년" },
];

export const SORTS: { sort: Sort; label: string }[] = [
  { sort: "relevance", label: "관련도" },
  { sort: "recent", label: "최신순" },
  { sort: "count", label: "건수순" },
];

export type SearchFilter = {
  scope: Scope;
  /** 고른 섬. 비면 전체 (⑦-10 「복수 선택, 기본 전체」) */
  islands: IslandCode[];
  days: Days;
  /** 관계 신뢰도. null 이면 전체 */
  conf: Confidence | null;
  sort: Sort;
};

export const NO_FILTER: SearchFilter = { scope: "all", islands: [], days: 0, conf: null, sort: "relevance" };

/**
 * 결과를 좁히는 필터가 걸렸나. 결과 없음(⑦-10c)에서 「필터 초기화」를 보일지
 * 가른다. 범위 탭과 정렬은 좁히는 것이 아니라 뺀다
 */
export function narrowed(f: SearchFilter): boolean {
  return f.islands.length > 0 || f.days !== 0 || f.conf !== null;
}

/** 지금 필터를 한 줄로 — 「필터: 전체 섬 · 전체 기간」 (⑦-10c) */
export function filterText(f: SearchFilter, islandName: (id: IslandCode) => string): string {
  const parts = [
    f.islands.length ? f.islands.map(islandName).join(" · ") : "전체 섬",
    f.days ? (DAYS.find((x) => x.days === f.days)?.label ?? `최근 ${f.days}일`) : "전체 기간",
  ];
  if (f.conf) parts.push(CONF_LABEL[f.conf]);
  return parts.join(" · ");
}

/* ────────────────────────────────────────────────────────────────
 * 색인
 * ──────────────────────────────────────────────────────────────── */

/** 찾을 수 있는 영토 하나 */
export type Entry = {
  id: string;
  name: string;
  aliases: string[];
  islandId: IslandCode;
  /** 전체 기간 사건 수. 행위자면 그 행위자가 올린 사건 수다 */
  eventCount: number;
  /** 가장 늦은 사건 게시 시각. 사건이 없으면 null */
  lastAt: string | null;
};

/** 찾을 수 있는 관계 하나. 건수와 마지막 본 날은 전체 기간으로 센다 */
export type RelEntry = { rel: Relation; count: number; last: string | null };

export type SearchIndex = {
  entries: Entry[];
  byId: Map<string, Entry>;
  /** 허위 · 반출 제외가 아니고 올라온 영토가 지도에 나온 적 있는 사건 */
  events: Ev[];
  rels: RelEntry[];
  /** 행위자 → 주 활동 영토 (사건을 가장 많이 올린 곳). 올린 곳이 없으면 null */
  main: Map<string, string | null>;
  /** 데이터 기준 시각. 기간 필터가 여기서 거슬러 센다 */
  today: Date;
};

export type IndexInput = {
  territories: readonly { id: string; name: string; islandId: IslandCode; aliases?: string[] }[];
  events: readonly Ev[];
  /** 활동 관계를 넣은 관계 전부 (`withActivity`) */
  relations: readonly Relation[];
  /** 한 번이라도 지도에 나온 영토 id */
  seen: ReadonlySet<string>;
  today: Date;
};

/** 모든 사건을 넣는 기준일. 관계 건수를 전체 기간으로 셀 때 쓴다 */
const FAR = new Date(8.64e15);

/** 최신순 비교. 노션이 적은 날짜 · 시각 글자로 세운다 (`eventsIn` 과 같다) */
function newer(a: string | null, b: string | null): number {
  if (a === b) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return b.slice(0, 16).localeCompare(a.slice(0, 16)) || Date.parse(b) - Date.parse(a);
}

export function buildIndex(i: IndexInput): SearchIndex {
  const events = i.events.filter((e) => !e.excluded && e.verdict !== "false" && i.seen.has(e.territoryId));

  const count = new Map<string, number>();
  const last = new Map<string, string>();
  const bump = (id: string, at: string) => {
    count.set(id, (count.get(id) ?? 0) + 1);
    const l = last.get(id);
    if (!l || newer(l, at) > 0) last.set(id, at);
  };
  for (const e of events) {
    bump(e.territoryId, e.postedAt);
    if (e.actorTerritoryId && e.actorTerritoryId !== e.territoryId) bump(e.actorTerritoryId, e.postedAt);
  }

  const entries: Entry[] = i.territories
    .filter((t) => i.seen.has(t.id))
    .map((t) => ({
      id: t.id,
      name: t.name,
      aliases: t.aliases ?? [],
      islandId: t.islandId,
      eventCount: count.get(t.id) ?? 0,
      lastAt: last.get(t.id) ?? null,
    }));
  const byId = new Map(entries.map((e) => [e.id, e]));

  // 허위 · 반출 제외만 근거인 관계는 건수가 0 이라 빠진다. 근거가 처음부터 없는
  // 관계(명부 「연결된 곳」)는 1 이다 (score.ts relationCount)
  const rels: RelEntry[] = [];
  for (const rel of i.relations) {
    if (!byId.has(rel.from) || !byId.has(rel.to)) continue;
    const n = relationCount(rel, events, FAR);
    if (n === 0) continue;
    rels.push({ rel, count: n, last: relationSpan(rel, events, FAR).last });
  }

  // 주 활동 영토 — 그 행위자가 사건을 가장 많이 올린 곳. 같으면 늦게 올린 곳
  const main = new Map<string, string | null>();
  for (const a of entries) {
    if (a.islandId !== "ACTOR") continue;
    const tally = new Map<string, { n: number; at: string }>();
    for (const e of events) {
      if (e.actorTerritoryId !== a.id || e.territoryId === a.id) continue;
      const t = tally.get(e.territoryId) ?? { n: 0, at: e.postedAt };
      t.n += 1;
      if (newer(t.at, e.postedAt) > 0) t.at = e.postedAt;
      tally.set(e.territoryId, t);
    }
    let best: string | null = null;
    let bn = 0;
    let bat = "";
    for (const [id, t] of tally) {
      if (t.n > bn || (t.n === bn && newer(bat, t.at) > 0)) {
        best = id;
        bn = t.n;
        bat = t.at;
      }
    }
    main.set(a.id, best);
  }

  return { entries, byId, events, rels, main, today: i.today };
}

/* ────────────────────────────────────────────────────────────────
 * 이름 대조
 * ──────────────────────────────────────────────────────────────── */

/** 검색어를 대조용으로. 앞뒤 빈칸을 떼고 소문자로 (4.2.2 「대소문자 무시」) */
export function needleOf(q: string): string {
  return q.trim().toLowerCase();
}

export type Match = {
  /** 0 완전 일치 · 1 앞부분 · 2 중간. 이 차례로 세운다 (4.2.2) */
  rank: 0 | 1 | 2;
  /** 이름에서 일치한 자리. 별칭으로 걸렸으면 -1 (칠할 자리가 없다) */
  at: number;
  /** 별칭으로 걸렸으면 그 별칭 */
  via?: string;
};

/** 이름과 별칭 가운데 가장 잘 맞는 것 (4.2.2 「영토 이름과 별칭」) */
export function matchName(name: string, aliases: readonly string[], needle: string): Match | null {
  if (!needle) return null;
  let best: Match | null = null;
  for (const [s, via] of [[name, undefined], ...aliases.map((a) => [a, a])] as [string, string | undefined][]) {
    const low = s.toLowerCase();
    const i = low.indexOf(needle);
    if (i < 0) continue;
    const rank = low === needle ? 0 : i === 0 ? 1 : 2;
    if (!best || rank < best.rank) best = { rank, at: via ? -1 : i, via };
  }
  return best;
}

/** 아무 글에서 검색어 자리. 굵게 칠하는 데 쓴다. 없으면 -1 */
export function markAt(text: string, needle: string): number {
  return needle ? text.toLowerCase().indexOf(needle) : -1;
}

/* ────────────────────────────────────────────────────────────────
 * 찾기
 * ──────────────────────────────────────────────────────────────── */

export type EntityHit = { kind: "entity"; e: Entry; m: Match };
export type ActorHit = { kind: "actor"; e: Entry; m: Match; main: string | null };
/** 사건 — `rank` 는 딸려 나오게 한 대상의 일치 단계다 */
export type EventHit = { kind: "event"; ev: Ev; rank: number };
/** 관계 — `via` 는 검색어에 걸린 쪽 영토다. 둘 다 걸렸으면 도착 쪽 */
export type RelHit = { kind: "rel"; r: RelEntry; rank: number; via: string };
export type Hit = EntityHit | ActorHit | EventHit | RelHit;

export type Results = {
  entity: EntityHit[];
  actor: ActorHit[];
  event: EventHit[];
  rel: RelHit[];
};

export const EMPTY: Results = { entity: [], actor: [], event: [], rel: [] };

export function total(r: Results): number {
  return r.entity.length + r.actor.length + r.event.length + r.rel.length;
}

const DAY = 24 * 60 * 60 * 1000;

/**
 * 검색어로 네 묶음을 채운다. **범위 탭은 여기서 안 거른다** — 탭마다 건수를
 * 적어야 해서(⑦-10d) 묶음을 다 채우고 화면이 고른다.
 *
 * 필터는 이렇게 건다.
 *
 *   섬        엔티티는 그 섬, 행위자는 행위자 섬, 사건은 올라온 곳이나 올린
 *             행위자의 섬, 관계는 양 끝 가운데 하나의 섬
 *   기간      사건은 게시 시각, 관계는 마지막 본 날. 엔티티 · 행위자는 날짜가
 *             없어 안 거른다. 근거 사건이 없는 관계(명부 「연결된 곳」)는 날짜가
 *             없으므로 기간을 고르면 빠진다
 *   신뢰도    관계만. 사건 판정은 신뢰도 세 단계와 이름이 달라 안 섞는다
 *
 * `weightOf` 는 같은 일치 단계 안의 차례다 — 「가중치 점수 높은 순」(4.2.2).
 * 기준일의 활동도를 넘긴다. 지도에 없으면 0 이다.
 */
export function search(
  ix: SearchIndex,
  q: string,
  f: SearchFilter,
  weightOf: (id: string) => number = () => 0,
): Results {
  const needle = needleOf(q);
  if (!needle) return EMPTY;

  const islandOk = (id: string) => {
    if (f.islands.length === 0) return true;
    const e = ix.byId.get(id);
    return !!e && f.islands.includes(e.islandId);
  };
  const cut = f.days ? ix.today.getTime() - f.days * DAY : -Infinity;
  const inDays = (at: string | null) => !f.days || (at !== null && Date.parse(at) >= cut);

  // 이름에 걸린 대상. 연관 검색의 씨앗이다 — 섬 필터와 상관없이 씨앗은 다 쓴다.
  // 사건 · 관계는 제 섬으로 따로 거른다
  const seeds = new Map<string, Match>();
  for (const e of ix.entries) {
    const m = matchName(e.name, e.aliases, needle);
    if (m) seeds.set(e.id, m);
  }

  const entity: EntityHit[] = [];
  const actor: ActorHit[] = [];
  for (const [id, m] of seeds) {
    const e = ix.byId.get(id)!;
    if (islandOk(id)) entity.push({ kind: "entity", e, m });
    if (e.islandId === "ACTOR" && (f.islands.length === 0 || f.islands.includes("ACTOR"))) {
      actor.push({ kind: "actor", e, m, main: ix.main.get(id) ?? null });
    }
  }

  const event: EventHit[] = [];
  for (const ev of ix.events) {
    const a = seeds.get(ev.territoryId);
    const b = ev.actorTerritoryId ? seeds.get(ev.actorTerritoryId) : undefined;
    if (!a && !b) continue;
    if (!islandOk(ev.territoryId) && !(ev.actorTerritoryId && islandOk(ev.actorTerritoryId))) continue;
    if (!inDays(ev.postedAt)) continue;
    event.push({ kind: "event", ev, rank: Math.min(a?.rank ?? 3, b?.rank ?? 3) });
  }

  const rel: RelHit[] = [];
  for (const r of ix.rels) {
    const a = seeds.get(r.rel.from);
    const b = seeds.get(r.rel.to);
    if (!a && !b) continue;
    if (!islandOk(r.rel.from) && !islandOk(r.rel.to)) continue;
    if (f.conf && r.rel.confidence !== f.conf) continue;
    if (!inDays(r.last)) continue;
    rel.push({ kind: "rel", r, rank: Math.min(a?.rank ?? 3, b?.rank ?? 3), via: b ? r.rel.to : r.rel.from });
  }

  const byEntry = (x: { e: Entry; m: Match }, y: { e: Entry; m: Match }) => {
    if (f.sort === "recent") return newer(x.e.lastAt, y.e.lastAt) || x.e.name.localeCompare(y.e.name);
    if (f.sort === "count") return y.e.eventCount - x.e.eventCount || x.e.name.localeCompare(y.e.name);
    return (
      x.m.rank - y.m.rank ||
      weightOf(y.e.id) - weightOf(x.e.id) ||
      y.e.eventCount - x.e.eventCount ||
      x.e.name.localeCompare(y.e.name)
    );
  };
  entity.sort(byEntry);
  actor.sort(byEntry);

  // 사건은 건수가 없다. 건수순이면 최신순으로 둔다
  event.sort(
    (x, y) =>
      (f.sort === "relevance" ? x.rank - y.rank : 0) ||
      newer(x.ev.postedAt, y.ev.postedAt) ||
      x.ev.id.localeCompare(y.ev.id),
  );
  rel.sort((x, y) => {
    if (f.sort === "recent") return newer(x.r.last, y.r.last) || y.r.count - x.r.count || x.r.rel.id.localeCompare(y.r.rel.id);
    if (f.sort === "count") return y.r.count - x.r.count || x.r.rel.id.localeCompare(y.r.rel.id);
    return x.rank - y.rank || y.r.count - x.r.count || x.r.rel.id.localeCompare(y.r.rel.id);
  });

  return { entity, actor, event, rel };
}

/* ────────────────────────────────────────────────────────────────
 * 결과 없음 — 「이것을 찾으셨나요?」 (⑦-10c)
 * ──────────────────────────────────────────────────────────────── */

/** 편집 거리. 이름이 짧아 표 하나로 충분하다 */
function distance(a: string, b: string): number {
  const prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i += 1) {
    let diag = prev[0];
    prev[0] = i;
    for (let j = 1; j <= b.length; j += 1) {
      const up = prev[j];
      prev[j] = Math.min(prev[j] + 1, prev[j - 1] + 1, diag + (a[i - 1] === b[j - 1] ? 0 : 1));
      diag = up;
    }
  }
  return prev[b.length];
}

/**
 * 철자가 가까운 이름 최대 3개 (4.2.2, 예: lockbit5 → LockBit).
 *
 * 이름 전체와, 이름 앞부분(검색어 길이만큼)을 둘 다 대 본다 — 치다 만 이름에서
 * 한 글자 틀린 것도 잡는다. 허용 거리는 검색어 세 글자에 하나, 적어도 1 이다.
 */
export function nearby(ix: SearchIndex, q: string, max = 3): Entry[] {
  const needle = needleOf(q);
  if (needle.length < 2) return [];
  const limit = Math.max(1, Math.floor(needle.length / 3));
  const scored: { e: Entry; d: number }[] = [];
  for (const e of ix.entries) {
    let d = Infinity;
    for (const s of [e.name, ...e.aliases]) {
      const low = s.toLowerCase();
      d = Math.min(d, distance(needle, low), distance(needle, low.slice(0, needle.length)));
    }
    if (d <= limit) scored.push({ e, d });
  }
  return scored
    .sort((a, b) => a.d - b.d || b.e.eventCount - a.e.eventCount || a.e.name.localeCompare(b.e.name))
    .slice(0, max)
    .map((x) => x.e);
}

/* ────────────────────────────────────────────────────────────────
 * 결과 고르기
 * ──────────────────────────────────────────────────────────────── */

/**
 * 고른 대상이 지금 기준일에 안 보이면 옮겨 갈 분기. 보이면 null 이다.
 *
 * 설계서 4.2.2 「기준일 이후 대상을 고르면 기준일을 그 날짜로 옮기고 안내 표시」.
 * **뒤쪽(이후)을 먼저 본다.** 뒤에 없으면 앞쪽에서 가장 가까운 분기다 — 폐쇄된
 * 곳처럼 지금은 지도에서 빠진 대상도 고르면 보이는 곳으로 간다. 어디에도 없으면
 * 옮기지 않는다 (null).
 */
export function quarterFor(
  quarters: readonly QuarterKey[],
  current: QuarterKey,
  visible: (q: QuarterKey) => boolean,
): QuarterKey | null {
  if (visible(current)) return null;
  for (const q of quarters) if (q > current && visible(q)) return q;
  for (let i = quarters.length - 1; i >= 0; i -= 1) {
    const q = quarters[i];
    if (q < current && visible(q)) return q;
  }
  return null;
}

/* ────────────────────────────────────────────────────────────────
 * 최근 검색 (⑦-10)
 * ──────────────────────────────────────────────────────────────── */

/** 최근 검색 한 줄. 누르면 바로 그 대상으로 간다 (4.2.2) */
export type Recent = {
  kind: Hit["kind"];
  /** 엔티티 · 행위자는 영토 id, 사건은 사건 id, 관계는 관계 id */
  id: string;
  /** 관계만. 검색어에 걸렸던 쪽 영토 — 다시 열 때 관계 탭 중심을 같게 잡는다 */
  via?: string;
  label: string;
  sub: string;
  /** 고른 시각 (밀리초) */
  at: number;
};

export const RECENT_MAX = 5;

/** 같은 대상은 한 번만, 최근 것이 앞 */
export function pushRecent(list: readonly Recent[], r: Recent): Recent[] {
  return [r, ...list.filter((x) => !(x.kind === r.kind && x.id === r.id))].slice(0, RECENT_MAX);
}

/** 오른쪽 배지 — 「방금」 · 「3분 전」 · 「2시간 전」 · 「어제」 · 「09-14」 (⑦-10) */
export function agoText(at: number, now: number): string {
  const min = Math.floor((now - at) / 60000);
  if (min < 1) return "방금";
  if (min < 60) return `${min}분 전`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}시간 전`;
  if (h < 48) return "어제";
  const d = new Date(at);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
