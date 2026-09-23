// ─────────────────────────────────────────────────────────────────────────
// 육각 격자 배치. 「설계서 3.4 헥사 칸 수」가 정한 칸 수를 실제 자리에 앉힌다.
//
// 점수 계산(설계서 3.2~3.5)은 여기 없다. 이 파일은 「섬 A 는 87칸, 섬 B 는 54칸」
// 까지 정해진 뒤부터를 맡는다. 계산과 배치를 갈라 두어야 가중치를 바꿔도
// (설계서 3.1 — 「가중치와 전체 칸 수는 제안값」) 배치 코드를 안 건드린다.
//
// 순수 계산만 한다. DOM·React·전역 상태를 건드리지 않고 난수도 쓰지 않는다.
// 같은 입력이면 같은 출력이라야 기준일을 옮겨 다시 그렸을 때 섬이 커진 것이
// 데이터 때문인지 배치가 흔들린 것인지 구분된다.
// (설계서 3.4 — 「기준일을 옮기면 그 날짜까지의 사건으로 다시 계산」)
//
// 좌표는 두 겹이다.   격자 (col,row)  →  화면 (x,y)
// 뾰족 위(pointy-top) 육각을 odd-r 오프셋으로 놓는다. 홀수 행이 오른쪽으로 반 칸
// 밀린다. 열 간격은 √3·size, 행 간격은 1.5·size 다.
//
// 배치 규칙은 옛 지도(dcsite 의 assets/hex.js · assets/hexcanvas.js ·
// map3d/index.html)에서 옮겨 왔다. 옮기면서 달라진 세 곳은 growIslands,
// wobble, cornerLattice 주석에 각각 적어 두었다.
// ─────────────────────────────────────────────────────────────────────────

/** 격자 칸 하나. `[col, row]` — odd-r 오프셋 좌표다. */
export type Cell = [number, number];

/** 화면 좌표 한 점. */
export type Point = { x: number; y: number };

export const SQ3 = Math.sqrt(3);

// ── 좌표 변환 ─────────────────────────────────────────────────────────────

/**
 * 격자 칸의 한가운데를 화면 좌표로 옮긴다. 뾰족 위 · odd-r 오프셋.
 *
 * `row & 1` 로 홀수 행을 가린다. `row % 2` 를 쓰면 음수 행에서 −1 이 나와
 * 밀림 방향이 뒤집힌다. 격자는 0 부터 시작하지만 xyToCell 은 화면 밖(음수 행)도
 * 받으므로 둘이 같은 식을 써야 왕복이 맞는다.
 */
export function cellToXY(col: number, row: number, size: number): Point {
  return {
    x: size * SQ3 * (col + 0.5 * (row & 1)),
    y: size * 1.5 * row,
  };
}

/**
 * 화면 좌표에서 가장 가까운 칸을 찾는다. cellToXY 의 역이다.
 *
 * 육각은 사각형이 아니라서 나눗셈만으로는 어느 칸인지 갈리지 않는다.
 * 큐브 좌표 (q, r, s) 로 바꿔 셋을 각각 반올림한 뒤, 가장 많이 어긋난 축을
 * 나머지 둘에서 되계산한다 (q + r + s = 0 이라는 성질). 그래야 칸 경계에서
 * 이웃 칸으로 새지 않는다.
 */
export function xyToCell(x: number, y: number, size: number): { col: number; row: number } {
  const q = ((SQ3 / 3) * x - y / 3) / size;
  const r = ((2 / 3) * y) / size;
  const s = -q - r;

  let rq = Math.round(q);
  let rr = Math.round(r);
  const rs = Math.round(s);
  const dq = Math.abs(rq - q);
  const dr = Math.abs(rr - r);
  const ds = Math.abs(rs - s);

  if (dq > dr && dq > ds) rq = -rr - rs;
  else if (dr > ds) rr = -rq - rs;

  // `| 0` 으로 −0 을 0 으로 눌러 둔다. Math.round(-0.1) 은 −0 이고, 그대로 두면
  // 칸 열쇠가 "0,-0" 으로 찍혀 "0,0" 과 다른 칸이 된다. 화면 맨 윗줄 바로 위를
  // 가리켰을 때만 나는 일이라 눈에 잘 안 띈다.
  const row = rr | 0;
  // (row - (row & 1)) 은 항상 짝수라 `>> 1` 이 나눗셈과 정확히 같다.
  return { col: (rq + ((row - (row & 1)) >> 1)) | 0, row };
}

