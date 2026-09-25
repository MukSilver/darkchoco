/**
 * 상세 패널이 보여 줄 내용을 조립한다 — 설계서 4.2.4 · 4.3.1 · 4.3.2.
 *
 * 생태계 · 섬 · 영토 셋이 같은 틀을 쓴다. 헤더 · 통계 카드 둘 · 설명 ·
 * 구성 막대 · 월별 막대 순서가 같고 들어가는 값만 다르다. 그래서 조립을
 * 여기 모으고 `DetailPanel` 은 그리기만 한다.
 */

import type { MapLayout } from "./layout.ts";
import { connectedIslandCount, islandPairs, partnerCount, type RelView } from "./relations.ts";
import type { MapResult, TerritoryMetrics } from "./score.ts";
import type { Ev } from "./types.ts";

export type PanelStat = {
  label: string;
  value: string;
  /** 카드 아래 작은 글씨. 없으면 안 낸다 */
  note?: string;
  /** 위·아래 화살표 방향과 색. 0 이거나 없으면 화살표 없음 */
  trend?: number;
  /** 화살표 옆 글씨. 없으면 `trend` 의 절댓값을 쓴다 */
  trendText?: string;
};

export type PanelShare = {
  name: string;
  token: string;
  percent: number;
};

export type PanelBar = { label: string; count: number };

export type PanelView = {
  /** 눈표 앞쪽 글씨. `ISLAND` 처럼 대문자로 낸다 */
  kindLabel: string;
  /** 눈표 뒤쪽 글씨 */
  stateLabel: string;
  /** 눈표 앞쪽 글씨 색 토큰. 섬을 고르면 그 섬 색이다 */
  kindToken: string | null;
  title: string;
  subtitle: string;
  stats: PanelStat[];
  /** 설명 절 제목. 「생태계 설명」 · 「섬 설명」 · 「영토 설명」 */
  descTitle: string;
  description: string;
  /** 구성 막대. 영토를 고르면 없다 */
  shares: PanelShare[] | null;
  sharesTitle: string;
  /** 막대 색 토큰. 구성 막대가 섬 색 하나로 통일되는 자리에 쓴다 */
  barToken: string | null;
  months: PanelBar[];
  eventCount: number;
  linkCount: number;
};

/**
 * 섬 종류별 고정 설명 한 줄 (설계서 4.3.1 · 4.3.2).
 *
 * **포럼 것만 실제 문안이다.** 피그마 `⑦-2 섬 선택 (포럼)` 에 적혀 있는 것을
 * 그대로 옮겼다. 나머지 섬은 설계서에도 피그마에도 문안이 없다. **지어내지
 * 않고 비워 둔다** — 비면 아래 자동 문장만 나간다. 설계서가 영토 쪽에
 * 「DB 설명이 없는 영토는 자동 문장만」이라고 적은 것과 같은 처리다.
 *
 * 문안은 팀이 정할 일이라 여기 채우는 것은 최현서를 거쳐야 한다.
 */
const ISLAND_BLURB: Record<string, string> = {
  FORUM:
    "해킹 도구 · 유출 데이터 · 접근 권한이 거래되고 공유되는 다크웹 포럼 유형.",
};

/** 월 이름표 `YYYY-MM` */
function ymOf(d: Date): string {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

/**
 * 기준일에서 거슬러 12개월치 건수.
 *
 * **설계서 3.x 에 이 집계가 없다.** 화면(4.3.1 · 4.3.2)이 「월별 막대, 실제
 * 건수」라고만 적어 두어서 여기서 셌다. 점수가 아니라 건수라 가중치를 안 탄다.
 */
export function monthlyCounts(
  events: readonly Ev[],
  d: Date,
  keep: (e: Ev) => boolean,
): PanelBar[] {
  const buckets = new Map<string, number>();
  const labels: string[] = [];
  for (let i = 11; i >= 0; i--) {
    const m = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - i, 1));
    const k = ymOf(m);
    labels.push(k);
    buckets.set(k, 0);
  }
  for (const e of events) {
    if (e.excluded || e.verdict === "false" || !keep(e)) continue;
    const t = new Date(e.postedAt);
    if (Number.isNaN(t.getTime()) || t.getTime() > d.getTime()) continue;
    const k = ymOf(t);
    if (buckets.has(k)) buckets.set(k, (buckets.get(k) ?? 0) + 1);
  }
  return labels.map((k) => ({ label: k, count: buckets.get(k) ?? 0 }));
}

