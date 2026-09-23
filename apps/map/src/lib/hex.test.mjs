// hex.ts 시험.  node --experimental-strip-types --test src/lib/hex.test.mjs
//
// 시험을 .mjs 로 두는 이유가 있다. Node 22 의 타입 벗기기는 상대 경로에 실제
// 확장자(`./hex.ts`)를 요구하는데, 이 저장소 tsconfig 는 allowImportingTsExtensions
// 를 안 켜 두어서 그 import 가 든 .ts 파일은 `next build` 의 타입 검사에서 걸린다.
// .mjs 는 tsconfig 의 include(**/*.ts, **/*.tsx, **/*.mts) 밖이라 빌드를 안 건드린다.

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  SQ3,
  cellToXY,
  xyToCell,
  hexPoints,
  gridSize,
  growIslands,
  splitTerritories,
  outline,
  labelAnchor,
} from './hex.ts';

const key = (c, r) => `${c},${r}`;
const near = (a, b, eps = 1e-9) => Math.abs(a - b) <= eps;

/** 두 칸 사이 육각 거리 (odd-r → 큐브). */
function hexDist(a, b) {
  const ax = a[0] - ((a[1] - (a[1] & 1)) >> 1);
  const az = a[1];
  const bx = b[0] - ((b[1] - (b[1] & 1)) >> 1);
  const bz = b[1];
  return (Math.abs(ax - bx) + Math.abs(ax + az - bx - bz) + Math.abs(az - bz)) / 2;
}

// ── 1. 좌표 변환이 왕복해도 같은 칸으로 돌아온다 ──────────────────────────

test('1. cellToXY → xyToCell 왕복이 같은 칸으로 돌아온다', () => {
  for (const size of [1, 7, 18, 40.5]) {
    for (let row = -6; row <= 30; row++) {
      for (let col = -6; col <= 30; col++) {
        const p = cellToXY(col, row, size);
        const back = xyToCell(p.x, p.y, size);
        assert.deepEqual(back, { col, row }, `size=${size} (${col},${row})`);
      }
    }
  }
});

test('1b. 칸 한가운데에서 살짝 벗어나도 같은 칸으로 떨어진다', () => {
  const size = 18;
  // 칸 반지름의 30% 안쪽이면 어느 방향으로 밀어도 제 칸이다.
  const off = size * 0.3;
  for (let row = 0; row <= 12; row++) {
    for (let col = 0; col <= 12; col++) {
      const p = cellToXY(col, row, size);
      for (let k = 0; k < 6; k++) {
        const a = (Math.PI / 3) * k;
        const back = xyToCell(p.x + Math.cos(a) * off, p.y + Math.sin(a) * off, size);
        assert.deepEqual(back, { col, row });
      }
    }
  }
});

test('1c. 격자 간격이 뾰족 위 육각과 맞는다', () => {
  const size = 10;
  const a = cellToXY(0, 0, size);
  const b = cellToXY(1, 0, size);
  const c = cellToXY(0, 1, size);
  assert.ok(near(b.x - a.x, SQ3 * size), '열 간격 √3·size');
  assert.ok(near(c.y - a.y, 1.5 * size), '행 간격 1.5·size');
  assert.ok(near(c.x - a.x, (SQ3 * size) / 2), '홀수 행은 반 칸 오른쪽');
});

test('1d. hexPoints 는 뾰족 위 꼭짓점 여섯을 낸다', () => {
  const size = 12;
  const pts = hexPoints(0, 0, size);
  assert.equal(pts.length, 6);
  for (const [x, y] of pts) assert.ok(near(Math.hypot(x, y), size, 1e-9), '전부 반지름 위');
  const xs = pts.map(([x]) => x);
  const ys = pts.map(([, y]) => y);
  assert.ok(near(Math.max(...xs) - Math.min(...xs), SQ3 * size), '폭 √3·size');
  assert.ok(near(Math.max(...ys) - Math.min(...ys), 2 * size), '높이 2·size');
  // 0번 모서리(pts[0]→pts[1])가 동쪽 이웃과 맞닿는 변이라야 outline 이 맞는다.
  assert.ok(near(pts[0][0], pts[1][0]), '0번 변은 오른쪽 세로변');
});

// ── 2. growIslands 가 요청한 칸 수를 정확히 돌려준다 ──────────────────────

const DESIGN = { RANSOMWARE: 152, FORUM: 87, TELEGRAM: 35, OTHER: 9 }; // 설계서 3.4 표 얼개