// 꼭짓점 여섯을 정수 격자로 센다. 각도 −30°, 30°, 90°, 150°, 210°, 270° 를
// [x 는 size·√3/2 단위, y 는 size/2 단위] 로 적은 것이다.
//   −30° → (cos, sin) = (+√3/2, −1/2) → (+1, −1)
// 실수 대신 정수로 두는 이유는 outline 에 적어 두었다.
const CORNER_U: readonly Cell[] = [
  [+1, -1], // 0  우상
  [+1, +1], // 1  우하
  [0, +2], // 2  아래 꼭짓점
  [-1, +1], // 3  좌하
  [-1, -1], // 4  좌상
  [0, -2], // 5  위 꼭짓점
];

/**
 * 육각 하나의 꼭짓점 여섯. (cx, cy) 는 화면 좌표로 찍은 한가운데다.
 *
 * 차례가 0 번 우상부터 시계 방향(화면은 y 가 아래로 간다)이고, 이 차례는
 * DIRS 의 모서리 번호와 짝이 맞다. k 번 모서리는 pts[k] → pts[(k+1)%6] 선분이다.
 * outline 이 그 짝을 그대로 쓰므로 둘 중 하나만 고치면 테두리가 어긋난다.
 */
export function hexPoints(cx: number, cy: number, size: number): Cell[] {
  const ux = (size * SQ3) / 2;
  const uy = size / 2;
  return CORNER_U.map(([dx, dy]): Cell => [cx + dx * ux, cy + dy * uy]);
}

// ── 격자 ─────────────────────────────────────────────────────────────────

// 요구 칸 수보다 격자를 넉넉히 잡는다. 딱 맞게 잡으면 섬들이 서로 막혀
// 둥글게 못 자라고 격자 테두리 모양 그대로 네모가 된다.
const FILL = 0.6;

// 뾰족 위 육각은 열 간격이 √3(≈1.73)·size, 행 간격이 1.5·size 다. 행이 더
// 촘촘하므로 칸 수를 같게 두면 화면에서 세로로 길쭉해진다. 열을 1.7 배 뽑아 맞춘다.
const ASPECT = 1.7;

/** 칸 수 총합에 맞는 격자 크기. 섬이 자랄 여백까지 얹어서 돌려준다. */
export function gridSize(total: number): { cols: number; rows: number } {
  if (!(total > 0)) return { cols: 1, rows: 1 };
  const cols = Math.max(1, Math.ceil(Math.sqrt((total / FILL) * ASPECT)));
  const rows = Math.max(1, Math.ceil(total / FILL / cols) + 2);
  return { cols, rows };
}

// 방향 여섯. [짝수 행 오프셋, 홀수 행 오프셋, 그 방향이 막는 모서리 번호]
const DIRS: readonly (readonly [Cell, Cell, number])[] = [
  [[+1, 0], [+1, 0], 0], // 동
  [[0, +1], [+1, +1], 1], // 남동
  [[-1, +1], [0, +1], 2], // 남서
  [[-1, 0], [-1, 0], 3], // 서
  [[-1, -1], [0, -1], 4], // 북서
  [[0, -1], [+1, -1], 5], // 북동
];

const key = (col: number, row: number): string => `${col},${row}`;

function neighbors(col: number, row: number): Cell[] {
  const out: Cell[] = [];
  for (const [ev, od] of DIRS) {
    const [dc, dr] = (row & 1) === 0 ? ev : od;
    out.push([col + dc, row + dr]);
  }
  return out;
}

