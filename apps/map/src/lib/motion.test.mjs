/**
 * src/lib/motion.ts 시험 — 시점을 옮길 때 섬이 옮겨 가는 계산 (G-10 묶음 6).
 *
 *   node --experimental-strip-types --test src/lib/motion.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { boxOrigin, flipFrom, growFrom, islandBoxes, parseMs } from './motion.ts';

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
