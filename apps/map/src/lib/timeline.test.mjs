/**
 * src/lib/timeline.ts 시험 — 타임라인 탭의 시점 고르기와 집계 (설계서 4.3.7).
 *
 *   node --experimental-strip-types --test src/lib/timeline.test.mjs
 *
 * 스냅샷은 손으로 만든다. `snapshots` 는 `computeMap` 을 부르므로 그 부분은
 * 작은 자료로 한 번만 돌린다.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  chipQuarter,
  compareStart,
  comparePick,
  diff,
  growth,
  peakOf,
  snapshots,
  stepYear,
  thumbBoxes,
  yearCards,
  yearChips,
} from './timeline.ts';
import { quarterRange } from './quarter.ts';

/** 2021-Q4 ~ 2026-Q3. 실제 데이터와 같은 모양이다 (첫 해 Q4 하나, 올해 Q1~Q3) */
const QS = quarterRange('2021-Q4', '2026-Q3');

const info = (id) => ({ name: id, token: id.toLowerCase() });

/** 손으로 만든 스냅샷. byIsland 차례가 섬 목록 차례다 */
function snap(ym, events, byIsland = {}, delta = null) {
  const [y, q] = ym.split('-Q').map(Number);
  return {
    ym, year: y, q, events, delta, fresh: null,
    byIsland: { FORUM: 0, RANSOMWARE: 0, TELEGRAM: 0, ACTOR: 0, ...byIsland },
    layout: { viewBox: '0 0 100 100', size: 10, islands: [], territories: [] },
  };
}

test('연도 칩은 분기 목록 안의 분기를 가리킨다 (L797)', () => {
  assert.equal(chipQuarter(2023, QS), '2023-Q3', '보통 해는 3분기');
  assert.equal(chipQuarter(2021, QS), '2021-Q4', '첫 해에 3분기가 없으면 가장 가까운 분기');
  assert.equal(chipQuarter(2026, QS), '2026-Q3');
  assert.equal(chipQuarter(2026, quarterRange('2025-Q1', '2026-Q2')), '2026-Q2', '올해가 2분기에서 끝나면 2분기');
  assert.equal(chipQuarter(2027, QS), null, '목록에 없는 해');
  assert.equal(chipQuarter(2021, quarterRange('2021-Q1', '2021-Q2')), '2021-Q2');
});

test('◀ / ▶▶ 는 한 해씩, 끝에서 멈춘다 (L798)', () => {
  assert.equal(stepYear(QS, '2024-Q3', -1), '2023-Q3');
  assert.equal(stepYear(QS, '2024-Q3', 1), '2025-Q3');
  assert.equal(stepYear(QS, '2022-Q2', -1), '2021-Q4', '한 해 앞이 목록 밖이면 첫 분기에서 멈춘다');
  assert.equal(stepYear(QS, '2021-Q4', -1), null, '이미 처음이면 없다');
  assert.equal(stepYear(QS, '2026-Q1', 1), '2026-Q3', '한 해 뒤가 목록 밖이면 끝 분기');
  assert.equal(stepYear(QS, '2026-Q3', 1), null);
  assert.equal(stepYear(QS, '1999-Q1', 1), null, '목록에 없는 시점');
});

test('시점 비교 — 처음은 3년 전 같은 분기 ↔ 최근, 칩은 A · B 를 번갈아 채운다 (L812-813)', () => {
  const c = compareStart(QS);
  assert.deepEqual(c, { a: '2023-Q3', b: '2026-Q3', next: 'a' });
  const c1 = comparePick(c, '2022-Q3');
  assert.deepEqual(c1, { a: '2022-Q3', b: '2026-Q3', next: 'b' }, '첫 클릭이 A');
  const c2 = comparePick(c1, '2025-Q3');
  assert.deepEqual(c2, { a: '2022-Q3', b: '2025-Q3', next: 'a' }, '두 번째가 B');
  assert.equal(comparePick(c2, '2024-Q3').a, '2024-Q3', '세 번째는 다시 A');

  assert.deepEqual(
    compareStart(quarterRange('2025-Q1', '2026-Q2')),
    { a: '2025-Q1', b: '2026-Q2', next: 'a' },
    '3년치가 안 되면 첫 분기가 A',
  );
  assert.equal(compareStart(['2026-Q3']), null, '시점이 하나면 비교가 없다');
});

