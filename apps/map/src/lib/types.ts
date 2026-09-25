/**
 * 지도가 쓰는 공용 타입.
 *
 * **설계서 2장이 정본이다.** 이름과 뜻을 거기서 그대로 가져왔다.
 * 노션 칸 이름과 다른 곳이 있는데, 그것은 설계서 2.4 대응표를 따른 것이다.
 */

/** 웹. 계산이 이 단위로 갈린다 (설계서 3.4 「오픈웹과 다크웹은 따로 계산」). */
export type Web = "open" | "dark";

/**
 * 섬 — 성격이 같은 영토 묶음.
 *
 * **`web` 을 키에 같이 넣는 이유가 있다.** 설계서 2.3 의 개발 코드에 `OTHER` 가
 * 오픈웹과 다크웹에 하나씩 있어서, 코드만으로는 섬이 유일하게 정해지지 않는다.
 * 설계서가 그 처리를 안 적어 두어서 여기서 정했다.
 */
export type Island = {
  id: IslandCode;
  web: Web;
  name: string;
  /** 헥사 채움 색 (설계서 2.3) */
  hex: string;
  /** 범례 아이콘 색 (설계서 2.3) */
  legend: string;
};

export type DarkIslandCode =
  | "FORUM"
  | "RANSOMWARE"
  | "TELEGRAM"
  /**
   * **판 1.2 에서 「기타」 자리를 이것이 차지했다.** 설계서 2.3 이 「다크웹 기타
   * 섬(접근 중개, 집계, 모니터링)은 두지 않음. 그 자리를 행위자 섬으로 씀」
   * 이라고 못박았다. 색(#808DA0 · #64748B)도 그대로 물려받았다.
   *
   * 행위자 1명이 영토 1개다 (설계서 4.3.8). 그 행위자가 올린 사건을 원래
   * 영토와 여기서 한 번씩, 두 번 센다.
   */
  | "ACTOR";
// 미분류(UNCLASSIFIED)는 2026-09-23 에 없앴다. 까닭은 `islands.ts` 에 있다

export type OpenIslandCode =
  | "CODE_REPOSITORY"
  | "TEXT_HOSTING"
  | "COMMUNITY"
  | "CLOUD_STORAGE"
  | "FILE_SHARING"
  | "BACKEND_SERVICE"
  | "RESEARCH_SOURCE"
  | "OTHER";

export type IslandCode = DarkIslandCode | OpenIslandCode;

/** 섬을 유일하게 가리키는 열쇠. `OTHER` 가 양쪽에 있어 웹을 붙인다. */
export type IslandKey = `${Web}:${IslandCode}`;

export const islandKey = (web: Web, id: IslandCode): IslandKey => `${web}:${id}`;

/**
 * 영토 — 실제 장소나 집단. 포럼 한 곳, 랜섬웨어 그룹 한 곳이 영토 하나다.
 *
 * 랜섬웨어 그룹은 **행위자이면서 영토**다 (설계서 2.1). 그 그룹이 올린 글은
 * 그 그룹 영토의 사건이 된다.
 */
export type Territory = {
  id: string;
  name: string;
  islandId: IslandCode;
  web: Web;
  /**
   * 같은 영토의 다른 이름과 주소. 설계서 2.1 이 「별칭으로 묶어 하나로 취급」
   * 하라고 적었다. 노션 「게시 플랫폼」 표기가 흩어져 있어 이것이 필요하다 (5.1-1).
   */
  aliases?: string[];
  /**
   * 활동도 원자료 (설계서 3.3). 섬마다 뜻이 다르다 — 포럼 회원 수, 텔레그램
   * 구독자 수, 랜섬웨어 피해 기업 수(약 여섯 달 건수). 게시처 DB 「규모」 칸에서
   * 읽는다. 랜섬 규모가 「피해 월평균 M건 (최근 D일)」 꼴이면 굽기가 M × D ÷ 30 으로
   * 돌려 옛 「피해 기업 N」 과 같은 단위로 싣는다 (2026-09-25, `bake.py` `registry_size`).
   * 행위자는 이 칸을 안 쓰고 사건 수를 센다. 없으면 활동도 0 이다
   */
  raw?: number | null;
  /** 포럼만. 게시물 수 · 스레드 수. 회원 수와 따로 지수를 내 평균한다 (3.3) */
  posts?: number | null;
  threads?: number | null;
  /**
   * 이 영토가 지도에 처음 나오는 날. 가장 이른 사건의 게시 시각이다.
   * 그보다 앞선 분기 스냅샷에는 영토가 없다 (작업판 영토분기별 탭).
   * 사건이 없는 명부 영토는 비워 두고, 이번 분기에만 나온다
   */
  since?: string | null;
  /** 행위자 섬만. 행위자 DB 정보 칸 (설계서 4.3.8, 2026-09-26 최현서) */
  actor?: ActorInfo;
};

