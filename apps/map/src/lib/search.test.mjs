/**
 * src/lib/search.ts 시험 — 검색 창과 전체 결과 화면이 쓰는 계산 (설계서 4.2.2).
 *
 *   node --experimental-strip-types --test src/lib/search.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  NO_FILTER,
  agoText,
  buildIndex,
  markAt,
  matchName,
  narrowed,
  nearby,
  pushRecent,
  quarterFor,
  search,
  total,
} from './search.ts';

/* ── 재료 ─────────────────────────────────────────────────────── */

const TODAY = new Date('2026-09-25T00:00:00Z');

let seq = 0;
function ev(territoryId, postedAt, extra = {}) {
  seq += 1;
  return {
    id: `e${seq}`, territoryId, postedAt, verdict: 'high', size: 'unknown',
    repost: false, excluded: false, ...extra,
  };
}

const TERR = [
  { id: 'bf', name: 'BreachForums bf', islandId: 'FORUM', aliases: ['BreachForums'] },
  { id: 'xss', name: 'XSS.is', islandId: 'FORUM' },
  { id: 'qilin', name: 'Qilin', islandId: 'RANSOMWARE' },
  { id: 'lockbit', name: 'LockBit', islandId: 'RANSOMWARE' },
  { id: 'chan', name: '랜섬웨어 공지 채널', islandId: 'TELEGRAM' },
  { id: 'hex', name: 'hexbreaker', islandId: 'ACTOR', aliases: ['hexb'] },
  // 한 번도 지도에 안 나온 곳 (2.5 로 빠짐)
  { id: 'gone', name: 'BreachGone', islandId: 'FORUM' },
];
const SEEN = new Set(['bf', 'xss', 'qilin', 'lockbit', 'chan', 'hex']);

const E1 = ev('bf', '2026-09-10T10:00:00+09:00', { actorTerritoryId: 'hex' });
const E2 = ev('bf', '2026-05-01T10:00:00+09:00', { actorTerritoryId: 'hex' });
const E3 = ev('xss', '2026-09-20T10:00:00+09:00', { actorTerritoryId: 'hex' });
const E4 = ev('qilin', '2026-09-01T10:00:00+09:00');
const E5 = ev('bf', '2026-09-12T10:00:00+09:00', { verdict: 'false' });
const E6 = ev('bf', '2026-09-13T10:00:00+09:00', { excluded: true });
const E7 = ev('gone', '2026-09-14T10:00:00+09:00');
const EVENTS = [E1, E2, E3, E4, E5, E6, E7];

const REL = [
  { id: 'R1', from: 'qilin', to: 'bf', kind: 'affiliate', confidence: 'confirmed', evidence: [E4.id] },
  { id: 'R2', from: 'chan', to: 'bf', kind: 'contact', confidence: 'estimated', evidence: [] },
  // 허위 사건만 근거 — 빠진다
  { id: 'R3', from: 'lockbit', to: 'bf', kind: 'leak', confidence: 'high', evidence: [E5.id] },
  // 두 단계 — bf 와 관계있는 qilin 의 다른 관계. bf 로 찾으면 안 나온다
  { id: 'R4', from: 'qilin', to: 'lockbit', kind: 'sale', confidence: 'high', evidence: [E4.id] },
  { id: 'R5', from: 'hex', to: 'bf', kind: 'activity', confidence: 'confirmed', evidence: [E1.id, E2.id] },
];

const IX = buildIndex({ territories: TERR, events: EVENTS, relations: REL, seen: SEEN, today: TODAY });
const ids = (xs, f) => xs.map(f);

/* ── 색인 ─────────────────────────────────────────────────────── */

test('색인은 지도에 나온 적 없는 영토와 허위 · 반출 제외 사건을 뺀다', () => {
  assert.ok(!IX.byId.has('gone'));
  assert.deepEqual(ids(IX.events, (e) => e.id).sort(), [E1.id, E2.id, E3.id, E4.id].sort());
  // 사건 수는 전체 기간이다. 행위자는 올린 사건을 센다
  assert.equal(IX.byId.get('bf').eventCount, 2);
  assert.equal(IX.byId.get('hex').eventCount, 3);
  assert.equal(IX.byId.get('lockbit').eventCount, 0);
});