test('전년 대비는 한 해 앞 같은 분기와 견준다 (L806)', () => {
  const island = { id: 'FORUM', web: 'dark', name: '포럼', hex: '#000', legend: '#000' };
  const territories = [{ id: 'f1', name: 'f1', islandId: 'FORUM', web: 'dark', since: '2024-01-05T00:00:00Z' }];
  const at = (iso) => ({ id: iso, territoryId: 'f1', postedAt: iso, verdict: 'high', size: 'unknown', repost: false, excluded: false });
  const events = [
    at('2024-01-05T00:00:00Z'),
    at('2024-05-05T00:00:00Z'),
    at('2024-08-05T00:00:00Z'),
    at('2025-02-05T00:00:00Z'),
    at('2025-02-06T00:00:00Z'),
  ];
  const today = new Date('2025-03-31T00:00:00Z');
  const s = snapshots(
    { islands: [island], territories, events, web: 'dark', today },
    quarterRange('2024-Q1', '2025-Q1'),
  );
  assert.deepEqual(s.map((x) => x.events), [1, 2, 3, 3, 5]);
  assert.deepEqual(s.map((x) => x.delta), [null, null, null, null, 4], '2025-Q1 − 2024-Q1 = 5 − 1');
});

test('연도 칩 · 스냅샷 카드 — 해마다 한 칸, 올해 카드는 최신 분기 (L797 · L807)', () => {
  const snaps = QS.map((ym, i) => snap(ym, 10 + i));
  const chips = yearChips(snaps);
  assert.deepEqual(chips.map((c) => c.snap.ym), ['2021-Q4', '2022-Q3', '2023-Q3', '2024-Q3', '2025-Q3', '2026-Q3']);
  assert.equal(chips[3].snap.events, snaps.find((s) => s.ym === '2024-Q3').events, '칩 숫자 = 칩이 가리키는 시점의 건수');

  // 올해가 Q4 까지 있으면 칩은 Q3, 카드는 최신
  const longer = quarterRange('2021-Q4', '2026-Q4').map((ym, i) => snap(ym, i));
  assert.equal(yearChips(longer).at(-1).snap.ym, '2026-Q3');
  assert.equal(yearCards(longer).at(-1).snap.ym, '2026-Q4');
  assert.equal(yearCards(longer)[0].snap.ym, '2021-Q4');
  assert.deepEqual(yearCards([]), []);
});

test('성장 요약과 섬별 증가는 0건 섬도 넣고 섬 목록 차례를 지킨다 (L808-809)', () => {
  const a = snap('2023-Q3', 10, { FORUM: 6, RANSOMWARE: 4 });
  const b = snap('2026-Q3', 30, { FORUM: 12, RANSOMWARE: 10, ACTOR: 13 });
  const g = growth(a, b, info);
  assert.deepEqual(g.map((r) => r.islandId), ['FORUM', 'RANSOMWARE', 'TELEGRAM', 'ACTOR'], '건수 순이 아니라 목록 차례');
  assert.deepEqual(g.map((r) => [r.from, r.to]), [[6, 12], [4, 10], [0, 0], [0, 13]]);
  assert.equal(g[0].rate, 100);
  assert.equal(g[3].rate, null, '처음이 0건이면 비율이 없다');

  const d = diff(a, b, info);
  assert.deepEqual(d.islands.map((i) => i.islandId), ['FORUM', 'RANSOMWARE', 'TELEGRAM', 'ACTOR']);
  assert.equal(d.islands[2].delta, 0);
  assert.equal(d.deltaEvents, 20);
  assert.equal(d.times, 3);
});

test('눈금 최댓값과 썸네일 viewBox', () => {
  assert.equal(peakOf([snap('2024-Q1', 0), snap('2024-Q2', 5, { RANSOMWARE: 7 })]), 7);
  assert.equal(peakOf([]), 1, '빈 목록도 0 으로 나누지 않게 1');

  // 가장 큰 폭 · 높이로 맞추고 제 가운데에 둔다
  assert.deepEqual(thumbBoxes(['0 0 100 50', '-10 -20 200 100']), ['-50 -25 200 100', '-10 -20 200 100']);
});