/**
 * 행위자 DB 정보 칸 — 행위자 패널 [개요] (설계서 4.3.8).
 *
 * 역할 · 국가는 선택지, 처음 본 날은 날짜다. 다루는 것과 다른 이름은 사람이 쓰는
 * 칸이라 굽기가 조직명 대조 · 값 훑기 · 핸들 모양 검사를 통과한 것만 싣는다
 * (`bake.py` `actor_info`). 다른 이름은 검색도 찾는다 (4.2.2)
 */
export type ActorInfo = {
  roles?: string[];
  countries?: string[];
  firstSeen?: string;
  deals?: string;
  otherNames?: string[];
};

/**
 * 검증 판정. 설계서 3.2 의 신뢰 가중치가 이 값을 본다.
 *
 * **`unverified`(검증 전) 가 화면 칩에는 없다.** 설계서 2.5 신뢰도 표에 그 줄이
 * 빠져 있어서, 화면에 무엇으로 보일지는 아직 정해지지 않았다.
 */
export type Verdict =
  | "confirmed" // 확인됨
  | "high" // 신뢰성 높음
  | "unverified" // 검증 전
  | "unknown" // 미확인
  | "low" // 신뢰성 낮음
  | "false"; // 허위

/** 규모 등급 (설계서 3.2, 제안값). 노션에 이 칸이 아직 없다 (5.1-3). */
export type SizeGrade = "large" | "medium" | "small" | "unknown";

/** 사건 — 영토에 올라온 게시 1건. */
export type Ev = {
  id: string;
  territoryId: string;
  /** 게시 시각. ISO 문자열. 기준일 비교에 쓴다 */
  postedAt: string;
  verdict: Verdict;
  size: SizeGrade;
  /** 재게시이거나 같은 글이면 참 (설계서 3.2 중복 가중치) */
  repost: boolean;
  /**
   * 노션 「일부러 반출하지 않음」. 참이면 화면·검색·다운로드에서 통째로 뺀다
   * (설계서 2.4). 점수 집계에서도 빠진다 (3.1 의 `E(T,D)` 정의)
   */
  excluded: boolean;
  /**
   * 행위자 섬 영토 id. 이 사건을 올린 행위자가 행위자 섬 영토이면 채운다.
   * **같은 사건을 행위자 영토에서 한 번 더 센다** (설계서 3.4, 판 1.2 결정).
   * 행위자 영토는 행위자 DB 줄에서 만들고, 사건과는 게시자 핸들로 잇는다
   * (2026-09-25 22시 최현서). 행위자 DB 에 없는 핸들의 사건은 이 칸이 비어 있다
   */
  actorTerritoryId?: string;
  /**
   * 게시 시각이 없어 관측 시각이나 수집일을 대신 넣은 사건.
   * **점수와 칸 수에는 넣고, 최근 30일 · 7일 창과 상태 · 변화율 · 급상승,
   * 행위자 활동도(사건 수)에서는 뺀다** (정본 엑셀 업데이트 탭, 2026-09-23 최현서)
   */
  dateSubstituted?: boolean;
  /**
   * 사건 종류 칩 (설계서 2.3). 수집 DB 「게시 성격」에서 온다. 「사기 의심」처럼
   * 칩이 없는 사건은 비어 있다
   */
  kind?: EvKind;
  /**
   * 제목 재료 (2026-09-25 최현서 결정 — 「국가 · 산업 분야 · 날짜 · 규모」).
   * **사건 제목은 싣지 않는다.** 자료 제목에 피해 조직 이름이 든다.
   * 국가는 두 글자 부호(KR), 산업 분야는 줄인 낱말(유통), 규모는 주장 규모 글에서
   * 뽑은 숫자와 단위다. 모르면 비어 있다
   */
  country?: string;
  industry?: string;
  sizeValue?: number;
  sizeUnit?: string;
  /**
   * 공식 발표 사고(유출 사고 DB)만 (설계서 4.3.4). 사고 시점, 유출 항목, 외부 확인,
   * 출처 종류. 넷 다 날짜나 선택지다. **조직명과 출처 링크는 안 싣는다** (2026-09-26)
   */
  occurredAt?: string;
  leakItems?: string[];
  confirm?: string;
  sourceKind?: string;
};

