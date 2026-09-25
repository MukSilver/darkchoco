/**
 * 웹 — 오픈웹과 다크웹 (설계서 1.2 · 2.3).
 *
 * 검색 결과 줄에 웹을 적는 데 쓴다. 설계서 4.2.2 가 「결과에 오픈웹/다크웹 표시」,
 * 엔티티 줄을 「이름, 웹, 섬, 활동도, 사건 수」로 정했고 5.3 이 피그마 ⑦-10 · 10a ·
 * 10d 에 「결과 행에 웹 표시」를 할 일로 남겼다.
 */

import { DARK_ISLANDS } from "./islands.ts";
import type { IslandCode, Web } from "./types.ts";

/** 화면에 적는 웹 이름. 머리띠 웹 전환 탭과 같은 글이다 (설계서 4.2.1) */
export const WEB_LABEL: Record<Web, string> = { open: "오픈웹", dark: "다크웹" };

const DARK = new Set<IslandCode>(DARK_ISLANDS.map((i) => i.id));

/**
 * 섬 코드로 웹을 가른다.
 *
 * **코드만으로 갈린다.** 옛 판에는 `OTHER` 가 두 웹에 하나씩 있어 웹을 따로 받아야
 * 했는데(`islandKey`), 판 1.2 에서 다크웹 기타 자리를 행위자 섬(`ACTOR`)이 차지해
 * `OTHER` 는 오픈웹에만 남았다 (설계서 2.3). 검색 색인(`search.ts` `Entry`)이 웹을
 * 안 들고 있어도 섬 코드로 적을 수 있다.
 */
export function webOfIsland(id: IslandCode): Web {
  return DARK.has(id) ? "dark" : "open";
}
