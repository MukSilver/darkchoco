/**
 * 상세 패널이 보여 줄 내용을 조립한다 — 설계서 4.2.4 · 4.3.1 · 4.3.2 · 4.3.8.
 *
 * 생태계 · 섬 · 영토 · 행위자 넷이 같은 틀을 쓴다. 헤더 · 통계 카드 둘 · 설명 ·
 * 구성 막대 · 월별 막대 순서가 같고 들어가는 값만 다르다. 영토는 「공식 발표
 * 사고」 절이, 행위자는 「행위자 정보」 · 「주 활동 영토」 절이 더 붙는다.
 * 그래서 조립을 여기 모으고 `DetailPanel` 은 그리기만 한다.
 */

import { activityTerritories, mainTerritory } from "./actors.ts";
import { dayOf, eventTitle, sizeText } from "./events.ts";
import type { MapLayout, TerritoryShape } from "./layout.ts";
import {
  connectedIslandCount,
  islandPairs,
  josa,
  linksOf,
  partnerCount,
  touching,
  type IslandPairRow,
  type RelView,
} from "./relations.ts";
import { inScope, type MapResult, type TerritoryMetrics } from "./score.ts";
import type { ActorInfo, Ev, Territory } from "./types.ts";

export type PanelStat = {
  label: string;
  value: string;
  /**
   * 값 바로 아래 원자료 한 줄 — 「회원 6,972명」 (설계서 4.3.2 「활동도: 0~100,
   * 원자료 값」). 아래 ▲▼ 줄과 따로 둔다. 한 줄에 섞으면 변화율이 원자료의
   * 변화처럼 읽힌다 (원자료는 한 시점뿐이다, 3.3). 없으면 안 낸다
   */
  raw?: string;
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

/**
 * 영토 [개요] 「공식 발표 사고」 절 (설계서 4.3.2) — 이 영토가 보도된 유출 위치로
 * 적힌 유출 사고 DB 건수와 최근 1건. 제목은 분류 칸으로 지은 것이다 (`eventTitle`).
 * 조직명은 싣지도 않고 내지도 않는다 (2026-09-26)
 */
export type PanelOfficial = {
  count: number;
  latest: {
    id: string;
    title: string;
    /**
     * 공표일 `2026-05-14` — 공식 발표 사건은 게시 시각이 공표 시점이다. 게시에 붙은 사고(G-9)는
     * 그 사고의 공표일이고, 공표일이 비었으면 null 이다 (게시일을 공표일처럼 적지 않는다)
     */
    day: string | null;
    /**
     * `255GB` 처럼. 모르면 null. 게시에 붙은 사고는 늘 null 이다 — 사고의 유출 규모를 안
     * 싣고, 게시의 주장 규모를 공식 발표 규모처럼 적으면 안 된다
     */
    size: string | null;
  } | null;
};

/** 행위자 [개요] 정보 한 줄 — 「역할 · 판매자」 */
export type PanelInfoRow = { label: string; value: string };

/** 행위자 [개요] 활동 영토 한 줄. 누르면 그 영토를 고른다 */
export type PanelActivity = {
  territoryId: string;
  name: string;
  /** 그 영토 섬의 색 토큰 */
  token: string;
  count: number;
};

/** 행위자 [개요]에만 붙는 절 (설계서 4.3.8) */
export type PanelActor = {
  /** 다른 이름 · 역할 · 국가 · 처음 본 날 · 다루는 것. 빈 칸은 줄째 뺀다 */
  info: PanelInfoRow[];
  /** 주 활동 영토 (사건이 가장 많은 곳). 올린 곳이 없으면 null */
  main: PanelActivity | null;
  /** 나머지 활동 영토. 많은 순 */
  others: PanelActivity[];
};

export type PanelView = {
  /** 눈표 앞쪽 글씨. `ISLAND` 처럼 대문자로 낸다 */
  kindLabel: string;
  /** 눈표 뒤쪽 글씨 */
  stateLabel: string;
  /** 눈표 글씨 색 토큰(앞뒤 한 색). 섬을 고르면 그 섬 색이다 (피그마 ⑦-2) */
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
  /** 공식 발표 사고 절. 영토만 있고 섬 · 생태계 · 행위자는 null */
  official: PanelOfficial | null;
  /** 행위자 절. 행위자 영토만 있다 */
  actor: PanelActor | null;
};

/**
 * 섬 종류별 고정 설명 한 줄 (설계서 4.3.1 · 4.3.2).
 *
 * **포럼 것만 확정 문안이다.** 피그마 `⑦-2 섬 선택 (포럼)` 에 적혀 있는 것을
 * 그대로 옮겼다. 나머지 셋은 설계서에도 피그마에도 문안이 없어 **초안이다** —
 * 정본 작업판 코드값 탭 섬 표의 「들어가는 곳」 칸을 포럼 문안과 같은 꼴(「…
 * 유형.」)로 다듬었다 (2026-09-26). 팀이 문안을 정하면 여기만 바꾼다.
 * README 「우측 패널」 절에 확인할 것으로 적어 두었다.
 */
const ISLAND_BLURB: Record<string, string> = {
  FORUM:
    "해킹 도구 · 유출 데이터 · 접근 권한이 거래되고 공유되는 다크웹 포럼 유형.",
  // 초안 — 코드값 탭 「랜섬웨어 그룹의 유출 사이트. 그룹은 영토로만 보고 행위자에는 넣지 않습니다」
  RANSOMWARE:
    "랜섬웨어 그룹이 피해 사실을 주장하고 탈취한 자료를 공개하는 유출 사이트 유형.",
  // 초안 — 코드값 탭 「텔레그램 채널·그룹」. 2차 유포로 올라온 사건도 채널 몫이다 (3.3)
  TELEGRAM:
    "유출 자료가 공지되거나 다시 퍼지는 텔레그램 채널 · 그룹 유형.",
  // 초안 — 코드값 탭 「행위자 1명(계정 1개)이 영토 1개. 랜섬웨어 그룹은 넣지 않음」
  ACTOR:
    "포럼 · 채널에 글을 올린 행위자를 계정 하나에 엔티티 하나로 모은 유형으로, 랜섬웨어 그룹은 넣지 않습니다.",
};

/**
 * 활동도 카드의 원자료 한 줄 (설계서 3.3 · 4.3.2). 섬마다 뜻이 달라 단위를 붙인다.
 *
 *   포럼       회원 N명            게시처 DB 규모 (회원 수)
 *   텔레그램   구독자 N명          게시처 DB 규모
 *   랜섬웨어   피해 약 N건 (6개월)  굽기가 약 여섯 달 건수로 맞춰 싣는다 (`Territory.raw`)
 *
 * 원자료가 없으면 단위 이름에 「—」 를 붙인다. 활동도가 0 인 까닭이 거기 있다.
 * 행위자는 원자료가 사건 수라 `actorView` 가 따로 적는다. 다른 섬은 없다
 */
export function rawText(islandId: string, raw: number | null | undefined): string | undefined {
  const n = typeof raw === "number" && Number.isFinite(raw) ? Math.round(raw).toLocaleString("ko-KR") : null;
  switch (islandId) {
    case "FORUM":
      return n === null ? "회원 —" : `회원 ${n}명`;
    case "TELEGRAM":
      return n === null ? "구독자 —" : `구독자 ${n}명`;
    case "RANSOMWARE":
      return n === null ? "피해 —" : `피해 약 ${n}건 (6개월)`;
    default:
      return undefined;
  }
}

/**
 * 영토 자동 문장 — 피그마 ⑦-11b 문안 그대로다. 피그마의 「은(는)」 자리에 받침을 본
 * 조사를 넣는다 (`josa`). 뒤 문장은 지도가 지금 무엇을 보이는지 알린다
 */
export function territorySentence(
  name: string,
  islandName: string,
  eventCount: number,
  confirmed: number,
): string {
  return (
    `${name}${josa(name, "은", "는")} ${islandName} 섬에 속한 엔티티로, ` +
    `사건 ${eventCount}건과 검증된 관계 ${confirmed}건이 관측되었습니다. ` +
    "영토를 클릭하면 관계선과 연결된 섬만 강조됩니다."
  );
}

/**
 * 행위자 자동 문장 (설계서 4.3.8 「설명: 행위자 DB '어떤 곳인지' 1줄 + 자동 문장」).
 * **피그마에 행위자 화면이 없어 우리가 정한 꼴이다** (5.3). 헤더에 있는 값 —
 * 사건 수 · 주 활동 영토 · 활동 영토 수 — 만으로 짓는다. 행위자 DB 설명 칸은
 * 사람이 쓰는 글이라 반출하지 않아 자동 문장만 나간다
 */
export function actorSentence(
  handle: string,
  eventCount: number,
  mainName: string | null,
  places: number,
): string {
  const subj = `${handle}${josa(handle, "은", "는")}`;
  if (eventCount === 0) return `${subj} 이 기준일까지 올린 사건이 없습니다.`;
  if (!mainName) return `${subj} 이 기준일까지 사건 ${eventCount}건을 올린 행위자입니다.`;
  const head = `${subj} 사건 ${eventCount}건을 올린 행위자로, 주 활동 영토는 ${mainName}입니다.`;
  return places > 1 ? `${head} ${mainName} 외에 ${places - 1}곳에서도 활동했습니다.` : head;
}

/**
 * 행위자 정보 줄 (설계서 4.3.8, 2026-09-26 최현서 「행위자 정보칸 실어주고」).
 * 굽기가 싣는 다섯 칸을 설계서 표 차례(다른 이름 먼저)로 늘어놓고 빈 칸은 줄째 뺀다
 */
export function actorInfoRows(a: ActorInfo | undefined): PanelInfoRow[] {
  if (!a) return [];
  const rows: PanelInfoRow[] = [
    { label: "다른 이름", value: (a.otherNames ?? []).join(", ") },
    { label: "역할", value: (a.roles ?? []).join(" · ") },
    { label: "국가", value: (a.countries ?? []).join(" · ") },
    { label: "처음 본 날", value: a.firstSeen ?? "" },
    { label: "다루는 것", value: a.deals ?? "" },
  ];
  return rows.filter((r) => r.value.trim() !== "");
}

/**
 * 공식 발표 사고 절 (설계서 4.3.2). **이 영토에 올라온 공식 발표 사건**(`kind` 가
 * `official`)을 센다 — 굽기가 보도된 유출 위치를 영토로 맞춰 둔 것이다. 다른 건수와
 * 같이 기준일에 지도에 든 것만(`inScope`) 센다. 최근 1건은 공표 시점이 가장 늦은 것이다.
 * 행위자 칸(`actorTerritoryId`)은 안 본다 — 설계서가 「보도된 유출 위치」로 정했다.
 *
 * **이 영토의 게시에 붙은 공식 발표 사고도 센다** (G-9). 붙은 사고는 따로 된 사건이 아니라
 * 게시의 영토를 쓴다. 한 사고가 두 게시에 붙어도(INC-241) **사고 번호당 한 번** 센다.
 *
 *   기준일    붙은 사고도 **공표일로** 넣는다 — 따로 된 공식 발표 사건과 같게, 날짜만 적힌 값은
 *            그날 0시(UTC)다. 공표일이 비면 알 수 없어 게시가 기준일에 들었을 때만 센다
 *   빼는 것   게시가 반출 제외 · 허위면 안 센다 — 지도에 없는 게시라 팝업을 열 곳이 없다.
 *            허위 게시에 붙은 사고는 굽기 로그 「판정과 어긋난 짝」 에 번호로 남는다
 *   최근 1건  공표 날짜 → 시각 → 번호 차례. 공표일이 빈 사고는 맨 뒤이고 「공표 기록 없음」 이다.
 *            붙은 사고는 규모를 안 적는다(사고 규모를 안 싣는다). 누르면 그 게시 팝업이 열린다
 *
 * 머지 전 검토(2026-09-28)에서 첫 판이 붙은 사고를 게시일로 기준일에 넣고, 공표일이 빈 사고에
 * 게시일을 공표일처럼 적고, 게시의 주장 규모를 적던 것을 고쳤다
 */
export function officialOf(events: readonly Ev[], territoryId: string, d: Date): PanelOfficial {
  // 사고 번호 → 그 사고를 보여 줄 사건 · 공표 날짜(없으면 null) · 견줄 시각
  type Hit = { e: Ev; day: string | null; at: number };
  const seen = new Map<string, Hit>();
  for (const e of events) {
    if (e.territoryId !== territoryId || e.excluded || e.verdict === "false") continue;
    let hit: Hit;
    let incId: string;
    if (e.kind === "official") {
      if (!inScope(e, d)) continue;
      incId = e.id;
      hit = { e, day: dayOf(e), at: Date.parse(e.postedAt) };
    } else if (e.incident) {
      const ann = e.incident.announcedAt;
      if (ann ? !(Date.parse(ann) <= d.getTime()) : !inScope(e, d)) continue;
      incId = e.incident.id;
      hit = { e, day: ann ?? null, at: ann ? Date.parse(ann) : Date.parse(e.postedAt) };
    } else {
      continue;
    }
    const had = seen.get(incId);
    // 같은 사고가 두 게시에 붙으면 먼저 올라온 게시를 연다
    if (!had || Date.parse(e.postedAt) < Date.parse(had.e.postedAt)) seen.set(incId, hit);
  }
  const later = (a: Hit, b: Hit): number =>
    (a.day === null) !== (b.day === null)
      ? (a.day === null ? -1 : 1)
      : (a.day ?? "").localeCompare(b.day ?? "") || a.at - b.at || b.e.id.localeCompare(a.e.id);
  let latest: Hit | null = null;
  for (const x of seen.values()) {
    if (!latest || later(x, latest) > 0) latest = x;
  }
  return {
    count: seen.size,
    latest: latest
      ? {
          id: latest.e.id,
          title: eventTitle(latest.e),
          day: latest.day,
          size: latest.e.kind === "official" ? sizeText(latest.e) : null,
        }
      : null,
  };
}

/**
 * 월별 막대 축 이름표 자리 (피그마 컴포넌트 `Bar Chart · 월별 막대`, ⑦-1 · ⑦-11b).
 * 피그마는 12개월에 넷을 적는다 — 첫 달, 세 달 뒤, 여섯 달 뒤, 마지막 달
 * (`2025-10 · 2026-01 · 2026-04 · 2026-09`). 세 달 간격으로 찍고 마지막 달과
 * 세 달 안으로 붙는 것은 뺀다 — 이름표가 겹친다
 */
export function monthTicks(n: number): number[] {
  if (n <= 0) return [];
  const out: number[] = [];
  for (let i = 0; i < n - 1; i += 3) if (n - 1 - i >= 3) out.push(i);
  out.push(n - 1);
  return out;
}

/**
 * 선택 없음 [연결] — 섬 쌍 요약 전부 (피그마 ⑦-1 탭 「연결 N」). `islandPairs` 를
 * 섬마다 불러 겹친 줄은 한 번만 남긴다. 같은 함수라 섬 [연결] 탭 줄과 건수가 같다
 */
export function allIslandPairs(
  rels: readonly RelView[],
  islandOf: (territoryId: string) => string | undefined,
  islandKeys: readonly string[],
): IslandPairRow[] {
  const rows = new Map<string, IslandPairRow>();
  for (const k of islandKeys) {
    for (const r of islandPairs(rels, islandOf, k)) rows.set(`${r.from}>${r.to}`, r);
  }
  return [...rows.values()].sort(
    (a, b) => b.count - a.count || a.from.localeCompare(b.from) || a.to.localeCompare(b.to),
  );
}

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
  /**
   * 영토 id → 명부 칸 (활동도 원자료 · 행위자 정보). `MAP.territories` 에서 온다 —
   * `layout` 에는 계산 결과만 있어 이 둘이 없다. 없으면 두 자리를 비워 둔다
   */
  registry?: (id: string) => Pick<Territory, "raw" | "actor"> | undefined;
  /**
   * 지나간 분기 스냅샷 이름(`2025 Q3`). 가장 최근 분기면 없다. 생태계 머리글이
   * 「2025 Q3 스냅샷 · 사건 N건」으로 바뀐다 (피그마 ⑦-1a · ⑦-1b)
   */
  snapshot?: string | null;
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
    // 지나간 분기를 보고 있으면 무엇을 보는지부터 적는다 (피그마 ⑦-1a · ⑦-1b)
    subtitle: i.snapshot
      ? `${i.snapshot} 스냅샷 · 사건 ${eventCount}건`
      : `섬 ${live.length} · 엔티티 ${ts.length} · 연결 ${linkCount}`,
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
    official: null,
    actor: null,
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
    // 피그마 ⑦-2 머리글에는 부제 줄이 없다. 설계서 4.3.1 표가 헤더에 「섬·엔티티·연결
    // 수」를 적어 두어 설계서를 따라 남긴다 (설계서가 정본)
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
    official: null,
    actor: null,
  };
}