test('허위 사건만 근거인 관계는 빠지고, 근거 없는 관계는 1건으로 남는다', () => {
  const by = new Map(IX.rels.map((r) => [r.rel.id, r]));
  assert.ok(!by.has('R3'));
  assert.equal(by.get('R2').count, 1);
  assert.equal(by.get('R2').last, null);
  assert.equal(by.get('R5').count, 2);
});

test('주 활동 영토는 사건을 가장 많이 올린 곳이다', () => {
  assert.equal(IX.main.get('hex'), 'bf');
});

/* ── 이름 대조 ───────────────────────────────────────────────── */

test('이름 대조는 대소문자를 무시하고 완전 · 앞부분 · 중간을 가른다', () => {
  assert.deepEqual(matchName('Qilin', [], 'qilin'), { rank: 0, at: 0, via: undefined });
  assert.equal(matchName('BreachForums bf', [], 'bre').rank, 1);
  assert.equal(matchName('BreachForums bf', [], 'forum').rank, 2);
  assert.equal(matchName('BreachForums bf', [], 'forum').at, 6);
  // 별칭이 더 잘 맞으면 별칭으로 걸리고 칠할 자리는 없다
  assert.deepEqual(matchName('BreachForums bf', ['BreachForums'], 'breachforums'), { rank: 0, at: -1, via: 'BreachForums' });
  assert.equal(matchName('Qilin', [], 'zz'), null);
  assert.equal(markAt('Qilin → BreachForums bf', 'bre'), 8);
});

/* ── 찾기 ─────────────────────────────────────────────────────── */

test('영토를 찾으면 그 영토의 사건과 관계가 딸려 나오고 두 단계는 안 나온다', () => {
  const r = search(IX, 'Breach', NO_FILTER);
  assert.deepEqual(ids(r.entity, (h) => h.e.id), ['bf']);
  assert.deepEqual(r.actor, []);
  assert.deepEqual(ids(r.event, (h) => h.ev.id), [E1.id, E2.id]);
  assert.deepEqual(ids(r.rel, (h) => h.r.rel.id).sort(), ['R1', 'R2', 'R5']);
  assert.ok(!r.rel.some((h) => h.r.rel.id === 'R4'));
  assert.equal(r.rel.find((h) => h.r.rel.id === 'R1').via, 'bf');
  assert.equal(total(r), 6);
});

test('행위자는 엔티티와 행위자 묶음 둘 다에 나오고, 올린 사건과 활동 관계가 딸린다', () => {
  const r = search(IX, 'hexb', NO_FILTER);
  assert.deepEqual(ids(r.entity, (h) => h.e.id), ['hex']);
  assert.deepEqual(ids(r.actor, (h) => h.e.id), ['hex']);
  assert.equal(r.actor[0].main, 'bf');
  assert.deepEqual(ids(r.event, (h) => h.ev.id), [E3.id, E1.id, E2.id]);
  assert.deepEqual(ids(r.rel, (h) => h.r.rel.id), ['R5']);
});

test('검색어가 비면 아무것도 없다', () => {
  assert.equal(total(search(IX, '  ', NO_FILTER)), 0);
});

/* ── 필터 ─────────────────────────────────────────────────────── */

test('섬 필터 — 엔티티는 그 섬, 관계는 한쪽 끝이 그 섬이면 남는다', () => {
  const f = { ...NO_FILTER, islands: ['TELEGRAM'] };
  const r = search(IX, 'Breach', f);
  assert.deepEqual(r.entity, []);
  assert.deepEqual(r.event, []);
  assert.deepEqual(ids(r.rel, (h) => h.r.rel.id), ['R2']);
  assert.ok(narrowed(f));
  assert.ok(!narrowed({ ...NO_FILTER, scope: 'rel', sort: 'count' }));
});

test('섬 필터에 행위자 섬이 없으면 행위자 묶음이 빠진다', () => {
  assert.equal(search(IX, 'hexb', { ...NO_FILTER, islands: ['FORUM'] }).actor.length, 0);
  assert.equal(search(IX, 'hexb', { ...NO_FILTER, islands: ['ACTOR'] }).actor.length, 1);
});

test('기간 필터 — 사건은 게시 시각, 관계는 마지막 본 날. 날짜 없는 관계는 빠진다', () => {
  const r = search(IX, 'Breach', { ...NO_FILTER, days: 30 });
  assert.deepEqual(ids(r.event, (h) => h.ev.id), [E1.id]);
  assert.deepEqual(ids(r.rel, (h) => h.r.rel.id).sort(), ['R1', 'R5']);
  assert.equal(r.entity.length, 1, '엔티티는 기간으로 안 거른다');
});

