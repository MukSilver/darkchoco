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

import { Fragment } from "react";

import { cellToXY, hexPoints } from "@/lib/hex";
import type { MapLayout, TerritoryShape } from "@/lib/layout";

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
  /** 고른 영토. 있으면 그 영토만 진하고 나머지는 흐리다 (설계서 4.2.3) */
  selectedTerritory?: string;
  /** 고른 섬. 그 섬 전체가 진하다 */
  selectedIsland?: string;
  onHoverTerritory?: (id: string | null) => void;
};

/**
 * **고르는 일은 여기서 안 한다.** 각 도형에 `data-pick` 과 `data-id` 만 달고
 * `MapCanvas` 가 `pointerup` 한 곳에서 판정한다. 캔버스가 드래그 때문에
 * 포인터를 캡처하는데, 캡처 중에는 `click` 이 캡처한 쪽으로 가 버려서
 * 도형에 건 `onClick` 이 안 불린다.
 */
export default function HexMap({
  layout,
  selectedTerritory,
  selectedIsland,
  onHoverTerritory,
}: HexMapProps) {
  const hasSelection = Boolean(selectedTerritory || selectedIsland);
  const labelled = pickLabels(layout, selectedIsland);

  /** 고른 것이 있으면 나머지는 흐리다. 없으면 다 같은 진하기다 */
  const dim = (t: TerritoryShape) => {
    if (!hasSelection) return false;
    if (selectedTerritory) return t.territoryId !== selectedTerritory;
    return t.islandKey !== selectedIsland;
  };

  return (
    <svg
      viewBox={layout.viewBox}
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
            opacity={0.28}
            filter={`url(#glow-${i.token})`}
          />
        ))}
      </g>

      {/* 2층 — 영토 채움. 이것이 지도의 본체다 */}
      <g>
        {layout.territories.map((t) => (
          <Fragment key={t.territoryId}>
            <path
              data-pick="territory"
              data-id={t.territoryId}
              d={cellsPath(t, layout.size)}
              fill={`var(--t-island-${t.token})`}
              stroke="var(--t-border-hex)"
              strokeWidth={1}
              opacity={dim(t) ? 0.25 : 1}
              className="cursor-pointer transition-opacity"
              onMouseEnter={() => onHoverTerritory?.(t.territoryId)}
              onMouseLeave={() => onHoverTerritory?.(null)}
            />
          </Fragment>
        ))}
      </g>

      {/* 3층 — 고른 영토의 테두리를 한 번 더 그어 떠오르게 한다 */}
      {selectedTerritory && (
        <g aria-hidden>
          {layout.territories
            .filter((t) => t.territoryId === selectedTerritory)
            .map((t) => (
              <path
                key={t.territoryId}
                d={t.outline}
                fill="none"
                stroke="var(--t-text-title)"
                strokeWidth={2}
              />
            ))}
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
              className="cursor-pointer"
            >
              <rect
                width={w}
                height={18}
                rx={9}
                fill="var(--t-surface-panel)"
                stroke="var(--t-border-card)"
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
            return (
              <g
                key={t.territoryId}
                transform={`translate(${t.label.x - w / 2} ${t.label.y - 7})`}
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
