// 육각 배치와 2층 투영. 지도의 뼈대입니다.
// graph/final/f8_iso.py 의 배치 규칙을 옮긴 것이고, 여기가 원본이 됩니다.
//
// 좌표가 세 겹입니다.
//   격자 (col,row)  →  판 위 (wx,wy)  →  화면 (sx,sy)
// 판 위 좌표는 두 층이 같습니다. 층은 z 하나로만 다릅니다.
// 그래서 같은 (col,row)는 두 층에서 화면 x가 같고, 위아래로 정확히 겹칩니다.

export const SQ3 = Math.sqrt(3);

// 기울기와 눌림. 평행 기울임이라 앞뒤 면적 비가 보존됩니다.
// 원근이 아니므로 크기를 서로 비교해도 됩니다.
export const SHX = 0.60;
export const SHY = 0.345;

// 뾰족 위 육각의 꼭짓점 여섯
const CORN = Array.from({ length: 6 }, (_, k) => {
  const a = ((60 * k - 30) * Math.PI) / 180;
  return [Math.cos(a), Math.sin(a)];
});

// 방향 여섯. [짝수행 오프셋, 홀수행 오프셋, 그 방향이 막는 모서리 번호]
const DIRS = [
  [[+1, 0], [+1, 0], 0],
  [[0, +1], [+1, +1], 1],
  [[-1, +1], [0, +1], 2],
  [[-1, 0], [-1, 0], 3],
  [[-1, -1], [0, -1], 4],
  [[0, -1], [+1, -1], 5],
];

export function neighbors(col, row, cols, rows) {
  const out = [];
  for (const [ev, od] of DIRS) {
    const [dc, dr] = row % 2 === 0 ? ev : od;
    const c = col + dc, r = row + dr;
    if (c >= 0 && c < cols && r >= 0 && r < rows) out.push([c, r]);
  }
  return out;
}

export function makeGrid({ size, originX, originY, gap }) {
  const S = size;

  // 격자 → 판 위
  const world = (col, row) => [S * SQ3 * (col + 0.5 * (row & 1)), S * 1.5 * row];

  // 판 위 → 화면. z 가 층 높이입니다.
  const project = (wx, wy, z) => [originX + wx + wy * SHX, originY + wy * SHY - z];

  const center = (col, row, z) => {
    const [wx, wy] = world(col, row);
    return project(wx, wy, z);
  };

  // 육각 하나의 화면 꼭짓점
  const cell = (col, row, z, k = 0.94) => {
    const [wx, wy] = world(col, row);
    return CORN.map(([cx, cy]) => project(wx + S * k * cx, wy + S * k * cy, z));
  };

  // 판 네 귀퉁이
  const plate = (cols, rows, z, pad = S * 1.4) => {
    const [w0, h0] = world(cols - 1, rows - 1);
    return [
      project(-pad, -pad, z),
      project(w0 + pad, -pad, z),
      project(w0 + pad, h0 + pad, z),
      project(-pad, h0 + pad, z),
    ];
  };

  return { size: S, world, project, center, cell, plate, gap };
}

// 씨앗에서 이웃으로 번지며 n칸을 먹습니다. 덩어리가 둥글게 뭉칩니다.
// taken 은 이미 임자가 있는 칸입니다. 여기 든 칸은 건너뜁니다.
export function growBlob({ seed, count, cols, rows, taken, world, squash = 0.95 }) {
  const key = ([c, r]) => c + "," + r;
  const [sw, sh] = world(seed[0], seed[1]);
  const dist = ([c, r]) => {
    const [wx, wy] = world(c, r);
    return (wx - sw) ** 2 + ((wy - sh) * squash) ** 2;
  };

  const got = [];
  const front = [seed];
  const seen = new Set([key(seed)]);

  while (front.length && got.length < count) {
    front.sort((a, b) => dist(a) - dist(b));
    const cur = front.shift();
    // 이미 임자가 있는 칸이라도 이웃은 큐에 넣습니다. 그래야 장애물을 돌아 자랍니다.
    const mine = !taken.has(key(cur));
    if (mine) { taken.set(key(cur), true); got.push(cur); }
    for (const nb of neighbors(cur[0], cur[1], cols, rows)) {
      if (!taken.has(key(nb)) && !seen.has(key(nb))) {
        seen.add(key(nb));
        front.push(nb);
      }
    }
  }
  return got;
}

// 덩어리의 바깥 모서리만 골라냅니다. 해안선을 그릴 때 씁니다.
export function outline(cells, z, grid) {
  const set = new Set(cells.map(([c, r]) => c + "," + r));
  const segs = [];
  for (const [c, r] of cells) {
    const pts = grid.cell(c, r, z);
    for (const [ev, od, edge] of DIRS) {
      const [dc, dr] = r % 2 === 0 ? ev : od;
      if (set.has(c + dc + "," + (r + dr))) continue;
      segs.push([pts[edge], pts[(edge + 1) % 6]]);
    }
  }
  return segs;
}

// 덩어리의 화면 경계 상자. 선의 화살촉을 덩어리 바깥에 찍을 때 씁니다.
// 반지름 어림값을 쓰면 화살촉이 칸 밑에 묻힙니다.
export function bbox(cells, z, grid) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [c, r] of cells) {
    for (const [x, y] of grid.cell(c, r, z)) {
      if (x < x0) x0 = x;
      if (y < y0) y0 = y;
      if (x > x1) x1 = x;
      if (y > y1) y1 = y;
    }
  }
  return { x0, y0, x1, y1, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 };
}

// 경계 상자 바깥으로 밀어낸 점. 선의 시작과 끝을 여기에 둡니다.
export function edgePoint(box, towardX, towardY, pad = 6) {
  const dx = towardX - box.cx, dy = towardY - box.cy;
  const len = Math.hypot(dx, dy) || 1;
  const hw = (box.x1 - box.x0) / 2 + pad;
  const hh = (box.y1 - box.y0) / 2 + pad;
  // 경계 상자와 만나는 지점까지의 배율
  const t = Math.min(hw / Math.abs(dx || 1e-6), hh / Math.abs(dy || 1e-6));
  return [box.cx + (dx / len) * len * t, box.cy + (dy / len) * len * t];
}

// 두 점을 잇는 곡선. 휨을 선 길이에 비례시키고 방향을 지정할 수 있게 둡니다.
// 상수로 휘면 짧은 선은 과하게 휘고 긴 선은 직선처럼 보입니다.
export function curve(p1, p2, { bend = 0.18, side = 1 } = {}) {
  const [x1, y1] = p1, [x2, y2] = p2;
  const dx = x2 - x1, dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const off = len * bend * side;
  const mx = (x1 + x2) / 2 - (dy / len) * off;
  const my = (y1 + y2) / 2 + (dx / len) * off;
  return { d: `M${x1.toFixed(1)},${y1.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`, mid: [mx, my] };
}

export function polyPoints(pts) {
  return pts.map(([x, y]) => x.toFixed(1) + "," + y.toFixed(1)).join(" ");
}

export const HEX_CORNERS = CORN;
