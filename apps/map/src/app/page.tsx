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
import EntityTab from "@/components/EntityTab";
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
import { DEFAULT_PERIOD, eventTitle, eventsIn, type Period } from "@/lib/events";
import { allIslandPairs, belongsTo, ecosystemView, islandView, territoryView } from "@/lib/panel";
import type { Ev } from "@/lib/types";
import {
  defaultCenter,
  islandPairs,
  josa,
  linkRows,
  linksOf,
  pairViews,
  partnerOf,
  relationsAt,
  touching,
  withActivity,
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
  type Hit,
  type Recent,
  type SearchFilter,
} from "@/lib/search";
import { quarterEnd, quarterOfDate, spanOf, type QuarterKey } from "@/lib/quarter";
import { chipQuarter, quartersOf, snapshots } from "@/lib/timeline";

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
  selection: MapSelection;
  panelTab: PanelTabKey;
  linkSel: LinkSel;
  mapView: MapView;
  ym: QuarterKey;
};

/** 뒤로 가기 기록에 우리가 넣은 칸이라는 표시 */
const HISTORY_KEY = "dcRel";

/** 이 창을 연 시각. 뒤로 가기 기록 표가 새로 고침 전 것과 겹치지 않게 한다 */
const OPENED_AT = Date.now().toString(36);

function presentIn(d: Date): Set<string> {
  const r = computeMap({ ...MAP, today: TODAY }, d);
  return new Set(r.territories.filter((t) => t.web === "dark" && t.cells > 0).map((t) => t.territoryId));
}

