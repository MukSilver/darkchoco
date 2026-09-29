// mapui.ts 시험.  node --experimental-strip-types --test src/lib/mapui.test.mjs
//
// 지도 조작의 자리 계산 — 고른 영토로 옮기기 · 툴팁 뒤집기 · 스냅샷 눈금 · 스냅샷 이름.

import test from 'node:test';
import assert from 'node:assert/strict';

import { fitTicks, labelT, labelTicks, pastSnapshot, revealPan, tipPlace, toCanvas } from './mapui.ts';
import { quarterText } from './quarter.ts';

// 판 1000 × 680, 위 여백 16 · 아래 여백 64 → 지도 판은 1000 × 600
const STAGE = { w: 1000, h: 680, top: 16, bottom: 64 };
// 판과 비율이 같은 viewBox 라 1 단위가 2px 이다
const VB = '0 0 500 300';
const HOME = { zoom: 100, pan: { x: 0, y: 0 } };

/* ── viewBox → 캔버스 ────────────────────────────────────────── */

test('처음 자리에서는 viewBox 가운데가 판 가운데다', () => {
  assert.deepEqual(toCanvas({ x: 250, y: 150 }, VB, STAGE, HOME), { x: 500, y: 316 });
  assert.deepEqual(toCanvas({ x: 0, y: 0 }, VB, STAGE, HOME), { x: 0, y: 16 });
});

test('판보다 납작한 viewBox 는 가운데 앉는다 (xMidYMid meet)', () => {
  // 1000 × 200 은 폭에 맞춰 1 단위 1px, 위아래로 200px 씩 빈다
  assert.deepEqual(toCanvas({ x: 0, y: 0 }, '0 0 1000 200', STAGE, HOME), { x: 0, y: 216 });
});

test('줌은 판 가운데를 기준으로 키우고 이동은 그 뒤에 더한다', () => {
  const v = { zoom: 200, pan: { x: 30, y: -40 } };
  // 가운데는 줌에 안 움직인다
  assert.deepEqual(toCanvas({ x: 250, y: 150 }, VB, STAGE, v), { x: 530, y: 276 });
  // 왼쪽 위 끝은 가운데에서 두 배 멀어진다
  assert.deepEqual(toCanvas({ x: 0, y: 0 }, VB, STAGE, v), { x: -500 + 30, y: 316 - 600 - 40 });
});

/* ── 화면 밖이면 옮기기 (설계서 4.2.3) ───────────────────────── */

test('보이는 영토는 안 옮긴다', () => {
  assert.equal(revealPan({ x: 250, y: 150 }, VB, STAGE, HOME), null);
  assert.equal(revealPan({ x: 30, y: 30 }, VB, STAGE, HOME), null);
});

test('화면 밖 영토는 줌을 두고 판 가운데로 옮긴다', () => {
  // 200% 로 키우면 왼쪽 위 칸이 판 밖으로 나간다
  const v = { zoom: 200, pan: { x: 0, y: 0 } };
  const p = { x: 50, y: 40 };
  const pan = revealPan(p, VB, STAGE, v);
  assert.ok(pan);
  const at = toCanvas(p, VB, STAGE, { zoom: 200, pan });
  assert.ok(Math.abs(at.x - 500) <= 1);
  assert.ok(Math.abs(at.y - 316) <= 1);
});

test('가장자리 여백 안쪽으로 붙은 것도 밖으로 본다', () => {
  // x = 10 단위 → 20px. 여백 48px 안쪽이다
  assert.ok(revealPan({ x: 10, y: 150 }, VB, STAGE, HOME));
  // 아래 여백(힌트 · 줌 자리)으로 내려간 것도 밖이다
  assert.ok(revealPan({ x: 250, y: 299 }, VB, STAGE, HOME));
});

test('끌어서 옮긴 상태도 그 이동을 기준으로 가른다', () => {
  const dragged = { zoom: 100, pan: { x: -700, y: 0 } };
  // 가운데 영토가 왼쪽 밖으로 밀려 나갔다
  const pan = revealPan({ x: 250, y: 150 }, VB, STAGE, dragged);
  assert.deepEqual(pan, { x: 0, y: 0 });
});

/* ── 툴팁 뒤집기 ──────────────────────────────────────────────── */

const TIP = { w: 255, h: 141 };
const BOX = { w: 800, h: 600 };

