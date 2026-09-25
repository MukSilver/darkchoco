/**
 * src/lib/entity.ts 시험 — 엔티티 탭 KPI 와 최근 관측 (설계서 4.3.5).
 *
 *   node --experimental-strip-types --test src/lib/entity.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { latestSeen, monthDay, recentKpi, seenDays } from './entity.ts';
import { computeMap } from './score.ts';

let seq = 0;
function ev(territoryId, postedAt, extra = {}) {
  seq += 1;
  return {
    id: `e${seq}`, territoryId, postedAt, verdict: 'high', size: 'unknown',
    repost: false, excluded: false, ...extra,
  };
}

const D = new Date('2026-09-30T23:59:59Z');

test('최근 30일 사건 — 행위자 섬도 제 몫이 잡히고 전월 대비는 직전 30일과의 차다 (L725)', () => {
  const islands = [
    { id: 'FORUM', web: 'dark', name: '포럼', hex: '#000', legend: '#000' },
    { id: 'ACTOR', web: 'dark', name: '행위자', hex: '#000', legend: '#000' },
  ];
  const territories = [
    { id: 'f1', name: 'f1', islandId: 'FORUM', web: 'dark', since: '2026-01-01T00:00:00Z' },
    { id: 'a1', name: 'a1', islandId: 'ACTOR', web: 'dark', since: '2026-01-01T00:00:00Z' },
    { id: 'a2', name: 'a2', islandId: 'ACTOR', web: 'dark', since: '2026-01-01T00:00:00Z' },
  ];
  const events = [
    ev('f1', '2026-09-20T00:00:00Z', { actorTerritoryId: 'a1' }),
    ev('f1', '2026-09-25T00:00:00Z', { actorTerritoryId: 'a2' }),
    ev('f1', '2026-09-26T00:00:00Z', { actorTerritoryId: 'a2' }),
    ev('f1', '2026-08-20T00:00:00Z', { actorTerritoryId: 'a1' }), // 직전 30일
    ev('f1', '2026-09-27T00:00:00Z', { actorTerritoryId: 'a1', dateSubstituted: true }), // 창에서 뺀다
    ev('f1', '2026-09-28T00:00:00Z', { actorTerritoryId: 'a1', verdict: 'false' }), // 허위
    ev('f1', '2026-01-01T00:00:00Z'),
  ];
  const r = computeMap({ islands, territories, events }, D);
  const rows = (island) =>
    r.territories.filter((t) => t.islandKey.endsWith(island)).map((metrics) => ({ metrics }));

  assert.deepEqual(recentKpi(rows('ACTOR')), { count: 3, trend: 2 }, '행위자 섬: 이번 3건, 직전 1건');
  assert.deepEqual(recentKpi(rows('FORUM')), { count: 3, trend: 2 }, '포럼 섬도 같은 사건을 제 영토로 센다');
  assert.deepEqual(
    recentKpi([{ metrics: { recent30: 4, prev30: 0 } }]),
    { count: 4, trend: null },
    '직전 30일이 0건이면 화살표가 없다',
  );
  assert.deepEqual(recentKpi([]), { count: 0, trend: null });
});

test('최근 관측은 시각으로 둔다 — 해가 바뀌어도 차례가 맞다 (L737-739)', () => {
  const events = [
    ev('t1', '2025-12-30T00:00:00Z'),
    ev('t2', '2026-01-02T00:00:00Z'),
    ev('t2', '2026-02-01T00:00:00Z', { verdict: 'false' }), // 허위는 뺀다
    ev('t3', '2026-10-05T00:00:00Z'), // 기준일 뒤
    ev('t3', '2026-03-01T00:00:00Z', { excluded: true }), // 반출 제외
    ev('t4', '2026-05-01T00:00:00Z', { actorTerritoryId: 'a1' }),
  ];
  const seen = latestSeen(events, D);
  assert.equal(monthDay(seen.t1), '12-30');
  assert.equal(monthDay(seen.t2), '01-02', '허위 사건은 관측으로 안 친다');
  assert.equal(seen.t3, undefined, '기준일 뒤 · 반출 제외만 있으면 없다');
  assert.equal(monthDay(seen.a1), '05-01', '행위자 영토는 그 행위자가 올린 사건도 제 것');
  // 글자로는 '12-30' > '01-02' 지만 실제로는 t2 가 더 최근이다
  assert.ok(seen.t2 > seen.t1);
});

test('최근 관측 글자는 가장 늦은 사건의 노션 날짜 글자다 (사건 줄과 같게)', () => {
  const D = new Date('2026-09-30T23:59:59Z');
  const ev = (id, t, postedAt, extra = {}) => ({
    id, territoryId: t, postedAt, verdict: 'high', size: 'unknown', repost: false, excluded: false, ...extra,
  });
  const got = seenDays([
    ev('a', 'f', '2026-05-14T06:58:00.000+09:00'),
    ev('b', 'f', '2026-05-01T10:00:00.000+09:00'),
    ev('c', 'r', '2026-06-01', { actorTerritoryId: 'x' }),
    ev('d', 'r', '2026-10-05'),
    ev('e', 'r', '2026-07-01', { verdict: 'false' }),
  ], D);
  // +09:00 새벽 사건도 노션 날짜(05-14) 그대로다. UTC 로 옮기면 05-13 이 된다
  assert.deepEqual(got, { f: '05-14', r: '06-01', x: '06-01' });
});