/**
 * 사건 종류 칩 (설계서 2.3).
 *
 * **판 1.2 에서 「공지」와 「제휴자 모집」이 빠지고 「공식 발표」가 들어왔다.**
 * 앞 둘은 노션 게시 성격에 값이 없고 값을 새로 만들지 않기로 했다. 제휴자
 * 모집은 사건이 아니라 관계선 종류로만 쓴다.
 *
 * 「사기 의심」은 칩 없이 필터에서만 쓴다.
 */
export type EvKind =
  | "data_post" // 데이터 게시
  | "claim" // 피해 주장
  | "sale" // 판매
  | "access_sale" // 접근 구매
  | "repost" // 재게시
  | "official"; // 공식 발표 — 유출 사고 DB 1행

/** 신뢰도 3단계. 관계선 모양이 여기 걸린다 (설계서 2.5). */
export type Confidence = "confirmed" | "high" | "estimated";

/**
 * 관계선 — 다크웹 영토와 영토를 잇는다. 방향이 있다.
 *
 * **노션에 관계선 DB 가 2026-09-22 에 생겼고 굽기가 읽는다** (`tools/bake.py`
 * `bake_relations`). 「근거 사건 ID」 한 칸을 작업판 수식처럼 빈칸을 지우고
 * 쉼표로 끊는다.
 *
 * 건수와 처음·마지막 본 날은 싣지 않는다. 기준일마다 달라서 `score.ts` 의
 * `relationCount` · `relationSpan` 이 `evidence` 로 센다.
 */
export type Relation = {
  id: string;
  from: string; // 영토 id
  to: string; // 영토 id
  kind: RelationKind;
  confidence: Confidence;
  /** 근거 사건 id 들. 기준일에 지도에 든 것만 건수가 된다 (설계서 3.9) */
  evidence: string[];
  /**
   * 근거 사건이 없는 관계선의 명부 「연결된 곳」 원문 (설계서 4.3.6). 두 영토의
   * 그 칸에서 상대 이름이 든 항목만 굽기가 골랐다. 가해 쪽 주소가 들 수 있다
   * (2026-09-25 최현서 결정). 피해 조직 이름이 든 항목은 굽기가 뺐다
   */
  note?: string;
};

export type RelationKind =
  | "affiliate" // 제휴자 모집
  | "contact" // 공지·연락
  | "leak" // 데이터 유출
  | "access" // 접근 공급
  | "sale" // 데이터 판매
  | "successor" // 후속 (이전·압수 후 이어진 곳)
  // 판 1.2 에서 늘었다. 행위자 섬이 생기면서 필요해진 종류다 (설계서 2.3)
  | "activity"; // 활동 (행위자 → 영토)

/**
 * 연결선 — 오픈웹 영토와 다크웹 영토를 잇는다. 3D 화면에 쓴다.
 *
 * **3D 는 2026-09-22 에 보류했다.** 협업 건이라 뒤로 미뤘다. 타입만 남겨 둔다.
 * 노션 「연결 관계 DB」 확장이 필요하다 (설계서 5.1-5).
 */
export type Link = {
  id: string;
  openTerritoryId: string;
  darkTerritoryId: string;
  kind: LinkKind;
  confidence: Confidence;
  evidence: string[];
};

export type LinkKind =
  | "repost" // 재게시
  | "link_share" // 링크 공유
  | "file_copy" // 파일 복제
  | "source_claim" // 출처 주장
  | "same_content" // 동일 내용
  | "other";

/** 지도 한 장이 쓰는 재료 전부. 굽기가 이 모양으로 낸다. */
export type MapData = {
  /** 언제 구웠나. 화면에 「데이터 기준 시각」으로 뜬다 (설계서 4.2.1) */
  generatedAt: string;
  islands: Island[];
  territories: Territory[];
  events: Ev[];
  relations: Relation[];
  links: Link[];
};