test('신뢰도 필터는 관계만 거른다', () => {
  const r = search(IX, 'Breach', { ...NO_FILTER, conf: 'estimated' });
  assert.deepEqual(ids(r.rel, (h) => h.r.rel.id), ['R2']);
  assert.equal(r.event.length, 2);
});

/* ── 정렬 ─────────────────────────────────────────────────────── */

test('관련도는 일치 단계 다음 가중치다', () => {
  const ix = buildIndex({
    territories: [
      { id: 'a', name: 'Alpha Market', islandId: 'FORUM' },
      { id: 'b', name: 'Alpha', islandId: 'FORUM' },
      { id: 'c', name: 'Alphabet', islandId: 'FORUM' },
      { id: 'd', name: 'The Alpha', islandId: 'FORUM' },
    ],
    events: [], relations: [], seen: new Set(['a', 'b', 'c', 'd']), today: TODAY,
  });
  const w = { a: 10, c: 50 };
  const r = search(ix, 'alpha', NO_FILTER, (id) => w[id] ?? 0);
  assert.deepEqual(ids(r.entity, (h) => h.e.id), ['b', 'c', 'a', 'd']);
});

test('최신순과 건수순', () => {
  const recent = search(IX, 'Breach', { ...NO_FILTER, sort: 'recent' });
  // 근거 없는 관계(마지막 본 날 없음)는 맨 뒤
  assert.deepEqual(ids(recent.rel, (h) => h.r.rel.id), ['R5', 'R1', 'R2']);
  const count = search(IX, 'Breach', { ...NO_FILTER, sort: 'count' });
  assert.equal(count.rel[0].r.rel.id, 'R5');
});

/* ── 결과 없음 ───────────────────────────────────────────────── */

test('철자가 가까운 이름 — lockbit5 → LockBit', () => {
  assert.equal(total(search(IX, 'lockbit5', NO_FILTER)), 0);
  assert.deepEqual(ids(nearby(IX, 'lockbit5'), (e) => e.id), ['lockbit']);
  // 치다 만 이름에서 한 글자 틀린 것
  assert.deepEqual(ids(nearby(IX, 'qilim'), (e) => e.id), ['qilin']);
  assert.deepEqual(nearby(IX, 'zzzzzz'), []);
});

/* ── 결과 고르기 ─────────────────────────────────────────────── */

test('기준일 옮기기는 뒤쪽을 먼저, 없으면 앞쪽에서 가장 가까운 분기다', () => {
  const Q = ['2025-Q4', '2026-Q1', '2026-Q2', '2026-Q3'];
  assert.equal(quarterFor(Q, '2026-Q1', () => true), null, '지금 보이면 안 옮긴다');
  assert.equal(quarterFor(Q, '2026-Q1', (q) => q >= '2026-Q2'), '2026-Q2');
  assert.equal(quarterFor(Q, '2026-Q3', (q) => q <= '2026-Q1'), '2026-Q1');
  assert.equal(quarterFor(Q, '2026-Q1', () => false), null);
});

/* ── 최근 검색 ───────────────────────────────────────────────── */

test('최근 검색은 같은 대상을 한 번만, 다섯 개까지 둔다', () => {
  let list = [];
  for (let i = 0; i < 7; i += 1) list = pushRecent(list, { kind: 'entity', id: `t${i}`, label: '', sub: '', at: i });
  assert.deepEqual(ids(list, (x) => x.id), ['t6', 't5', 't4', 't3', 't2']);
  list = pushRecent(list, { kind: 'entity', id: 't4', label: '', sub: '', at: 9 });
  assert.deepEqual(ids(list, (x) => x.id), ['t4', 't6', 't5', 't3', 't2']);
  // 종류가 다르면 id 가 같아도 다른 대상이다
  assert.equal(pushRecent(list, { kind: 'event', id: 't4', label: '', sub: '', at: 10 }).length, 5);
});

test('최근 검색 시각 배지', () => {
  const now = Date.parse('2026-09-25T12:00:00');
  assert.equal(agoText(now - 20 * 1000, now), '방금');
  assert.equal(agoText(now - 3 * 60000, now), '3분 전');
  assert.equal(agoText(now - 5 * 3600000, now), '5시간 전');
  assert.equal(agoText(now - 30 * 3600000, now), '어제');
  assert.equal(agoText(Date.parse('2026-09-14T09:00:00'), now), '09-14');
});
