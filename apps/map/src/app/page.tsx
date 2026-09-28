/**
 * 다크웹 2D 지도 화면.
 *
 * 재료는 `mapData.ts` 가 준다 — `tools/bake.py` 가 노션에서 구워 둔
 * `src/data/map.json` 이고, 그것이 없으면 예시 데이터로 물러선다.
 * 무엇을 보고 있는지는 머리띠 옆에 적는다.
 */

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import AppHeader from "@/components/AppHeader";
import DetailPanel, { type PanelTabKey } from "@/components/DetailPanel";
import EntityTab, { SORT_LABEL, type SortKey } from "@/components/EntityTab";
import EventReport from "@/components/EventReport";
import EventsTab from "@/components/EventsTab";
import Legend from "@/components/Legend";
import LinksTab, { type LinkSel } from "@/components/LinksTab";
import MapCanvas, { MAP_VIEW_HOME, type MapSelection, type MapView } from "@/components/MapCanvas";
import RelationPanel from "@/components/RelationPanel";
import RelationTab, { type RelPair } from "@/components/RelationTab";
import SearchOverlay from "@/components/SearchOverlay";
import SearchResults from "@/components/SearchResults";
import { recentOf, type SearchCtx } from "@/components/SearchRows";
import SnapshotBar from "@/components/SnapshotBar";
import TimelineTab from "@/components/TimelineTab";
import ViewTabs, { type ViewTabKey } from "@/components/ViewTabs";
import { DARK_ISLANDS, islandToken } from "@/lib/islands";
import { layoutMap } from "@/lib/layout";
import { MAP, isBaked } from "@/lib/mapData";
import { latestSeen, seenDays } from "@/lib/entity";
import { DEFAULT_PERIOD, eventTitle, eventsIn, touchesEvent, type Period } from "@/lib/events";
import { pastSnapshot } from "@/lib/mapui";
import { allIslandPairs, belongsTo, ecosystemView, islandView, territoryView } from "@/lib/panel";
import { eventReport, linkedOf, type ReportNames } from "@/lib/report";
import type { Ev, Relation } from "@/lib/types";
import {
  backLabel,
  defaultCenter,
  expandHops,
  islandPairs,
  josa,
  linkRows,
  linksOf,
  pairViews,
  partnerOf,
  relationsAt,
  touching,
  withActivity,
  withEstimated,
  type IslandPairRow,
  type RelView,
} from "@/lib/relations";
import { computeMap } from "@/lib/score";
import {
  EMPTY,
  NO_FILTER,
  buildIndex,
  pushRecent,
  quarterFor,
  search,
  total,
  type EventHit,
  type Hit,
  type Recent,
  type SearchFilter,
} from "@/lib/search";
import { quarterEnd, quarterOfDate, quarterText, spanOf, type QuarterKey } from "@/lib/quarter";
import { boxSize, centerBox, quartersOf, snapshots, type Compare } from "@/lib/timeline";

/**
 * 「오늘」. **구운 시각이다.** 구운 파일이 없을 때만 보는 사람의 시계를 쓴다.
 *
 * 설계서 3.1 이 「이번 분기는 오늘」이라고 해서 필요한 값이다. 정본은 이번
 * 분기 기준일을 「계산한 날」로 잡는다. 보는 사람의 시계를 쓰면 다시 굽지
 * 않아도 날짜가 넘어가면서 최근 30일 창과 분기가 혼자 바뀐다 — 10월 1일이
 * 되자 사건 없는 명부 영토가 모두 사라지는 것이 검토에서 나왔다.
 *
 * 계산 쪽(`score.ts`)은 `Date.now()` 를 안 쓰기로 했으므로 화면이 넘겨 준다.
 * 모듈이 읽힐 때 한 번만 잡는다.
 */
const TODAY = isBaked && MAP.generatedAt ? new Date(MAP.generatedAt) : new Date();

/**
 * 스냅샷 바 눈금 범위. **데이터에서 잡되 오늘이 든 분기까지는 늘 둔다.**
 *
 * 고정해 두면 구운 데이터의 기간이 바뀔 때마다 앞뒤가 비거나 잘린다.
 * 마지막 사건의 분기에서 끊으면 새 분기에 사건이 아직 없을 때 이번 분기를
 * 고를 수 없고, 사건 없는 명부 영토가 이번 분기에만 나오므로 지도에서 빠진다.
 * 단위는 분기다 (설계서 4.2.5, 판 1.2). 분기 열쇠는 글자 차례가 곧 시간 차례다.
 */
const [FROM, LAST] = spanOf(MAP.events);
const TO: QuarterKey = LAST > quarterOfDate(TODAY) ? LAST : quarterOfDate(TODAY);

/** 관계 전부. 활동 관계(행위자 → 영토)는 사건에서 만든다 (설계서 3.9 · 4.3.8) */
const ALL_RELS = withActivity(MAP.relations, MAP.events);

/**
 * 영토 id → 명부 칸. 패널 [개요]가 활동도 원자료(4.3.2)와 행위자 정보(4.3.8)를
 * 여기서 읽는다 — 배치 결과(`layout`)에는 계산 값만 있다
 */
const REGISTRY = new Map(MAP.territories.map((t) => [t.id, t]));
const registryOf = (id: string) => REGISTRY.get(id);

/** 사건 id → 사건. 보고서 팝업이 쌓아 둔 번호로 사건을 찾는다 */
const EV_BY_ID = new Map(MAP.events.map((e) => [e.id, e]));

/**
 * 보고서 팝업의 이름. **기준일과 무관하게 명부에서 찾는다** — 검색 「상세」는 기준일
 * 밖 사건도 열어서, 기준일 지도(`layout`)에 없는 영토 이름도 나와야 한다
 */
const ISLAND_NAME = new Map(DARK_ISLANDS.map((i) => [i.id as string, i.name]));
const REPORT_NAMES: ReportNames = {
  nameOf: (id) => REGISTRY.get(id)?.name ?? id,
  islandOf: (id) => ISLAND_NAME.get(REGISTRY.get(id)?.islandId ?? "") ?? "",
};

/**
 * [연결] 탭에서 관계 탭으로 넘어갈 때 적어 두는 출발 화면 (설계서 4.3.3
 * 「출발 화면 상태 (선택, 탭, 행 선택, 줌, 기준일) 그대로 복원」).
 */
type Origin = {
  /**
   * 이 이동이 쌓은 뒤로 가기 기록의 표. 남은 옛 기록과 가르는 데 쓴다. 새로
   * 고친 뒤에도 겹치지 않게 연 시각을 붙인다 — 카운터만 쓰면 새로 고친 뒤 다시
   * 1 부터 세어 옛 기록과 같아진다
   */
  seq: string;
  tab: ViewTabKey;
  /** 되살릴 선택. 기준일 밖이라 안 보이던 선택도 그대로 둔다 (기준일과 같이 되살아난다) */
  selection: MapSelection;
  /**
   * 떠날 때 화면에 보이던 선택(`liveSelection`). 돌아가기 단추 글이 이것을 읽는다 — 원래 선택을
   * 읽으면 기준일 밖에 숨은 영토 이름이 단추에 찍혔다 (2026-09-28 검토)
   */
  shown: MapSelection;
  panelTab: PanelTabKey;
  linkSel: LinkSel;
  mapView: MapView;
  ym: QuarterKey;
  /** 패널이 펼쳐져 있었나. 관계 탭에 들어갈 때 펼치므로(`enterFromLinks`) 돌아갈 때 되살린다 */
  panelOpen: boolean;
  /**
   * 타임라인 시점 비교. 관계 탭에 갔다 돌아가면 되살린다 — 전에는 타임라인을 떠나며 꺼 둔 채
   * 돌아와 비교가 풀려 있었다 (2026-09-28 코드 분석)
   */
  compare: Compare | null;
};

/** 뒤로 가기 기록에 우리가 넣은 칸이라는 표시 */
const HISTORY_KEY = "dcRel";

/** 엔티티 표 처음 정렬 — 활동도 높은 순 (설계서 4.3.5). 로고를 누르면 여기로 돌아간다 */
const ENTITY_SORT_HOME: { key: SortKey; asc: boolean } = { key: "activity", asc: false };

/** 이 창을 연 시각. 뒤로 가기 기록 표가 새로 고침 전 것과 겹치지 않게 한다 */
const OPENED_AT = Date.now().toString(36);