test('2. growIslands 가 요청한 칸 수를 정확히 돌려준다', () => {
  const cases = [
    DESIGN,
    { A: 1 },
    { A: 1, B: 1, C: 1, D: 1, E: 1 },
    { A: 200, B: 200 },
    { A: 400 },
    { A: 60, B: 0, C: 40 },
    { A: 13, B: 13, C: 13, D: 13, E: 13, F: 13, G: 13, H: 13 },
  ];
  for (const want of cases) {
    const got = growIslands(want);
    assert.deepEqual(Object.keys(got).sort(), Object.keys(want).sort(), '섬 목록이 그대로');
    for (const [id, n] of Object.entries(want)) {
      assert.equal(got[id].length, n, `${JSON.stringify(want)} 의 ${id}`);
    }
  }
});

test('2b. 빈 요청과 0칸 요청을 견딘다', () => {
  assert.deepEqual(growIslands({}), {});
  assert.deepEqual(growIslands({ A: 0 }), { A: [] });
});

// ── 3. 섬끼리 칸이 겹치지 않는다 ─────────────────────────────────────────

test('3. 섬끼리 칸이 겹치지 않는다', () => {
  for (const want of [DESIGN, { A: 200, B: 200 }, { A: 50, B: 50, C: 50, D: 50, E: 50, F: 50 }]) {
    const got = growIslands(want);
    const seen = new Set();
    let count = 0;
    for (const cells of Object.values(got)) {
      for (const [c, r] of cells) {
        const k = key(c, r);
        assert.ok(!seen.has(k), `칸 ${k} 을 두 섬이 함께 가졌다`);
        seen.add(k);
        count++;
      }
    }
    assert.equal(seen.size, count);
  }
});

test('3b. 모든 칸이 격자 안에 있다', () => {
  const want = DESIGN;
  const total = Object.values(want).reduce((s, n) => s + n, 0);
  const { cols, rows } = gridSize(total);
  assert.ok(cols * rows >= total, '격자가 요청보다 넓다');
  for (const cells of Object.values(growIslands(want))) {
    for (const [c, r] of cells) {
      assert.ok(c >= 0 && c < cols && r >= 0 && r < rows, `${key(c, r)} 가 격자 밖`);
    }
  }
});

test('3c. 섬 하나하나가 이어져 있다', () => {
  const got = growIslands(DESIGN);
  const DIRS = [
    [[+1, 0], [+1, 0]], [[0, +1], [+1, +1]], [[-1, +1], [0, +1]],
    [[-1, 0], [-1, 0]], [[-1, -1], [0, -1]], [[0, -1], [+1, -1]],
  ];
  for (const [id, cells] of Object.entries(got)) {
    const own = new Set(cells.map(([c, r]) => key(c, r)));
    const seen = new Set([key(cells[0][0], cells[0][1])]);
    const q = [cells[0]];
    for (let i = 0; i < q.length; i++) {
      const [c, r] = q[i];
      for (const [ev, od] of DIRS) {
        const [dc, dr] = (r & 1) === 0 ? ev : od;
        const k = key(c + dc, r + dr);
        if (own.has(k) && !seen.has(k)) {
          seen.add(k);
          q.push([c + dc, r + dr]);
        }
      }
    }
    assert.equal(seen.size, cells.length, `${id} 섬이 갈라졌다`);
  }
});

// ── 4. splitTerritories 가 준 칸 집합 밖으로 안 나간다 ────────────────────

test('4. splitTerritories 가 준 칸 집합 밖으로 안 나가고 겹치지도 않는다', () => {
  const island = growIslands(DESIGN).RANSOMWARE; // 152칸
  const allow = new Set(island.map(([c, r]) => key(c, r)));

  const cases = [
    { Qilin: 54, Gunra: 10, Akira: 40, Play: 30, Cl0p: 18 }, // 합 152 — 섬을 꽉 채움
    { Qilin: 54, Gunra: 10 }, // 합 64 — 남는 자리가 있음
    { Solo: 152 },
    { A: 1, B: 1, C: 1 },
  ];

  for (const want of cases) {
    const got = splitTerritories(island, want);
    const seen = new Set();
    for (const [id, cells] of Object.entries(got)) {
      assert.equal(cells.length, want[id], `${id} 칸 수`);
      for (const [c, r] of cells) {
        const k = key(c, r);
        assert.ok(allow.has(k), `${id} 의 ${k} 가 섬 밖으로 나갔다`);
        assert.ok(!seen.has(k), `${k} 을 두 영토가 함께 가졌다`);
        seen.add(k);
      }
    }
  }
});