test('툴팁은 커서 오른쪽 아래에 뜬다', () => {
  assert.deepEqual(tipPlace({ x: 100, y: 100 }, TIP, BOX), { left: 114, top: 114 });
});

test('오른쪽 · 아래를 넘으면 커서 반대쪽으로 뒤집는다', () => {
  assert.deepEqual(tipPlace({ x: 700, y: 100 }, TIP, BOX), { left: 700 - 14 - 255, top: 114 });
  assert.deepEqual(tipPlace({ x: 100, y: 550 }, TIP, BOX), { left: 114, top: 550 - 14 - 141 });
  assert.deepEqual(tipPlace({ x: 790, y: 590 }, TIP, BOX), { left: 521, top: 435 });
});

test('캔버스가 툴팁보다 작으면 끝에 붙인다', () => {
  assert.deepEqual(tipPlace({ x: 100, y: 60 }, TIP, { w: 300, h: 150 }), { left: 45, top: 9 });
});

/* ── 스냅샷 눈금 (설계서 4.2.5) ──────────────────────────────── */

test('분기가 적으면 이름표를 다 단다', () => {
  assert.deepEqual(labelTicks(5, 8), [0, 1, 2, 3, 4]);
  assert.deepEqual(labelTicks(1, 8), [0]);
  assert.deepEqual(labelTicks(0, 8), []);
});

test('이름표 수는 슬라이더 폭에 맞춘다 — 좁으면 줄이고 넓으면 분기 수대로 (G-10 묶음 6 검토)', () => {
  // 20분기, 1280 창 · 패널 연 스냅샷 바(슬라이더 약 286px). 셋마다 달면 첫 둘이 겹친다
  assert.deepEqual(fitTicks(20, 286, 40, 8), [0, 5, 10, 15, 19]);
  // 넓은 바(약 390px)는 분기 수로 정한 것과 같다
  assert.deepEqual(fitTicks(20, 390, 40, 8), labelTicks(20, 8));
  assert.deepEqual(fitTicks(20, 60, 40, 8), [0, 19], '아주 좁으면 양 끝만');
  assert.deepEqual(fitTicks(1, 286, 40, 8), [0]);
  assert.deepEqual(fitTicks(0, 286, 40, 8), []);
});

test('많으면 건너뛰되 오른쪽 끝은 늘 단다', () => {
  // 9분기(2024 Q3 ~ 2026 Q3) — 피그마 ⑦-1a 처럼 두 분기마다
  assert.deepEqual(labelTicks(9, 8), [0, 2, 4, 6, 8]);
  assert.deepEqual(labelTicks(10, 8), [0, 2, 4, 6, 8, 9]);
});

test('끝 바로 앞 이름표가 반 간격도 안 떨어지면 뺀다', () => {
  // 17분기 → 세 분기마다. 15 와 16 이 붙으므로 15 를 뺀다
  assert.deepEqual(labelTicks(17, 8), [0, 3, 6, 9, 12, 16]);
});

/* ── 스냅샷 이름 (피그마 ⑦-1a · ⑦-1b) ───────────────────────── */

test('지나간 분기만 스냅샷 이름을 낸다', () => {
  assert.equal(pastSnapshot('2025-Q3', '2026-Q3'), '2025 Q3');
  // 화면 분기 표기는 한 꼴이다 — 타임라인 · 스냅샷 바 · 관계 패널이 같이 쓴다 (G-10 묶음 9)
  assert.equal(quarterText('2021-Q4'), '2021 Q4');
  assert.equal(pastSnapshot('2026-Q3', '2026-Q3'), null);
});

test('같은 두 영토 사이 선들의 알약 자리 — 가운데, 그다음 양옆으로 번갈아, 끝에서 멈춘다 (G-10 남은 결함)', () => {
  assert.equal(labelT(0), 0.5);
  assert.ok(Math.abs(labelT(1) - 0.33) < 1e-9);
  assert.ok(Math.abs(labelT(2) - 0.67) < 1e-9);
  assert.ok(Math.abs(labelT(3) - 0.16) < 1e-9);
  assert.equal(labelT(9), 0.16, '많아도 앞쪽 끝 가까이에서 멈춘다');
  assert.equal(labelT(10), 0.84, '뒤쪽 끝도');
});
