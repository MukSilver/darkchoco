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
import type { Ev, MapData, Relation, Territory } from "./types";

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
  };
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
    }));
}

/** 구운 파일에 사건이 들어 있나. 화면이 「예시 데이터」 표시를 이것으로 가른다 */
export const isBaked = (baked.events?.length ?? 0) > 0;

const territories = isBaked ? baked.territories.map(pickTerritory) : [];
const events = isBaked ? baked.events.map(pickEv) : [];

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