/**
 * 구성 막대 — 상위 넷 + 「기타 N곳」 (설계서 4.3.1).
 *
 * 설계서 표 제목이 「엔티티 구성 (지도 비중)」인데 피그마는 「(사건 비중)」이고
 * 표 옆 메모가 「구성 막대 제목은 지도 비중으로 수정 예정」이다. 셋이 서로
 * 다르다. **수정 예정이라고 적힌 쪽을 따라 지도 비중(칸 수)으로 낸다** —
 * 그래야 막대 길이와 지도에서 보이는 넓이가 같은 말을 한다.
 */
export function topShares(
  rows: { name: string; cells: number }[],
  token: string,
  topN = 4,
): PanelShare[] {
  const total = rows.reduce((a, r) => a + r.cells, 0);
  if (total <= 0) return [];
  const sorted = [...rows].sort((a, b) => b.cells - a.cells);
  const head = sorted.slice(0, topN);
  const rest = sorted.slice(topN);
  const out = head.map((r) => ({
    name: r.name,
    token,
    percent: Math.round((r.cells / total) * 100),
  }));
  if (rest.length > 0) {
    const sum = rest.reduce((a, r) => a + r.cells, 0);
    out.push({
      name: `기타 ${rest.length}곳`,
      token,
      percent: Math.round((sum / total) * 100),
    });
  }
  return out;
}

/**
 * 기준일에서 거슬러 N일 안의 건수.
 *
 * `score.ts` 의 창 계산은 가중치 점수를 내는데, 화면 카드가 요구하는 것은
 * 「실제 건수」다 (설계서 4.3.1 · 4.3.5). 그래서 따로 센다.
 */
export function countInWindow(
  events: readonly Ev[],
  d: Date,
  days: number,
  keep: (e: Ev) => boolean,
): number {
  const from = d.getTime() - days * 24 * 60 * 60 * 1000;
  let n = 0;
  for (const e of events) {
    // 날짜를 대신 넣은 사건은 창 집계에서 뺀다 (score.ts 와 같은 규칙)
    if (e.excluded || e.verdict === "false" || e.dateSubstituted || !keep(e)) continue;
    const t = new Date(e.postedAt).getTime();
    if (Number.isNaN(t)) continue;
    if (t > from && t <= d.getTime()) n += 1;
  }
  return n;
}

/**
 * 최근 30일 건수의 직전 30일 대비 변화율 (%).
 *
 * 설계서 4.3.1 이 섬 카드에 「소속 영토 사건 합, 30일 변화율」을 요구한다.
 * `score.ts` 의 `countChangeRate30d` 는 영토 하나짜리라 여기서 묶어 센다.
 * 직전 30일이 0건이면 나눌 수 없어 `null` 이다.
 */
function countRate30d(
  events: readonly Ev[],
  d: Date,
  keep: (e: Ev) => boolean,
): number | null {
  const DAY = 24 * 60 * 60 * 1000;
  const now = d.getTime();
  const a0 = now - 30 * DAY;
  const b0 = now - 60 * DAY;
  let cur = 0;
  let prev = 0;
  for (const e of events) {
    if (e.excluded || e.verdict === "false" || e.dateSubstituted || !keep(e)) continue;
    const t = new Date(e.postedAt).getTime();
    if (Number.isNaN(t)) continue;
    if (t > a0 && t <= now) cur += 1;
    else if (t > b0 && t <= a0) prev += 1;
  }
  if (prev === 0) return null;
  return ((cur - prev) / prev) * 100;
}

/**
 * 사건 수 카드의 아래 한 줄.
 *
 * 변화율은 퍼센트라 화살표 옆에 `%` 가 붙어야 한다 (피그마 `▲ 9% · 지난 30일`).
 * 활동도 카드는 점수 차라 숫자만 붙는다. 그래서 글씨를 따로 준다.
 * 직전 30일이 0건이면 변화율이 없어 기간만 적는다.
 */
function countCard(rate: number | null): Partial<PanelStat> {
  if (rate === null) return { note: "지난 30일" };
  return {
    note: "지난 30일",
    trend: rate,
    trendText: `${Math.abs(Math.round(rate))}%`,
  };
}

