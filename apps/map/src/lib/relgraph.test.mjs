/**
 * src/lib/relgraph.ts 시험 — 관계도 배율별 라벨 고르기와 범례 밀기 (2026-09-28 최현서 5번).
 *
 *   node --experimental-strip-types --test src/lib/relgraph.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  LABEL_TOP,
  boardFit,
  labelScale,
  legendFit,
  legendShift,
  nodeBoxes,
  placeLabels,
  textWidth,
  topInner,
  wantedLabels,
} from './relgraph.ts';

/** 알약 하나. 자리 후보를 안 주면 (x, y) 한 곳뿐이다 */
function cand(id, count, { outer = false, force = false, x = 0, y = 0, spots, w = 100, h = 26 } = {}) {
  return { id, count, outer, force, w, h, spots: spots ?? [{ x, y }] };
}

/** 서로 멀리 떨어진 1단계 선 여섯, 바깥 선 둘 */
function spread() {
  return [
    cand('a', 9, { x: 0 }),
    cand('b', 3, { x: 300 }),
    cand('c', 7, { x: 600 }),
    cand('d', 1, { x: 900 }),
    cand('e', 5, { x: 1200 }),
    cand('f', 2, { x: 1500 }),
    cand('o1', 50, { outer: true, x: 0, y: 500 }),
    cand('o2', 1, { outer: true, x: 300, y: 500 }),
  ];
}

const ids = (m) => [...m.keys()].sort();

test('알약 크기 — 판이 설계 크기로 그리면 확대한 만큼 줄고, 줄일 때는 판과 같이 준다', () => {
  assert.equal(labelScale(50), 1);
  assert.equal(labelScale(100), 1);
  assert.equal(labelScale(125), 0.8);
  assert.equal(labelScale(200), 0.5);
});

test('알약 크기 — 작은 판은 설계 크기(13px)까지 먼저 키우고 그다음 지킨다', () => {
  const near = (a, b) => Math.abs(a - b) < 1e-9;
  // 1366 급 — 판이 viewBox 를 0.7 배로 그린다. 125% 는 13 × 0.875px 라 아직 그림과 같이 큰다
  assert.equal(labelScale(125, 0.7), 1);
  // 150% 는 그림대로면 13 × 1.05px — 13px 에 맞춰 조금 줄인다
  assert.ok(near(labelScale(150, 0.7), 1 / 1.05));
  // 화면 크기로 보면 150% · 200% 모두 13px
  assert.ok(near(13 * 0.7 * 1.5 * labelScale(150, 0.7), 13));
  assert.ok(near(13 * 0.7 * 2 * labelScale(200, 0.7), 13));
  // 100% 에서 이미 13px 를 넘는 큰 판은 100% 화면 크기를 지킨다
  assert.ok(near(13 * 1.2 * 2 * labelScale(200, 1.2), 13 * 1.2));
  // 판 크기를 모르거나 0 이면 설계 크기 판으로 본다
  assert.equal(labelScale(200, 0), 0.5);
});

test('판 배율 — 가운데 맞춤이라 가로 · 세로 가운데 작은 쪽', () => {
  const vb = { w: 1000, h: 620 };
  assert.equal(boardFit(null, vb), 1);
  assert.equal(boardFit({ w: 700, h: 500 }, vb), 0.7);
  assert.equal(boardFit({ w: 2000, h: 620 }, vb), 1);
  assert.equal(boardFit({ w: 0, h: 500 }, vb), 1);
});