function neighborsIn(col: number, row: number, cols: number, rows: number): Cell[] {
  return neighbors(col, row).filter(([c, r]) => c >= 0 && c < cols && r >= 0 && r < rows);
}

// ── 결정적 잡음 ───────────────────────────────────────────────────────────

/**
 * 해안선을 흔드는 잡음. −0.5 ~ +0.5.
 *
 * Math.random 을 쓰면 새로 그릴 때마다 섬 모양이 달라져 같은 지도로 안 보인다.
 * 칸 좌표를 해시해 「고정된 무작위」를 만든다.
 *
 * 옛 판은 곱셈을 그냥 `*` 로 했는데, h × 1274126177 이 2^53 을 넘겨 아래 비트가
 * 잘렸다. 결과는 그래도 같았지만 섞임이 나빠진다. Math.imul 로 32비트 곱을 쓴다.
 */
function wobble(col: number, row: number, salt: number): number {
  let h = salt | 0;
  h = (Math.imul(h, 31) + Math.imul(col, 2654435761)) | 0;
  h = (Math.imul(h, 31) + Math.imul(row, 40503)) | 0;
  h ^= h >>> 13;
  h = Math.imul(h, 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296 - 0.5;
}

// 거리를 잴 때 세로만 0.95 로 줄인다. 1.0 으로 두면 섬이 모두 정원이 되어
// 다섯 섬이 똑같이 생긴 동그라미로 보인다. 살짝 눌러야 서로 구분된다.
const SQUASH = 0.95;

// Math.sqrt 는 IEEE-754 가 결과를 한 값으로 못박지만 Math.hypot 은 정밀도가
// 구현에 맡겨져 있다. 배치가 런타임에 따라 달라지지 않게 sqrt 로 잰다.
function dist(ax: number, ay: number, bx: number, by: number): number {
  const dx = ax - bx;
  const dy = (ay - by) * SQUASH;
  return Math.sqrt(dx * dx + dy * dy);
}

/** id 순서에 기대지 않도록 (칸 수 내림차순, id 오름차순)으로 세운다. */
function demandOrder(want: Record<string, number>): { id: string; need: number }[] {
  return Object.keys(want)
    .map((id) => ({ id, need: Math.max(0, Math.floor(want[id] ?? 0)) }))
    .filter((o) => o.need > 0)
    .sort((a, b) => b.need - a.need || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}

// ── 섬 키우기 ─────────────────────────────────────────────────────────────

/**
 * 섬마다 씨앗을 흩어 놓는다. 가장 큰 섬을 한가운데, 나머지를 둘레에 고르게.
 *
 * 고정 표로 자리를 박아 두면 웹마다 있는 섬이 달라 한쪽으로 몰린다
 * (설계서 2.3 — 오픈웹에는 랜섬웨어·포럼이 없고 다크웹에는 코드 저장소가 없다).
 * 그래서 이번에 실제로 칸을 받은 섬만 놓는다.
 *
 * cos·sin 은 정밀도가 구현에 맡겨져 있지만 결과를 칸 번호로 반올림하므로
 * 마지막 자리 차이가 자리를 바꾸지 못한다.
 */
function defaultSeeds(order: { id: string; need: number }[], cols: number, rows: number): Record<string, Cell> {
  const cx = (cols - 1) / 2;
  const cy = (rows - 1) / 2;
  const R = Math.min(cols, rows * 1.5) * 0.3;
  const out: Record<string, Cell> = {};
  const used = new Set<string>();

  order.forEach((o, i) => {
    let col: number;
    let row: number;
    if (i === 0) {
      col = Math.round(cx);
      row = Math.round(cy);
    } else {
      // 시작 각도를 반 칸 틀어 두 웹의 지도가 서로 포개져 보이지 않게 한다.
      const th = ((i - 1) / Math.max(1, order.length - 1)) * Math.PI * 2 + Math.PI * 0.18;
      // 세로는 행 간격이 1.5 배 촘촘하므로 반지름을 1.5 로 나눠 원으로 보이게 한다.
      col = Math.round(cx + Math.cos(th) * R);
      row = Math.round(cy + (Math.sin(th) * R) / 1.5);
    }
    [col, row] = nudgeFree(clamp(col, 0, cols - 1), clamp(row, 0, rows - 1), cols, rows, used);
    used.add(key(col, row));
    out[o.id] = [col, row];
  });
  return out;
}

function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v;
}

/**
 * 씨앗이 겹치면 가까운 빈 칸으로 비킨다.
 *
 * 섬이 많으면 둘레 계산이 같은 칸을 두 번 집을 수 있다. 그대로 두면 한 섬이
 * 남의 씨앗에서 출발해 모양이 뒤엉킨다. 고리 모양으로 한 칸씩 넓혀 찾는다.
 */
function nudgeFree(col: number, row: number, cols: number, rows: number, used: Set<string>): Cell {
  if (!used.has(key(col, row))) return [col, row];
  for (let ring = 1; ring < cols + rows; ring++) {
    for (let dr = -ring; dr <= ring; dr++) {
      for (let dc = -ring; dc <= ring; dc++) {
        if (Math.max(Math.abs(dr), Math.abs(dc)) !== ring) continue;
        const c = col + dc;
        const r = row + dr;
        if (c < 0 || c >= cols || r < 0 || r >= rows) continue;
        if (!used.has(key(c, r))) return [c, r];
      }
    }
  }
  return [col, row];
}

type Growth = {
  id: string;
  need: number;
  idx: number;
  got: Cell[];
  front: Cell[];
  seen: Set<string>;
  sx: number;
  sy: number;
  cost: Map<string, number>;
};

/**
 * 섬마다 받을 칸 수를 주면 섬별 칸 집합을 돌려준다.
 *
 * **대륙을 순서대로 키우면 가장 큰 섬이 격자를 다 먹는다.** 설계서 3.4 의 실제
 * 계산에서 DarkForums 혼자 87칸(21.7%)이다. 큰 것부터 다 키우고 나면 작은 섬은
 * 가장자리로 밀려 지도에서 사라진다. 그래서 라운드로빈으로 **한 바퀴에 한 칸씩**
 * 동시에 키운다. 작은 섬도 제 씨앗 자리에서 제 칸을 받는다.
 *
 * 옛 growTogether 와 다른 곳이 하나 있다. 꺼낸 칸에 이미 임자가 있으면 옛 판은
 * 바로 다음 섬으로 넘어갔는데, 그러면 그 칸의 이웃이 큐에 안 들어가 섬이 장애물
 * 뒤에서 멈춰 버렸다. 임자가 있어도 이웃은 큐에 넣어 돌아 자라게 한다.
 *
 * @param want  섬 id → 받을 칸 수 (설계서 3.4 의 H(T) 를 섬 단위로 합한 값)
 * @param seeds 씨앗 자리. 안 주면 스스로 흩어 놓는다. 일부만 줘도 된다
 */
export function growIslands(
  want: Record<string, number>,
  seeds?: Record<string, [number, number]>,
): Record<string, Cell[]> {
  const out: Record<string, Cell[]> = {};
  for (const id of Object.keys(want)) out[id] = [];

  const order = demandOrder(want);
  if (order.length === 0) return out;

  const total = order.reduce((s, o) => s + o.need, 0);
  const { cols, rows } = gridSize(total);

  // 준 씨앗을 먼저 자리 잡고, 안 준 섬만 스스로 흩어 놓는다.
  const given: Record<string, Cell> = {};
  const taken = new Set<string>();
  const usedSeed = new Set<string>();
  for (const o of order) {
    const s = seeds?.[o.id];
    if (!s) continue;
    const [c, r] = nudgeFree(clamp(Math.round(s[0]), 0, cols - 1), clamp(Math.round(s[1]), 0, rows - 1), cols, rows, usedSeed);
    usedSeed.add(key(c, r));
    given[o.id] = [c, r];
  }
  const rest = order.filter((o) => !given[o.id]);
  const auto = defaultSeeds(rest, cols, rows);
  for (const o of rest) {
    const a = auto[o.id] ?? [0, 0];
    const [c, r] = nudgeFree(a[0], a[1], cols, rows, usedSeed);
    usedSeed.add(key(c, r));
    given[o.id] = [c, r];
  }

  const state: Growth[] = order.map((o, i) => {
    const seed = given[o.id] ?? [0, 0];
    const p = cellToXY(seed[0], seed[1], 1);
    return {
      id: o.id,
      need: o.need,
      idx: i,
      got: [],
      front: [seed],
      seen: new Set([key(seed[0], seed[1])]),
      sx: p.x,
      sy: p.y,
      cost: new Map(),
    };
  });

  // 씨앗에서 가까운 칸부터 먹되 잡음을 섞는다. 안 섞으면 섬이 정확한 원이 되어
  // 지도가 아니라 벤 다이어그램처럼 보인다. 잡음 폭을 거리에 비례시켜야
  // 씨앗 근처가 너덜거리지 않는다.
  const costOf = (g: Growth, c: number, r: number): number => {
    const k = key(c, r);
    const memo = g.cost.get(k);
    if (memo !== undefined) return memo;
    const p = cellToXY(c, r, 1);
    const d = dist(p.x, p.y, g.sx, g.sy);
    const v = d + wobble(c, r, g.idx * 977 + 13) * Math.max(1.6, d * 0.34);
    g.cost.set(k, v);
    return v;
  };

  // 같은 값일 때 순서가 흔들리지 않게 칸 번호로 한 번 더 가른다.
  const byCost = (g: Growth) => (a: Cell, b: Cell): number =>
    costOf(g, a[0], a[1]) - costOf(g, b[0], b[1]) || a[1] - b[1] || a[0] - b[0];

  let live = true;
  while (live) {
    live = false;
    for (const g of state) {
      if (g.got.length >= g.need || g.front.length === 0) continue;
      live = true;
      g.front.sort(byCost(g));
      const cur = g.front.shift();
      if (!cur) continue;
      const k = key(cur[0], cur[1]);
      if (!taken.has(k)) {
        taken.add(k);
        g.got.push(cur);
      }
      for (const nb of neighborsIn(cur[0], cur[1], cols, rows)) {
        const nk = key(nb[0], nb[1]);
        if (!g.seen.has(nk)) {
          g.seen.add(nk);
          g.front.push(nb);
        }
      }
    }
  }

  // 마지막 수단. 섬이 다른 섬에 완전히 둘러싸이면 자랄 자리를 잃는다. 그때만
  // 남은 빈 칸에서 씨앗에 가까운 것을 채워 「요청한 칸 수」를 지킨다. 붙어 있지
  // 않을 수 있으므로 여기까지 오는 일이 잦으면 격자를 키우는 쪽이 옳다.
  fillShortfall(state, taken, cols, rows);

  for (const g of state) out[g.id] = g.got;
  return out;
}

function fillShortfall(state: Growth[], taken: Set<string>, cols: number, rows: number): void {
  const short = state.filter((g) => g.got.length < g.need);
  if (short.length === 0) return;

  const free: Cell[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (!taken.has(key(c, r))) free.push([c, r]);
    }
  }

  for (const g of short) {
    const pool = free
      .filter(([c, r]) => !taken.has(key(c, r)))
      .map((cell) => {
        const p = cellToXY(cell[0], cell[1], 1);
        return { cell, d: dist(p.x, p.y, g.sx, g.sy) };
      })
      .sort((a, b) => a.d - b.d || a.cell[1] - b.cell[1] || a.cell[0] - b.cell[0]);
    for (const { cell } of pool) {
      if (g.got.length >= g.need) break;
      taken.add(key(cell[0], cell[1]));
      g.got.push(cell);
    }
  }
}