/**
 * 사건이 영토에 드는가. **행위자 영토는 그 행위자가 올린 사건도 제 것이다**
 * (설계서 3.4, `Ev.actorTerritoryId`). territoryId 만 보면 행위자 섬 · 영토
 * 패널의 월별 막대와 30일 변화가 늘 비어 나온다.
 */
export function belongsTo(e: Ev, ids: ReadonlySet<string>): boolean {
  return ids.has(e.territoryId) || (!!e.actorTerritoryId && ids.has(e.actorTerritoryId));
}

export type BuildInput = {
  layout: MapLayout;
  result: MapResult;
  events: readonly Ev[];
  d: Date;
  /** 기준일에 그릴 관계 (`relationsAt`). [연결] 탭 배지와 머리글 연결 수가 여기서 나온다 */
  rels: readonly RelView[];
  /** 영토 id → 최근 관측일 `MM-DD` */
  lastSeen: Record<string, string>;
};

function islandOfFn(layout: MapLayout): (id: string) => string | undefined {
  const m = new Map(layout.territories.map((t) => [t.territoryId, t.islandKey]));
  return (id) => m.get(id);
}

/** 선택 없음 — 다크웹 생태계 전체 (피그마 ⑦-1) */
export function ecosystemView(i: BuildInput): PanelView {
  const { layout, result, events, d } = i;
  const live = layout.islands;
  // 생태계의 연결 수는 이 기준일에 그릴 관계선 수다 (설계서 6.4 「연결 수」)
  const linkCount = i.rels.length;
  const ts = result.territories.filter((t) => t.cells > 0);
  // 영토 사건 수를 더하지 않는다. 행위자 섬이 같은 사건을 한 번 더 세서
  // 그 몫이 두 번 들어간다 (정본 요약 탭의 217 = 실제 170 + 행위자 47)
  const eventCount = result.eventCount.dark;

  return {
    kindLabel: "ECOSYSTEM",
    stateLabel: "선택 없음",
    kindToken: null,
    title: "다크웹 생태계",
    subtitle: `섬 ${live.length} · 엔티티 ${ts.length} · 연결 ${linkCount}`,
    stats: [
      // 평균 활동도에 30일 변화를 안 붙인다 (판 1.2 에서 뜻을 잃었다).
      // 섬마다 뜻이 다른 값이라 섬 평균을 다시 평균하지 않고 영토 평균을 낸다
      { label: "활동도 (평균)", value: String(avgActivity(ts)) },
      {
        label: "사건 수",
        value: String(eventCount),
        ...countCard(countRate30d(events, d, () => true)),
      },
    ],
    descTitle: "생태계 설명",
    description:
      "다크웹에서 활동하는 포럼 · 랜섬웨어 그룹 · 텔레그램 채널 · 행위자를 유형별 섬으로 묶은 지도입니다. 칸이 넓을수록 사건과 활동이 많은 곳이며, 섬별로 한 가지 색을 씁니다.",
    sharesTitle: "유형별 구성 (지도 비중)",
    shares: live
      .map((isl) => ({
        name: isl.name,
        token: isl.token,
        percent: Math.round((isl.cells.length / cellSum(layout)) * 100),
      }))
      .sort((a, b) => b.percent - a.percent),
    barToken: null,
    months: monthlyCounts(events, d, () => true),
    eventCount,
    linkCount,
  };
}

