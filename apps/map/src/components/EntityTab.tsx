/**
 * 엔티티 탭 — 설계서 4.3.5. 영토를 표로 견준다.
 *
 * 섬 필터로 한 번에 섬 하나만 본다. 위에 KPI 카드 넷, 가운데 표, 아래 최근
 * 주요 이벤트다.
 *
 * 「최근 주요 이벤트」는 고른 섬의 최신 사건 셋이다 (설계서 4.3.5, 피그마 ⑦-7).
 * 사건 제목은 분류 칸으로 새로 지은 것이다 — 자료 제목에 피해 조직 이름이
 * 들어 있어 굽기가 안 싣는다 (2026-09-25 최현서 결정, `events.ts`).
 */

"use client";

import { useMemo, useState } from "react";

import EventRow from "./EventRow";
import { recentKpi } from "@/lib/entity";
import { eventsIn } from "@/lib/events";
import type { MapLayout, TerritoryShape } from "@/lib/layout";
import { belongsTo } from "@/lib/panel";
import type { Status } from "@/lib/score";
import type { Ev } from "@/lib/types";

/** 표에서 정렬 가능한 열 (설계서 4.3.5) */
type SortKey = "activity" | "delta" | "events" | "lastSeen";

/** 상태 칩. 설계서 3.7 의 두 값이고 피그마 `⑦-7` 의 칩 모양이다 */
const STATUS_CHIP: Record<Status, string> = {
  활성: "bg-success-bg text-success border-success-edge",
  "관측 중": "text-neutral border-neutral-edge",
};

export type EntityTabProps = {
  layout: MapLayout;
  events: readonly Ev[];
  /** 기준일 D */
  d: Date;
  /** 영토 id → 최근 관측일 `MM-DD`. 화면에 적는 값이다 */
  lastSeen: Record<string, string>;
  /** 영토 id → 최근 관측 시각 (ms). 「최근 관측」 열 정렬이 이것을 쓴다 (설계서 L737-739) */
  seenAt: Record<string, number>;
  /** 고른 섬. 지도에서 섬을 고른 채 넘어오면 그 섬으로 연다 (설계서 4.3.5) */
  islandKey?: string;
  onPickIsland: (key: string) => void;
  /** 행을 누르면 그 영토를 고른다. 패널이 그 영토로 바뀐다 */
  selectedTerritory?: string;
  onPickTerritory: (id: string) => void;
  /** 「지도에서 보기」 */
  onGoToMap: (id: string) => void;
  /** 「최근 주요 이벤트」 사건 누르기 — 보고서 팝업 (설계서 4.3.5 L745 · 4.3.4, 한 번 클릭) */
  onOpenEvent?: (id: string) => void;
};