// ── 영토 나누기 ───────────────────────────────────────────────────────────

/**
 * 섬이 받은 칸을 영토들에게 비중대로 나눈다.
 *
 * **영토는 자기 섬 밖으로 나가면 안 된다.** 나가면 색이 같은 칸이 남의 섬에
 * 박혀 「섬 = 성격이 같은 영토의 묶음」(설계서 2.1)이 깨진다. allow 집합으로 막는다.
 *
 * 큰 영토부터 놓고, 씨앗은 **이미 찬 칸에서 가장 먼 빈 칸**으로 고른다. 그래야
 * 영토들이 섬 안에서 서로 밀어내며 골고루 퍼진다. 가운데부터 차례로 놓으면
 * 나중 영토가 초승달 모양으로 가장자리를 두른다.
 *
 * @param islandCells 그 섬이 받은 칸 (growIslands 의 결과 한 항목)
 * @param want        영토 id → 받을 칸 수 (설계서 3.4 의 H(T))
 */
export function splitTerritories(
  islandCells: [number, number][],
  want: Record<string, number>,
): Record<string, Cell[]> {
  const out: Record<string, Cell[]> = {};
  for (const id of Object.keys(want)) out[id] = [];

  const allow = new Set(islandCells.map(([c, r]) => key(c, r)));
  // 입력 차례에 기대지 않도록 칸도 한 번 세운다. 같은 칸 묶음이면 순서가 달라도
  // 같은 그림이 나와야 한다.
  const cells = [...islandCells].sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  const used = new Set<string>();

  for (const { id, need } of demandOrder(want)) {
    const free = cells.filter(([c, r]) => !used.has(key(c, r)));
    if (free.length === 0) continue;

    const seed = pickSeed(free, cells, used);
    const got = growWithin(seed, need, used, allow);
    for (const [c, r] of got) used.add(key(c, r));

    // 앞 영토가 섬을 갈라놓아 씨앗에서 못 닿는 주머니가 생길 수 있다.
    // 그때만 남은 칸에서 가까운 것을 채운다. 섬 밖으로는 여전히 안 나간다.
    if (got.length < need) {
      const seedXY = cellToXY(seed[0], seed[1], 1);
      const pool = cells
        .filter(([c, r]) => !used.has(key(c, r)))
        .map((cell) => {
          const p = cellToXY(cell[0], cell[1], 1);
          return { cell, d: dist(p.x, p.y, seedXY.x, seedXY.y) };
        })
        .sort((a, b) => a.d - b.d || a.cell[1] - b.cell[1] || a.cell[0] - b.cell[0]);
      for (const { cell } of pool) {
        if (got.length >= need) break;
        used.add(key(cell[0], cell[1]));
        got.push(cell);
      }
    }
    out[id] = got;
  }
  return out;
}