test('노드 이름 자리 — 글줄마다 따로, 붙인 쪽에 맞춰', () => {
  assert.equal(textWidth('ab', 10), 12);
  assert.equal(textWidth('활동', 10), 20);
  const base = { x: 500, y: 300, r: 20, outer: false, center: false, name: 'Qilin', sub: 'Ransomware · 활동도 42' };
  // 아래에 붙이면 육각형 · 이름 줄 · 둘째 줄 셋. 둘째 줄이 이름 줄보다 넓고 아래다
  const below = nodeBoxes({ ...base, side: 'below' });
  assert.equal(below.length, 3);
  const [hex, name, sub] = below;
  assert.ok(hex.x > 500 - 20 && hex.w < 40, '육각형은 꼭짓점을 뺀 안쪽');
  assert.ok(name.y > 300 + 20 && sub.y > name.y + name.h - 1);
  assert.ok(sub.w > name.w);
  assert.ok(Math.abs(name.x + name.w / 2 - 500) < 1e-9, '가운데 맞춤');
  // 바깥 고리는 이름 한 줄
  assert.equal(nodeBoxes({ ...base, side: 'below', outer: true }).length, 2);
  // 왼쪽에 붙이면 노드 왼쪽에서 끝나고, 오른쪽이면 노드 오른쪽에서 시작한다
  const left = nodeBoxes({ ...base, side: 'left', sub: '활동도 42' })[1];
  const right = nodeBoxes({ ...base, side: 'right', sub: '활동도 42' })[1];
  assert.ok(Math.abs(left.x + left.w - (500 - 20 - 10)) < 1e-9);
  assert.equal(right.x, 500 + 20 + 10);
});

test('주요 관계는 1단계 선 가운데 건수 상위 넷 — 바깥 선은 건수가 커도 안 든다', () => {
  assert.equal(LABEL_TOP, 4);
  assert.deepEqual([...topInner(spread())].sort(), ['a', 'b', 'c', 'e']);
  // 건수가 같으면 들어온 차례
  const tie = [cand('x', 2), cand('y', 2), cand('z', 2)];
  assert.deepEqual([...topInner(tie, 2)], ['x', 'y']);
});

test('100% 는 지금까지 규칙 — 1단계 선 전부, 바깥 선은 안 단다', () => {
  assert.deepEqual([...wantedLabels(spread(), 100)].sort(), ['a', 'b', 'c', 'd', 'e', 'f']);
});

test('100% 미만은 1단계 건수 상위만, 125% 이상은 바깥 선까지 전부', () => {
  assert.deepEqual([...wantedLabels(spread(), 75)].sort(), ['a', 'b', 'c', 'e']);
  assert.deepEqual([...wantedLabels(spread(), 50)].sort(), ['a', 'b', 'c', 'e']);
  assert.equal(wantedLabels(spread(), 125).size, 8);
  assert.equal(wantedLabels(spread(), 200).size, 8);
});

test('강조 · 고른 선은 배율과 상관없이 단다', () => {
  const list = spread().map((c) => (c.id === 'd' || c.id === 'o2' ? { ...c, force: true } : c));
  const at50 = wantedLabels(list, 50);
  assert.ok(at50.has('d'), '건수 1 이라 상위 넷 밖이어도');
  assert.ok(at50.has('o2'), '바깥 선이어도');
  assert.ok(wantedLabels(list, 100).has('o2'));
  assert.deepEqual(ids(placeLabels(list, 50, [])), ['a', 'b', 'c', 'd', 'e', 'o2']);
});

test('라벨끼리 겹치면 건수가 큰 것부터 놓고 뒤 것은 뺀다', () => {
  const list = [cand('small', 2, { x: 10 }), cand('big', 8, { x: 0 })];
  assert.deepEqual(ids(placeLabels(list, 100, [])), ['big']);
});

test('강조 · 고른 선은 겹쳐도 안 빠진다 — 겹친 쪽이 빠진다', () => {
  const list = [cand('big', 8, { x: 0 }), cand('picked', 1, { x: 10, force: true })];
  assert.deepEqual(ids(placeLabels(list, 100, [])), ['picked']);
});