test('4b. 섬보다 많이 달라고 하면 섬 크기까지만 준다', () => {
  const island = growIslands({ A: 20 }).A;
  const got = splitTerritories(island, { X: 15, Y: 15 });
  const total = got.X.length + got.Y.length;
  assert.equal(total, 20, '섬 밖으로 넘치지 않는다');
  assert.equal(got.X.length, 15, '큰 영토가 먼저 받는다');
  assert.equal(got.Y.length, 5);
});

test('4c. 빈 섬을 줘도 터지지 않는다', () => {
  assert.deepEqual(splitTerritories([], { A: 5 }), { A: [] });
});

// ── 5. 라운드로빈 증명 ───────────────────────────────────────────────────

test('5. 큰 섬 하나와 작은 셋을 주면 작은 셋이 다 제자리를 받는다', () => {
  // 작은 섬 씨앗을 일부러 큰 섬 씨앗 바로 옆에 둔다. 순서대로 키우면 큰 섬이
  // 이 자리를 전부 먹어 작은 섬들이 격자 가장자리로 밀려난다.
  const want = { BIG: 300, A: 5, B: 5, C: 5 };
  const seeds = { BIG: [15, 10], A: [15, 6], B: [11, 12], C: [19, 12] };
  const got = growIslands(want, seeds);

  for (const id of ['A', 'B', 'C']) {
    assert.equal(got[id].length, 5, `${id} 가 5칸을 못 받았다`);
    // 5칸이면 씨앗과 그 이웃뿐이다. 두 고리 안에 있으면 제자리를 지킨 것이다.
    for (const cell of got[id]) {
      assert.ok(hexDist(cell, seeds[id]) <= 2, `${id} 의 ${key(...cell)} 가 씨앗에서 밀려났다`);
    }
  }

  assert.equal(got.BIG.length, 300);
  // 큰 섬은 작은 섬들을 비켜 가며 멀리까지 자랐다 — 작은 섬이 밀린 게 아니다.
  const far = got.BIG.filter((cell) => hexDist(cell, seeds.BIG) >= 8).length;
  assert.ok(far > 0, '큰 섬이 제대로 못 자랐다면 시험 자체가 무의미하다');

  // 작은 섬 셋이 큰 섬 안쪽에 박혀 있다: 큰 섬이 그 둘레를 감쌌다는 뜻.
  const bigSet = new Set(got.BIG.map(([c, r]) => key(c, r)));
  for (const id of ['A', 'B', 'C']) {
    const ring = got[id].some(([c, r]) =>
      [[c + 1, r], [c - 1, r], [c, r + 1], [c, r - 1]].some(([nc, nr]) => bigSet.has(key(nc, nr))),
    );
    assert.ok(ring, `${id} 가 큰 섬과 맞닿아 있지 않다 — 가장자리로 밀려난 모양`);
  }
});

test('5b. 칸 수가 크게 차이 나도 작은 섬이 사라지지 않는다', () => {
  const want = { HUGE: 380, T1: 1, T2: 1, T3: 1, T4: 1 };
  const got = growIslands(want);
  for (const id of ['T1', 'T2', 'T3', 'T4']) assert.equal(got[id].length, 1, id);
  assert.equal(got.HUGE.length, 380);
});

// ── 6. 같은 입력이면 같은 출력이다 ───────────────────────────────────────

test('6. 같은 입력이면 같은 출력이다', () => {
  for (let i = 0; i < 3; i++) {
    assert.deepEqual(growIslands(DESIGN), growIslands(DESIGN));
  }
  const island = growIslands(DESIGN).FORUM;
  const want = { DarkForums: 40, Breached: 30, Nulled: 17 };
  assert.deepEqual(splitTerritories(island, want), splitTerritories(island, want));
  assert.equal(outline(island, 18), outline(island, 18));
  assert.deepEqual(labelAnchor(island, 18), labelAnchor(island, 18));
});

test('6b. 객체 키 차례가 달라도 결과가 같다', () => {
  const a = { RANSOMWARE: 152, FORUM: 87, TELEGRAM: 35, OTHER: 9 };
  const b = { OTHER: 9, TELEGRAM: 35, FORUM: 87, RANSOMWARE: 152 };
  const ga = growIslands(a);
  const gb = growIslands(b);
  for (const id of Object.keys(a)) assert.deepEqual(ga[id], gb[id], id);
});

test('6c. 칸 차례가 달라도 영토·테두리·이름표가 같다', () => {
  const island = growIslands({ A: 60 }).A;
  const flipped = [...island].reverse();
  const want = { X: 25, Y: 20, Z: 15 };
  assert.deepEqual(splitTerritories(island, want), splitTerritories(flipped, want));
  assert.equal(outline(island, 14), outline(flipped, 14));
  assert.deepEqual(labelAnchor(island, 14), labelAnchor(flipped, 14));
});

