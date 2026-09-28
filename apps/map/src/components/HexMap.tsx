/**
 * 육각 지도 SVG.
 *
 * **칸을 하나씩 그리지 않고 영토 단위로 묶어 그린다.** 400칸을 각각 `<polygon>`
 * 으로 두면 노드가 400개가 되고, 호버·선택 때마다 전부 다시 칠해진다. 영토
 * 하나가 `<path>` 하나(그 영토 칸을 다 담은 단일 경로)라 노드가 열 몇 개로 준다.
 *
 * 칸 사이 경계선은 그 경로 안에 육각 테두리를 같이 그려 낸다 — 채움과 테두리를
 * 한 경로에 담으면 칸 경계가 안 보이므로, 채움용 경로와 격자용 경로를 나눈다.
 */

import { useState } from "react";
import { cellToXY, hexPoints } from "@/lib/hex";
import type { MapLayout, TerritoryShape } from "@/lib/layout";
import { CONF_DASH, KIND_NAME, type RelView } from "@/lib/relations";

/** 칸 하나의 육각 경로 */
function hexPath(col: number, row: number, size: number): string {
  const c = cellToXY(col, row, size);
  const pts = hexPoints(c.x, c.y, size);
  return `M${pts.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join("L")}Z`;
}

/** 영토가 가진 칸을 다 담은 하나의 경로 */
function cellsPath(t: TerritoryShape, size: number): string {
  return t.cells.map(([c, r]) => hexPath(c, r, size)).join("");
}

/**
 * 떠오른 영토의 입체 (설계서 4.2.3 「영토가 떠오르고」, 피그마 ⑦-11b · ⑦-3).
 *
 * 윗면을 `LIFT` 만큼 올리고, 같은 칸을 `DEPTH` 만큼 내려 옆면 색으로 먼저 깐다.
 * 둘 사이로 옆면이 드러난다. 피그마 ⑦-11b 에서 옆면 두께가 칸 반지름의 절반쯤
 * (Qilin 칸 반지름 21px 에 옆면 11~13px)이라 합을 5 로 둔다 — viewBox 칸 반지름이
 * 10 이다 (`layout.ts` HEX). 윗면만 올리면 옆면이 얇아 입체로 안 읽히고, 옆면만
 * 내리면 아래 칸을 너무 덮는다
 */
const LIFT = 2;
const DEPTH = 3;

/**
 * 알약 폭을 재려고 글자 너비를 어림한다.
 *
 * SVG 는 글자가 그려지기 전에는 실제 폭을 모른다. 한글은 글꼴 크기만큼 넓고
 * 라틴 글자는 그 60% 쯤이라 글자 수로만 세면 「랜섬웨어 공지 채널」 같은
 * 이름이 알약 밖으로 나간다. 두 가지를 따로 센다.
 */
function textWidth(s: string, fontSize: number): number {
  let w = 0;
  for (const ch of s) w += /[가-힣ㄱ-ㆎ]/.test(ch) ? 1 : 0.58;
  return w * fontSize;
}

/**
 * 이름표를 달 영토를 고른다 — **섬마다 칸이 많은 둘까지**.
 *
 * 전부 달면 작은 영토의 이름표가 서로 겹쳐 글자가 안 읽힌다. 피그마 `⑦-1` 도
 * 섬마다 둘씩만 달려 있다. 나머지 이름은 호버 툴팁과 패널이 말해 준다.
 *
 * **고른 섬은 넷까지 보여 준다.** 피그마 `⑦-2 섬 선택 (포럼)` 이 그렇다.
 * 다른 섬이 흐려져 자리가 넉넉해지므로 더 달아도 안 겹친다.
 */
function pickLabels(
  layout: MapLayout,
  selectedIsland?: string,
): TerritoryShape[] {
  const byIsland = new Map<string, TerritoryShape[]>();
  for (const t of layout.territories) {
    const list = byIsland.get(t.islandKey) ?? [];
    list.push(t);
    byIsland.set(t.islandKey, list);
  }
  const out: TerritoryShape[] = [];
  for (const [key, list] of byIsland) {
    const n = key === selectedIsland ? 4 : 2;
    out.push(
      ...[...list].sort((a, b) => b.cells.length - a.cells.length).slice(0, n),
    );
  }
  return out;
}

