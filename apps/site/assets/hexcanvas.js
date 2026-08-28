// 회전하는 2층 벌집 판 — Canvas 2D 렌더러. 라이브러리 0개.
//
// 왜 Canvas 인가: 육각 2,000개 2층을 매 프레임 다시 그려도 1.4ms 입니다.
// SVG 로도 60fps 는 나오지만 여유가 2배뿐이라 조명·그림자를 넣을 자리가 없습니다.
// WebGL 은 이 규모에서 이득이 없고, Chrome M139 가 SwiftShader 폴백을 없애서
// GPU 없는 강의실 PC 에서 화면이 아예 안 뜰 위험만 삽니다.
//
// 좌표가 세 겹입니다.  격자(c,r) → 판 위(px,py,pz) → 화면(sx,sy)
// 판 위 좌표는 두 층이 같습니다. 층은 pz 하나로만 다릅니다.

export const SQ3 = Math.sqrt(3);

// 지금 SVG 지도의 투영 [[1, 0.60], [0, 0.345]] 입니다.
// 특이값 분해하면 앙각 14.3° · 롤 9.2° 의 직교 카메라와 정확히 같습니다.
// 그래서 φ=0 에서 지금 화면이 픽셀 단위로 보존됩니다.
export const M = { a: 1, b: 0.60, c: 0, d: 0.345 };

// A(φ) = M · Rz(φ). 프레임당 이 넷만 새로 구하면 회전이 끝납니다.
export function matrixOf(phi) {
  const cf = Math.cos(phi), sf = Math.sin(phi);
  return {
    a: M.a * cf + M.b * sf,       // sx = a*px + b*py
    b: -M.a * sf + M.b * cf,
    c: M.c * cf + M.d * sf,       // sy = c*px + d*py - pz
    d: -M.c * sf + M.d * cf,
    det: M.a * M.d - M.b * M.c,   // 0.345 — φ 와 무관한 상수
  };
}

// 격자 → 판 위. 뾰족 위(pointy-top), odd-r 오프셋.
export function world(col, row, S) {
  return [S * SQ3 * (col + 0.5 * (row & 1)), S * 1.5 * row];
}

// 판 위 → 화면
export function project(px, py, pz, A, OX, OY) {
  return [OX + A.a * px + A.b * py, OY + A.c * px + A.d * py - pz];
}

// 화면 → 판 위. det 가 φ 와 무관한 상수라 어느 각도에서도 역행렬이 있습니다.
export function unproject(sx, sy, pz, A, OX, OY) {
  const X = sx - OX, Y = sy - OY + pz;
  const inv = 1 / A.det;
  return [(A.d * X - A.b * Y) * inv, (-A.c * X + A.a * Y) * inv];
}

// 판 위 → 격자. Red Blob Games 의 pixel_to_hex + cube_round.
export function worldToCell(wx, wy, S) {
  const q = (SQ3 / 3 * wx - wy / 3) / S;
  const r = (2 / 3 * wy) / S;
  const s = -q - r;
  let rq = Math.round(q), rr = Math.round(r), rs = Math.round(s);
  const dq = Math.abs(rq - q), dr = Math.abs(rr - r), ds = Math.abs(rs - s);
  if (dq > dr && dq > ds) rq = -rr - rs;
  else if (dr > ds) rr = -rq - rs;
  const row = rr;
  return [rq + ((row - (row & 1)) >> 1), row];   // odd-r 오프셋 (col,row)
}

// 육각 꼭짓점 여섯. 평행 투영이라 **모든 칸이 서로 평행이동 관계**입니다.
// 그래서 프레임당 한 번만 구하고 2,000칸은 좌표만 옮깁니다.
export function hexOutline(A, S, inset = 0.94) {
  const pts = [];
  for (let k = 0; k < 6; k++) {
    const ang = ((60 * k - 30) * Math.PI) / 180;
    const dx = S * inset * Math.cos(ang), dy = S * inset * Math.sin(ang);
    pts.push([A.a * dx + A.b * dy, A.c * dx + A.d * dy]);
  }
  return pts;
}

// ── 색 ─────────────────────────────────────────────────────────────
// 밝기를 곱하지 않고 섞습니다. 곱하면 채도가 죽어 업종 구분이 무너집니다.
function mix(hex, target, t) {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  const [tr, tg, tb] = target;
  return `rgb(${Math.round(r + (tr - r) * t)},${Math.round(g + (tg - g) * t)},${Math.round(b + (tb - b) * t)})`;
}
const WHITE = [255, 255, 255], BLACK = [11, 14, 20];

