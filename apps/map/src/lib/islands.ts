/**
 * 섬 정의. 설계서 2.3 코드값 표를 그대로 옮긴 것이다.
 *
 * 색이 둘인 이유는 설계서가 그렇게 나눠 두었기 때문이다 — `hex` 는 지도 칸을
 * 채우는 색이고 `legend` 는 범례 아이콘 색이다. 미묘하게 다르다.
 */

import type { Island, IslandCode, IslandKey, Web } from "./types.ts";
import { islandKey } from "./types.ts";

/** 다크웹 섬 넷 (설계서 2.3) */
export const DARK_ISLANDS: Island[] = [
  { id: "FORUM", web: "dark", name: "포럼", hex: "#877BF3", legend: "#6D5EF0" },
  { id: "RANSOMWARE", web: "dark", name: "랜섬웨어", hex: "#F26666", legend: "#EF4444" },
  { id: "TELEGRAM", web: "dark", name: "텔레그램", hex: "#54B8E3", legend: "#2FA8DD" },
  // 판 1.2 에서 「기타」가 「행위자」로 바뀌었다 (설계서 2.3). 색은 그대로다
  { id: "ACTOR", web: "dark", name: "행위자", hex: "#808DA0", legend: "#64748B" },
];

/*
 * **미분류 섬은 2026-09-23 에 없앴다** (최현서 결정).
 *
 * 9/22 에 「소스가 빈 26건을 넣고 미분류 섬을 둔다」고 정해 다섯째 섬을
 * 두었다. 옛 설계서 3.4 실측 표가 그 26건을 분모에 넣어야 맞았기 때문이다.
 * 정본(설계서 PDF 63쪽 2.5)은 「소스 · 게시 플랫폼 · 게시 시각 가운데 하나라도
 * 비면 뺀다」로 못박았고 3.5 표에도 미분류가 없다. 정본대로 간다.
 *
 * 되돌리라는 말이 오면 되살린다 — git 3b00a25 앞 판에 섬 정의와 색 토큰
 * (`--t-island-unclassified`)이 있다.
 */

/**
 * 오픈웹 섬 여덟 (설계서 2.3).
 *
 * **지금은 안 쓴다.** 오픈웹 화면은 닥스훈트 몫이다 (설계서 1.2).
 * 그래도 적어 두는 이유는, 3D 연결 화면이 두 웹의 섬을 같이 그리기 때문이다.
 * 3D 는 2026-09-22 에 보류했지만 살아날 때 여기서 꺼내 쓴다.
 */
export const OPEN_ISLANDS: Island[] = [
  { id: "CODE_REPOSITORY", web: "open", name: "코드 저장소", hex: "#447AFF", legend: "#2F6BFF" },
  { id: "TEXT_HOSTING", web: "open", name: "텍스트 호스팅", hex: "#2CBFAF", legend: "#14B8A6" },
  { id: "COMMUNITY", web: "open", name: "커뮤니티", hex: "#FA812D", legend: "#F97316" },
  { id: "CLOUD_STORAGE", web: "open", name: "클라우드 스토리지", hex: "#4CC4F9", legend: "#38BDF8" },
  { id: "FILE_SHARING", web: "open", name: "파일 공유", hex: "#976CF7", legend: "#8B5CF6" },
  { id: "BACKEND_SERVICE", web: "open", name: "백엔드 서비스", hex: "#38CB6E", legend: "#22C55E" },
  { id: "RESEARCH_SOURCE", web: "open", name: "리서치 소스", hex: "#ECBB21", legend: "#EAB308" },
  { id: "OTHER", web: "open", name: "기타", hex: "#D0D9E4", legend: "#CBD5E1" },
];

export const ISLANDS: Island[] = [...DARK_ISLANDS, ...OPEN_ISLANDS];

const BY_KEY = new Map<IslandKey, Island>(
  ISLANDS.map((i) => [islandKey(i.web, i.id), i]),
);

/**
 * 섬 하나를 찾는다.
 *
 * **웹을 같이 받는 이유가 있다.** 설계서 2.3 의 개발 코드에 `OTHER` 가 오픈웹과
 * 다크웹에 하나씩 있어서 코드만으로는 섬이 유일하게 정해지지 않는다. 설계서가
 * 그 처리를 안 적어 두어서 여기서 정한 것이다.
 */
export function island(web: Web, id: IslandCode): Island | undefined {
  return BY_KEY.get(islandKey(web, id));
}

/** 그 웹의 섬 전부. 범례에 이 차례로 낸다 */
export function islandsOf(web: Web): Island[] {
  return ISLANDS.filter((i) => i.web === web);
}

/**
 * 섬 코드 → 색 토큰 꼬리. 화면이 `--t-island-<꼬리>` 로 쓴다.
 *
 * **섬 색을 위 `hex`·`legend` 대신 토큰으로 가져오는 자리가 있다.** 저 두 값은
 * 설계서 2.3 표의 것이고 그 표는 화이트 판 기준이다. 라이트 블랙 판은 같은 섬이
 * 다른 색이라 (포럼 `#877BF3` → `#7666FF`) 판을 타는 토큰이 필요하다.
 * 데이터에 딸린 색은 `hex`, 화면이 칠하는 색은 토큰이다.
 */
/**
 * 다크웹 섬 이름. 그 분기 지도(`layout.islands`)에 섬이 없어도 이름을 낸다 — 관계 탭 섬 간 보기에서
 * 스냅샷 바로 섬이 없던 분기로 가면 칩 · 패널 제목이 빈칸이 되었다 (2026-09-29 검토)
 */
export function islandName(id: string): string {
  // 지도 섬 열쇠는 `dark:ACTOR` 꼴이다(`layout.ts`). 코드만 떼어 찾는다
  const code = id.slice(id.lastIndexOf(":") + 1);
  return DARK_ISLANDS.find((i) => i.id === code)?.name ?? id;
}

export function islandToken(id: IslandCode): string {
  switch (id) {
    case "FORUM":
      return "forum";
    case "RANSOMWARE":
      return "ransomware";
    case "TELEGRAM":
      return "telegram";
    case "ACTOR":
      return "actor";
    default:
      // 오픈웹 OTHER 뿐이다. 다크웹에는 기타 섬이 없다 (설계서 2.3)
      return "etc";
  }
}