test('첫 자리가 막히면 선을 따라 옮긴 다음 자리에 앉는다', () => {
  const list = [
    cand('big', 8, { x: 0 }),
    cand('small', 2, { spots: [{ x: 10, y: 0 }, { x: 10, y: 60 }] }),
  ];
  const m = placeLabels(list, 100, []);
  assert.deepEqual(ids(m), ['big', 'small']);
  assert.deepEqual(m.get('small'), { x: 10, y: 60 });
});

test('노드 이름을 피한다 — 못 피하면 빼되, 줄였을 때만 주요 관계는 걸쳐도 단다', () => {
  const name = { x: -80, y: -20, w: 160, h: 40 };
  // 상위 넷을 먼저 채워 두고(멀리), 다섯째(주요 밖)를 이름 위에 둔다
  const far = [cand('a', 9, { x: 1000 }), cand('b', 8, { x: 1300 }), cand('c', 7, { x: 1600 }), cand('d', 6, { x: 1900 })];
  const minor = cand('m', 1, { spots: [{ x: 0, y: 0 }, { x: 0, y: 10 }] });
  assert.ok(!placeLabels([...far, minor], 100, [name]).has('m'), '주요 밖은 이름을 못 피하면 뺀다');
  // 비킬 자리가 있으면 그리로 간다
  const movable = cand('m', 1, { spots: [{ x: 0, y: 0 }, { x: 0, y: 200 }] });
  assert.deepEqual(placeLabels([...far, movable], 100, [name]).get('m'), { x: 0, y: 200 });
  // 줄였을 때(100% 미만)는 주요 관계가 이름에 걸쳐도 단다 — 주요 관계는 글자가 있어야 한다
  const major = cand('a', 9, { x: 0 });
  assert.deepEqual(placeLabels([major], 75, [name]).get('a'), { x: 0, y: 0 });
  // 100% 이상에서는 주요 관계도 이름을 피할 자리가 없으면 뺀다 — 2단계에서 라벨이 이름을 덮던 것
  // (2026-09-28 최현서 5번). 확대하면 사이가 벌어져 다시 보인다
  assert.ok(!placeLabels([major], 100, [name]).has('a'));
});

test('확대하면 알약이 작아져 100% 에서 겹치던 둘이 같이 앉는다', () => {
  // 가운데가 80 떨어진 폭 100 알약 둘 — 100% 에서는 겹치고 200% 에서는 폭 50 이라 안 겹친다
  const list = [cand('a', 5, { x: 0 }), cand('b', 4, { x: 80 })];
  assert.deepEqual(ids(placeLabels(list, 100, [])), ['a']);
  assert.deepEqual(ids(placeLabels(list, 200, [])), ['a', 'b']);
  // 작은 판(0.7 배)에서는 125% 까지 알약이 그림과 같이 커서 아직 겹친다
  assert.deepEqual(ids(placeLabels(list, 125, [], { fit: 0.7 })), ['a']);
  assert.deepEqual(ids(placeLabels(list, 200, [], { fit: 0.7 })), ['a', 'b']);
});

test('확대해도 1단계 라벨이 바깥 선 라벨에 밀리지 않는다', () => {
  // 바깥 선이 건수가 더 커도 1단계를 먼저 놓는다
  const list = [cand('outer', 50, { outer: true, x: 0 }), cand('inner', 2, { x: 10 })];
  assert.deepEqual(ids(placeLabels(list, 125, [])), ['inner']);
});

test('only 를 주면 배율과 상관없이 부른 선과 강조 · 고른 선만 단다 (팀 피드백 1)', () => {
  const list = spread().map((c) => (c.id === 'f' ? { ...c, force: true } : c));
  // 아무것도 안 부르면 고른 선만 — 기본으로 숨긴다
  assert.deepEqual(ids(placeLabels(list, 100, [], { only: new Set() })), ['f']);
  // 배율이 커도 마찬가지다 — 9/28 규칙이면 200% 에서 여덟 다 단다
  assert.deepEqual(ids(placeLabels(list, 200, [], { only: new Set() })), ['f']);
  // 부른 선은 바깥 선이어도, 건수가 작아도 단다
  assert.deepEqual(ids(placeLabels(list, 50, [], { only: new Set(['d', 'o2']) })), ['d', 'f', 'o2']);
});