/**
 * 영토 선택 — 설계서 4.3.2, 피그마 ⑦-11b. 행위자 섬 영토는 `actorView` 로 간다
 * (4.3.8 — 머리글 · 절이 다르다)
 */
export function territoryView(
  i: BuildInput,
  territoryId: string,
): PanelView | null {
  const { layout, events, d, lastSeen } = i;
  const t = layout.territories.find((x) => x.territoryId === territoryId);
  if (!t) return null;
  const isl = layout.islands.find((x) => x.islandKey === t.islandKey);
  if (isl?.islandId === "ACTOR") return actorView(i, t);
  const m = t.metrics;
  // 탭 배지는 연결된 엔티티 수, 머리글은 연결된 섬 수다 (설계서 4.3.2)
  const mine = linksOf(i.rels, territoryId, false);
  const linkCount = partnerCount(mine, territoryId);
  const islandsLinked = connectedIslandCount(mine, territoryId, islandOfFn(layout));
  // 「검증된 관계」 — 이 영토가 닿은 관계 가운데 신뢰도 확인됨인 것 (⑦-11b, 설계서 2.5).
  // [연결] 탭이 늘어놓는 관계와 같은 목록에서 센다
  const confirmed = touching(i.rels, territoryId).filter((v) => v.rel.confidence === "confirmed").length;
  const islandName = isl?.name ?? "이";

  return {
    kindLabel: "TERRITORY",
    stateLabel: "선택됨",
    kindToken: t.token,
    title: t.name,
    // 피그마 ⑦-11b 「랜섬웨어 섬 · 사건 38건 · 활동도 93 · 연결된 섬 3」
    subtitle: `${islandName} 섬 · 사건 ${m.eventCount}건 · 활동도 ${m.activity} · 연결된 섬 ${islandsLinked}`,
    stats: [
      {
        // 활동도 옆 ▲▼ 는 사건 수 변화율이다 (설계서 3.7, 판 1.2)
        label: "활동도",
        value: String(m.activity),
        // 명부를 못 받았으면 원자료 줄을 안 낸다 — 「—」 는 명부에 값이 없다는 뜻이다
        raw: i.registry ? rawText(isl?.islandId ?? "", i.registry(territoryId)?.raw) : undefined,
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
    // 게시처 DB 「어떤 곳인지」 1줄은 사람이 쓰는 글이라 반출하지 않는다. 설계서가
    // 「DB 설명이 없는 영토는 자동 문장만」이라 적은 대로 자동 문장만 낸다
    description: territorySentence(t.name, islandName, m.eventCount, confirmed),
    sharesTitle: "",
    shares: null,
    barToken: t.token,
    months: monthlyCounts(events, d, (e) => belongsTo(e, new Set([territoryId]))),
    eventCount: m.eventCount,
    linkCount,
    official: officialOf(events, territoryId, d),
    actor: null,
  };
}

/**
 * 행위자 선택 — 설계서 4.3.8. **피그마 화면이 없다** (5.3). 영토 [개요] 틀에 설계서
 * 표의 요소를 차례대로 얹었다 — 헤더, 다른 이름(과 행위자 정보), 주 활동 영토,
 * 설명, 월별 막대.
 *
 * 활동 영토는 기준일에 지도에 든 사건만 세고, 지도에 있는 영토만 적는다 — 눌러서
 * 고를 수 있어야 하고, [연결] 탭 「활동한 영토」 건수와 같아야 한다 (설계서 3.9).
 */
function actorView(i: BuildInput, t: TerritoryShape): PanelView {
  const { layout, events, d, lastSeen } = i;
  const id = t.territoryId;
  const m = t.metrics;
  const byId = new Map(layout.territories.map((x) => [x.territoryId, x]));
  const rows = activityTerritories(events, id, (e) => inScope(e, d) && byId.has(e.territoryId));
  const main = mainTerritory(rows);
  const place = (r: { territoryId: string; count: number }): PanelActivity => ({
    territoryId: r.territoryId,
    name: byId.get(r.territoryId)?.name ?? r.territoryId,
    token: byId.get(r.territoryId)?.token ?? t.token,
    count: r.count,
  });
  const mainRow = rows.find((r) => r.territoryId === main);
  // 탭 배지는 활동한 영토 수다 — [연결] 탭이 활동 관계만 늘어놓는다 (4.3.8)
  const linkCount = partnerCount(linksOf(i.rels, id, true), id);

  // 행위자 활동도 원자료는 사건 수다 (설계서 3.3). 날짜를 대신 넣은 사건은 빠진다
  // (score.ts `rawCount`) — 그런 사건이 있어 사건 수 카드와 값이 다르면 그렇다고 적는다
  const rawCount = events.filter(
    (e) => belongsTo(e, new Set([id])) && inScope(e, d) && !e.dateSubstituted,
  ).length;
  const raw = rawCount === m.eventCount ? `사건 ${rawCount}건` : `날짜 확인 사건 ${rawCount}건`;

  return {
    kindLabel: "ACTOR",
    stateLabel: "선택됨",
    kindToken: t.token,
    title: t.name,
    // 설계서 4.3.8 「사건 수 · 활동도 · 활동 영토 수」
    subtitle: `사건 ${m.eventCount}건 · 활동도 ${m.activity} · 활동 영토 ${rows.length}곳`,
    stats: [
      { label: "활동도", value: String(m.activity), raw, ...countCard(m.countChangeRate30d) },
      { label: "사건 수", value: String(m.eventCount), note: `최근 관측 ${lastSeen[id] ?? "—"}` },
    ],
    descTitle: "행위자 설명",
    description: actorSentence(t.name, m.eventCount, mainRow ? place(mainRow).name : null, rows.length),
    sharesTitle: "",
    shares: null,
    barToken: t.token,
    months: monthlyCounts(events, d, (e) => belongsTo(e, new Set([id]))),
    eventCount: m.eventCount,
    linkCount,
    official: null,
    actor: {
      info: actorInfoRows(i.registry?.(id)?.actor),
      main: mainRow ? place(mainRow) : null,
      others: rows.filter((r) => r.territoryId !== main).map(place),
    },
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
