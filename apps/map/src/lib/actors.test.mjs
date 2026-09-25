/**
 * src/lib/actors.ts 시험 — 행위자의 활동 영토와 주 활동 영토 (설계서 4.3.8).
 * 검색(전체 기간)과 행위자 패널(기준일까지)이 같은 함수를 쓴다.
 *
 *   node --experimental-strip-types --test src/lib/actors.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { activityTerritories, mainTerritory } from './actors.ts';

let seq = 0;
function ev(territoryId, postedAt, extra = {}) {
  seq += 1;
  return {
    id: `a${seq}`, territoryId, postedAt, verdict: 'high', size: 'unknown',
    repost: false, excluded: false, ...extra,
  };
}

test('사건이 많은 영토가 앞이고, 같으면 늦게 올린 곳이 앞이다', () => {
  const events = [
    ev('bf', '2026-05-01T10:00:00+09:00', { actorTerritoryId: 'hex' }),
    ev('bf', '2026-06-01T10:00:00+09:00', { actorTerritoryId: 'hex' }),
    ev('xss', '2026-09-01T10:00:00+09:00', { actorTerritoryId: 'hex' }),
    ev('cr', '2026-08-01T10:00:00+09:00', { actorTerritoryId: 'hex' }),
    // 다른 행위자 · 행위자 영토 자신에 올라온 것은 안 센다
    ev('bf', '2026-09-02T10:00:00+09:00', { actorTerritoryId: 'other' }),
    ev('hex', '2026-09-03T10:00:00+09:00', { actorTerritoryId: 'hex' }),
  ];
  const rows = activityTerritories(events, 'hex');
  assert.deepEqual(rows.map((r) => [r.territoryId, r.count]), [['bf', 2], ['xss', 1], ['cr', 1]]);
  assert.equal(rows[0].last, '2026-06-01T10:00:00+09:00');
  assert.equal(mainTerritory(rows), 'bf');
});

test('keep 으로 거른 사건만 센다 — 패널은 기준일까지다', () => {
  const events = [
    ev('bf', '2026-05-01T10:00:00+09:00', { actorTerritoryId: 'hex' }),
    ev('xss', '2026-09-20T10:00:00+09:00', { actorTerritoryId: 'hex' }),
    ev('xss', '2026-09-21T10:00:00+09:00', { actorTerritoryId: 'hex' }),
  ];
  const cut = Date.parse('2026-06-30T23:59:59Z');
  const rows = activityTerritories(events, 'hex', (e) => Date.parse(e.postedAt) <= cut);
  assert.deepEqual(rows.map((r) => r.territoryId), ['bf']);
  // 전체 기간이면 xss 가 주 활동 영토다
  assert.equal(mainTerritory(activityTerritories(events, 'hex')), 'xss');
});

test('올린 곳이 없으면 주 활동 영토는 null 이다', () => {
  assert.deepEqual(activityTerritories([], 'hex'), []);
  assert.equal(mainTerritory([]), null);
});