/** 이미 찬 칸에서 가장 먼 빈 칸. 아직 아무것도 안 찼으면 한가운데 것. */
function pickSeed(free: Cell[], cells: Cell[], used: Set<string>): Cell {
  const fallback = free[Math.floor(free.length / 2)] ?? free[0];
  if (used.size === 0) return fallback as Cell;

  const usedXY = cells.filter(([c, r]) => used.has(key(c, r))).map(([c, r]) => cellToXY(c, r, 1));
  let best: Cell = free[0] as Cell;
  let bestD = -1;
  for (const cell of free) {
    const p = cellToXY(cell[0], cell[1], 1);
    let d = Infinity;
    for (const u of usedXY) d = Math.min(d, dist(p.x, p.y, u.x, u.y));
    if (d > bestD) {
      bestD = d;
      best = cell;
    }
  }
  return best;
}

/**
 * 씨앗에서 이웃으로 번지며 count 칸을 먹는다. allow 밖으로는 안 나간다.
 *
 * 이미 임자가 있는 칸이라도 이웃은 큐에 넣는다. 그래야 장애물을 돌아 자란다.
 */
function growWithin(seed: Cell, count: number, used: Set<string>, allow: Set<string>): Cell[] {
  const got: Cell[] = [];
  if (count <= 0) return got;

  const s = cellToXY(seed[0], seed[1], 1);
  const memo = new Map<string, number>();
  const costOf = (c: number, r: number): number => {
    const k = key(c, r);
    const m = memo.get(k);
    if (m !== undefined) return m;
    const p = cellToXY(c, r, 1);
    const v = dist(p.x, p.y, s.x, s.y);
    memo.set(k, v);
    return v;
  };

  const front: Cell[] = [seed];
  const seen = new Set([key(seed[0], seed[1])]);

  while (front.length > 0 && got.length < count) {
    front.sort((a, b) => costOf(a[0], a[1]) - costOf(b[0], b[1]) || a[1] - b[1] || a[0] - b[0]);
    const cur = front.shift();
    if (!cur) break;
    const k = key(cur[0], cur[1]);
    if (allow.has(k) && !used.has(k)) got.push(cur);
    for (const nb of neighbors(cur[0], cur[1])) {
      const nk = key(nb[0], nb[1]);
      if (allow.has(nk) && !seen.has(nk)) {
        seen.add(nk);
        front.push(nb);
      }
    }
  }
  return got;
}

