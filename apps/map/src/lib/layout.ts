/**
 * 계산 결과를 그릴 도형으로 바꾼다.
 *
 * `score.ts` 는 「영토가 몇 칸인가」까지만 낸다. `hex.ts` 는 「칸 수를 주면
 * 어디에 놓을까」만 안다. 둘을 붙여 화면이 바로 그릴 수 있는 모양으로 내는
 * 것이 이 파일이다.
 *
 * **여기서 숫자를 새로 만들지 않는다.** 칸 수는 `score.ts` 가 설계서 3.4 대로
 * 낸 것을 그대로 쓴다. `verify.mjs` 가 「칸 수 = 사고 수」를 자동으로 잡는데,
 * 여기서 칸 수를 손보면 그 검사가 무의미해진다.
 */

import type { Cell, Point } from "./hex.ts";
import {
  SQ3,
  cellToXY,
  growIslands,
  labelAnchor,
  outline,
  splitTerritories,
} from "./hex.ts";
import { islandToken } from "./islands.ts";
import type { IslandMetrics, MapResult, TerritoryMetrics } from "./score.ts";
import type { Island, IslandCode, Territory, Web } from "./types.ts";

/** 육각 하나의 반지름. viewBox 안의 값이라 화면 크기와 무관하다 */
export const HEX = 10;

export type IslandShape = {
  islandKey: string;
  islandId: string;
  name: string;
  /** `--t-island-<token>` 으로 색을 찾는다 */
  token: string;
  cells: Cell[];
  /** 섬 테두리 `path` 의 `d` */
  outline: string;
  /** 섬 이름표를 앉힐 자리. 덩어리 위쪽 바깥이다 */
  label: Point;
  eventCount: number;
  metrics: IslandMetrics;
};

export type TerritoryShape = {
  territoryId: string;
  name: string;
  /** 같은 곳의 다른 표기. 검색이 이것으로도 찾는다 (설계서 4.2.2) */
  aliases: string[];
  islandKey: string;
  token: string;
  cells: Cell[];
  outline: string;
  /** 영토 이름표 자리. 덩어리 안쪽 깊은 곳이다 */
  label: Point;
  metrics: TerritoryMetrics;
};

export type MapLayout = {
  /** SVG `viewBox` 값 */
  viewBox: string;
  size: number;
  islands: IslandShape[];
  territories: TerritoryShape[];
};

/** 섬과 섬 사이에 비워 둘 칸 수 */
const GAP_COLS = 4;
const GAP_ROWS = 4;

/** 섬을 늘어놓는 열 수. 피그마 `⑦-1` 이 2열 × 2행이다 */
const GRID_COLS = 2;

/**
 * 섬 하나를 제자리에서 키우고, 왼쪽 위를 (0,0) 으로 당겨 놓는다.
 *
 * **섬을 한꺼번에 키우면 서로 맞닿는다.** `growIslands` 에 다섯을 같이 주면
 * 한 격자에서 동시에 자라 사이가 붙는다. 씨앗을 아무리 벌려도 랜섬웨어가
 * 207칸이라 결국 이웃과 만난다. 피그마 `⑦-1` 은 섬 넷이 확실히 떨어져 있고
 * 사이가 빈 격자라, 섬마다 따로 키운 뒤 통째로 옮기는 쪽이 맞다.
 */
function growAlone(key: string, need: number): Cell[] {
  const got = growIslands({ [key]: need })[key] ?? [];
  if (got.length === 0) return got;
  let minC = Infinity;
  let minR = Infinity;
  for (const [c, r] of got) {
    if (c < minC) minC = c;
    if (r < minR) minR = r;
  }
  // 행을 짝수만큼 옮긴다. odd-r 오프셋이라 홀수만큼 옮기면 칸이 반 칸
  // 어긋나 덩어리 모양이 틀어진다
  const dr = minR - (minR % 2);
  return got.map(([c, r]): Cell => [c - minC, r - dr]);
}

