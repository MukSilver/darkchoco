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
  /**
   * 진하게 남길 영토. 영토를 고르면 그 영토와 관계로 이어진 영토다
   * (설계서 4.2.3 「연결된 영토만 표시 중」). 없으면 위 두 값으로 가른다
   */
  lit?: ReadonlySet<string>;
  /** 테두리를 그어 떠오르게 할 영토. [연결] 행을 고르면 상대 영토도 뜬다 (4.3.3) */
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
  selectedTerritory,
  selectedIsland,
  onHoverTerritory,
  lit,
  raised,
  litIslands,
  lines = [],
}: HexMapProps) {
  const hasSelection = Boolean(selectedTerritory || selectedIsland);

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
    return [{ v, ...curve(a.label, b.label, k) }];
  });

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
            opacity={dimIsland(i.islandKey) ? 0.08 : 0.28}
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

      {/*
        3층 — 고른 영토의 테두리를 한 번 더 그어 떠오르게 한다.
        [연결] 행을 고르면 상대 영토도 같이 뜬다 (설계서 4.3.3)
      */}
      {(selectedTerritory || raised) && (
        <g aria-hidden>
          {layout.territories
            .filter((t) => t.territoryId === selectedTerritory || raised?.has(t.territoryId))
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