test('부른 라벨은 이름이나 다른 라벨을 못 피해도 단다 — 피할 자리가 있으면 그리로', () => {
  const name = { x: -80, y: -20, w: 160, h: 40 };
  const m = cand('m', 1, { spots: [{ x: 0, y: 0 }, { x: 0, y: 10 }] });
  assert.deepEqual(placeLabels([m], 100, [name], { only: new Set(['m']) }).get('m'), { x: 0, y: 0 });
  const movable = cand('m', 1, { spots: [{ x: 0, y: 0 }, { x: 0, y: 200 }] });
  assert.deepEqual(placeLabels([movable], 100, [name], { only: new Set(['m']) }).get('m'), { x: 0, y: 200 });
  // 둘을 같이 부르면 라벨끼리는 피해 본다
  const two = [cand('a', 5, { x: 0 }), cand('b', 4, { spots: [{ x: 10, y: 0 }, { x: 10, y: 60 }] })];
  const got = placeLabels(two, 100, [], { only: new Set(['a', 'b']) });
  assert.deepEqual(got.get('b'), { x: 10, y: 60 });
});

test('범례 밀기 — 범례 밑으로 들어간 만큼, 오른쪽이 넘치지 않을 만큼만', () => {
  const vb = { w: 1000, h: 620 };
  // 판 크기를 모르면 안 민다
  assert.equal(legendShift(null, 218, { min: 185, max: 815 }, vb), 0);
  // 1366 창 — 판이 700 × 500 이면 폭에 맞춰 0.7 배, 범례가 viewBox 311 까지 덮는다
  const s = legendShift({ w: 700, h: 500 }, 218, { min: 185, max: 815 }, vb);
  assert.ok(Math.abs(s - (218 / 0.7 - 185)) < 1e-9);
  // 넓은 그래프는 오른쪽 끝이 viewBox 에 닿을 때까지만
  assert.equal(legendShift({ w: 700, h: 500 }, 218, { min: 70, max: 930 }, vb), 70);
  // 판이 넓어 범례가 그래프에 안 닿으면 안 민다
  assert.equal(legendShift({ w: 1600, h: 620 }, 218, { min: 185, max: 815 }, vb), 0);
});

test('범례 맞춤 — 밀기로 모자라면 범례 오른쪽에 맞게 줄이고, 세로 가운데를 지킨다 (G-10 남은 결함)', () => {
  const vb = { w: 1000, h: 620 };
  // 밀기로 비킬 수 있으면 밀기만
  const a = legendFit({ w: 700, h: 500 }, 218, { min: 185, max: 815 }, vb);
  assert.equal(a.s, 1);
  assert.ok(Math.abs(a.dx - (218 / 0.7 - 185)) < 1e-9);
  // 섬 간 보기처럼 넓은 그래프(210 ~ 990)는 밀기가 10 에서 막힌다 — 범례 오른쪽(311)부터 1000 까지로 줄인다
  const covered = 218 / 0.7;
  const b = legendFit({ w: 700, h: 500 }, 218, { min: 210, max: 990 }, vb);
  assert.ok(b.s < 1 && b.s >= 0.6);
  assert.ok(Math.abs(b.s * 210 + b.dx - covered) < 1e-9, '왼쪽 끝이 범례 오른쪽에 온다');
  assert.ok(b.s * 990 + b.dx <= 1000 + 1e-9, '오른쪽 끝은 viewBox 안');
  assert.ok(Math.abs(b.dy - ((1 - b.s) * 620) / 2) < 1e-9, '세로 가운데');
  // 판 크기를 모르면 그대로
  assert.deepEqual(legendFit(null, 218, { min: 210, max: 990 }, vb), { dx: 0, dy: 0, s: 1 });
});
