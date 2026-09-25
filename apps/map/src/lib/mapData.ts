/**
 * 화면이 쓰는 지도 재료. **구운 파일을 읽는다.**
 *
 * `tools/bake.py` 가 노션에서 뽑아 `src/data/map.json` 으로 구워 둔 것이다.
 * 화면은 노션을 직접 안 본다 — 보면 반출 관문이 사라진다 (프젝 `DEV.md`).
 *
 * **섬은 구운 파일에 없다.** 섬 이름과 색은 설계서 2.3 값이라 노션에 없고
 * `islands.ts` 상수에서 온다. 굽기는 섬 코드만 쓴다.
 *
 * 구운 파일이 없거나 비어 있으면 예시 데이터로 물러선다. 굽기를 안 돌린
 * 사람도 화면을 볼 수 있어야 하고, 무엇을 보고 있는지는 `isBaked` 가 말한다.
 */

import raw from "@/data/map.json";
import { DARK_ISLANDS } from "./islands";
import { SAMPLE } from "./sample";
import type { ActorInfo, Ev, MapData, Relation, Territory } from "./types";

const baked = raw as unknown as Omit<MapData, "islands"> & {
  islands?: MapData["islands"];
};

/**
 * 구운 파일에서 **아는 칸만 골라 담는다.**
 *
 * 굽기가 이미 같은 검사를 하지만 여기서 한 번 더 한다. 까닭 둘이다.
 *
 *   1. 굽기 검사를 안 거친 파일이 들어올 수 있다. 손으로 고쳤거나, 옛 굽기가
 *      만든 것이거나, 다른 사람이 만들어 준 것일 수 있다
 *   2. `raw as unknown as …` 캐스팅이 타입 검사를 건너뛴다. JSON 에 여분 칸이
 *      있어도 타입스크립트가 못 잡는다
 *
 * 피해 조직 이름을 안 내기로 했으므로 (2026-09-23), 그 이름이 어느 경로로
 * 들어와도 화면까지는 못 가게 막는 자리가 하나 더 있어야 한다.
 */
function pickTerritory(t: Territory): Territory {
  return {
    id: t.id,
    name: t.name,
    islandId: t.islandId,
    web: t.web,
    ...(t.aliases?.length ? { aliases: t.aliases } : {}),
    // 활동도 원자료와 처음 나온 날 (설계서 3.3, score.ts presentAt). 숫자와 날짜만이다
    ...(typeof t.raw === "number" ? { raw: t.raw } : {}),
    ...(typeof t.posts === "number" ? { posts: t.posts } : {}),
    ...(typeof t.threads === "number" ? { threads: t.threads } : {}),
    ...(t.since ? { since: t.since } : {}),
    ...(t.islandId === "ACTOR" && t.actor ? pickActor(t.actor) : {}),
  };
}

/** 행위자 DB 역할 선택지 (굽기 `ROLE_VALUES` 와 같게) */
const ROLES = new Set(["판매자", "운영자", "해킹 그룹", "재배포", "중개·보증", "랜섬웨어 그룹"]);

/** 행위자 정보 (설계서 4.3.8). 굽기의 모양 검사를 여기서 한 번 더 한다 */
function pickActor(a: ActorInfo): { actor?: ActorInfo } {
  const out: ActorInfo = {};
  const roles = (a.roles ?? []).filter((r) => ROLES.has(r));
  if (roles.length) out.roles = roles;
  const countries = (a.countries ?? []).filter((c) => /^[가-힣A-Za-z ]{1,12}$/.test(c));
  if (countries.length) out.countries = countries;
  if (typeof a.firstSeen === "string" && /^\d{4}-\d{2}-\d{2}$/.test(a.firstSeen)) out.firstSeen = a.firstSeen;
  if (typeof a.deals === "string" && a.deals && a.deals.length <= 80 && !/[@＠]|\d{11,}/.test(a.deals)) out.deals = a.deals;
  // 파이썬 `\w` 처럼 한글도 받는다 (굽기 `RE_HANDLE_SHAPE`)
  const names = (a.otherNames ?? []).filter((x) => /^[\p{L}\p{N}_-]{2,32}$/u.test(x));
  if (names.length) out.otherNames = names;
  return Object.keys(out).length ? { actor: out } : {};
}

/** 사건 종류 칩 값 (설계서 2.3). 굽기가 이것 밖의 값을 내면 안 받는다 */
const EV_KINDS = new Set<string>(["data_post", "claim", "sale", "access_sale", "repost", "official"]);
/** 규모 단위. 굽기의 `claim_size` 가 내는 값뿐이다 */
const SIZE_UNITS = new Set(["TB", "GB", "MB", "KB", "억", "만", "건"]);
/** 공식 발표 사고 선택지 (굽기 `LEAK_ITEMS` · `CONFIRM_VALUES` · `SOURCE_KINDS` 와 같게) */
const LEAK_ITEMS = new Set(["이름", "이메일", "전화", "계정", "주소", "카드금융", "주민번호", "기타", "회사 내부 자료"]);
const RISKS = new Set(["high", "medium", "low"]);
const CONFIRMS = new Set(["조직 공식 발표", "게시글만", "언론 보도", "규제기관 확정", "연구자 발견"]);
const SOURCE_KINDS = new Set(["언론 보도", "보안업체", "기타", "기업 공지", "개인정보보호위원회", "한국인터넷진흥원"]);