export default function EntityTab({
  layout,
  events,
  d,
  lastSeen,
  seenAt,
  islandKey,
  onPickIsland,
  selectedTerritory,
  onPickTerritory,
  onGoToMap,
  onOpenEvent,
}: EntityTabProps) {
  const [sort, setSort] = useState<SortKey>("activity");
  const [asc, setAsc] = useState(false);
  const [pickedEv, setPickedEv] = useState<string | null>(null);

  // 섬을 안 고른 채 들어오면 첫 섬을 연다. 설계서는 「기본 포럼」인데
  // 포럼이 0건인 기준일도 있으므로 목록 첫 섬으로 둔다
  const island =
    layout.islands.find((i) => i.islandKey === islandKey) ?? layout.islands[0];

  const rows = useMemo(() => {
    if (!island) return [];
    const mine = layout.territories.filter(
      (t) => t.islandKey === island.islandKey,
    );
    const val = (t: TerritoryShape) => {
      switch (sort) {
        case "activity":
          return t.metrics.activity;
        case "delta":
          return t.metrics.countChangeRate30d ?? -Infinity;
        case "events":
          return t.metrics.eventCount;
        case "lastSeen":
          // 화면 글자 `MM-DD` 가 아니라 시각으로 견준다. 데이터가 2021 년부터라
          // 글자로 견주면 해가 바뀌는 자리에서 차례가 뒤집힌다 (설계서 L737-739)
          return seenAt[t.territoryId] ?? -Infinity;
      }
    };
    return [...mine].sort((a, b) => {
      const x = val(a);
      const y = val(b);
      // -Infinity 끼리 빼면 NaN 이라 크기로만 가른다
      const c = x === y ? 0 : x < y ? -1 : 1;
      return asc ? c : -c;
    });
  }, [layout, island, sort, asc, seenAt]);

  if (!island) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-[14px] border border-edge bg-canvas text-[13px] text-label">
        이 기준일까지 올라온 사건이 없습니다
      </div>
    );
  }

  // 이 섬에 속한 영토 id. 최근 주요 이벤트를 고를 때 쓴다
  const mine = new Set(rows.map((t) => t.territoryId));
  const live = rows.filter((t) => t.metrics.status === "활성");
  // 최근 30일 사건과 전월 대비 (설계서 4.3.5 L725). 행위자 섬도 제 몫이 잡힌다
  const recent = recentKpi(rows);
  const avg = rows.length
    ? Math.round(rows.reduce((a, t) => a + t.metrics.activity, 0) / rows.length)
    : 0;
  // **평균 활동도에 30일 변화를 안 붙인다** (설계서 4.3.5, 판 1.2).
  // 활동도가 규모 원자료로 갈려 시점 간 차가 뜻을 잃었다
  const top = rows.length
    ? [...rows].sort((a, b) => b.metrics.activity - a.metrics.activity)[0]
    : null;

  /**
   * 정렬 머리. 단추로 감싸 키보드로도 누른다. 정렬할 수 있는 열은 흐린 ↕ 를 달아 알린다 —
   * 전에는 정렬 중인 열에만 ▲▼ 가 있어 다른 열이 눌리는지 몰랐다 (2026-09-28 코드 분석)
   */
  const head = (key: SortKey, name: string, extra = "") => (
    <th
      className={"py-s3 font-normal text-label " + extra}
      aria-sort={sort === key ? (asc ? "ascending" : "descending") : undefined}
    >
      <button
        type="button"
        onClick={() => {
          if (sort === key) setAsc((v) => !v);
          else {
            setSort(key);
            setAsc(false);
          }
        }}
        className="-mx-s1 flex items-center gap-s1 whitespace-nowrap rounded-[6px] px-s1 hover-seg"
      >
        {name}
        {sort === key ? (
          <span className="text-body">{asc ? "▲" : "▼"}</span>
        ) : (
          <span aria-hidden className="text-disabled">
            ↕
          </span>
        )}
      </button>
    </th>
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-s4 overflow-y-auto">
      <nav
        aria-label="섬 고르기"
        className="flex shrink-0 gap-s1 self-start rounded-[12px] bg-track p-[3px]"
      >
        {layout.islands.map((i) => {
          const on = i.islandKey === island.islandKey;
          const n = layout.territories.filter(
            (t) => t.islandKey === i.islandKey,
          ).length;
          return (
            <button
              key={i.islandKey}
              type="button"
              aria-current={on ? "page" : undefined}
              onClick={() => onPickIsland(i.islandKey)}
              // 고른 칸은 화면 탭(`ViewTabs`)처럼 테두리 있는 패널색 칸이다 — 전에는 bg-selected 가
              // 통 색과 거의 같아 무엇을 골랐는지 흐렸다 (2026-09-28 코드 분석)
              className={[
                "flex items-center gap-s2 whitespace-nowrap rounded-[10px] border px-s4 py-s2 text-[13px]",
                on ? "border-edge bg-panel font-semibold text-strong" : "border-transparent text-label hover-seg",
              ].join(" ")}
            >
              <span
                aria-hidden
                className="size-[7px] rounded-full"
                style={{
                  background: `var(--t-island-${i.token}-legend, var(--t-island-${i.token}))`,
                }}
              />
              {i.name}
              <span className="text-[11px] tabular-nums">{n}</span>
            </button>
          );
        })}
      </nav>

      <div className="grid shrink-0 grid-cols-4 gap-s4">
        <Kpi label="평균 활동도" value={String(avg)} />
        <Kpi
          label="활성 엔티티"
          value={`${live.length} / ${rows.length}`}
          note="전체 엔티티 대비"
        />
        {/* 피그마 ⑦-7 「▲ 4 · 전월 대비」. 직전 30일이 0건이면 견줄 것이 없어 기간만 적는다 */}
        <Kpi
          label="최근 30일 사건"
          value={String(recent.count)}
          trend={recent.trend ?? undefined}
          note={
            recent.trend === null
              ? "지난 30일"
              : recent.trend === 0
                ? "전월과 같음"
                : "전월 대비"
          }
        />
        <Kpi
          label="최고 활동도"
          value={top ? String(top.metrics.activity) : "—"}
          note={top?.name ?? ""}
        />
      </div>

      {/*
        표는 고정 배치다 — 열 폭을 머리가 정하고 엔티티 이름 열이 남는 폭을 받아 말줄임한다.
        상세 패널이 펼쳐진 1280 창(표 폭 약 660)에서도 모든 열이 보인다. 표 폭이 좁으면
        (`@container`) 활동도 막대를 줄인다. 전에는 자동 배치라 이름이 여러 줄로 접히고 오른쪽
        열이 칸 밖으로 밀렸다 (2026-09-28 검토 — 패널이 탭을 옮겨도 펼쳐진 채 남게 된 뒤)
      */}
      <div className="@container shrink-0 overflow-x-auto rounded-[14px] border border-edge">
        <table className="w-full table-fixed border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-divider bg-panel text-left text-[12px]">
              <th className="w-[44px] py-s3 pl-s5 font-normal text-label">#</th>
              <th className="py-s3 font-normal text-label">엔티티</th>
              {head("activity", "활동도", "w-[112px] @min-[820px]:w-[220px]")}
              {head("delta", "30일", "w-[68px]")}
              <th className="w-[84px] py-s3 font-normal text-label">상태</th>
              {head("events", "사건", "w-[64px]")}
              {head("lastSeen", "최근 관측", "w-[84px]")}
              <th className="w-[120px] py-s3 pr-s4" />
            </tr>
          </thead>
          <tbody>
            {rows.map((t, k) => {
              const m = t.metrics;
              const on = t.territoryId === selectedTerritory;
              return (
                <tr
                  key={t.territoryId}
                  onClick={() => onPickTerritory(t.territoryId)}
                  // 키보드로도 고른다 — Enter · Space (2026-09-28 코드 분석)
                  tabIndex={0}
                  aria-selected={on}
                  onKeyDown={(ev) => {
                    if (ev.target !== ev.currentTarget) return;
                    if (ev.key === "Enter" || ev.key === " ") {
                      ev.preventDefault();
                      onPickTerritory(t.territoryId);
                    }
                  }}
                  className={[
                    "cursor-pointer border-b border-divider last:border-0",
                    on ? "bg-row-selected" : "bg-panel hover-row",
                  ].join(" ")}
                >
                  <td className="py-s4 pl-s5 tabular-nums text-label">{k + 1}</td>
                  <td className="py-s4 pr-s3">
                    <span className="flex min-w-0 items-center gap-s3">
                      <span
                        aria-hidden
                        className="size-[8px] shrink-0 rounded-full"
                        style={{
                          background: `var(--t-island-${t.token}-legend, var(--t-island-${t.token}))`,
                        }}
                      />
                      <span
                        title={t.name}
                        className={
                          "truncate " + (on ? "font-semibold text-strong" : "text-body")
                        }
                      >
                        {t.name}
                      </span>
                    </span>
                  </td>
                  <td className="py-s4">
                    <span className="flex items-center gap-s3">
                      <span className="h-[5px] flex-1 overflow-hidden rounded-full bg-bar-track">
                        <span
                          className="block h-full rounded-full bg-bar-fill"
                          style={{ width: `${m.activity}%` }}
                        />
                      </span>
                      <span className="w-[32px] text-right font-semibold tabular-nums text-strong">
                        {m.activity}
                      </span>
                    </span>
                  </td>
                  <td className="py-s4 tabular-nums">
                    {/* 사건 수 30일 변화율. 직전 30일이 0건이면 안 낸다 (3.7) */}
                    {m.countChangeRate30d === null ||
                    Math.round(m.countChangeRate30d) === 0 ? (
                      <span className="text-label">—</span>
                    ) : (
                      <span
                        style={{
                          color:
                            m.countChangeRate30d > 0
                              ? "var(--t-trend-up)"
                              : "var(--t-trend-down)",
                        }}
                      >
                        {m.countChangeRate30d > 0 ? "▲" : "▼"}
                        {Math.abs(Math.round(m.countChangeRate30d))}%
                      </span>
                    )}
                  </td>
                  <td className="py-s4">
                    <span
                      className={
                        "rounded-[6px] border px-s2 py-[2px] text-[11px] " +
                        STATUS_CHIP[m.status]
                      }
                    >
                      {m.status}
                    </span>
                  </td>
                  <td className="py-s4 tabular-nums text-body">
                    {m.eventCount}건
                  </td>
                  <td className="py-s4 tabular-nums text-label">
                    {lastSeen[t.territoryId] ?? "—"}
                  </td>
                  <td className="py-s4 pr-s4 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onGoToMap(t.territoryId);
                      }}
                      // 두 줄로 접히던 것을 한 줄로 (2026-09-28 코드 분석). 열 폭도 단추에 맞췄다
                      className="whitespace-nowrap rounded-[8px] border border-edge px-s3 py-[3px] text-[11px] text-label hover-edge"
                    >
                      지도에서 보기
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <RecentEvents
        title={`최근 주요 이벤트 · ${island.name}`}
        list={eventsIn(events, d, { kind: "all" }, (e) => belongsTo(e, mine)).slice(0, 3)}
        nameOf={(id) => layout.territories.find((t) => t.territoryId === id)?.name ?? ""}
        picked={pickedEv}
        onPick={setPickedEv}
        onOpen={onOpenEvent}
      />
    </div>
  );
}

/**
 * 「최근 주요 이벤트」 — 고른 섬의 최신 사건 셋, 날짜순 (설계서 4.3.5).
 * 누르면 보고서 팝업(4.3.4)이 열린다(한 번 클릭 — 최현서 9번). 카드 오른쪽 위 안내 문구도
 * 그에 맞춰 고쳤다(피그마 ⑦-7 은 「사건 더블클릭 → 상세 팝업」)
 */
function RecentEvents({
  title,
  list,
  nameOf,
  picked,
  onPick,
  onOpen,
}: {
  title: string;
  list: Ev[];
  nameOf: (territoryId: string) => string;
  picked: string | null;
  onPick: (id: string | null) => void;
  onOpen?: (id: string) => void;
}) {
  return (
    <section className="flex shrink-0 flex-col gap-s3 rounded-[14px] border border-edge px-s5 py-s4">
      <div className="flex items-baseline justify-between gap-s3">
        <h3 className="text-[12px] text-label">{title}</h3>
        {onOpen && list.length > 0 && <span className="text-[11px] text-label">사건 클릭 → 상세 팝업</span>}
      </div>
      {list.length === 0 ? (
        <p className="text-[12px] text-label">이 기준일까지 이 섬에 올라온 사건이 없습니다.</p>
      ) : (
        <div className="grid grid-cols-3 gap-s4">
          {list.map((e) => (
            <EventRow
              key={e.id}
              e={e}
              where={
                e.actorTerritoryId && nameOf(e.actorTerritoryId)
                  ? `${nameOf(e.actorTerritoryId)} → ${nameOf(e.territoryId)}`
                  : nameOf(e.territoryId)
              }
              on={picked === e.id}
              onClick={() => onPick(picked === e.id ? null : e.id)}
              // 누르면 그 줄을 강조하고 팝업을 연다 (다른 두 자리와 같게)
              onOpen={
                onOpen &&
                (() => {
                  onPick(e.id);
                  onOpen(e.id);
                })
              }
            />
          ))}
        </div>
      )}
    </section>
  );
}

function Kpi({
  label,
  value,
  note,
  trend,
}: {
  label: string;
  value: string;
  note?: string;
  trend?: number;
}) {
  return (
    <div className="rounded-[14px] border border-edge bg-card px-s5 py-s4">
      <div className="text-[12px] text-label">{label}</div>
      <div className="mt-s2 text-[30px] font-semibold leading-none tabular-nums text-title">
        {value}
      </div>
      <div className="mt-s3 flex items-baseline gap-s2 text-[11px] tabular-nums">
        {trend !== undefined && trend !== 0 && (
          <span
            style={{
              color: trend > 0 ? "var(--t-trend-up)" : "var(--t-trend-down)",
            }}
          >
            {trend > 0 ? "▲" : "▼"}
            {Math.abs(trend)}
          </span>
        )}
        {note && <span className="text-label">{note}</span>}
      </div>
    </div>
  );
}