// 면별 밝기 — 한 바퀴 도는 동안 어느 면도 새까매지지 않게 합니다.
export const FACE = {
  top:   c => mix(c, WHITE, 0.00),
  wallA: c => mix(c, BLACK, 0.22),   // 밝은 벽
  wallB: c => mix(c, BLACK, 0.38),   // 중간
  wallC: c => mix(c, BLACK, 0.54),   // 어두운 벽
};

// ── 장면 만들기 ────────────────────────────────────────────────────
// 좌표 계산을 여기 한 곳에만 둡니다. Canvas 와 SVG 두 백엔드가
// 좌표를 따로 계산하면 두 그림이 미묘하게 어긋나고, 그건 인쇄해 봐야 발견됩니다.
export function buildScene(cellsByPlace, places, layers, opts) {
  const { S, phi, OX, OY, zOf, thick, lift } = opts;
  const A = matrixOf(phi);
  const outline = hexOutline(A, S, 0.94);

  // 층별로 나눕니다. 위층이 언제나 앞이므로 정렬이 필요 없습니다.
  const byLayer = {};
  for (const l of layers) byLayer[l.id] = [];
  for (const p of places) {
    const cells = cellsByPlace[p.id];
    if (cells && cells.length) byLayer[p.layer]?.push({ place: p, cells });
  }

  const scene = { A, outline, S, OX, OY, thick, groups: [] };
  for (const l of layers) {
    const pz = zOf(l.id);
    const items = [];
    for (const { place, cells } of byLayer[l.id]) {
      const z = pz + (place.investigated ? lift : 0);
      const pts = [];
      for (const [c, r] of cells) {
        const [wx, wy] = world(c, r, S);
        pts.push(project(wx, wy, z, A, OX, OY));
      }
      items.push({ place, pts, z });
    }
    scene.groups.push({ layer: l, pz, items });
  }
  return scene;
}

// ── 그리기 ─────────────────────────────────────────────────────────
// 순서: 아래층 → 유통선 → 위층 → 라벨. φ 와 무관하게 항상 이 순서가 정답입니다.
function hexPath(ctx, cx, cy, outline) {
  ctx.moveTo(cx + outline[0][0], cy + outline[0][1]);
  for (let k = 1; k < 6; k++) ctx.lineTo(cx + outline[k][0], cy + outline[k][1]);
  ctx.closePath();
}

export function drawGroup(ctx, group, scene, colorOf, quality) {
  const { outline, thick } = scene;
  const { shadows } = quality;

  // 1) 바닥 그림자 — 시점과 무관해서 회전에 공짜입니다
  if (shadows) {
    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,.32)";
    ctx.beginPath();
    for (const it of group.items)
      for (const [x, y] of it.pts) hexPath(ctx, x + 3, y + 6, outline);
    ctx.fill();
    ctx.restore();
  }

  // 2) 옆면 — 아래로 thick 만큼 내린 사다리꼴. 칸마다 기둥을 세우면 벽이 6천 장이라
  //    아래쪽 세 모서리만 내립니다.
  for (const it of group.items) {
    const base = colorOf(it.place);
    ctx.fillStyle = FACE.wallB(base);
    ctx.beginPath();
    for (const [x, y] of it.pts) {
      for (const e of [[2, 3], [3, 4], [4, 5]]) {
        const p1 = outline[e[0]], p2 = outline[e[1]];
        ctx.moveTo(x + p1[0], y + p1[1]);
        ctx.lineTo(x + p2[0], y + p2[1]);
        ctx.lineTo(x + p2[0], y + p2[1] + thick);
        ctx.lineTo(x + p1[0], y + p1[1] + thick);
        ctx.closePath();
      }
    }
    ctx.fill();
  }

  // 3) 윗면 — 업종 색을 그대로. 칸별 stroke 는 금지입니다(획 하나가 채움의 5.7배).
  for (const it of group.items) {
    ctx.fillStyle = FACE.top(colorOf(it.place));
    ctx.globalAlpha = it.place.investigated ? 1 : 0.34;
    ctx.beginPath();
    for (const [x, y] of it.pts) hexPath(ctx, x, y, outline);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}