/**
 * 보고서 팝업 재료 (설계서 3.10 · 4.3.4). 유출 항목 · 위험도 · 연결된 사건 · 사기 의심은
 * 모든 사건에, 사고 시점 · 외부 확인 · 출처 종류는 공식 발표 사건에만 받는다.
 * 연결된 사건은 목록 안 사건 번호만 남긴다 (`MAP` 을 만들 때 거른다)
 */
function pickOfficial(e: Ev): Partial<Ev> {
  const out: Partial<Ev> = {};
  const items = (e.leakItems ?? []).filter((x) => LEAK_ITEMS.has(x));
  if (items.length) out.leakItems = items;
  if (e.risk && RISKS.has(e.risk)) out.risk = e.risk;
  if (Array.isArray(e.linked) && e.linked.length) out.linked = e.linked.filter((x) => typeof x === "string");
  if (e.scam === true) out.scam = true;
  if (e.kind !== "official") return out;
  if (typeof e.occurredAt === "string" && /^\d{4}-\d{2}-\d{2}$/.test(e.occurredAt)) out.occurredAt = e.occurredAt;
  if (e.confirm && CONFIRMS.has(e.confirm)) out.confirm = e.confirm;
  if (e.sourceKind && SOURCE_KINDS.has(e.sourceKind)) out.sourceKind = e.sourceKind;
  return out;
}

/**
 * 제목 재료 (2026-09-25 최현서 결정). **분류 값만 받는다** — 국가는 두 글자
 * 부호, 산업 분야는 짧은 한국어 낱말, 규모는 숫자와 정해진 단위다. 모양이
 * 다르면 굽기를 안 거친 값일 수 있어 버린다.
 */
function pickTitleBits(e: Ev): Partial<Ev> {
  const out: Partial<Ev> = {};
  if (e.kind && EV_KINDS.has(e.kind)) out.kind = e.kind;
  if (typeof e.country === "string" && /^[A-Z]{2}$/.test(e.country)) out.country = e.country;
  if (typeof e.industry === "string" && /^[가-힣A-Za-z]{1,12}$/.test(e.industry)) out.industry = e.industry;
  if (typeof e.sizeValue === "number" && Number.isFinite(e.sizeValue) && e.sizeUnit && SIZE_UNITS.has(e.sizeUnit)) {
    out.sizeValue = e.sizeValue;
    out.sizeUnit = e.sizeUnit;
  }
  return out;
}

function pickEv(e: Ev): Ev {
  return {
    id: e.id,
    territoryId: e.territoryId,
    postedAt: e.postedAt,
    verdict: e.verdict,
    size: e.size,
    repost: e.repost,
    excluded: e.excluded,
    ...(e.actorTerritoryId ? { actorTerritoryId: e.actorTerritoryId } : {}),
    ...(e.dateSubstituted ? { dateSubstituted: true } : {}),
    ...pickTitleBits(e),
    ...pickOfficial(e),
  };
}

/**
 * 관계선도 아는 칸만 담는다. **양 끝이 목록 안 영토인 것만 받는다.**
 * 근거도 목록 안 사건만 남긴다 — 목록 밖 id 는 셀 수 없는 값이다.
 */
function pickRelations(
  rels: readonly Relation[] | undefined,
  territories: readonly Territory[],
  events: readonly Ev[],
): Relation[] {
  const terr = new Set(territories.map((t) => t.id));
  const evs = new Set(events.map((e) => e.id));
  return (rels ?? [])
    .filter((r) => terr.has(r.from) && terr.has(r.to) && r.from !== r.to)
    .map((r) => ({
      id: r.id,
      from: r.from,
      to: r.to,
      kind: r.kind,
      confidence: r.confidence,
      evidence: (r.evidence ?? []).filter((x) => evs.has(x)),
      // 명부 「연결된 곳」 원문 (설계서 4.3.6). 근거가 없는 관계에만 뜻이 있다
      ...(typeof r.note === "string" && r.note && !(r.evidence ?? []).length
        ? { note: r.note.slice(0, 400) }
        : {}),
    }));
}

/** 구운 파일에 사건이 들어 있나. 화면이 「예시 데이터」 표시를 이것으로 가른다 */
export const isBaked = (baked.events?.length ?? 0) > 0;

const territories = isBaked ? baked.territories.map(pickTerritory) : [];
const events = (() => {
  if (!isBaked) return [];
  const list = baked.events.map(pickEv);
  // 연결된 사건은 목록 안 사건끼리만 (굽기 검사와 같은 규칙)
  const ids = new Set(list.map((e) => e.id));
  return list.map((e) => {
    if (!e.linked) return e;
    const linked = e.linked.filter((x) => ids.has(x) && x !== e.id);
    const { linked: _drop, ...rest } = e;
    void _drop;
    return linked.length ? { ...rest, linked } : rest;
  });
})();

export const MAP: MapData = isBaked
  ? {
      generatedAt: baked.generatedAt,
      islands: DARK_ISLANDS,
      territories,
      events,
      relations: pickRelations(baked.relations, territories, events),
      // 연결 관계 DB 가 노션에 없다 (설계서 5.1-5). 구운 파일에 값이 있어도
      // 안 받는다 — 지어낸 것일 수 있다
      links: [],
    }
  : SAMPLE;