// ── 테두리 ───────────────────────────────────────────────────────────────

/**
 * 꼭짓점을 정수로 센다.
 *
 * 화면 좌표(실수)를 그대로 열쇠로 쓰면 같은 꼭짓점이 계산 경로에 따라 마지막
 * 자리에서 어긋나 테두리가 끊긴다. 뾰족 위 육각의 꼭짓점은 전부
 * x = ux · size·√3/2, y = uy · size/2 꼴이라 (ux, uy) 가 딱 떨어지는 정수다.
 * 이웃한 두 칸이 공유하는 꼭짓점은 여기서 정확히 같은 정수가 된다.
 */
function cornerLattice(col: number, row: number, k: number): Cell {
  const corner = CORNER_U[k] as Cell;
  return [2 * col + (row & 1) + corner[0], 3 * row + corner[1]];
}

function fmt(v: number): string {
  const r = Math.round(v * 1000) / 1000;
  return (r === 0 ? 0 : r).toString();
}

/**
 * 칸 묶음의 바깥 모서리를 SVG path 로 낸다.
 *
 * 칸마다 육각을 다 그리면 벌집 격자가 되어 영토 경계가 안 보인다. 바깥과 맞닿은
 * 변만 골라 이어 붙인다. 구멍이 있거나 덩어리가 갈라져 있으면 닫힌 고리가
 * 여럿 나오고, 그것을 한 path 에 이어 붙인다 (nonzero 규칙에서 구멍이 뚫린다).
 */