export type HexMapProps = {
  layout: MapLayout;
  /**
   * 그릴 틀. 없으면 `layout.viewBox`(그 분기에 그려진 칸에 맞춘 틀). 지도 탭 · 타임라인은
   * 모든 분기를 합친 크기 틀(`centerBox`)을 넘겨 분기마다 축척이 같다 (G-10 묶음 4)
   */
  viewBox?: string;
  /** 고른 영토. 있으면 그 영토만 진하고 나머지는 흐리다 (설계서 4.2.3) */
  selectedTerritory?: string;
  /** 고른 섬. 그 섬 전체가 진하다 */
  selectedIsland?: string;
  /** 마우스를 올린 영토. 진하게 칠한다 (설계서 4.2.3 「영토 진하게」) */
  hovered?: string | null;
  onHoverTerritory?: (id: string | null) => void;
  /**
   * 진하게 남길 영토. 영토를 고르면 그 영토와 관계로 이어진 영토다
   * (설계서 4.2.3 「연결된 영토만 표시 중」). 없으면 위 두 값으로 가른다.
   * **이 영토들은 떠오른다** — 피그마 ⑦-11b · ⑦-3 에서 고른 영토와 이어진 영토가
   * 같이 입체로 떠 있다
   */
  lit?: ReadonlySet<string>;
  /** 떠오르게 할 영토. [연결] 행을 고르면 상대 영토도 뜬다 (4.3.3) */
  raised?: ReadonlySet<string>;
  /** 이어진 섬. 여기 없는 섬은 이름표와 번짐을 흐리게 한다 (4.2.3 「연결 없는 섬은 흐리게」) */
  litIslands?: ReadonlySet<string>;
  /** 그릴 관계선. 영토를 골랐을 때만 온다 */
  lines?: readonly RelView[];
};

/**
 * 관계선 곡선. 두 영토 이름표 자리를 잇고 가운데를 옆으로 민다.
 *
 * 같은 두 영토 사이에 관계가 여럿이면(종류가 다르면 관계도 다르다) `k` 번째
 * 선을 조금씩 더 밀어 겹치지 않게 한다. 라벨은 곡선의 한가운데(t = 0.5)에 앉는다.
 */
function curve(
  a: { x: number; y: number },
  b: { x: number; y: number },
  k: number,
): { d: string; mid: { x: number; y: number } } {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const bend = len * 0.12 + k * 22;
  const cx = mx - (dy / len) * bend;
  const cy = my + (dx / len) * bend;
  return {
    d: `M${a.x.toFixed(1)},${a.y.toFixed(1)}Q${cx.toFixed(1)},${cy.toFixed(1)} ${b.x.toFixed(1)},${b.y.toFixed(1)}`,
    mid: { x: 0.25 * a.x + 0.5 * cx + 0.25 * b.x, y: 0.25 * a.y + 0.5 * cy + 0.25 * b.y },
  };
}

/**
 * 지도 위 선의 점선 간격. 범례(`CONF_DASH`)는 화면 픽셀 기준인데 지도는
 * viewBox 단위라(칸 반지름 10) 그대로 쓰면 점이 너무 굵다. 줄여서 쓴다
 */
function mapDash(dash: string): string | undefined {
  if (!dash) return undefined;
  return dash
    .split(" ")
    .map((n) => String(Number(n) * 0.6))
    .join(" ");
}

/**
 * **고르는 일은 여기서 안 한다.** 각 도형에 `data-pick` 과 `data-id` 만 달고
 * `MapCanvas` 가 `pointerup` 한 곳에서 판정한다. 캔버스가 드래그 때문에
 * 포인터를 캡처하는데, 캡처 중에는 `click` 이 캡처한 쪽으로 가 버려서
 * 도형에 건 `onClick` 이 안 불린다.
 */
