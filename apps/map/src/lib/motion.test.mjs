/**
 * src/lib/motion.ts 시험 — 시점을 옮길 때 섬이 옮겨 가는 계산 (G-10 묶음 6).
 *
 *   node --experimental-strip-types --test src/lib/motion.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { boxOrigin, boxUnder, flipFrom, flipTo, growFrom, islandBoxes, parseMs } from './motion.ts';

/** transform 글자 `translate(ax, ay) scale(s) translate(bx, by)` 를 숫자 다섯으로 */
function parts(t) {
  const n = t.match(/-?[\d.]+/g).map(Number);
  assert.equal(n.length, 5, t);
  return n;
}

/**
 * CSS 가 두 transform 을 보간하듯 함수마다 따로 섞고, 점 (x, y) 가 진행도 p 에서 어디 그려지는지 낸다.
 * 두 목록의 함수 모양이 같아야 이렇게 섞인다
 */
function drawAt(from, to, p, x, y) {
  const a = parts(from);
  const b = parts(to);
  const [ax, ay, s, bx, by] = a.map((v, i) => v + (b[i] - v) * p);
  return { x: ax + s * (x + bx), y: ay + s * (y + by) };
}

test('섬 상자는 칸 가운데들을 다 담고, 칸이 없는 섬은 뺀다', () => {
  const boxes = islandBoxes({
    islands: [
      { islandKey: 'a', cells: [[0, 0], [1, 0], [0, 1]] },
      { islandKey: 'empty', cells: [] },
    ],
  });
  assert.ok(boxes.has('a'));
  assert.ok(!boxes.has('empty'));
  const a = boxes.get('a');
  assert.ok(a.w > 0 && a.h > 0);
});

test('FLIP — 틀이 옮겨 가면 앞 자리를 새 틀 기준으로 옮겨 적는다', () => {
  const was = { cx: 100, cy: 50, w: 40, h: 20 };
  const now = { cx: 120, cy: 60, w: 80, h: 40 };
  // 틀이 그대로면 앞 가운데로 옮기고 크기 비 0.5
  assert.equal(flipFrom(was, now, { x: 0, y: 0 }, { x: 0, y: 0 }), 'translate(100px, 50px) scale(0.5) translate(-120px, -60px)');
  // 새 틀 원점이 (-10, -5) 로 옮겼으면 앞 자리도 그만큼
  assert.equal(flipFrom(was, now, { x: 0, y: 0 }, { x: -10, y: -5 }), 'translate(90px, 45px) scale(0.5) translate(-120px, -60px)');
  // 크기 비는 0.4~2.5 로 자른다
  assert.match(flipFrom({ ...was, w: 1, h: 1 }, now, { x: 0, y: 0 }, { x: 0, y: 0 }), /scale\(0\.4\)/);
});

test('섬 가운데는 곧게 간다 — 도착 모양이 첫 모양과 같은 함수 목록 (G-10 묶음 6 검토)', () => {
  const was = { cx: 100, cy: 50, w: 40, h: 20 };
  const now = { cx: 420, cy: 330, w: 80, h: 40 };
  const from = flipFrom(was, now, { x: 0, y: 0 }, { x: 0, y: 0 });
  const to = flipTo(now);
  assert.equal(to, 'translate(420px, 330px) scale(1) translate(-420px, -330px)');
  for (const p of [0, 0.25, 0.5, 0.75, 1]) {
    const at = drawAt(from, to, p, now.cx, now.cy);
    assert.ok(Math.abs(at.x - (100 + 320 * p)) < 0.01, `x p=${p}`);
    assert.ok(Math.abs(at.y - (50 + 280 * p)) < 0.01, `y p=${p}`);
  }
  // 새 섬도 번지는 동안 제자리다
  const g = drawAt(growFrom(now), to, 0.5, now.cx, now.cy);
  assert.ok(Math.abs(g.x - now.cx) < 0.01 && Math.abs(g.y - now.cy) < 0.01);
});

test('끊긴 움직임은 지금 그려진 자리에서 잇는다', () => {
  const box = { cx: 100, cy: 60, w: 40, h: 20 };
  assert.deepEqual(boxUnder({ a: 1, d: 1, e: 0, f: 0 }, box), box, '행렬이 항등이면 그대로');
  // 반 크기로 줄어 (10, 5) 옮겨 그려지는 중
  assert.deepEqual(boxUnder({ a: 0.5, d: 0.5, e: 10, f: 5 }, box), { cx: 60, cy: 35, w: 20, h: 10 });
});

test('새로 생긴 섬은 제자리에서 번져 나온다', () => {
  assert.equal(growFrom({ cx: 10, cy: 20, w: 5, h: 5 }), 'translate(10px, 20px) scale(0.85) translate(-10px, -20px)');
});

test('틀 원점과 CSS 시간 읽기', () => {
  assert.deepEqual(boxOrigin('-50 -35 200 120'), { x: -50, y: -35 });
  assert.equal(parseMs('480ms'), 480);
  assert.equal(parseMs(' 0.3s '), 300);
  assert.equal(parseMs('0ms'), 0);
  assert.equal(parseMs(''), 0, '움직임 줄이기 · 못 읽음은 0 — 안 움직인다');
});