// ── 테두리와 이름표 ──────────────────────────────────────────────────────

test('outline: 육각 하나는 닫힌 여섯 변이다', () => {
  const d = outline([[0, 0]], 10);
  assert.match(d, /^M[-\d.]+,[-\d.]+( L[-\d.]+,[-\d.]+){5} Z$/, d);
});

test('outline: 빈 입력은 빈 문자열', () => {
  assert.equal(outline([], 10), '');
});

test('outline: 고리 모양이면 바깥과 안쪽 두 고리가 나온다', () => {
  // 가운데 (1,1) 을 뺀 도넛
  const ring = [];
  for (let r = 0; r <= 2; r++) for (let c = 0; c <= 2; c++) if (!(c === 1 && r === 1)) ring.push([c, r]);
  const d = outline(ring, 10);
  assert.equal(d.split('Z').length - 1, 2, `닫힌 고리 두 개라야 한다: ${d}`);
});

test('outline: 붙어 있는 두 칸 사이에는 선이 안 그어진다', () => {
  const one = outline([[0, 0]], 10).split('L').length;
  const two = outline([[0, 0], [1, 0]], 10).split('L').length;
  // 낱개 둘이면 변이 12개, 붙어 있으면 맞닿은 두 변이 빠져 10개다.
  assert.equal(one - 1, 5);
  assert.equal(two - 1, 9);
});

test('labelAnchor: 오목한 영토에서도 덩어리 안에 앉는다', () => {
  // C 자 — 무게중심은 가운데 빈 칸으로 빠진다
  const cShape = [
    [0, 0], [1, 0], [2, 0],
    [0, 1],
    [0, 2], [1, 2], [2, 2],
  ];
  const size = 20;
  const anchor = labelAnchor(cShape, size);
  const inside = cShape.some(([c, r]) => {
    const p = cellToXY(c, r, size);
    return near(p.x, anchor.x, 1e-9) && near(p.y, anchor.y, 1e-9);
  });
  assert.ok(inside, `이름표가 덩어리 밖에 앉았다: ${JSON.stringify(anchor)}`);

  // 무게중심은 정말로 빈 칸 쪽이라는 것도 같이 보인다
  const mid = cShape.reduce(
    (a, [c, r]) => {
      const p = cellToXY(c, r, size);
      return { x: a.x + p.x / cShape.length, y: a.y + p.y / cShape.length };
    },
    { x: 0, y: 0 },
  );
  const hole = cellToXY(1, 1, size);
  assert.ok(Math.hypot(mid.x - hole.x, mid.y - hole.y) < size, '무게중심은 구멍 근처다');
});

test('labelAnchor: 덩어리 한가운데가 가장자리보다 깊다', () => {
  const blob = [];
  for (let r = 0; r <= 6; r++) for (let c = 0; c <= 6; c++) blob.push([c, r]);
  const size = 10;
  const anchor = labelAnchor(blob, size);
  const cell = xyToCell(anchor.x, anchor.y, size);
  assert.ok(cell.col >= 2 && cell.col <= 4, `가운데 열이라야 한다: ${JSON.stringify(cell)}`);
  assert.ok(cell.row >= 2 && cell.row <= 4, `가운데 행이라야 한다: ${JSON.stringify(cell)}`);
});

test('labelAnchor: 빈 입력은 원점', () => {
  assert.deepEqual(labelAnchor([], 10), { x: 0, y: 0 });
});

// ── 설계서 3.4 얼개로 한 바퀴 ────────────────────────────────────────────

test('설계서 3.4 표대로 섬을 만들고 영토를 나눠도 규칙이 지켜진다', () => {
  const islands = growIslands({ FORUM: 87, RANSOMWARE: 54, TELEGRAM: 29, OTHER: 230 });
  assert.equal(islands.FORUM.length, 87);

  // 섬 칸 수 = 소속 영토 칸 수의 합 (설계서 3.4)
  const terr = { DarkForums: 87 };
  const split = splitTerritories(islands.FORUM, terr);
  assert.equal(split.DarkForums.length, 87);

  const allow = new Set(islands.FORUM.map(([c, r]) => key(c, r)));
  for (const [c, r] of split.DarkForums) assert.ok(allow.has(key(c, r)));

  assert.ok(outline(split.DarkForums, 18).endsWith('Z'));
  const a = labelAnchor(split.DarkForums, 18);
  assert.ok(Number.isFinite(a.x) && Number.isFinite(a.y));
});
