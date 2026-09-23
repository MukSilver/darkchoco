/**
 * 엔티티 탭 — 설계서 4.3.5. 영토를 표로 견준다.
 *
 * 섬 필터로 한 번에 섬 하나만 본다. 위에 KPI 카드 넷, 가운데 표, 아래 최근
 * 주요 이벤트다.
 *
 * **「최근 주요 이벤트」는 안 만들었다.** 사건마다 제목과 종류 칩이 필요한데
 * (피그마 `⑦-7` 아래쪽), 우리 사건 타입에는 게시일 · 판정 · 규모 · 재게시뿐이다.
 * 제목은 게시글 본문에서 와야 하고 그 길에 반출 관문이 있다. 굽기가 무엇을
 * 실어 올지 정해지면 그때 붙인다.
 */

"use client";

import { useMemo, useState } from "react";

import type { MapLayout, TerritoryShape } from "@/lib/layout";
import { countInWindow } from "@/lib/panel";
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
  /** 영토 id → 최근 관측일 `MM-DD` */
  lastSeen: Record<string, string>;
  /** 고른 섬. 지도에서 섬을 고른 채 넘어오면 그 섬으로 연다 (설계서 4.3.5) */
  islandKey?: string;
  onPickIsland: (key: string) => void;
  /** 행을 누르면 그 영토를 고른다. 패널이 그 영토로 바뀐다 */
  selectedTerritory?: string;
  onPickTerritory: (id: string) => void;
  /** 「지도에서 보기」 */
  onGoToMap: (id: string) => void;
};

export default function EntityTab({
  layout,
  events,
  d,
  lastSeen,
  islandKey,
  onPickIsland,
  selectedTerritory,
  onPickTerritory,
  onGoToMap,
}: EntityTabProps) {
  const [sort, setSort] = useState<SortKey>("activity");
  const [asc, setAsc] = useState(false);

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
          // `MM-DD` 문자열이라 사전순이 곧 날짜순이다. 해가 바뀌면 틀리지만
          // 이 열은 한 해 안에서 견주는 용도다
          return lastSeen[t.territoryId] ?? "";
      }
    };
    return [...mine].sort((a, b) => {
      const x = val(a);
      const y = val(b);
      const c = typeof x === "string" ? x.localeCompare(y as string) : x - (y as number);
      return asc ? c : -c;
    });
  }, [layout, island, sort, asc, lastSeen]);

  if (!island) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-[14px] border border-edge bg-canvas text-[13px] text-label">
        이 기준일까지 올라온 사건이 없습니다
      </div>
    );
  }

  // 이 섬에 속한 영토 id. 30일 사건 수를 셀 때 쓴다
  const mine = new Set(rows.map((t) => t.territoryId));
  const live = rows.filter((t) => t.metrics.status === "활성");
  const avg = rows.length
    ? Math.round(rows.reduce((a, t) => a + t.metrics.activity, 0) / rows.length)
    : 0;
  // **평균 활동도에 30일 변화를 안 붙인다** (설계서 4.3.5, 판 1.2).
  // 활동도가 규모 원자료로 갈려 시점 간 차가 뜻을 잃었다
  const top = rows.length
    ? [...rows].sort((a, b) => b.metrics.activity - a.metrics.activity)[0]
    : null;

  const head = (key: SortKey, name: string, extra = "") => (
    <th
      className={"cursor-pointer py-s3 font-normal text-label " + extra}
      onClick={() => {
        if (sort === key) setAsc((v) => !v);
        else {
          setSort(key);
          setAsc(false);
        }
      }}
    >
      {name}
      {sort === key && <span className="ml-s1">{asc ? "▲" : "▼"}</span>}
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
              className={[
                "flex items-center gap-s2 rounded-[10px] px-s4 py-s2 text-[13px]",
                on ? "bg-selected font-semibold text-strong" : "text-label",
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
        <Kpi
          label="최근 30일 사건"
          value={String(
            countInWindow(events, d, 30, (e) => mine.has(e.territoryId)),
          )}
          note="지난 30일"
        />
        <Kpi
          label="최고 활동도"
          value={top ? String(top.metrics.activity) : "—"}
          note={top?.name ?? ""}
        />
      </div>

      <div className="shrink-0 overflow-hidden rounded-[14px] border border-edge">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-divider bg-panel text-left text-[12px]">
              <th className="w-[48px] py-s3 pl-s5 font-normal text-label">#</th>
              <th className="py-s3 font-normal text-label">엔티티</th>
              {head("activity", "활동도", "w-[220px]")}
              {head("delta", "30일", "w-[80px]")}
              <th className="w-[92px] py-s3 font-normal text-label">상태</th>
              {head("events", "사건", "w-[80px]")}
              {head("lastSeen", "최근 관측", "w-[100px]")}
              <th className="w-[110px] py-s3 pr-s5" />
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
                  className={[
                    "cursor-pointer border-b border-divider last:border-0",
                    on ? "bg-row-selected" : "bg-panel",
                  ].join(" ")}
                >
                  <td className="py-s4 pl-s5 tabular-nums text-label">{k + 1}</td>
                  <td className="py-s4">
                    <span className="flex items-center gap-s3">
                      <span
                        aria-hidden
                        className="size-[8px] shrink-0 rounded-full"
                        style={{
                          background: `var(--t-island-${t.token}-legend, var(--t-island-${t.token}))`,
                        }}
                      />
                      <span
                        className={
                          on ? "font-semibold text-strong" : "text-body"
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
                  <td className="py-s4 pr-s5 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onGoToMap(t.territoryId);
                      }}
                      className="rounded-[8px] border border-edge px-s3 py-[3px] text-[11px] text-label"
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

      <p className="shrink-0 rounded-[14px] border border-edge bg-card px-s5 py-s4 text-[12px] text-label">
        최근 주요 이벤트는 사건 제목이 있어야 만들 수 있습니다. 지금 사건에는
        게시일과 검증 판정만 있습니다.
      </p>
    </div>
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