export default function HexMap({
  layout,
  viewBox,
  selectedTerritory,
  selectedIsland,
  hovered,
  onHoverTerritory,
  lit,
  raised,
  litIslands,
  lines = [],
}: HexMapProps) {
  const hasSelection = Boolean(selectedTerritory || selectedIsland);
  /**
   * 누를 수 있는 지도인가. 고르기는 `MapCanvas` 가 받으므로 마우스 올림을 받는 쪽(=캔버스 안)만
   * 손가락 커서를 준다 — 전에는 타임라인 지도처럼 눌러도 아무 일이 없는 자리도 손가락이었다
   */
  const interactive = Boolean(onHoverTerritory);
  const pointer = interactive ? "cursor-pointer" : "";
  // 마우스를 올린 섬 이름표. 테두리를 섬 색으로 바꾼다 (2026-09-28 코드 분석 — hover 가 없었다)
  const [hoverIsland, setHoverIsland] = useState<string | null>(null);

  /** 떠오르는가 — 고른 영토, 이어진 영토, [연결] 행의 상대 영토 */
  const isUp = (t: TerritoryShape) =>
    t.territoryId === selectedTerritory ||
    Boolean(lit?.has(t.territoryId)) ||
    Boolean(raised?.has(t.territoryId));
  const flat = layout.territories.filter((t) => !isUp(t));
  // 고른 영토를 맨 뒤에 그린다. 떠오른 이웃과 맞닿은 테두리가 고른 쪽 색으로 남는다
  const up = layout.territories
    .filter(isUp)
    .sort(
      (a, b) =>
        Number(a.territoryId === selectedTerritory) -
        Number(b.territoryId === selectedTerritory),
    );
  const hoveredFlat = flat.find((t) => t.territoryId === hovered);
  /** 이름표와 관계선 끝 자리. 떠오른 영토는 윗면이 올라간 만큼 같이 올린다 */
  const anchor = (t: TerritoryShape) =>
    isUp(t) ? { x: t.label.x, y: t.label.y - LIFT } : t.label;
  const hoverProps = (id: string) => ({
    onMouseEnter: () => onHoverTerritory?.(id),
    onMouseLeave: () => onHoverTerritory?.(null),
  });

  /** 고른 것이 있으면 나머지는 흐리다. 없으면 다 같은 진하기다 */
  const dim = (t: TerritoryShape) => {
    if (lit) return !lit.has(t.territoryId);
    if (!hasSelection) return false;
    if (selectedTerritory) return t.territoryId !== selectedTerritory;
    return t.islandKey !== selectedIsland;
  };
  const dimIsland = (key: string) => (litIslands ? !litIslands.has(key) : false);

  // 이름표는 섬마다 둘씩이다. 관계로 이어진 영토는 그 밖이어도 이름을 단다 —
  // 선 끝에 이름이 없으면 어디로 이어졌는지 모른다 (피그마 ⑦-3)
  const picked = pickLabels(layout, selectedIsland);
  const labelled = [
    ...picked,
    ...layout.territories.filter((t) => lit?.has(t.territoryId) && !picked.includes(t)),
  ];

  const byId = new Map(layout.territories.map((t) => [t.territoryId, t]));
  const pairSeen = new Map<string, number>();
  const drawn = lines.flatMap((v) => {
    const a = byId.get(v.rel.from);
    const b = byId.get(v.rel.to);
    if (!a || !b) return [];
    const key = [v.rel.from, v.rel.to].sort().join("|");
    const k = pairSeen.get(key) ?? 0;
    pairSeen.set(key, k + 1);
    return [{ v, ...curve(anchor(a), anchor(b), k) }];
  });

  return (
    <svg
      viewBox={viewBox ?? layout.viewBox}
      className="size-full"
      role="img"
      aria-label="다크웹 섬 지도"
    >
      <defs>
        {/* 섬마다 은은한 번짐. 피그마에서 섬 둘레가 제 색으로 빛난다 */}
        {layout.islands.map((i) => (
          <filter
            key={i.islandKey}
            id={`glow-${i.token}`}
            x="-25%"
            y="-25%"
            width="150%"
            height="150%"
          >
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        ))}
        {/* 떠오른 영토 아래 그림자. 피그마 ⑦-11b 에서 떠오른 덩어리 아래가 어둡다 */}
        <filter id="raise-shadow" x="-10%" y="-10%" width="120%" height="130%">
          <feDropShadow dx={0} dy={2.5} stdDeviation={2} floodOpacity={0.45} />
        </filter>
      </defs>

      {/* 1층 — 번짐. 섬 테두리를 제 색으로 흐리게 한 번 더 그린다 */}
      <g aria-hidden>
        {layout.islands.map((i) => (
          <path
            key={i.islandKey}
            d={i.outline}
            fill="none"
            stroke={`var(--t-island-${i.token})`}
            strokeWidth={6}
            opacity={dimIsland(i.islandKey) ? 0.08 : 0.28}
            filter={`url(#glow-${i.token})`}
          />
        ))}
      </g>

      {/*
        2층 — 영토 채움. 이것이 지도의 본체다. 떠오른 영토는 3층이 그린다.
        흐린 칸은 섬마다 정해진 흐림색으로 불투명하게 칠한다 (피그마 ⑦-11b · ⑦-3 ·
        ⑦-10b, `tokens.css` 「흐린 칸」). 전에는 섬 색을 25% 로 깔아 바탕이 비쳤다
      */}
      <g>
        {flat.map((t) => (
          <path
            key={t.territoryId}
            data-pick="territory"
            data-id={t.territoryId}
            d={cellsPath(t, layout.size)}
            fill={dim(t) ? `var(--t-island-${t.token}-dim)` : `var(--t-island-${t.token})`}
            stroke="var(--t-border-hex)"
            strokeWidth={1}
            className={`${pointer} transition-colors`}
            {...hoverProps(t.territoryId)}
          />
        ))}
        {/*
          마우스를 올린 영토 (설계서 4.2.3 「영토 진하게」, 컴포넌트 시트 `DW/Hex v2`
          Hover — 한 단계 진한 채움에 옆면 색 테두리). 흐려진 영토도 올리면 진하다.

          **제자리 경로의 색을 바꾸지 않고 위에 한 겹 덮는다.** 이웃 영토가 뒤에
          그려져 테두리 반쪽을 덮기 때문이다. 덮는 겹은 포인터를 안 받는다 — 받으면
          올린 순간 아래 경로에서 `mouseleave` 가 나서 호버가 깜박인다
        */}
        {hoveredFlat && (
          <path
            aria-hidden
            d={cellsPath(hoveredFlat, layout.size)}
            fill={`var(--t-island-${hoveredFlat.token}-hover)`}
            stroke="var(--t-hex-hover-edge)"
            strokeWidth={1.4}
            className="pointer-events-none"
          />
        )}
      </g>

      {/*
        3층 — 떠오른 영토 (설계서 4.2.3 · 4.3.3, 피그마 ⑦-11b · ⑦-3, `DW/Hex v2`
        Selected · Linked). 고른 영토와 이어진 영토, [연결] 행의 상대 영토다.

        **옆면을 다 깐 뒤 윗면을 다 올린다.** 떠오른 영토끼리 맞닿으면 위쪽 영토의
        옆면이 아래쪽 영토 윗면을 덮지 않아야 한다. 고른 영토의 윗면은 마우스를
        올린 것처럼 한 단계 진하다 — 시트에서 Selected 윗면이 Hover 색이다.
        클릭은 두 겹 다 받는다. 옆면도 그 영토로 보이기 때문이다
      */}
      {up.length > 0 && (
        <g>
          <g filter="url(#raise-shadow)">
            {up.map((t) => (
              <path
                key={t.territoryId}
                data-pick="territory"
                data-id={t.territoryId}
                d={cellsPath(t, layout.size)}
                transform={`translate(0 ${DEPTH})`}
                fill={`var(--t-island-${t.token}-side)`}
                stroke={`var(--t-island-${t.token}-side)`}
                strokeWidth={1}
                className={pointer}
                {...hoverProps(t.territoryId)}
              />
            ))}
          </g>
          {up.map((t) => (
            <path
              key={t.territoryId}
              data-pick="territory"
              data-id={t.territoryId}
              d={cellsPath(t, layout.size)}
              transform={`translate(0 ${-LIFT})`}
              // 마우스를 올리면 밝아지고, 고른 영토는 밝은 윤곽선으로 이어진 영토와 가른다
              // (2026-09-28 최현서 6번 · 코드 분석 — 전에는 고른 것과 이어진 것의 윗면이 거의 같았다)
              fill={t.territoryId === hovered ? `var(--t-island-${t.token}-hover)` : `var(--t-island-${t.token})`}
              stroke={
                t.territoryId === selectedTerritory
                  ? "var(--t-hex-selected-edge)"
                  : t.territoryId === hovered
                    ? "var(--t-hex-hover-edge)"
                    : `var(--t-island-${t.token}-side)`
              }
              strokeWidth={t.territoryId === selectedTerritory ? 2 : t.territoryId === hovered ? 1.4 : 1}
              className={pointer}
              {...hoverProps(t.territoryId)}
            />
          ))}
        </g>
      )}

      {/*
        관계선 층. 영토를 골랐을 때 그 영토의 선만 그린다 (설계서 4.2.3). 피그마
        ⑦-3 처럼 옅은 회색 선에 신뢰도별 모양이고, 라벨은 「종류 건수」 알약이다.
        클릭은 안 받는다 — 선 위를 눌러도 아래 영토가 골라진다
      */}
      {drawn.length > 0 && (
        <g aria-hidden className="pointer-events-none">
          {drawn.map(({ v, d }) => (
            <path
              key={v.rel.id}
              d={d}
              fill="none"
              stroke="var(--t-text-body)"
              strokeWidth={1.1}
              strokeDasharray={mapDash(CONF_DASH[v.rel.confidence])}
              strokeLinecap="round"
              opacity={0.85}
            />
          ))}
          {drawn.map(({ v, mid }) => {
            const name = KIND_NAME[v.rel.kind];
            const w = textWidth(name, 8) + textWidth(`${v.count}건`, 7) + 18;
            return (
              <g key={`l-${v.rel.id}`} transform={`translate(${mid.x - w / 2} ${mid.y - 8})`}>
                <rect width={w} height={16} rx={4} fill="var(--t-surface-panel)" stroke="var(--t-border-card)" strokeWidth={0.8} />
                <text x={7} y={11} fontSize={8} fontWeight={600}>
                  <tspan fill="var(--t-text-title)">{name}</tspan>
                  <tspan dx={4} fontSize={7} fill="var(--t-text-label)">
                    {v.count}건
                  </tspan>
                </text>
              </g>
            );
          })}
        </g>
      )}

      {/* 4층 — 섬 이름표. 덩어리 위에 알약으로 뜬다 */}
      <g>
        {layout.islands.map((i) => {
          const w = textWidth(i.name, 9) + textWidth(`${i.eventCount}건`, 8) + 30;
          return (
            <g
              key={i.islandKey}
              data-pick="island"
              data-id={i.islandKey}
              transform={`translate(${i.label.x - w / 2} ${i.label.y - 9})`}
              opacity={dimIsland(i.islandKey) ? 0.4 : 1}
              className={pointer}
              onMouseEnter={interactive ? () => setHoverIsland(i.islandKey) : undefined}
              onMouseLeave={interactive ? () => setHoverIsland(null) : undefined}
            >
              <rect
                width={w}
                height={18}
                rx={9}
                fill={hoverIsland === i.islandKey ? "var(--t-surface-track)" : "var(--t-surface-panel)"}
                stroke={hoverIsland === i.islandKey ? `var(--t-island-${i.token})` : "var(--t-border-card)"}
              />
              <circle cx={11} cy={9} r={3} fill={`var(--t-island-${i.token})`} />
              <text x={19} y={12.5} fontSize={9} fontWeight={600}>
                <tspan fill="var(--t-text-strong)">{i.name}</tspan>
                <tspan dx={5} fontSize={8} fill="var(--t-text-label)">
                  {i.eventCount}건
                </tspan>
              </text>
            </g>
          );
        })}
      </g>

      {/*
        5층 — 영토 이름표. 덩어리 안쪽에 알약으로 앉는다.

        **`pointer-events: none` 이 꼭 있어야 한다.** 없으면 이름표가 덮은
        자리에서 클릭이 이름표로 가고, 그 `<g>` 에는 `data-pick` 이 없어서
        「빈 곳을 눌렀다」로 읽혀 선택이 풀린다. 이름표는 보여 주기만 한다
      */}
      <g aria-hidden className="pointer-events-none">
        {labelled
          .filter((t) => !dim(t))
          .map((t) => {
            const w = textWidth(t.name, 8) + 12;
            const at = anchor(t);
            return (
              <g
                key={t.territoryId}
                transform={`translate(${at.x - w / 2} ${at.y - 7})`}
              >
                <rect
                  width={w}
                  height={14}
                  rx={4}
                  fill="var(--t-surface-app)"
                  opacity={0.88}
                />
                <text
                  x={w / 2}
                  y={10}
                  fontSize={8}
                  fontWeight={600}
                  textAnchor="middle"
                  fill="var(--t-text-title)"
                >
                  {t.name}
                </text>
              </g>
            );
          })}
      </g>
    </svg>
  );
}