export function outline(cells: [number, number][], size: number): string {
  if (cells.length === 0) return '';

  const own = new Set(cells.map(([c, r]) => key(c, r)));
  const sorted = [...cells].sort((a, b) => a[1] - b[1] || a[0] - b[0]);

  // 시작 꼭짓점 → 끝 꼭짓점들. 모서리를 늘 같은 회전 방향으로 담으므로
  // 각 꼭짓점의 들고 남이 같아지고, 따라가면 반드시 제자리로 돌아온다.
  const edges = new Map<string, Cell[]>();
  for (const [c, r] of sorted) {
    for (const [ev, od, edge] of DIRS) {
      const [dc, dr] = (r & 1) === 0 ? ev : od;
      if (own.has(key(c + dc, r + dr))) continue;
      const a = cornerLattice(c, r, edge);
      const b = cornerLattice(c, r, (edge + 1) % 6);
      const ak = key(a[0], a[1]);
      const list = edges.get(ak);
      if (list) list.push(b);
      else edges.set(ak, [b]);
    }
  }

  const ux = (size * SQ3) / 2;
  const uy = size / 2;
  const starts = [...edges.keys()].sort();
  const parts: string[] = [];
  const limit = cells.length * 6 + 6;

  for (const start of starts) {
    for (;;) {
      const first = edges.get(start);
      if (!first || first.length === 0) break;

      const loop: Cell[] = [];
      let cur: Cell = start.split(',').map(Number) as Cell;
      for (let guard = 0; guard < limit; guard++) {
        const outs = edges.get(key(cur[0], cur[1]));
        if (!outs || outs.length === 0) break;
        const next = outs.shift();
        if (!next) break;
        loop.push(cur);
        cur = next;
        if (key(cur[0], cur[1]) === start) break;
      }
      if (loop.length < 3) continue;

      const d = loop
        .map(([lx, ly], i) => `${i === 0 ? 'M' : 'L'}${fmt(lx * ux)},${fmt(ly * uy)}`)
        .join(' ');
      parts.push(`${d} Z`);
    }
  }
  return parts.join(' ');
}

