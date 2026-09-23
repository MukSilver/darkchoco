/**
 * 다크웹 2D 지도 화면.
 *
 * 재료는 `mapData.ts` 가 준다 — `tools/bake.py` 가 노션에서 구워 둔
 * `src/data/map.json` 이고, 그것이 없으면 예시 데이터로 물러선다.
 * 무엇을 보고 있는지는 머리띠 옆에 적는다.
 */

"use client";

import { useEffect, useMemo, useState } from "react";

import AppHeader from "@/components/AppHeader";
import DetailPanel from "@/components/DetailPanel";
import EntityTab from "@/components/EntityTab";
import Legend from "@/components/Legend";
import MapCanvas, { type MapSelection } from "@/components/MapCanvas";
import SearchOverlay from "@/components/SearchOverlay";
import SnapshotBar from "@/components/SnapshotBar";
import TimelineTab from "@/components/TimelineTab";
import ViewTabs, { type ViewTabKey } from "@/components/ViewTabs";
import { DARK_ISLANDS } from "@/lib/islands";
import { layoutMap } from "@/lib/layout";
import { MAP, isBaked } from "@/lib/mapData";
import { ecosystemView, islandView, territoryView } from "@/lib/panel";
import { computeMap } from "@/lib/score";
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

export default function Page() {
  const [ym, setYm] = useState<QuarterKey>(TO);
  const [selection, setSelection] = useState<MapSelection>({ kind: "none" });
  const [panelOpen, setPanelOpen] = useState(true);
  const [tab, setTab] = useState<ViewTabKey>("map");
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [searching, setSearching] = useState(false);
  // 최근 검색. 검색 부품은 닫으면 사라지므로 여기서 들고 있는다
  const [recent, setRecent] = useState<string[]>([]);

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
    const input = {
      layout,
      result,
      events: MAP.events,
      d,
      linkCount: MAP.links.length,
      lastSeen,
    };
    if (selection.kind === "island") {
      return islandView(input, selection.key) ?? ecosystemView(input);
    }
    if (selection.kind === "territory") {
      return territoryView(input, selection.id) ?? ecosystemView(input);
    }
    return ecosystemView(input);
  }, [layout, result, d, lastSeen, selection]);

  /**
   * 단축키 둘.
   *
   *   Esc      선택 해제 (설계서 4.2.3)
   *   Ctrl+K   검색 열기 (설계서 4.2.2, 맥은 ⌘K)
   *
   * 검색이 열려 있으면 Esc 는 검색이 받는다 — 거기서 `stopPropagation` 을
   * 안 걸고 여기서 가른다. 검색을 닫는 것과 선택을 푸는 것이 한 번에
   * 일어나면 사람이 무엇이 닫힌 것인지 모른다.
   */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearching(true);
        return;
      }
      if (e.key === "Escape" && !searching) setSelection({ kind: "none" });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [searching]);

  /** 설계서 4.2.4 — 섬이나 영토를 고르면 패널이 자동으로 펼쳐진다 */
  const select = (s: MapSelection) => {
    setSelection(s);
    if (s.kind !== "none") setPanelOpen(true);
  };

  /**
   * 탭을 옮기면 재생을 멈춘다.
   *
   * 스냅샷 바는 한 달씩, 타임라인은 한 해씩 넘긴다. 켠 채로 탭을 옮기면
   * 간격이 바뀌어 사람이 무엇을 보고 있는지 놓친다.
   */
  const goTab = (k: ViewTabKey) => {
    setTab(k);
    setPlaying(false);
  };

  // 영토 사건 수를 더하지 않는다. 행위자 섬이 같은 사건을 한 번 더 세서
  // 그 몫이 두 번 들어간다 (score.ts MapResult.eventCount)
  const eventCount = result.eventCount.dark;
  const activeTerritories = result.territories.filter((t) => t.cells > 0);

  /**
   * 타임라인 시점. 설계서 4.3.7 이 「연도 칩 클릭 시 그 해 9월로 이동」이라
   * 해마다 9월 말을 찍는다.
   *
   * **기준 시점이 스냅샷 바와 같은 값이다** (설계서 4.3.7). 여기서 연도를
   * 옮기면 지도 탭의 기준일도 같이 움직인다.
   */
  const quarters = useMemo(() => quartersOf(MAP.events, TODAY), []);
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

  return (
    <div className="flex min-h-0 flex-1 flex-col p-s5">
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[18px] border border-edge bg-panel">
        <AppHeader
          current="dark"
          generatedAt={MAP.generatedAt}
          onSearch={() => setSearching(true)}
        />

        <div className="flex min-h-0 flex-1">
          <Legend />

          <main className="flex min-h-0 flex-1 flex-col gap-s4 px-s5 py-s5">
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
                {tab === "map"
                  ? `섬 유형 ${layout.islands.length} · 엔티티 ${activeTerritories.length} · 사건 ${eventCount}건`
                  : tab === "entity"
                    ? `엔티티 ${activeTerritories.length} · 유형별 목록 · 활동도 순`
                    : playing
                      ? `재생 중 · ${quarters[0]} → ${quarters[quarters.length - 1]} (${speed}×)`
                      : `누적 · ${quarters[0]} → ${quarters[quarters.length - 1]}`}
              </p>
              <div className="flex-1" />
              <ViewTabs current={tab} onChange={goTab} />
            </div>

            {tab === "timeline" ? (
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
              스냅샷 바를 같이 두면 같은 값을 두 군데서 조작하게 된다
            */}
            {tab !== "timeline" && (
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

          <DetailPanel view={view} open={panelOpen} onToggle={setPanelOpen} />
        </div>
      </div>

      {searching && (
        <SearchOverlay
          layout={layout}
          recent={recent}
          onRecent={setRecent}
          onClose={() => setSearching(false)}
          onPick={(id) => {
            const t = layout.territories.find((x) => x.territoryId === id);
            if (t) select({ kind: "territory", id, name: t.name });
            goTab("map");
          }}
        />
      )}
    </div>
  );
}