export default function Page() {
  const [ym, setYm] = useState<QuarterKey>(TO);
  const [selection, setSelection] = useState<MapSelection>({ kind: "none" });
  const [panelOpen, setPanelOpen] = useState(true);
  const [panelTab, setPanelTab] = useState<PanelTabKey>("overview");
  const [linkSel, setLinkSel] = useState<LinkSel>(null);
  // 패널 [사건] 탭 기간. 다른 영토를 골라도 그대로 둔다 (설계서 4.3.2)
  const [period, setPeriod] = useState<Period>(DEFAULT_PERIOD);
  const [mapView, setMapView] = useState<MapView>(MAP_VIEW_HOME);
  const [tab, setTab] = useState<ViewTabKey>("map");
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
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
  // 관계 탭 (설계서 4.3.6)
  const [relCenter, setRelCenter] = useState<string | null>(null);
  const [relSel, setRelSel] = useState<string | null>(null);
  const [relPair, setRelPair] = useState<RelPair | null>(null);
  const [origin, setOrigin] = useState<Origin | null>(null);

  const d = useMemo(() => quarterEnd(ym, TODAY), [ym]);
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
   * 기준일 뒤에 올라온 사건은 뺀다 — 스냅샷을 과거로 옮겼는데 최근 관측이
   * 미래 날짜로 보이면 안 된다.
   */
  const lastSeen = useMemo(() => {
    const cut = d.getTime();
    const out: Record<string, number> = {};
    for (const e of MAP.events) {
      if (e.excluded) continue;
      const t = new Date(e.postedAt).getTime();
      if (Number.isNaN(t) || t > cut) continue;
      // 행위자 영토는 그 행위자가 올린 사건도 제 것이다 (Ev.actorTerritoryId)
      for (const id of [e.territoryId, e.actorTerritoryId]) {
        if (!id) continue;
        if (!(id in out) || t > out[id]) out[id] = t;
      }
    }
    return Object.fromEntries(
      Object.entries(out).map(([id, ms]) => {
        const dt = new Date(ms);
        const p = (n: number) => String(n).padStart(2, "0");
        return [id, `${p(dt.getUTCMonth() + 1)}-${p(dt.getUTCDate())}`];
      }),
    );
  }, [d]);

  const view = useMemo(() => {
    const input = { layout, result, events: MAP.events, d, rels, lastSeen, registry: registryOf };
    if (selection.kind === "island") {
      return islandView(input, selection.key) ?? ecosystemView(input);
    }
    if (selection.kind === "territory") {
      return territoryView(input, selection.id) ?? ecosystemView(input);
    }
    return ecosystemView(input);
  }, [layout, result, d, rels, lastSeen, selection]);

  /**
   * 지도 위 관계선 (설계서 4.2.3 · 4.3.3).
   *
   *   영토를 고름         그 영토의 관계선만. 이어진 영토만 진하고 연결 없는 섬은 흐리다
   *   [연결] 행을 고름     그 관계선만. 상대 영토도 떠오른다
   *   유형 간 행을 고름    그 섬 쌍의 관계선만
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

  const mapRel = useMemo(() => {
    if (liveLinkSel?.type === "pair") {
      const lines = pairViews(rels, islandOf, liveLinkSel.from, liveLinkSel.to);
      const lit = new Set(lines.flatMap((v) => [v.rel.from, v.rel.to]));
      return { lines, lit, raised: lit, litIslands: new Set([liveLinkSel.from, liveLinkSel.to]) };
    }
    if (selection.kind !== "territory") return null;
    const id = selection.id;
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
  }, [rels, selection, liveLinkSel, islandOf, isActor]);

  /**
   * 관계 탭 중심. 고른 영토가 없거나, 기준일을 옮겨 그 영토가 지도에서 빠졌으면
   * **관계가 가장 많은 영토**다 (설계서 4.3.6). 「기준일 옮기기」 뒤에도 이것으로
   * 중심이 선다 — 전에는 비어 있는 채로 남아 그래프가 안 그려졌다
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
  /** 설계서 4.2.4 — 섬이나 영토를 고르면 패널이 자동으로 펼쳐진다 */
  const select = (s: MapSelection) => {
    setSelection(s);
    // 다른 영토를 골라도 열려 있던 패널 탭은 그대로 둔다 (4.2.3). 행 선택만 푼다
    setLinkSel(null);
    // 검색에서 건 행위자 필터와 사건 강조도 푼다. 검색 결과를 고를 때는 이 뒤에 다시 건다
    setActorFilter(null);
    setFocusEvent(null);
    if (s.kind !== "none") setPanelOpen(true);
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
    setRelPair(null);
    setOrigin(null);
  };

  const restore = useCallback((o: Origin) => {
    setTab(o.tab);
    setSelection(o.selection);
    setPanelTab(o.panelTab);
    setLinkSel(o.linkSel);
    setMapView(o.mapView);
    setYm(o.ym);
    setRelSel(null);
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

  const enterFromLinks = (next: { center: string | null; sel: string | null; pair: RelPair | null }) => {
    seqRef.current += 1;
    const seq = `${OPENED_AT}-${seqRef.current}`;
    setOrigin({ seq, tab, selection, panelTab, linkSel, mapView, ym });
    setRelCenter(next.center);
    setRelSel(next.sel);
    setRelPair(next.pair);
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
    if (selection.kind !== "territory") return;
    enterFromLinks({ center: partnerOf(v, selection.id), sel: v.rel.id, pair: null });
  };

  /** 유형 간 행 더블클릭 — 섬 간 보기 (4.3.3 ②) */
  const openPair = (r: IslandPairRow) => {
    enterFromLinks({ center: null, sel: null, pair: { from: r.from, to: r.to } });
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
   */
  const goTab = (k: ViewTabKey) => {
    if (k === tab) return;
    if (k === "relation") {
      const picked = selection.kind === "territory" && present.has(selection.id) ? selection.id : null;
      setRelCenter(picked);
      clearRel();
    } else if (tab === "relation") {
      if (k === "map" && center && terr.has(center)) {
        select({ kind: "territory", id: center, name: terrName(center) });
      }
      dropOurEntry();
      clearRel();
    }
    setTab(k);
    setPlaying(false);
  };

  /**
   * 관계가 없을 때 관계가 생기는 분기 (4.3.3 예외 「기준일 옮기기」). 그 분기의
   * 지도를 새로 계산해 중심 영토의 관계가 실제로 그려지는지 본다.
   */
  const relViews = relPair
    ? pairViews(rels, islandOf, relPair.from, relPair.to)
    : center
      ? touching(rels, center)
      : [];
  const relEmpty = tab === "relation" && !relPair && relViews.length === 0;

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
      const here = relationsAt(ALL_RELS, MAP.events, qd, presentIn(qd));
      if (center ? touching(here, center).length > 0 : here.length > 0) return q;
    }
    return null;
  }, [relEmpty, center, ym, quarters]);

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
   */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
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
      if (tab === "relation") setRelSel(null);
      else {
        setSelection({ kind: "none" });
        setLinkSel(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [searchQ, results, tab]);

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
  /** 같은 일치 단계 안의 차례 — 기준일 활동도 (4.2.2 「가중치 점수 높은 순」) */
  const weightOf = useCallback((id: string) => terr.get(id)?.metrics.activity ?? 0, [terr]);
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
   * 검색 결과 고르기 — 설계서 4.2.2 「결과 선택」.
   *
   *   엔티티   지도로 가서 그 영토를 고르고 패널 [개요]. 관계 탭에서 찾았으면 관계 탭 중심을 바꾼다
   *   행위자   주 활동 영토로 가서 패널 [사건]을 그 행위자 사건만으로 거른다 (칩 「행위자: X ×」)
   *   사건     지도로 가서 올라온 영토를 고르고 패널 [사건]에서 그 사건을 강조 · 스크롤
   *   관계     관계 탭 ① 상태 (4.3.3) — 중심은 검색어에 걸린 쪽의 상대 영토다
   *
   * 그 대상이 기준일에 안 보이면 기준일을 옮기고 안내에 적는다. 사건이 [사건] 탭 기간
   * 밖이면 기간을 전체로 넓힌다 — 강조할 줄이 목록에 있어야 한다.
   */
  const pickHit = (h: Hit, q: string) => {
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
        setRelCenter(id);
        setRelSel(null);
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
      else setFocusEvent(h.ev.id);
      if (eventsIn(MAP.events, moved ? quarterEnd(moved, TODAY) : d, period, keep).length === 0) {
        setPeriod({ kind: "all" });
      }
    } else {
      const rel = h.r.rel;
      label = `${name(rel.from)} → ${name(rel.to)}`;
      const center = rel.from === h.via ? rel.to : rel.from;
      // 기준일은 관계 탭으로 옮긴 뒤에 바꾼다 — 돌아가기가 옮기기 전 기준일로 돌아온다
      const to = quarterFor(quarters, ym, (qq) =>
        relationsAt([rel], MAP.events, quarterEnd(qq, TODAY), presentAt(qq)).length > 0,
      );
      if (tab === "relation") {
        setRelCenter(center);
        setRelSel(rel.id);
        setRelPair(null);
      } else {
        enterFromLinks({ center, sel: rel.id, pair: null });
      }
      if (to) setYm(to);
      moved = to;
    }
    setToast({ label, q, moved });
  };

  /** 관계 탭 제목 옆 설명 (피그마 ⑦-8 · ⑦-8e · ⑦-8g, 설계서 4.3.3 ②) */
  const relSubtitle = () => {
    if (relPair) {
      const n = relViews.reduce((s, v) => s + v.count, 0);
      return `섬 간 보기 · ${islandInfo(relPair.from).name} → ${islandInfo(relPair.to).name} · 엔티티 ${relViews.length}쌍 · ${n}건`;
    }
    const s = relViews.find((v) => v.rel.id === relSel);
    if (s) return `${terrName(s.rel.from)} → ${terrName(s.rel.to)} 관계선 선택됨`;
    if (!center) return "이 기준일에 기록된 관계가 없습니다";
    return relViews.length
      ? `중심 엔티티 ${terrName(center)} · 1단계 관계 ${relViews.length}`
      : `중심 엔티티 ${terrName(center)} · 관계 0`;
  };

  /**
   * 패널 [사건] 탭 (설계서 4.3.1 · 4.3.2 · 4.3.8). 영토는 그 영토, 행위자는 그
   * 행위자가 올린 사건, 섬은 소속 영토 전부다 — `belongsTo` 가 셋을 같이 가른다.
   * 선택이 없으면 지도에 있는 영토 전부다 (피그마 ⑦-1 탭 「사건 N」). 행마다 영토
   * 이름이 붙는 것은 섬과 같다
   */
  const eventIds: Set<string> =
    selection.kind === "territory"
      ? new Set([selection.id])
      : selection.kind === "island"
        ? new Set(layout.territories.filter((t) => t.islandKey === selection.key).map((t) => t.territoryId))
        : present;
  const eventList = eventsIn(
    MAP.events,
    d,
    period,
    (e) => belongsTo(e, eventIds) && (!actorFilter || e.actorTerritoryId === actorFilter),
  );
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
    />
  );

  /**
   * 패널 [연결] 탭 본문. 선택이 없으면 섬 쌍 요약 전부다 (피그마 ⑦-1 탭 「연결 N」).
   * 섬 [연결] 탭과 같은 줄이라 행 동작(4.3.3)도 같다
   */
  const links = (() => {
    if (selection.kind === "none") {
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
    if (selection.kind === "island") {
      return (
        <LinksTab
          mode="island"
          rows={[]}
          pairs={islandPairs(rels, islandOf, selection.key)}
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
    const t = terr.get(selection.id);
    if (!t) return null;
    const actor = layout.islands.find((i) => i.islandKey === t.islandKey)?.islandId === "ACTOR";
    return (
      <LinksTab
        mode={actor ? "actor" : "territory"}
        selfId={selection.id}
        rows={linkRows(rels, selection.id)}
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
    <div className="flex min-h-0 flex-1 flex-col p-s5">
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[18px] border border-edge bg-panel">
        <AppHeader
          current="dark"
          generatedAt={MAP.generatedAt}
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

          <main className="relative flex min-h-0 flex-1 flex-col gap-s4 px-s5 py-s5">
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
                  {toast.moved && ` · 기준일을 ${toast.moved}로 옮겼어요`}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setSearchQ(toast.q);
                    setToast(null);
                  }}
                  className="rounded-[8px] border px-s2 py-[2px] font-semibold"
                  style={{ borderColor: "color-mix(in srgb, var(--t-surface-panel) 50%, transparent)" }}
                >
                  검색으로 돌아가기
                </button>
              </div>
            )}
            <div className="flex shrink-0 items-center gap-s4">
              <h1 className="text-[20px] font-semibold leading-none text-title">
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
              <p className="text-[12px] tabular-nums text-label">
                {results !== null
                  ? `'${results}' 검색 결과 ${total(allResults)}건`
                  : tab === "map"
                  ? `섬 유형 ${layout.islands.length} · 엔티티 ${activeTerritories.length} · 사건 ${eventCount}건`
                  : tab === "entity"
                    ? `엔티티 ${activeTerritories.length} · 유형별 목록 · 활동도 순`
                    : tab === "relation"
                      ? relSubtitle()
                      : playing
                        ? `재생 중 · ${quarters[0]} → ${quarters[quarters.length - 1]} (${speed}×)`
                        : `누적 · ${quarters[0]} → ${quarters[quarters.length - 1]}`}
              </p>
              <div className="flex-1" />
              {results !== null ? (
                <button
                  type="button"
                  onClick={() => setResults(null)}
                  className="rounded-[10px] border border-edge px-s3 py-s2 text-[12px] text-body hover:text-title"
                >
                  검색 결과 닫기 ×
                </button>
              ) : (
                <ViewTabs current={tab} onChange={goTab} />
              )}
            </div>

            {results !== null ? (
              <SearchResults
                ctx={searchCtx}
                q={results}
                results={allResults}
                filter={filter}
                onFilter={setFilter}
                onPick={(h) => pickHit(h, results)}
              />
            ) : tab === "timeline" ? (
              <TimelineTab
                snaps={snaps}
                current={ym}
                onPick={setYm}
                onPickYear={(y) => setYm(chipQuarter(y))}
                playing={playing}
                onPlaying={setPlaying}
                speed={speed}
                onSpeed={setSpeed}
                nameOf={nameOf}
              />
            ) : tab === "map" ? (
              <MapCanvas
                layout={layout}
                selection={selection}
                onSelect={select}
                lastSeen={lastSeen}
                view={mapView}
                onView={setMapView}
                lines={mapRel?.lines}
                lit={mapRel?.lit}
                raised={mapRel?.raised}
                litIslands={mapRel?.litIslands}
                hint={
                  toast && selection.kind === "territory"
                    ? `검색 결과 영토 자동 선택 · 관련 섬 ${mapRel?.litIslands.size ?? 1}곳 표시`
                    : undefined
                }
              />
            ) : tab === "relation" ? (
              <RelationTab
                layout={layout}
                views={rels}
                center={center}
                onCenter={(id) => {
                  setRelCenter(id);
                  setRelSel(null);
                  setRelPair(null);
                }}
                selected={relSel}
                onSelect={setRelSel}
                pair={relPair}
                onClearPair={() => {
                  setRelPair(null);
                  setRelCenter(defaultCenter(rels, terrName));
                  setRelSel(null);
                }}
                onPairPick={(v) => {
                  // 섬 간 보기에서 고르면 보통 관계 탭(①)이다. 중심은 도착 영토
                  setRelPair(null);
                  setRelCenter(v.rel.to);
                  setRelSel(v.rel.id);
                }}
                origin={
                  origin && origin.selection.kind === "territory"
                    ? { id: origin.selection.id, name: origin.selection.name }
                    : origin && origin.selection.kind === "island"
                      ? { id: "", name: origin.selection.name }
                      : origin
                        ? { id: "", name: "다크웹 생태계" }
                        : null
                }
                onBack={back}
                moveTo={moveTo}
                onMove={() => moveTo && setYm(moveTo)}
              />
            ) : (
              <EntityTab
                layout={layout}
                events={MAP.events}
                d={d}
                lastSeen={lastSeen}
                islandKey={
                  selection.kind === "island"
                    ? selection.key
                    : selection.kind === "territory"
                      ? layout.territories.find(
                          (x) => x.territoryId === selection.id,
                        )?.islandKey
                      : undefined
                }
                onPickIsland={(key) => {
                  const i = layout.islands.find((x) => x.islandKey === key);
                  if (i) select({ kind: "island", key, name: i.name });
                }}
                selectedTerritory={
                  selection.kind === "territory" ? selection.id : undefined
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
              />
            )}

            {/*
              타임라인 탭은 제 안에 시점 슬라이더를 갖는다 (피그마 ⑦-9b).
              스냅샷 바를 같이 두면 같은 값을 두 군데서 조작하게 된다.
              관계 탭에도 없다 (피그마 ⑦-8) — 기준일은 「기준일 옮기기」로만 바꾼다
            */}
            {results === null && tab !== "timeline" && tab !== "relation" && (
              <SnapshotBar
                from={FROM}
                to={TO}
                value={ym}
                onChange={setYm}
                playing={playing}
                onPlaying={setPlaying}
              />
            )}
          </main>

          {tab === "relation" ? (
            <RelationPanel
              open={panelOpen}
              onToggle={setPanelOpen}
              layout={layout}
              views={relViews}
              center={center}
              selected={relSel}
              onSelect={setRelSel}
              pair={relPair}
              onPairPick={(v) => {
                setRelPair(null);
                setRelCenter(v.rel.to);
                setRelSel(v.rel.id);
              }}
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
              onPickTerritory={(id) => {
                const t = terr.get(id);
                if (t) select({ kind: "territory", id, name: t.name });
              }}
            />
          )}
        </div>
      </div>

    </div>
  );
}