/** 칸 묶음의 폭과 높이 (칸 단위) */
function extent(cells: Cell[]): { w: number; h: number } {
  let maxC = 0;
  let maxR = 0;
  for (const [c, r] of cells) {
    if (c > maxC) maxC = c;
    if (r > maxR) maxR = r;
  }
  return { w: maxC + 1, h: maxR + 1 };
}

/** 칸 묶음을 통째로 옮긴다. 행 오프셋은 짝수여야 모양이 안 틀어진다 */
function shift(cells: Cell[], dc: number, dr: number): Cell[] {
  const even = dr - (dr % 2);
  return cells.map(([c, r]): Cell => [c + dc, r + even]);
}

export type LayoutInput = {
  islands: readonly Island[];
  territories: readonly Territory[];
  web: Web;
};

/**
 * 한 웹의 지도를 배치한다.
 *
 * @param result `computeMap` 결과. 칸 수가 여기서 온다
 */
export function layoutMap(input: LayoutInput, result: MapResult): MapLayout {
  const { web } = input;

  const islandMetrics = result.islands.filter(
    (i) => i.web === web && i.cells > 0,
  );

  /*
   * **섬 차례는 목록 차례다. 칸 수로 정렬하지 않는다.**
   *
   * 처음에는 큰 섬부터 좋은 자리를 주려고 칸 수로 세웠는데, 스냅샷 바로
   * 기준일을 옮기면 **섬이 화면을 가로질러 자리를 맞바꿨다.** 2026-06 에는
   * 텔레그램이 오른쪽 아래, 2026-09 에는 왼쪽 아래였다. 칸 수 순위가
   * 뒤집히면 자리도 뒤집힌 것이다.
   *
   * 설계서 4.2.5 는 스냅샷을 「같은 지도의 기준일별 차이」로 본다. 피그마
   * ⑦-1a 와 ⑦-1b 도 섬 자리는 같고 크기만 다르다. 재생으로 한 달씩 넘길 때
   * 섬이 튀면 무엇이 자란 것인지 눈으로 못 쫓는다.
   *
   * 목록 차례(설계서 2.3)로 고정하면 크기만 변한다. 열 폭과 행 높이가
   * 그 달의 섬 크기를 따르므로 자리가 조금씩은 움직이지만 맞바꾸지는 않는다.
   */
  const rank = new Map(input.islands.map((i, k) => [i.id as string, k]));
  const order = [...islandMetrics]
    .sort(
      (a, b) =>
        (rank.get(a.islandId) ?? 99) - (rank.get(b.islandId) ?? 99),
    )
    .map((i) => ({ key: i.islandKey, cells: i.cells }));

  // 섬마다 따로 키운 뒤 격자에 늘어놓는다
  const blobs = order.map((o) => {
    const cells = growAlone(o.key, o.cells);
    return { key: o.key, cells, ...extent(cells) };
  });

  // 열 폭과 행 높이는 그 줄에서 가장 큰 섬에 맞춘다. 섬이 서로 넘지 않는다
  const rowsOf = Math.ceil(blobs.length / GRID_COLS);
  const colW: number[] = Array(GRID_COLS).fill(0);
  const rowH: number[] = Array(rowsOf).fill(0);
  blobs.forEach((b, i) => {
    const cx = i % GRID_COLS;
    const cy = Math.floor(i / GRID_COLS);
    colW[cx] = Math.max(colW[cx], b.w);
    rowH[cy] = Math.max(rowH[cy], b.h);
  });

  const colX: number[] = [];
  const rowY: number[] = [];
  for (let i = 0, x = 0; i < GRID_COLS; i++) {
    colX.push(x);
    x += colW[i] + GAP_COLS;
  }
  for (let i = 0, y = 0; i < rowsOf; i++) {
    rowY.push(y);
    y += rowH[i] + GAP_ROWS;
  }

  const grown: Record<string, Cell[]> = {};
  blobs.forEach((b, i) => {
    const cx = i % GRID_COLS;
    const cy = Math.floor(i / GRID_COLS);
    // 제 칸 안에서 가운데로 놓는다. 작은 섬이 왼쪽 위에 몰리지 않는다
    const dc = colX[cx] + Math.floor((colW[cx] - b.w) / 2);
    const dr = rowY[cy] + Math.floor((rowH[cy] - b.h) / 2);
    grown[b.key] = shift(b.cells, dc, dr);
  });

  const nameOf = new Map(input.islands.map((i) => [i.id as string, i.name]));
  const byKey = new Map(islandMetrics.map((i) => [i.islandKey, i]));

  const islands: IslandShape[] = order.map((o) => {
    const m = byKey.get(o.key)!;
    const cells = grown[o.key] ?? [];
    return {
      islandKey: o.key,
      islandId: m.islandId,
      name: nameOf.get(m.islandId) ?? m.islandId,
      token: islandToken(m.islandId as IslandCode),
      cells,
      outline: outline(cells, HEX),
      label: labelTop(cells),
      eventCount: m.eventCount,
      metrics: m,
    };
  });

  const tName = new Map(input.territories.map((t) => [t.id, t.name]));
  const tAlias = new Map(input.territories.map((t) => [t.id, t.aliases ?? []]));
  const territories: TerritoryShape[] = [];

  for (const isl of islands) {
    const mine = result.territories.filter(
      (t) => t.islandKey === isl.islandKey && t.cells > 0,
    );
    const tw: Record<string, number> = {};
    for (const t of mine) tw[t.territoryId] = t.cells;

    const split = splitTerritories(isl.cells, tw);
    for (const t of mine) {
      const cells = split[t.territoryId] ?? [];
      if (cells.length === 0) continue;
      territories.push({
        territoryId: t.territoryId,
        name: tName.get(t.territoryId) ?? t.territoryId,
        aliases: tAlias.get(t.territoryId) ?? [],
        islandKey: isl.islandKey,
        token: isl.token,
        cells,
        outline: outline(cells, HEX),
        label: labelAnchor(cells, HEX),
        metrics: t,
      });
    }
  }

  return { viewBox: viewBoxOf(islands), size: HEX, islands, territories };
}