// ── 이름표 ───────────────────────────────────────────────────────────────

/**
 * 이름표를 앉힐 자리.
 *
 * 무게중심은 오목한 영토에서 덩어리 **밖으로** 나간다. C 자 모양이면 가운데가
 * 비어 있어 이름표가 남의 영토 위에 얹힌다. 그래서 바깥과 맞닿은 칸에서
 * 한 겹씩 안으로 파고들어(BFS) 가장 깊은 칸을 고른다. 그 칸은 반드시 제 덩어리
 * 안이고, 테두리에서 가장 멀어 글자가 잘리지 않는다.
 *
 * 칸이 없으면 원점을 돌려준다. 부르는 쪽에서 빈 영토를 걸러야 한다.
 */
export function labelAnchor(cells: [number, number][], size: number): Point {
  if (cells.length === 0) return { x: 0, y: 0 };

  const sorted = [...cells].sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  const own = new Set(sorted.map(([c, r]) => key(c, r)));

  const depth = new Map<string, number>();
  const queue: Cell[] = [];
  for (const [c, r] of sorted) {
    const edge = neighbors(c, r).some(([nc, nr]) => !own.has(key(nc, nr)));
    if (edge) {
      depth.set(key(c, r), 0);
      queue.push([c, r]);
    }
  }
  // 테두리가 하나도 없을 수는 없지만(유한한 덩어리) 방어해 둔다.
  if (queue.length === 0) {
    const head = sorted[0] as Cell;
    depth.set(key(head[0], head[1]), 0);
    queue.push(head);
  }

  for (let i = 0; i < queue.length; i++) {
    const cur = queue[i] as Cell;
    const d = depth.get(key(cur[0], cur[1])) ?? 0;
    for (const [nc, nr] of neighbors(cur[0], cur[1])) {
      const nk = key(nc, nr);
      if (!own.has(nk) || depth.has(nk)) continue;
      depth.set(nk, d + 1);
      queue.push([nc, nr]);
    }
  }

  let maxD = -1;
  for (const d of depth.values()) if (d > maxD) maxD = d;

  // 가장 깊은 칸이 여럿이면 덩어리 한가운데에 가까운 것을 고른다. 안 그러면
  // 길쭉한 영토에서 이름표가 한쪽 끝으로 쏠린다.
  let sumX = 0;
  let sumY = 0;
  for (const [c, r] of sorted) {
    const p = cellToXY(c, r, 1);
    sumX += p.x;
    sumY += p.y;
  }
  const midX = sumX / sorted.length;
  const midY = sumY / sorted.length;

  let best: Cell = sorted[0] as Cell;
  let bestD = Infinity;
  for (const cell of sorted) {
    if ((depth.get(key(cell[0], cell[1])) ?? -1) !== maxD) continue;
    const p = cellToXY(cell[0], cell[1], 1);
    const d = dist(p.x, p.y, midX, midY);
    if (d < bestD) {
      bestD = d;
      best = cell;
    }
  }
  return cellToXY(best[0], best[1], size);
}
