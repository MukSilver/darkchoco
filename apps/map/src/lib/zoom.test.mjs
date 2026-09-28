/**
 * src/lib/zoom.ts 시험 — 줌 범위와 휠 누적 (G-10 묶음 5).
 *
 *   node --experimental-strip-types --test src/lib/zoom.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { WHEEL_STEP, clampZoom, wheelSteps } from './zoom.ts';

test('줌은 50 ~ 200 사이 (설계서 4.2.3)', () => {
  assert.equal(clampZoom(25), 50);
  assert.equal(clampZoom(225), 200);
  assert.equal(clampZoom(125), 125);
});

test('휠은 모아서 문턱을 넘을 때 한 단계씩 — 트랙패드 한 번에 끝까지 튀지 않는다', () => {
  // 트랙패드처럼 작은 값이 여러 번 오면 문턱을 넘을 때까지 안 옮긴다
  let s = { acc: 0, steps: 0 };
  let moved = 0;
  for (let i = 0; i < 9; i++) {
    s = wheelSteps(s.acc, -10);
    moved += s.steps;
  }
  assert.equal(moved, 0, '-90 은 아직 문턱 밑');
  s = wheelSteps(s.acc, -10);
  assert.equal(s.steps, 1, '-100 을 넘으면 확대 한 단계');
  // 마우스 휠 한 칸(100)은 한 단계, 아래로는 축소
  assert.deepEqual(wheelSteps(0, WHEEL_STEP), { acc: 0, steps: -1 });
  // 줄 단위 휠은 한 줄을 40 으로 본다
  assert.equal(wheelSteps(0, -3, 1).steps, 1);
});