function presentIn(d: Date): Set<string> {
  const r = computeMap({ ...MAP, today: TODAY }, d);
  return new Set(r.territories.filter((t) => t.web === "dark" && t.cells > 0).map((t) => t.territoryId));
}

export default function Page() {
  const [ym, setYm] = useState<QuarterKey>(TO);
  const [selection, setSelection] = useState<MapSelection>({ kind: "none" });
  /**
   * 상세 패널 펼침. **화면 전체에 하나다** (2026-09-28 최현서 2번 — 설계서 4.2.4 와 다르다,
   * README 「설계서와 다른 곳」). 사람이 핸들로 바꾼 값이 기준이고 탭을 옮겨도 그대로다.
   * 섬 · 영토 · 관계를 고르면 펼치되 선택을 풀어도 접지 않는다. 첫 화면은 펼침이다
   */
  const [panelOpen, setPanelOpen] = useState(true);
  // 엔티티 탭 섬 필터. 표만 거른다 — 전역 선택과 패널을 안 건드린다 (null 이면 선택한 섬 · 영토의 섬)
  const [entityIsland, setEntityIsland] = useState<string | null>(null);
  // 엔티티 표 정렬. 탭을 다녀와도 남는다 (2026-09-28 코드 분석)
  const [entitySort, setEntitySort] = useState(ENTITY_SORT_HOME);
  const [panelTab, setPanelTab] = useState<PanelTabKey>("overview");
  const [linkSel, setLinkSel] = useState<LinkSel>(null);
  // 패널 [사건] 탭 기간. 다른 영토를 골라도 그대로 둔다 (설계서 4.3.2)
  const [period, setPeriod] = useState<Period>(DEFAULT_PERIOD);
  const [mapView, setMapView] = useState<MapView>(MAP_VIEW_HOME);
  // 타임라인 지도(Historical Map · 시점 비교 A/B) 줌 · 이동. 지도 탭과 따로 든다 (G-10 묶음 5)
  const [tlView, setTlView] = useState<MapView>(MAP_VIEW_HOME);
  // 화면 밖이면 보이게 옮길 영토. 고를 때 채우고 지도가 보고 나면 비운다 (설계서 4.2.3)
  const [reveal, setReveal] = useState<string | null>(null);
  const [tab, setTab] = useState<ViewTabKey>("map");
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  // 타임라인 시점 비교 (⑦-9c). 제목 옆 설명이 이것을 읽어 여기서 들고 있다
  const [compare, setCompare] = useState<Compare | null>(null);
  // 검색 창. null 이면 닫힘, 글이면 그 검색어를 채워 연다 (설계서 4.2.2)
  const [searchQ, setSearchQ] = useState<string | null>(null);
  // 최근 검색과 필터. 검색 부품은 닫으면 사라지므로 여기서 들고 있는다
  const [recent, setRecent] = useState<Recent[]>([]);
  const [filter, setFilter] = useState<SearchFilter>(NO_FILTER);
  // 전체 결과 화면(⑦-10d)의 검색어. 있으면 가운데 화면이 결과 목록으로 바뀐다
  const [results, setResults] = useState<string | null>(null);
  // 「검색 결과 'X'로 이동했어요 · 검색으로 돌아가기」 (⑦-10b)
  const [toast, setToast] = useState<{ label: string; q: string; moved: QuarterKey | null } | null>(null);
  // 검색에서 고른 행위자 · 사건. 패널 [사건]이 그 행위자로 거르고 그 사건을 강조한다 (4.2.2)
  const [actorFilter, setActorFilter] = useState<string | null>(null);
  const [focusEvent, setFocusEvent] = useState<string | null>(null);
  // 패널 [사건]에서 한 번 누른 사건. 지도가 그 사건의 관계선만 그린다 (피그마 ⑦-4)
  const [pickedEvent, setPickedEvent] = useState<string | null>(null);
  // 패널 [사건] 「사기 의심 숨기기」 (설계서 2.3 L98 — 칩 없이 필터에서만)
  const [hideScam, setHideScam] = useState(false);
  // 보고서 팝업 (설계서 4.3.4). 연 사건 번호를 쌓는다 — 맨 뒤가 지금 사건, 앞은 「‹ 이전 사건」 자리
  const [report, setReport] = useState<string[]>([]);
  // 관계 탭 (설계서 4.3.6)
  const [relCenter, setRelCenter] = useState<string | null>(null);
  // 고른 관계선(근거 화면 ⑦-8e)과 강조한 관계선(4.3.3 ① 이동 직후)은 따로 든다
  const [relSel, setRelSel] = useState<string | null>(null);
  const [relHi, setRelHi] = useState<string | null>(null);
  const [relPair, setRelPair] = useState<RelPair | null>(null);
  // 피그마 ⑦-8g 「추정 관계 포함」 · 「2단계로 확장」. 관계 탭에 들어올 때마다 기본값이다
  const [relEst, setRelEst] = useState(true);
  const [relDepth, setRelDepth] = useState<1 | 2>(1);
  const [origin, setOrigin] = useState<Origin | null>(null);

  const d = useMemo(() => quarterEnd(ym, TODAY), [ym]);
  // 지나간 분기면 「2025 Q3」. 제목 옆 · 패널 머리글 · 지도 힌트가 적는다 (피그마 ⑦-1a · ⑦-1b)
  const past = pastSnapshot(ym, TO);
  // 오늘을 넘겨야 사건이 없는 명부 영토가 이번 분기에만 나온다 (score.ts presentAt)
  const result = useMemo(() => computeMap({ ...MAP, today: TODAY }, d), [d]);
  const layout = useMemo(
    () =>
      layoutMap(
        { islands: MAP.islands, territories: MAP.territories, web: "dark" },
        result,
      ),
    [result],
  );

  /** 기준일에 그릴 관계. 세 화면이 이 목록 하나를 쓴다 (설계서 3.9) */
  const present = useMemo(() => new Set(layout.territories.map((t) => t.territoryId)), [layout]);
  const rels = useMemo(() => relationsAt(ALL_RELS, MAP.events, d, present), [d, present]);

  /**
   * 기준일 지도에 있는 선택. **기준일을 옮겨 고른 영토 · 섬이 그 분기 지도에서 빠졌으면 없던
   * 것으로 본다** — 남겨 두면 지도가 없는 영토만 진하게 두느라 전체가 흐려지고, 힌트는 「X
   * 선택됨」인데 X 가 안 보인다. 사건 없는 명부 영토는 이번 분기에만 나와서 그런 영토를 고르고
   * 과거로 가면 늘 생겼다 (2026-09-28 코드 분석). 상태(`selection`)는 그대로 둔다 — 기준일을
   * 되돌리면 다시 산다. [연결] 행의 `liveLinkSel` 과 같은 규칙이다.
   * 지도 · 힌트 · 패널 · [사건] · [연결] · 엔티티 탭은 이것을 본다
   */
  const liveSelection: MapSelection = useMemo(() => {
    if (selection.kind === "territory") return present.has(selection.id) ? selection : { kind: "none" };
    if (selection.kind === "island") {
      return layout.islands.some((i) => i.islandKey === selection.key) ? selection : { kind: "none" };
    }
    return selection;
  }, [selection, present, layout]);
  /** 관계 탭이 그리는 관계. 「추정 관계 포함」을 끄면 추정을 뺀다 (피그마 ⑦-8g) */
  const relShown = useMemo(() => withEstimated(rels, relEst), [rels, relEst]);
  const terr = useMemo(() => new Map(layout.territories.map((t) => [t.territoryId, t])), [layout]);
  const terrName = useCallback((id: string) => terr.get(id)?.name ?? id, [terr]);
  const islandOf = useCallback((id: string) => terr.get(id)?.islandKey, [terr]);
  const islandInfo = useCallback(
    (key: string) => {
      const i = layout.islands.find((x) => x.islandKey === key);
      return { name: i?.name ?? key, token: i?.token ?? "actor" };
    },
    [layout],
  );

  /**
   * 영토별 최근 관측일. 툴팁 다섯째 줄(설계서 4.2.3)과 영토 패널에 쓴다.
   *
   * 기준일 뒤에 올라온 사건 · 허위는 뺀다 (`latestSeen`). 시각은 엔티티 탭이
   * 정렬에 쓰고, 화면에는 `MM-DD` 만 적는다 (설계서 4.3.5)
   */
  const seenAt = useMemo(() => latestSeen(MAP.events, d), [d]);
  // 화면 글자는 노션 날짜 글자다 — 사건 줄과 같게 (`seenDays`). 정렬은 위 `seenAt`(밀리초)으로 한다
  const lastSeen = useMemo(() => seenDays(MAP.events, d), [d]);

  const view = useMemo(() => {
    const input = { layout, result, events: MAP.events, d, rels, lastSeen, registry: registryOf, snapshot: past };
    if (liveSelection.kind === "island") {
      return islandView(input, liveSelection.key) ?? ecosystemView(input);
    }
    if (liveSelection.kind === "territory") {
      return territoryView(input, liveSelection.id) ?? ecosystemView(input);
    }
    return ecosystemView(input);
  }, [layout, result, d, rels, lastSeen, liveSelection, past]);

  /**
   * 지도 위 관계선 (설계서 4.2.3 · 4.3.3).
   *
   *   영토를 고름         그 영토의 관계선만. 이어진 영토만 진하고 연결 없는 섬은 흐리다
   *   [연결] 행을 고름     그 관계선만. 상대 영토도 떠오른다
   *   유형 간 행을 고름    그 섬 쌍의 관계선만
   *   [사건] 행을 고름     그 사건이 근거인 관계선만 (피그마 ⑦-4, 설계서 4.3.3 L607 「한 번은 미리보기」)
   */
  const isActor = useCallback(
    (id: string) =>
      layout.islands.find((i) => i.islandKey === terr.get(id)?.islandKey)?.islandId === "ACTOR",
    [layout, terr],
  );

  /**
   * [연결] 행 선택. **기준일을 옮겨 그 행이 없어졌으면 없던 것으로 본다** — 남겨
   * 두면 빈 섬 쌍을 그리느라 지도 전체가 흐려지는데, 목록에는 고른 행이 없어
   * 사람이 풀 길이 없다. 상태는 그대로 둔다 (기준일을 되돌리면 다시 산다)
   */
  const liveLinkSel: LinkSel = useMemo(() => {
    if (!linkSel) return null;
    if (linkSel.type === "pair") {
      return pairViews(rels, islandOf, linkSel.from, linkSel.to).length ? linkSel : null;
    }
    return rels.some((v) => v.rel.id === linkSel.id) ? linkSel : null;
  }, [linkSel, rels, islandOf]);

  /**
   * 패널 [사건] 탭 (설계서 4.3.1 · 4.3.2 · 4.3.8). 영토는 그 영토, 행위자는 그
   * 행위자가 올린 사건, 섬은 소속 영토 전부다 — `belongsTo` 가 셋을 같이 가른다.
   * 선택이 없으면 지도에 있는 영토 전부다 (피그마 ⑦-1 탭 「사건 N」). 행마다 영토
   * 이름이 붙는 것은 섬과 같다.
   *
   * 「사기 의심 숨기기」를 켜면 여기서 뺀다 — 탭 배지와 헤더 건수가 목록과 같아야 한다.
   * 지도 선(아래 `mapRel`)이 고른 사건을 이 목록에서 찾으므로 위에 둔다
   */
  const eventIds: Set<string> = useMemo(
    () =>
      liveSelection.kind === "territory"
        ? new Set([liveSelection.id])
        : liveSelection.kind === "island"
          ? new Set(layout.territories.filter((t) => t.islandKey === liveSelection.key).map((t) => t.territoryId))
          : present,
    [liveSelection, layout, present],
  );
  const periodList = useMemo(
    () =>
      eventsIn(
        MAP.events,
        d,
        period,
        (e) => belongsTo(e, eventIds) && (!actorFilter || e.actorTerritoryId === actorFilter),
      ),
    [d, period, eventIds, actorFilter],
  );
  const scamCount = periodList.filter((e) => e.scam).length;
  const eventList = useMemo(
    () => (hideScam ? periodList.filter((e) => !e.scam) : periodList),
    [periodList, hideScam],
  );

  /**
   * [사건] 행 선택 (피그마 ⑦-4). **[사건] 탭을 보고 있고 그 사건이 목록에 있을 때만
   * 산다** — 기간 · 기준일을 옮겨 목록에서 빠졌거나 다른 패널 탭으로 가면 지도는 원래
   * 선으로 돌아온다. 상태는 그대로 둔다 (`liveLinkSel` 과 같은 규칙)
   */
  const liveEvent = useMemo(
    () => (panelTab === "events" && pickedEvent ? (eventList.find((e) => e.id === pickedEvent) ?? null) : null),
    [panelTab, pickedEvent, eventList],
  );

  const mapRel = useMemo(() => {
    // [사건] 행을 고름 — 그 사건이 근거인 관계선만 (행위자 사건이면 행위자 → 영토 활동 관계 포함).
    // 관계선이 없으면 올라온 영토(와 행위자)만 진하다
    if (liveEvent) {
      const ev = liveEvent;
      const lines = rels.filter((v) => touchesEvent(v.rel, ev));
      const ends = [ev.territoryId, ev.actorTerritoryId ?? "", ...lines.flatMap((v) => [v.rel.from, v.rel.to])];
      const lit = new Set(ends.filter((x) => present.has(x)));
      const litIslands = new Set([...lit].map((x) => islandOf(x)).filter((x): x is string => !!x));
      return { lines, lit, raised: lit, litIslands };
    }
    if (liveLinkSel?.type === "pair") {
      const lines = pairViews(rels, islandOf, liveLinkSel.from, liveLinkSel.to);
      const lit = new Set(lines.flatMap((v) => [v.rel.from, v.rel.to]));
      return { lines, lit, raised: lit, litIslands: new Set([liveLinkSel.from, liveLinkSel.to]) };
    }
    if (liveSelection.kind !== "territory") return null;
    const id = liveSelection.id;
    // 행위자는 활동 관계만 그린다 — [연결] 목록과 같게 (설계서 4.3.8)
    let lines = linksOf(rels, id, isActor(id));
    let raised: Set<string> | undefined;
    if (liveLinkSel?.type === "rel") {
      const v = lines.find((x) => x.rel.id === liveLinkSel.id);
      if (v) {
        lines = [v];
        raised = new Set([partnerOf(v, id)]);
      }
    }
    const lit = new Set([id, ...lines.map((v) => partnerOf(v, id))]);
    const litIslands = new Set([...lit].map((x) => islandOf(x)).filter((x): x is string => !!x));
    return { lines, lit, raised, litIslands };
  }, [rels, liveSelection, liveLinkSel, islandOf, isActor, liveEvent, present]);

  /**
   * 관계 탭 중심. 고른 영토가 없거나, 기준일을 옮겨 그 영토가 지도에서 빠졌으면
   * **관계가 가장 많은 영토**다 (설계서 4.3.6). 「기준일 옮기기」 뒤에도 이것으로
   * 중심이 선다 — 전에는 비어 있는 채로 남아 그래프가 안 그려졌다.
   *
   * 기본 중심은 추정을 뺀 목록이 아니라 **관계 전부**로 고른다. 「추정 관계 포함」을
   * 끄고 켤 때 중심이 옮겨 다니면 무엇이 가려졌는지 알 수 없다 (관계 없음 ⑦-8g 가
   * 「추정 관계를 포함하면 연결 후보를 확인할 수 있습니다」로 알린다)
   */
  const center = useMemo(
    () =>
      relPair
        ? null
        : relCenter && present.has(relCenter)
          ? relCenter
          : defaultCenter(rels, terrName),
    [relPair, relCenter, present, rels, terrName],
  );
  /**
   * 섬 · 영토 고르기. 고르면 패널을 펼친다 (설계서 4.2.4 「자동 펼침」). **선택을 풀어도
   * 접지는 않는다** — 펼침은 사람이 핸들로 정한 값이다 (2026-09-28 최현서 2번).
   *
   * `open` 이 거짓이면 펼치지 않는다. 사람이 고른 것이 아니라 탭을 옮기며 저절로 고르는
   * 자리(관계 탭 → 지도 탭의 중심 영토)가 쓴다 — 탭을 옮겨도 펼침은 그대로다
   */
  const select = (s: MapSelection, open = true) => {
    setSelection(s);
    // 엔티티 탭 섬 필터는 고른 것의 섬을 따라간다
    setEntityIsland(null);
    // 다른 영토를 골라도 열려 있던 패널 탭은 그대로 둔다 (4.2.3). 행 선택만 푼다.
    // **아무것도 안 고른 데서 처음 고르면 [개요]로 연다** (4.2.3 「영토 클릭 → 패널
    // [개요] 열림」). 전에는 선택을 풀기 전 탭이 남아 새로 고른 영토가 [사건]으로 열렸다
    if (liveSelection.kind === "none" && s.kind !== "none") setPanelTab("overview");
    // 화면 밖이면 지도가 옮긴다 (4.2.3 「화면 밖이면 보이는 위치로 이동」)
    setReveal(s.kind === "territory" ? s.id : null);
    setLinkSel(null);
    // 검색에서 건 행위자 필터와 사건 강조도 푼다. 검색 결과를 고를 때는 이 뒤에 다시 건다
    setActorFilter(null);
    setFocusEvent(null);
    // [사건] 행 선택도 푼다 — 다른 영토의 목록에는 그 사건이 없다
    setPickedEvent(null);
    // 「검색 결과로 이동했어요」 안내도 걷는다. 검색 결과를 고를 때는 이 뒤에 다시 띄운다
    setToast(null);
    if (open && s.kind !== "none") setPanelOpen(true);
  };

  /* ── 관계 탭 오가기 (설계서 4.3.3 · 4.3.6) ───────────── */

  const originRef = useRef<Origin | null>(null);
  useEffect(() => {
    originRef.current = origin;
  }, [origin]);
  /** 뒤로 가기 기록 번호. 관계 탭에 들어갈 때마다 하나씩 늘린다 */
  const seqRef = useRef(0);
  /** `history.back()` 을 불렀고 아직 popstate 가 안 왔다. 두 번 눌러 앱 밖으로 나가지 않게 한다 */
  const popping = useRef(false);
  const ourEntry = (o: Origin | null) =>
    !!o && !!window.history.state && window.history.state[HISTORY_KEY] === o.seq;

  const clearRel = () => {
    setRelSel(null);
    setRelHi(null);
    setRelPair(null);
    setRelEst(true);
    setRelDepth(1);
    setOrigin(null);
  };

  const restore = useCallback((o: Origin) => {
    setTab(o.tab);
    setSelection(o.selection);
    setPanelTab(o.panelTab);
    setLinkSel(o.linkSel);
    setMapView(o.mapView);
    setYm(o.ym);
    setPanelOpen(o.panelOpen);
    setCompare(o.tab === "timeline" ? o.compare : null);
    setToast(null);
    setRelSel(null);
    setRelHi(null);
    setRelPair(null);
    setOrigin(null);
    setPlaying(false);
  }, []);

  /**
   * 브라우저 뒤로 가기도 출발 화면을 되살린다 (설계서 4.3.3). 관계 탭에 들어갈
   * 때 기록을 한 칸만 쌓고, 관계 탭 안에서 중심을 바꾸는 것은 안 쌓는다.
   *
   * **기록에 번호를 단다.** 표시만 보면 앞서 남은 기록(탭을 눌러 관계 탭을 떠났거나
   * 새로 고친 뒤)과 이번 기록이 구별되지 않아, 돌아가기가 한 번에 안 된다.
   * 이번 이동의 기록을 떠났으면(번호가 다르면) 되살린다.
   */
  useEffect(() => {
    const onPop = () => {
      popping.current = false;
      const o = originRef.current;
      if (o && !(window.history.state && window.history.state[HISTORY_KEY] === o.seq)) restore(o);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [restore]);

  /**
   * 관계 탭으로 넘어간다. 넘겨 온 관계는 **강조만** 한다 (4.3.3 ① 표 — 선과 라벨
   * 테두리, 연혁 강조와 스크롤). 근거 화면은 그 선이나 「근거 보기」를 눌러야 뜬다
   */
  const enterFromLinks = (next: { center: string | null; hi: string | null; pair: RelPair | null }) => {
    seqRef.current += 1;
    const seq = `${OPENED_AT}-${seqRef.current}`;
    setOrigin({ seq, tab, selection, shown: liveSelection, panelTab, linkSel, mapView, ym, panelOpen, compare });
    // goTab 을 안 거치고 관계 탭으로 가므로 탭별 정리를 여기서 한다. 관계를 골라서 들어온
    // 것이라 패널을 펼치고(연혁 강조가 보여야 한다 — 고르면 펼친다는 규칙과 같다), 타임라인을
    // 떠나면 시점 비교를 푼다
    setPanelOpen(true);
    if (tab === "timeline") setCompare(null);
    setRelCenter(next.center);
    setRelSel(null);
    setRelHi(next.hi);
    setRelPair(next.pair);
    setRelEst(true);
    setRelDepth(1);
    setTab("relation");
    setPlaying(false);
    try {
      window.history.pushState({ ...(window.history.state ?? {}), [HISTORY_KEY]: seq }, "");
    } catch {
      // 기록을 못 쌓아도 돌아가기 단추는 된다
    }
  };

  /** [연결] 행 더블클릭 — 중심은 상대 영토, 그 관계를 강조한다 (4.3.3 ①) */
  const openRel = (v: RelView) => {
    if (liveSelection.kind !== "territory") return;
    enterFromLinks({ center: partnerOf(v, liveSelection.id), hi: v.rel.id, pair: null });
  };

  /** 유형 간 행 더블클릭 — 섬 간 보기 (4.3.3 ②) */
  const openPair = (r: IslandPairRow) => {
    enterFromLinks({ center: null, hi: null, pair: { from: r.from, to: r.to } });
  };

  /** 섬 간 보기에서 고르면 보통 관계 탭(①)이다. 중심은 도착 영토, 그 관계를 강조한다 (4.3.3 ②) */
  const pickFromPair = (v: RelView) => {
    setPanelOpen(true);
    setRelPair(null);
    setRelCenter(v.rel.to);
    setRelSel(null);
    setRelHi(v.rel.id);
  };

  /** 관계 탭 안에서 관계선을 고르거나 푼다. 고르면 들어올 때 건 강조는 다 쓴 것이다 */
  const pickRel = (id: string | null) => {
    setRelSel(id);
    setRelHi(null);
    // 관계를 고르면 펼친다 — 근거 화면(⑦-8e)이 패널에 뜬다. 풀 때는 안 접는다 (최현서 2번 규칙)
    if (id) setPanelOpen(true);
  };

  const back = () => {
    if (popping.current || !origin) return;
    if (ourEntry(origin)) {
      popping.current = true;
      window.history.back();
    } else {
      restore(origin);
    }
  };

  /** 관계 탭을 탭으로 떠날 때 우리가 쌓은 기록을 걷는다. 남기면 다음 돌아가기가 한 번 헛돈다 */
  const dropOurEntry = () => {
    if (!ourEntry(origin)) return;
    originRef.current = null;
    popping.current = true;
    window.history.back();
  };

  /**
   * 탭을 옮기면 재생을 멈춘다.
   *
   * 스냅샷 바는 한 달씩, 타임라인은 한 해씩 넘긴다. 켠 채로 탭을 옮기면
   * 간격이 바뀌어 사람이 무엇을 보고 있는지 놓친다.
   *
   * 관계 탭에 들어가면 지도에서 고른 영토가 중심이다. 없으면 관계가 가장 많은
   * 영토다 (4.3.6). 관계 탭에서 지도로 가면 중심 영토를 고른 지도다 (4.3.3 예외 표).
   *
   * **상세 패널 펼침은 건드리지 않는다.** 전에는 엔티티 · 타임라인 탭에서 접고 지도 · 관계
   * 탭에서 펼쳐서(피그마 ⑦-7 · ⑦-9b · ⑦-1 · ⑦-8) 탭마다 화면 탭 단추 자리가 옮겨 다녔다.
   * 이제 한 탭에서 펼쳤으면 다른 탭에서도 펼쳐져 있다 (2026-09-28 최현서 2번)
   */
  const goTab = (k: ViewTabKey) => {
    if (k === tab) return;
    if (k === "relation") {
      const picked = selection.kind === "territory" && present.has(selection.id) ? selection.id : null;
      setRelCenter(picked);
      clearRel();
    } else if (tab === "relation") {
      if (k === "map" && center && terr.has(center)) {
        select({ kind: "territory", id: center, name: terrName(center) }, false);
      }
      dropOurEntry();
      clearRel();
    }
    // 타임라인을 떠나면 시점 비교를 끈다. 비교 중 기준 시점은 늘 B 라 따로 옮길 것이
    // 없다 (4.3.7 「끄면 B 시점」). 검색 결과로 옮긴 기준일도 그대로 산다
    if (tab === "timeline") setCompare(null);
    setTab(k);
    setPlaying(false);
  };

  /**
   * 로고 — 첫 화면으로 (설계서 4.2.1 「클릭 시 첫 화면」).
   *
   * 정본의 첫 화면은 연결 3D(③-0)인데 3D 가 보류라 다크웹을 처음 연 상태로 돌린다.
   * 선택 · 화면 탭 · 줌 100% · 기준일(가장 최근 분기) · 패널 [개요]를 연 직후 값으로
   * 되돌리고 검색 · 전체 결과 · 이동 안내 · 재생 · 보고서 팝업을 닫는다. [사건] 행 선택과
   * 「사기 의심 숨기기」도 기간과 함께 처음 값으로 둔다. 관계 탭에서 쌓은 뒤로 가기
   * 기록도 걷는다. 최근 검색 · 검색 필터 · 재생 속도는 사람이 고른 설정이라 둔다
   */
  const goHome = () => {
    dropOurEntry();
    clearRel();
    setRelCenter(null);
    setTab("map");
    setSelection({ kind: "none" });
    setLinkSel(null);
    setActorFilter(null);
    setFocusEvent(null);
    setPickedEvent(null);
    setReport([]);
    setPanelOpen(true);
    setEntityIsland(null);
    // 정렬도 처음으로 — 섬 필터만 돌아가고 정렬은 남았다 (2026-09-29 묶음 7 검토)
    setEntitySort(ENTITY_SORT_HOME);
    setPanelTab("overview");
    setPeriod(DEFAULT_PERIOD);
    setHideScam(false);
    setMapView(MAP_VIEW_HOME);
    setTlView(MAP_VIEW_HOME);
    setYm(TO);
    setPlaying(false);
    setCompare(null);
    setSearchQ(null);
    setResults(null);
    setToast(null);
  };

  /**
   * 관계가 없을 때 관계가 생기는 분기 (4.3.3 예외 「기준일 옮기기」). 그 분기의
   * 지도를 새로 계산해 중심 영토의 관계가 실제로 그려지는지 본다.
   */
  const relViews = relPair
    ? pairViews(relShown, islandOf, relPair.from, relPair.to)
    : center
      ? touching(relShown, center)
      : [];
  const relEmpty = tab === "relation" && !relPair && relViews.length === 0;
  /** 1단계 · 2단계 노드와 선 (피그마 ⑦-8g 「2단계로 확장」). 섬 간 보기면 없다 */
  const relHops = !relPair && center ? expandHops(relShown, center, relDepth, terrName) : null;
  /**
   * 관계 탭 그래프에 그린 관계. **고른 관계선은 이 안에서만 산다** — 2단계에서 고른
   * 바깥 선은 1단계로 좁히면 판에서 사라지므로 패널 근거 화면도 같이 걷힌다
   */
  const relDrawn = relHops ? relHops.views : relViews;
  /** 「추정 관계 포함」을 꺼서 가린 중심의 관계 수. 관계 없음 안내가 갈린다 (⑦-8g) */
  const relHiddenEst =
    !relEst && center && !relPair ? touching(rels, center).filter((v) => v.rel.confidence === "estimated").length : 0;

  /**
   * 타임라인 시점. 설계서 4.3.7 이 「연도 칩 클릭 시 그 해 9월로 이동」이라
   * 해마다 9월 말을 찍는다.
   *
   * **기준 시점이 스냅샷 바와 같은 값이다** (설계서 4.3.7). 여기서 연도를
   * 옮기면 지도 탭의 기준일도 같이 움직인다.
   */
  const quarters = useMemo(() => quartersOf(MAP.events, TODAY), []);

  const moveTo = useMemo(() => {
    if (!relEmpty) return null;
    for (const q of quarters) {
      if (q === ym) continue;
      const qd = quarterEnd(q, TODAY);
      // 추정을 가렸으면 그 분기에서도 가린 채로 본다 — 옮겨 간 뒤 또 비면 안 된다
      const here = withEstimated(relationsAt(ALL_RELS, MAP.events, qd, presentIn(qd)), relEst);
      if (center ? touching(here, center).length > 0 : here.length > 0) return q;
    }
    return null;
  }, [relEmpty, center, ym, quarters, relEst]);

  /**
   * 단축키 둘.
   *
   *   Esc      선택 해제 (설계서 4.2.3). 관계 탭에서는 고른 관계선을 푼다
   *   Ctrl+K   검색 열기 (설계서 4.2.2, 맥은 ⌘K)
   *
   * 검색이 열려 있으면 Esc 는 검색이 받는다 — 거기서 `stopPropagation` 을
   * 안 걸고 여기서 가른다. 검색을 닫는 것과 선택을 푸는 것이 한 번에
   * 일어나면 사람이 무엇이 닫힌 것인지 모른다. 전체 결과 화면이 떠 있으면
   * Esc 는 그것을 닫는다.
   *
   * **보고서 팝업이 떠 있으면 Esc 는 팝업만 닫는다** (설계서 4.3.4 L684). 선택 해제나
   * 전체 결과 닫기가 같이 일어나지 않게 맨 앞에서 가른다. 팝업이 뒤 화면을 덮고
   * 있는 동안은 Ctrl+K 도 안 받는다 — 검색 창이 팝업 밑에 열린다
   */
  const reportOpen = report.length > 0;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (reportOpen) {
        if (e.key === "Escape") setReport([]);
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchQ((v) => v ?? "");
        return;
      }
      if (e.key !== "Escape" || searchQ !== null) return;
      if (results !== null) {
        setResults(null);
        return;
      }
      if (tab === "relation") {
        setRelSel(null);
        setRelHi(null);
      } else {
        // 빈 곳을 누른 것과 같게 푼다 — 검색에서 건 행위자 필터 · 사건 강조도 같이 푼다
        setSelection({ kind: "none" });
        setLinkSel(null);
        setPickedEvent(null);
        setActorFilter(null);
        setFocusEvent(null);
        setToast(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [searchQ, results, tab, reportOpen]);

  // 이동 안내는 잠깐 띄우고 걷는다
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 8000);
    return () => window.clearTimeout(t);
  }, [toast]);

  // 영토 사건 수를 더하지 않는다. 행위자 섬이 같은 사건을 한 번 더 세서
  // 그 몫이 두 번 들어간다 (score.ts MapResult.eventCount)
  const eventCount = result.eventCount.dark;
  const activeTerritories = result.territories.filter((t) => t.cells > 0);

  const snaps = useMemo(
    () =>
      snapshots(
        {
          islands: MAP.islands,
          territories: MAP.territories,
          events: MAP.events,
          web: "dark",
          today: TODAY,
        },
        quarters,
      ),
    [quarters],
  );
  /**
   * 모든 분기를 합친 지도 크기. 지도 탭 · Historical Map · 시점 비교 A/B 가 이 크기 틀로 그려
   * 분기마다 축척이 같다 — 확대는 줌으로만 한다 (G-10 묶음 4, 최현서 3번). 지금 분기 판도
   * 넣는다(스냅샷 목록 밖 분기여도 잘리지 않게)
   */
  const mapSize = useMemo(
    () => boxSize([...snaps.map((s) => s.layout.viewBox), layout.viewBox]),
    [snaps, layout],
  );
  const mapBox = useMemo(() => centerBox(layout.viewBox, mapSize), [layout, mapSize]);
  const nameOf = useMemo(() => {
    const m = new Map(DARK_ISLANDS.map((i) => [i.id as string, i.name]));
    return (id: string) => m.get(id) ?? id;
  }, []);

  /* ── 검색 (설계서 4.2.2) ─────────────────────────────── */

  /** 분기마다 지도에 든 영토. 검색 결과를 고를 때 기준일을 옮길지 가른다 */
  const presentBy = useMemo(
    () => new Map(snaps.map((s) => [s.ym, new Set(s.layout.territories.map((t) => t.territoryId))])),
    [snaps],
  );
  const presentAt = useCallback(
    (q: QuarterKey) => presentBy.get(q) ?? presentIn(quarterEnd(q, TODAY)),
    [presentBy],
  );
  /** 검색 색인. **기준일과 무관하게 전체 기간이다** — 한 번이라도 지도에 나온 영토가 대상이다 */
  const ix = useMemo(
    () =>
      buildIndex({
        territories: MAP.territories,
        events: MAP.events,
        relations: ALL_RELS,
        seen: new Set([...presentBy.values()].flatMap((x) => [...x])),
        today: TODAY,
      }),
    [presentBy],
  );
  /**
   * 같은 일치 단계 안의 차례 — 기준일 영토 점수 (4.2.2 「가중치 점수 높은 순」, 3.4 S(T,D)).
   * 전에는 활동도로 세웠다. 활동도는 규모 원자료라 사건 가중치가 안 든다
   */
  const weightOf = useCallback((id: string) => terr.get(id)?.metrics.score ?? 0, [terr]);
  const searchCtx: SearchCtx = useMemo(
    () => ({
      ix,
      islandName: (id) => nameOf(id),
      token: islandToken,
      activityOf: (id) => terr.get(id)?.metrics.activity ?? null,
    }),
    [ix, terr, nameOf],
  );
  const allResults = useMemo(
    () => (results === null ? EMPTY : search(ix, results, filter, weightOf)),
    [ix, results, filter, weightOf],
  );

  /** 고른 대상이 기준일에 안 보이면 기준일을 옮긴다 (4.2.2). 옮긴 분기를 돌려준다 */
  const moveFor = (visible: (q: QuarterKey) => boolean): QuarterKey | null => {
    const to = quarterFor(quarters, ym, visible);
    if (to) setYm(to);
    return to;
  };

  /**
   * 관계 탭 ① 상태로 간다 (설계서 4.3.3) — 검색에서 관계를 고를 때와 보고서 팝업의
   * 관계 줄을 누를 때가 같이 쓴다. 기준일에 그 관계가 없으면 있는 분기로 옮기고 옮긴
   * 분기를 돌려준다. 기준일은 관계 탭으로 옮긴 뒤에 바꾼다 — 돌아가기가 옮기기 전
   * 기준일로 돌아온다
   */
  const openRelation = (rel: Relation, center: string): QuarterKey | null => {
    const to = quarterFor(quarters, ym, (qq) =>
      relationsAt([rel], MAP.events, quarterEnd(qq, TODAY), presentAt(qq)).length > 0,
    );
    // 4.3.3 ①과 같은 상태 — 그 관계를 강조만 한다 (4.2.2 「관계」 결과 선택)
    if (tab === "relation") {
      setPanelOpen(true);
      setRelCenter(center);
      setRelSel(null);
      setRelHi(rel.id);
      setRelPair(null);
      // 가려 둔 추정 관계를 골랐으면 다시 보인다. 강조할 선이 판에 있어야 한다
      if (rel.confidence === "estimated") setRelEst(true);
    } else {
      enterFromLinks({ center, hi: rel.id, pair: null });
    }
    if (to) setYm(to);
    return to;
  };

  /**
   * 검색 결과 고르기 — 설계서 4.2.2 「결과 선택」.
   *
   *   엔티티   지도로 가서 그 영토를 고르고 패널 [개요]. 관계 탭에서 찾았으면 관계 탭 중심을 바꾼다
   *   행위자   주 활동 영토로 가서 패널 [사건]을 그 행위자 사건만으로 거른다 (칩 「행위자: X ×」)
   *   사건     지도로 가서 올라온 영토를 고르고 패널 [사건]에서 그 사건을 강조 · 스크롤.
   *            보고서 팝업은 띄우지 않는다 (L462). 전체 결과 「상세」만 연다 (`openFromSearch`)
   *   관계     관계 탭 ① 상태 (4.3.3) — 중심은 검색어에 걸린 쪽의 상대 영토다
   *
   * 그 대상이 기준일에 안 보이면 기준일을 옮기고 안내에 적는다. 사건이 [사건] 탭 기간
   * 밖이면 기간을 전체로 넓힌다 — 강조할 줄이 목록에 있어야 한다.
   */
  const pickHit = (h: Hit, q: string) => {
    // 재생을 멈춘다. 같은 탭이면 goTab 이 일찍 돌아가 재생이 남고, 옮긴 기준일을 1초 뒤에
    // 다음 분기가 덮어썼다 (2026-09-28 검토 — 끝에서 ▶ 가 되감게 되며 쉽게 닿는다)
    setPlaying(false);
    setRecent((r) => pushRecent(r, recentOf(searchCtx, h, Date.now())));
    setSearchQ(null);
    setResults(null);
    setActorFilter(null);
    setFocusEvent(null);
    const name = (id: string) => ix.byId.get(id)?.name ?? id;
    let label: string;
    let moved: QuarterKey | null;

    if (h.kind === "entity") {
      const id = h.e.id;
      label = h.e.name;
      moved = moveFor((qq) => presentAt(qq).has(id));
      if (tab === "relation") {
        setPanelOpen(true);
        setRelCenter(id);
        setRelSel(null);
        setRelHi(null);
        setRelPair(null);
      } else {
        goTab("map");
        select({ kind: "territory", id, name: h.e.name });
        setPanelTab("overview");
      }
    } else if (h.kind === "actor" || h.kind === "event") {
      const where = h.kind === "actor" ? (h.main ?? h.e.id) : h.ev.territoryId;
      const keep =
        h.kind === "actor"
          ? (e: Ev) => e.actorTerritoryId === h.e.id && belongsTo(e, new Set([where]))
          : (e: Ev) => e.id === h.ev.id;
      label = h.kind === "actor" ? h.e.name : eventTitle(h.ev);
      moved = moveFor(
        (qq) =>
          presentAt(qq).has(where) && eventsIn(MAP.events, quarterEnd(qq, TODAY), { kind: "all" }, keep).length > 0,
      );
      // 관계 탭에서 왔으면 탭을 먼저 옮긴다. 탭을 옮기며 중심 영토를 고르는 것을 아래 선택이 덮는다
      goTab("map");
      select({ kind: "territory", id: where, name: name(where) });
      setPanelTab("events");
      if (h.kind === "actor") setActorFilter(h.e.id);
      else {
        // 강조는 [사건] 행 선택과 같은 값이다 — 지도에도 그 사건의 관계선만 남는다.
        // 사기 의심을 숨겨 두었으면 고른 사건이 목록에 없으므로 푼다
        setFocusEvent(h.ev.id);
        setPickedEvent(h.ev.id);
        if (h.ev.scam) setHideScam(false);
      }
      if (eventsIn(MAP.events, moved ? quarterEnd(moved, TODAY) : d, period, keep).length === 0) {
        setPeriod({ kind: "all" });
      }
    } else {
      const rel = h.r.rel;
      label = `${name(rel.from)} → ${name(rel.to)}`;
      moved = openRelation(rel, rel.from === h.via ? rel.to : rel.from);
    }
    setToast({ label, q, moved });
  };

  /* ── 보고서 팝업 (설계서 4.3.4) ───────────────────────── */

  /**
   * 팝업 열기. 패널 [사건] · 엔티티 탭 최근 이벤트 · [개요] 공식 발표 사고 · 검색 「상세」 ·
   * 관계 탭 근거 목록(RelationPanel)이 부른다.
   * 뒤 화면은 그대로 둔다 — 기준일도 옮기지 않는다
   */
  const openReport = (id: string) => setReport([id]);

  /** 검색 전체 결과의 사건 「상세」 — 결과 화면 위에 팝업을 연다. 고른 것은 최근 검색에 남긴다 */
  const openFromSearch = (h: EventHit) => {
    setRecent((r) => pushRecent(r, recentOf(searchCtx, h, Date.now())));
    openReport(h.ev.id);
  };

  const reportEv = report.length ? (EV_BY_ID.get(report[report.length - 1]) ?? null) : null;
  const reportModel = useMemo(
    () =>
      reportEv
        ? eventReport(
            reportEv,
            REPORT_NAMES,
            linkedOf(MAP.events, reportEv),
            ALL_RELS.filter((r) => touchesEvent(r, reportEv)),
          )
        : null,
    [reportEv],
  );

  /**
   * 정보 표의 영토 이름 — 팝업을 닫고 지도에서 그 영토를 고른다 (설계서 L704). 검색
   * 결과 위에서 열었으면 결과 화면도 닫는다. 그 영토가 기준일 지도에 없으면(검색
   * 「상세」로 기준일 밖 사건을 연 경우) 보이는 분기로 기준일을 옮긴다 (4.2.2 와 같은 규칙)
   */
  const pickFromReport = (id: string) => {
    setPlaying(false);
    setReport([]);
    setResults(null);
    moveFor((qq) => presentAt(qq).has(id));
    goTab("map");
    select({ kind: "territory", id, name: REPORT_NAMES.nameOf(id) });
  };

  /** 팝업의 관계 줄 — 관계 탭 ① 상태. 중심은 사건이 올라온 영토의 상대 쪽이다 (검색 관계 고르기와 같다) */
  const relFromReport = (relId: string) => {
    const rel = ALL_RELS.find((r) => r.id === relId);
    if (!rel || !reportEv) return;
    setReport([]);
    setResults(null);
    openRelation(rel, rel.from === reportEv.territoryId ? rel.to : rel.from);
  };

  /** 관계 탭 제목 옆 설명 (피그마 ⑦-8 · ⑦-8e · ⑦-8g, 설계서 4.3.3 ②) */
  const relSubtitle = () => {
    if (relPair) {
      const n = relViews.reduce((s, v) => s + v.count, 0);
      return `섬 간 보기 · ${islandInfo(relPair.from).name} → ${islandInfo(relPair.to).name} · 엔티티 ${relViews.length}쌍 · ${n}건`;
    }
    // 2단계로 넓히면 중심에 닿지 않은 선도 고를 수 있어 그린 관계 전부에서 찾는다
    const s = relDrawn.find((v) => v.rel.id === relSel);
    if (s) return `${terrName(s.rel.from)} → ${terrName(s.rel.to)} 관계선 선택됨`;
    if (!center) return "이 기준일에 기록된 관계가 없습니다";
    if (!relViews.length) return `중심 엔티티 ${terrName(center)} · 관계 0`;
    if (relHops && relDepth === 2) {
      const n2 = relHops.hop2.length + relHops.rest;
      return `중심 엔티티 ${terrName(center)} · 2단계 확장 · 1단계 ${relHops.hop1.length}곳 · 2단계 ${n2}곳`;
    }
    return `중심 엔티티 ${terrName(center)} · 1단계 관계 ${relViews.length}`;
  };

  /** 패널 [사건] 탭 본문. 목록(`eventList`)은 지도 선이 같이 보느라 위에서 만든다 */
  const whereOf = (e: Ev) =>
    e.actorTerritoryId && terr.has(e.actorTerritoryId)
      ? `${terrName(e.actorTerritoryId)} → ${terrName(e.territoryId)}`
      : terrName(e.territoryId);
  const eventsBody = (
    <EventsTab
      key={focusEvent ?? ""}
      list={eventList}
      d={d}
      period={period}
      onPeriod={setPeriod}
      whereOf={whereOf}
      actor={actorFilter ? (ix.byId.get(actorFilter)?.name ?? actorFilter) : null}
      onClearActor={() => setActorFilter(null)}
      focus={focusEvent}
      picked={pickedEvent}
      onPick={setPickedEvent}
      onOpen={openReport}
      scamCount={scamCount}
      hideScam={hideScam}
      onHideScam={setHideScam}
    />
  );

  /**
   * 패널 [연결] 탭 본문. 선택이 없으면 섬 쌍 요약 전부다 (피그마 ⑦-1 탭 「연결 N」).
   * 섬 [연결] 탭과 같은 줄이라 행 동작(4.3.3)도 같다
   */
  const links = (() => {
    if (liveSelection.kind === "none") {
      return (
        <LinksTab
          mode="island"
          rows={[]}
          pairs={allIslandPairs(rels, islandOf, layout.islands.map((i) => i.islandKey))}
          nameOf={terrName}
          islandOf={islandOf}
          islandInfo={islandInfo}
          selected={liveLinkSel}
          onSelect={setLinkSel}
          onOpenRel={openRel}
          onOpenPair={openPair}
        />
      );
    }
    if (liveSelection.kind === "island") {
      return (
        <LinksTab
          mode="island"
          rows={[]}
          pairs={islandPairs(rels, islandOf, liveSelection.key)}
          nameOf={terrName}
          islandOf={islandOf}
          islandInfo={islandInfo}
          selected={liveLinkSel}
          onSelect={setLinkSel}
          onOpenRel={openRel}
          onOpenPair={openPair}
        />
      );
    }
    const t = terr.get(liveSelection.id);
    if (!t) return null;
    const actor = layout.islands.find((i) => i.islandKey === t.islandKey)?.islandId === "ACTOR";
    return (
      <LinksTab
        mode={actor ? "actor" : "territory"}
        selfId={liveSelection.id}
        rows={linkRows(rels, liveSelection.id)}
        pairs={islandPairs(rels, islandOf, t.islandKey)}
        nameOf={terrName}
        islandOf={islandOf}
        islandInfo={islandInfo}
        selected={liveLinkSel}
        onSelect={setLinkSel}
        onOpenRel={openRel}
        onOpenPair={openPair}
      />
    );
  })();

  return (
    // 화면 최소 크기 1280 × 720. 그보다 작은 창에서는 줄이지 않고 `body` 에 스크롤바가 뜬다
    // (2026-09-28 최현서 4번). 1280 은 범례 206 + 패널 312 + 여백을 빼고 가운데가 약 660 남는 폭이다 —
    // 스냅샷 바가 줄어들고 가운데가 `min-w-0` 이라 패널이 안 잘린다
    <div className="flex h-full min-h-[720px] min-w-[1280px] flex-col p-s5">
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[18px] border border-edge bg-panel">
        <AppHeader
          current="dark"
          generatedAt={MAP.generatedAt}
          onHome={goHome}
          onSearch={() => setSearchQ(results ?? toast?.q ?? "")}
          query={results ?? toast?.q}
        >
          {searchQ !== null && (
            <SearchOverlay
              ctx={searchCtx}
              layout={layout}
              initialQ={searchQ}
              filter={filter}
              onFilter={setFilter}
              recent={recent}
              onClearRecent={() => setRecent([])}
              onClose={() => setSearchQ(null)}
              onPick={pickHit}
              onAll={(q) => {
                setResults(q);
                setSearchQ(null);
              }}
              weightOf={weightOf}
            />
          )}
        </AppHeader>

        <div className="flex min-h-0 flex-1">
          <Legend />

          {/*
            `min-w-0` — 없으면 가운데 최소폭이 스냅샷 바 768 에 묶여 1384px 아래 창에서 오른쪽
            패널이 스크롤도 없이 잘렸다 (2026-09-28 코드 분석)
          */}
          <main className="relative flex min-h-0 min-w-0 flex-1 flex-col gap-s4 px-s5 py-s5">
            {toast && results === null && (
              // 지도 위쪽에 띄운다 (⑦-10b). 관계 탭은 위쪽에 돌아가기 줄과 칩 줄이 있어 아래쪽이다
              <div
                role="status"
                className={
                  "absolute left-1/2 z-20 flex w-max max-w-[90%] -translate-x-1/2 items-center gap-s3 rounded-[12px] px-s4 py-s2 text-[12px] shadow-xl " +
                  (tab === "relation" ? "bottom-[76px]" : "top-[76px]")
                }
                style={{ background: "var(--t-text-title)", color: "var(--t-surface-panel)" }}
              >
                <span>
                  검색 결과 &apos;{toast.label}&apos;{josa(toast.label, "으로", "로")} 이동했어요
                  {toast.moved && ` · 기준일을 ${quarterText(toast.moved)}로 옮겼어요`}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setSearchQ(toast.q);
                    setToast(null);
                  }}
                  className="rounded-[8px] border px-s2 py-[2px] font-semibold underline-offset-2 hover:underline"
                  style={{ borderColor: "color-mix(in srgb, var(--t-surface-panel) 50%, transparent)" }}
                >
                  검색으로 돌아가기
                </button>
              </div>
            )}
            {/*
              제목 줄. 제목 · 화면 탭은 안 접히고, 긴 설명(관계 탭 2단계 부제 따위)만 말줄임으로
              줄어든다 — 전에는 설명이 두 줄이 되며 「타임라인」 탭 글자가 쪼개지고 탭 높이가 바뀌었다
            */}
            <div className="flex shrink-0 items-center gap-s4">
              <h1 className="shrink-0 whitespace-nowrap text-[20px] font-semibold leading-none text-title">
                다크웹 생태계
              </h1>
              {!isBaked && (
                <span
                  className="rounded-[6px] border px-s2 py-[2px] text-[11px]"
                  style={{
                    color: "var(--t-neutral-text)",
                    background: "var(--t-neutral-bg)",
                    borderColor: "var(--t-neutral-border)",
                  }}
                  title="tools/bake.py 를 돌리면 노션의 실제 데이터로 바뀝니다"
                >
                  예시 데이터
                </span>
              )}
              <p className="min-w-0 truncate text-[12px] tabular-nums text-label">
                {results !== null
                  ? `'${results}' 검색 결과 ${total(allResults)}건`
                  : tab === "map"
                  ? `섬 유형 ${layout.islands.length} · 엔티티 ${activeTerritories.length} · 사건 ${eventCount}건${past ? ` · ${past} 스냅샷` : ""}`
                  : tab === "entity"
                    ? `엔티티 ${activeTerritories.length} · 유형별 목록 · ${SORT_LABEL[entitySort.key]} ${entitySort.asc ? "오름차순" : "순"}`
                    : tab === "relation"
                      ? relSubtitle()
                      : compare
                        ? `시점 비교 · A ${quarterText(compare.a)} ↔ B ${quarterText(compare.b)}`
                        : playing
                          ? `재생 중 · ${quarterText(quarters[0])} → ${quarterText(quarters[quarters.length - 1])} (${speed}×)`
                          : `누적 · ${quarterText(quarters[0])} → ${quarterText(quarters[quarters.length - 1])}`}
              </p>
              <div className="flex-1" />
              {/*
                화면 탭은 늘 같은 자리에 둔다. 검색 결과 화면에서 탭을 누르면 결과를 닫고 그 탭으로
                간다. 「검색 결과 닫기 ×」는 결과 목록 머리로 옮겼다 (2026-09-28 코드 분석)
              */}
              <ViewTabs
                current={tab}
                onChange={(k) => {
                  setResults(null);
                  goTab(k);
                }}
              />
            </div>

            {results !== null ? (
              <SearchResults
                ctx={searchCtx}
                q={results}
                results={allResults}
                filter={filter}
                onFilter={setFilter}
                onPick={(h) => pickHit(h, results)}
                onOpenEvent={openFromSearch}
                onClose={() => setResults(null)}
              />
            ) : tab === "timeline" ? (
              <TimelineTab
                snaps={snaps}
                current={ym}
                onPick={setYm}
                compare={compare}
                onCompare={setCompare}
                playing={playing}
                onPlaying={setPlaying}
                speed={speed}
                onSpeed={setSpeed}
                nameOf={nameOf}
                mapSize={mapSize}
                selection={liveSelection}
                onSelect={select}
                lastSeenAt={(q) => seenDays(MAP.events, quarterEnd(q, TODAY))}
                view={tlView}
                onView={setTlView}
              />
            ) : tab === "map" ? (
              <MapCanvas
                layout={layout}
                viewBox={mapBox}
                selection={liveSelection}
                onSelect={select}
                lastSeen={lastSeen}
                view={mapView}
                onView={setMapView}
                lines={mapRel?.lines}
                lit={mapRel?.lit}
                raised={mapRel?.raised}
                litIslands={mapRel?.litIslands}
                hint={
                  toast && liveSelection.kind === "territory"
                    ? `검색 결과 영토 자동 선택 · 관련 섬 ${mapRel?.litIslands.size ?? 1}곳 표시`
                    : liveEvent
                      ? mapRel?.lines.length
                        ? "선택한 사건의 관계선만 표시 중"
                        : "선택한 사건에 이어진 관계선이 없습니다"
                      : undefined
                }
                snapshot={past}
                reveal={reveal}
                onRevealed={(v) => {
                  if (v) setMapView(v);
                  setReveal(null);
                }}
              />
            ) : tab === "relation" ? (
              <RelationTab
                layout={layout}
                views={relShown}
                center={center}
                onCenter={(id) => {
                  // 중심 엔티티 칩도 영토 고르기라 펼친다
                  setPanelOpen(true);
                  setRelCenter(id);
                  setRelSel(null);
                  setRelHi(null);
                  setRelPair(null);
                }}
                selected={relSel}
                onSelect={pickRel}
                highlight={relHi}
                pair={relPair}
                onClearPair={() => {
                  setRelPair(null);
                  setRelCenter(defaultCenter(rels, terrName));
                  setRelSel(null);
                  setRelHi(null);
                }}
                onPairPick={pickFromPair}
                // 출발 화면이 있으면 고른 것이 없어도 돌아가기를 띄운다 (4.3.3 ① · 4.2.2).
                // 고른 것이 없었으면 단추 글이 출발 탭 이름이다
                origin={
                  origin
                    ? {
                        id: origin.shown.kind === "territory" ? origin.shown.id : null,
                        label: backLabel(origin.tab, origin.shown.kind === "none" ? null : origin.shown.name),
                      }
                    : null
                }
                onBack={back}
                moveTo={moveTo}
                onMove={() => moveTo && setYm(moveTo)}
                est={relEst}
                onEst={setRelEst}
                depth={relDepth}
                onDepth={setRelDepth}
                hiddenEst={relHiddenEst}
              />
            ) : (
              <EntityTab
                layout={layout}
                events={MAP.events}
                d={d}
                lastSeen={lastSeen}
                seenAt={seenAt}
                islandKey={
                  entityIsland && layout.islands.some((i) => i.islandKey === entityIsland)
                    ? entityIsland
                    : liveSelection.kind === "island"
                      ? liveSelection.key
                      : liveSelection.kind === "territory"
                        ? layout.territories.find(
                            (x) => x.territoryId === liveSelection.id,
                          )?.islandKey
                        : undefined
                }
                // 섬 필터는 표만 거른다 — 전에는 전역 선택을 그 섬으로 바꾸고 접어 둔 패널을
                // 펼쳐 표가 264px 좁아졌다 (2026-09-28 코드 분석). 설계서 4.3.5 도 행 클릭 때만
                // 패널 내용을 말한다
                onPickIsland={setEntityIsland}
                selectedTerritory={
                  liveSelection.kind === "territory" ? liveSelection.id : undefined
                }
                onPickTerritory={(id) => {
                  const t = layout.territories.find(
                    (x) => x.territoryId === id,
                  );
                  if (t) select({ kind: "territory", id, name: t.name });
                }}
                onGoToMap={(id) => {
                  const t = layout.territories.find(
                    (x) => x.territoryId === id,
                  );
                  if (t) select({ kind: "territory", id, name: t.name });
                  goTab("map");
                }}
                onOpenEvent={openReport}
                sort={entitySort.key}
                asc={entitySort.asc}
                onSort={(key, asc) => setEntitySort({ key, asc })}
              />
            )}

            {/*
              타임라인 탭은 제 안에 시점 슬라이더를 갖는다 (피그마 ⑦-9b).
              스냅샷 바를 같이 두면 같은 값을 두 군데서 조작하게 된다.
              관계 탭에는 둔다 — 피그마 ⑦-8 에는 없어 기준일을 「기준일 옮기기」로만 바꿨고, 시점을
              옮기려면 다른 탭에 다녀와야 했다 (2026-09-28 최현서 10번)
            */}
            {results === null && tab !== "timeline" && (
              <SnapshotBar
                from={FROM}
                to={TO}
                value={ym}
                onChange={setYm}
                playing={playing}
                onPlaying={setPlaying}
                speed={speed}
                onSpeed={setSpeed}
              />
            )}
          </main>

          {tab === "relation" ? (
            <RelationPanel
              open={panelOpen}
              onToggle={setPanelOpen}
              layout={layout}
              views={relViews}
              pool={relDrawn}
              center={center}
              selected={relSel}
              onSelect={pickRel}
              highlight={relHi}
              pair={relPair}
              onPairPick={pickFromPair}
              hiddenEst={relHiddenEst}
              onOpenEvent={openReport}
            />
          ) : (
            <DetailPanel
              view={view}
              open={panelOpen}
              onToggle={setPanelOpen}
              tab={panelTab}
              onTab={setPanelTab}
              links={links}
              events={eventsBody}
              eventBadge={eventList.length}
              onOpenEvent={openReport}
              onPickTerritory={(id) => {
                const t = terr.get(id);
                if (t) select({ kind: "territory", id, name: t.name });
              }}
            />
          )}
        </div>
      </div>

      {reportModel && (
        <EventReport
          model={reportModel}
          canBack={report.length > 1}
          onBack={() => setReport((s) => s.slice(0, -1))}
          onClose={() => setReport([])}
          onOpenLinked={(id) => setReport((s) => [...s, id])}
          onPickTerritory={pickFromReport}
          onOpenRel={relFromReport}
        />
      )}
    </div>
  );
}