/** 섬 선택 — 설계서 4.3.1 */
export function islandView(i: BuildInput, islandKey: string): PanelView | null {
  const { layout, result, events, d } = i;
  const isl = layout.islands.find((x) => x.islandKey === islandKey);
  if (!isl) return null;
  // 섬 [연결] 탭은 이 섬과 다른 섬 사이 요약만 보인다 (설계서 4.3.1)
  const linkCount = islandPairs(i.rels, islandOfFn(layout), islandKey).length;

  const mine = result.territories.filter((t) => t.islandKey === islandKey);
  const names = new Map(
    layout.territories
      .filter((t) => t.islandKey === islandKey)
      .map((t) => [t.territoryId, { name: t.name, cells: t.cells.length }]),
  );
  const rows = [...names.values()];
  const ids = new Set(names.keys());
  const eventCount = mine.reduce((a, t) => a + t.eventCount, 0);
  // 섬!O = 섬 안 모든 영토 활동도의 평균. 사건이 없는 영토도 든다
  const avg = result.islands.find((x) => x.islandKey === islandKey)?.avgActivity ?? 0;
  const top = rows.length ? [...rows].sort((a, b) => b.cells - a.cells)[0] : null;

  const blurb = ISLAND_BLURB[isl.islandId] ?? "";
  // 자동 문장. 피그마 ⑦-2 의 「엔티티 7곳 중 …의 사건 비중이 가장 큽니다」 꼴
  const auto = top
    ? `엔티티 ${rows.length}곳 중 ${top.name}의 비중이 가장 큽니다.`
    : "";

  return {
    kindLabel: "ISLAND",
    stateLabel: "선택됨",
    kindToken: isl.token,
    title: isl.name,
    subtitle: `엔티티 ${rows.length} · 사건 ${eventCount}건 · 연결 ${linkCount}`,
    stats: [
      { label: "활동도 (평균)", value: String(avg) },
      {
        label: "사건 수",
        value: String(eventCount),
        ...countCard(countRate30d(events, d, (e) => belongsTo(e, ids))),
      },
    ],
    descTitle: "섬 설명",
    description: [blurb, auto].filter(Boolean).join(" "),
    sharesTitle: "엔티티 구성 (지도 비중)",
    shares: topShares(rows, isl.token),
    barToken: isl.token,
    months: monthlyCounts(events, d, (e) => belongsTo(e, ids)),
    eventCount,
    linkCount,
  };
}

/** 영토 선택 — 설계서 4.3.2 */
export function territoryView(
  i: BuildInput,
  territoryId: string,
): PanelView | null {
  const { layout, events, d, lastSeen } = i;
  const t = layout.territories.find((x) => x.territoryId === territoryId);
  if (!t) return null;
  const isl = layout.islands.find((x) => x.islandKey === t.islandKey);
  const m = t.metrics;
  // 탭 배지는 연결된 엔티티 수, 머리글은 연결된 섬 수다 (설계서 4.3.2)
  const linkCount = partnerCount(i.rels, territoryId);
  const islandsLinked = connectedIslandCount(i.rels, territoryId, islandOfFn(layout));

  // 자동 문장. **설계서에도 피그마에도 예시가 없어 우리가 정한 꼴이다.**
  // 갖고 있는 값(섬 이름 · 비중 · 상태)만으로 만들고 없는 말은 안 붙인다
  const auto =
    `${isl?.name ?? "이 섬"} 섬에 속하며 섬 안 비중이 ` +
    `${Math.round(m.shareInIsland)}% 입니다.`;

  return {
    kindLabel: "TERRITORY",
    stateLabel: "선택됨",
    kindToken: t.token,
    title: t.name,
    subtitle:
      `${isl?.name ?? ""} · 사건 ${m.eventCount}건 · 활동도 ${m.activity} · 연결된 섬 ${islandsLinked}`.trim(),
    stats: [
      {
        // 활동도 옆 ▲▼ 는 사건 수 변화율이다 (설계서 3.7, 판 1.2)
        label: "활동도",
        value: String(m.activity),
        ...countCard(m.countChangeRate30d),
      },
      {
        // 설계서 4.3.2 는 이 카드에 「건수, 최근 관측일」만 적었다.
        // 30일 변화율은 섬 카드(4.3.1)에만 있다
        label: "사건 수",
        value: String(m.eventCount),
        note: `최근 관측 ${lastSeen[territoryId] ?? "—"}`,
      },
    ],
    descTitle: "영토 설명",
    description: auto,
    sharesTitle: "",
    shares: null,
    barToken: t.token,
    months: monthlyCounts(events, d, (e) => belongsTo(e, new Set([territoryId]))),
    eventCount: m.eventCount,
    linkCount,
  };
}

/**
 * 영토 활동도의 평균. **사건이 없는 영토도 넣는다** — 정본 섬!O 가 그렇다.
 * 활동도는 사건이 아니라 명부 규모에서 나오므로 사건 유무로 거르면 안 된다.
 */
function avgActivity(ts: TerritoryMetrics[]): number {
  const here = ts.filter((t) => t.present);
  if (here.length === 0) return 0;
  return Math.round(here.reduce((a, t) => a + t.activity, 0) / here.length);
}

function cellSum(layout: MapLayout): number {
  const n = layout.islands.reduce((a, i) => a + i.cells.length, 0);
  return n > 0 ? n : 1;
}