/**
 * 섬 이름표 자리 — 덩어리 **위쪽 바깥**이다.
 *
 * 영토 이름표(`labelAnchor`)와 다르다. 저것은 덩어리 안쪽 깊은 곳을 찾는데,
 * 섬 이름표는 피그마에서 섬 위에 떠 있는 알약이라 덩어리 밖이어야 한다.
 */
function labelTop(cells: Cell[]): Point {
  if (cells.length === 0) return { x: 0, y: 0 };
  let minY = Infinity;
  let sx = 0;
  let n = 0;
  for (const [c, r] of cells) {
    const p = cellToXY(c, r, HEX);
    if (p.y < minY) minY = p.y;
  }
  // 맨 윗줄에 있는 칸들의 가로 가운데
  for (const [c, r] of cells) {
    const p = cellToXY(c, r, HEX);
    if (p.y <= minY + HEX) {
      sx += p.x;
      n += 1;
    }
  }
  return { x: n ? sx / n : 0, y: minY - HEX * 2.2 };
}

/** 그려진 칸을 다 담는 `viewBox`. 이름표가 나갈 자리까지 여백을 둔다 */
function viewBoxOf(islands: IslandShape[]): string {
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const isl of islands) {
    for (const [c, r] of isl.cells) {
      const p = cellToXY(c, r, HEX);
      x0 = Math.min(x0, p.x);
      y0 = Math.min(y0, p.y);
      x1 = Math.max(x1, p.x);
      y1 = Math.max(y1, p.y);
    }
  }
  if (!Number.isFinite(x0)) return "0 0 100 100";
  // 육각 반쪽 + 섬 이름표가 들어갈 위쪽 여백
  const padX = HEX * SQ3;
  const padTop = HEX * 4;
  const padBottom = HEX * 2;
  return [
    x0 - padX,
    y0 - padTop,
    x1 - x0 + padX * 2,
    y1 - y0 + padTop + padBottom,
  ].join(" ");
}
