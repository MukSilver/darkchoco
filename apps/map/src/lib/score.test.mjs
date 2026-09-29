/**
 * src/lib/score.ts 시험 — 설계서 3장 규칙을 작은 자료로 본다.
 *
 *   node --experimental-strip-types --test src/lib/score.test.mjs
 *
 * 정본 엑셀 전체를 대 보는 시험은 `canon.test.mjs` 에 있다. 여기는 규칙
 * 하나하나를 손으로 셀 수 있는 크기로 본다.
 *
 * 왜 .mjs 인가
 *   node 22 의 타입 스트립으로 .ts 를 바로 읽으려면 import 에 '.ts' 확장자를
 *   적어야 한다. 그런데 이 프로젝트 tsconfig 는 allowImportingTsExtensions 가
 *   없어서, 시험을 .ts 로 두면 next build 의 타입 검사가 TS5097 로 막힌다.
 *   tsconfig 의 include 가 .mjs 를 보지 않으므로 시험만 .mjs 로 둔다.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_WEIGHTS,
  computeMap,
  endOfMonthUTC,
  eventScore,
  forumActivity,
  islandKey,
  islandPair,
  minusDays,
  presentAt,
  relationCount,
  relationSpan,
  riskLevel,
  topSurges,
} from './score.ts';
import { quartersOf } from './timeline.ts';
import { quarterEnd } from './quarter.ts';

/* ── 재료 만들기 ───────────────────────────────────────────────── */

let seq = 0;
function ev(territoryId, postedAt, verdict, size = 'unknown', repost = false, excluded = false) {
  seq += 1;
  return { id: `e${seq}`, territoryId, postedAt, verdict, size, repost, excluded };
}

/** 같은 모양 사건 n 건 */
function evs(n, territoryId, postedAt, verdict) {
  return Array.from({ length: n }, () => ev(territoryId, postedAt, verdict));
}

function island(id, web = 'dark') {
  return { id, web, name: id, hex: '#000000', legend: '#000000' };
}

function territory(id, islandId, web = 'dark', extra = {}) {
  return { id, name: id, islandId, web, ...extra };
}

function close(actual, expected, eps, msg) {
  assert.ok(Math.abs(actual - expected) <= eps, `${msg ?? ''} — 받은 값 ${actual}, 기대 ${expected}`);
}

const D = endOfMonthUTC(2026, 9); // 2026-09-30T23:59:59.999Z

/** 영토 하나의 계산 결과 */
function metricOf(input, id, d = D) {
  return computeMap(input, d).territories.find((m) => m.territoryId === id);
}

/* ── 3.2 사건 점수 ─────────────────────────────────────────────── */

test('3.2 — 신뢰성 높음 · 규모 모름 · 첫 게시 = 1점', () => {
  assert.equal(eventScore(ev('t', '2026-09-01T00:00:00Z', 'high', 'unknown', false)), 1);
  // '확인됨'도 같은 1.0 이다
  assert.equal(eventScore(ev('t', '2026-09-01T00:00:00Z', 'confirmed', 'unknown', false)), 1);
});

test('3.2 — 재게시도 1점을 그대로 받는다 (판 1.2 에서 중복 가중치 삭제)', () => {
  // 판 1.1 은 재게시를 0.5배로 깎아 0.4점이었다. 판 1.2 가 그 항을 없앴다
  assert.equal(eventScore(ev('t', '2026-09-01T00:00:00Z', 'unverified', 'unknown', true)), 0.8);
  assert.equal(
    eventScore(ev('t', '2026-09-01T00:00:00Z', 'unverified', 'unknown', false)),
    0.8,
    '처음 글과 재게시가 같은 점수여야 한다',
  );
});

test('3.2 — 규모 가중치 큼 1.5 / 중간 1.2 / 작음·모름 1.0', () => {
  assert.equal(eventScore(ev('t', '2026-09-01T00:00:00Z', 'high', 'large')), 1.5);
  assert.equal(eventScore(ev('t', '2026-09-01T00:00:00Z', 'high', 'medium')), 1.2);
  assert.equal(eventScore(ev('t', '2026-09-01T00:00:00Z', 'high', 'small')), 1);
  assert.equal(eventScore(ev('t', '2026-09-01T00:00:00Z', 'high', 'unknown')), 1);
  // 미확인 0.7, 신뢰성 낮음 0.4
  assert.equal(eventScore(ev('t', '2026-09-01T00:00:00Z', 'unknown')), 0.7);
  assert.equal(eventScore(ev('t', '2026-09-01T00:00:00Z', 'low')), 0.4);
});

test('가중치는 인자로 갈아 끼울 수 있다', () => {
  const w = { ...DEFAULT_WEIGHTS, trust: { ...DEFAULT_WEIGHTS.trust, unverified: 0.5 } };
  assert.equal(eventScore(ev('t', '2026-09-01T00:00:00Z', 'unverified'), w), 0.5);
  // 기본값은 그대로다
  assert.equal(eventScore(ev('t', '2026-09-01T00:00:00Z', 'unverified')), 0.8);
});

test('정본 가중치 — 기본점 20, 전체 800칸, 활동도 최솟값 0.5, 섬 비중 지수 0.6', () => {
  assert.equal(DEFAULT_WEIGHTS.base, 20);
  assert.equal(DEFAULT_WEIGHTS.totalCells.dark, 800);
  assert.equal(DEFAULT_WEIGHTS.activityMin, 0.5);
  assert.equal(DEFAULT_WEIGHTS.islandAlpha, 0.6);
});

/* ── 3.1 집계에 드는 사건 ──────────────────────────────────────── */

const ONE = { islands: [island('FORUM')], territories: [territory('t1', 'FORUM')] };

test('3.1·3.2 — 허위는 0점이고 점수·건수 모두에 안 들어간다', () => {
  const base = [ev('t1', '2026-09-10T00:00:00Z', 'high')];
  const withFalse = [...base, ev('t1', '2026-09-11T00:00:00Z', 'false')];
  assert.equal(eventScore(withFalse[1]), 0);
  const a = metricOf({ ...ONE, events: base }, 't1');
  const b = metricOf({ ...ONE, events: withFalse }, 't1');
  assert.equal(b.eventScoreSum, a.eventScoreSum, '허위가 점수를 바꾸면 안 된다');
  assert.equal(b.eventCount, 1, '허위는 사건 수 C(T,D) 에서도 빠진다');
});

test('3.1 — 반출 제외(excluded)는 점수·건수에서 빠진다', () => {
  const events = [
    ev('t1', '2026-09-10T00:00:00Z', 'high'),
    ev('t1', '2026-09-11T00:00:00Z', 'high', 'unknown', false, true),
  ];
  const m = metricOf({ ...ONE, events }, 't1');
  assert.equal(m.eventCount, 1);
  assert.equal(m.eventScoreSum, 1);
});

test('3.1 — 기준일 D 이후 게시는 빠지고, D 당일 게시는 들어간다', () => {
  const events = [
    ev('t1', '2026-09-30T18:00:00Z', 'high'), // 기준일 당일 낮
    ev('t1', '2026-10-01T00:00:00Z', 'high'), // 다음 날
  ];
  assert.equal(metricOf({ ...ONE, events }, 't1').eventCount, 1, 'D 당일 사건은 들어가야 한다');
  assert.equal(metricOf({ ...ONE, events }, 't1', endOfMonthUTC(2026, 10)).eventCount, 2);
});

test('게시 시각이 없거나 깨진 사건은 지도에 올리지 않는다 (설계서 2.5)', () => {
  const events = [ev('t1', '', 'high'), ev('t1', '언제였더라', 'high')];
  const m = metricOf({ ...ONE, events }, 't1');
  assert.equal(m.eventCount, 0);
  assert.equal(m.eventScoreSum, 0);
});

test('제 영토가 목록에 없는 사건은 어디에도 안 센다 — 행위자 영토에서도', () => {
  const input = {
    islands: [island('FORUM'), island('ACTOR')],
    territories: [territory('f1', 'FORUM'), territory('a1', 'ACTOR')],
    events: [{ ...ev('없는곳', '2026-09-10T00:00:00Z', 'high'), actorTerritoryId: 'a1' }],
  };
  const r = computeMap(input, D);
  assert.equal(r.territories.find((m) => m.territoryId === 'a1').eventCount, 0);
  assert.equal(r.eventCount.dark, 0);
});

/* ── 3.4 행위자 섬은 같은 사건을 한 번 더 센다 ─────────────────── */

test('3.4 — 행위자 영토는 그 행위자가 올린 사건을 한 번 더 센다. 지도 사건 수는 한 번이다', () => {
  const input = {
    islands: [island('FORUM'), island('ACTOR')],
    territories: [territory('f1', 'FORUM'), territory('a1', 'ACTOR')],
    events: [
      { ...ev('f1', '2026-09-10T00:00:00Z', 'high'), actorTerritoryId: 'a1' },
      ev('f1', '2026-09-11T00:00:00Z', 'high'),
    ],
  };
  const r = computeMap(input, D);
  const m = new Map(r.territories.map((x) => [x.territoryId, x]));
  assert.equal(m.get('f1').eventCount, 2);
  assert.equal(m.get('a1').eventCount, 1, '행위자 영토에도 든다');
  assert.equal(r.eventCount.dark, 2, '지도 사건 수는 한 번씩만 센다');
  // 행위자 활동도 원자료는 사건 수다. 행위자가 하나뿐이라 100 이다
  assert.equal(m.get('a1').activity, 100);
});

/* ── 3.3 활동도 ────────────────────────────────────────────────── */

test('3.3 — 포럼 활동도는 빈 지수를 빼고 평균한다 (90 · 72 → 81, 54 가 아니다)', () => {
  const max = { raw: 1637135, posts: 5720592, threads: 1779371 };
  // 회원 지수 90 · 게시물 지수 72 가 나오는 원자료 (정본 TER-0002 와 같은 모양)
  const members = Math.round(Math.exp((90 / 100) * Math.log(1 + max.raw)) - 1);
  const posts = Math.round(Math.exp((72 / 100) * Math.log(1 + max.posts)) - 1);
  assert.equal(forumActivity({ raw: members, posts, threads: 0 }, max), 81);
  assert.equal(forumActivity({ raw: null, posts: null, threads: null }, max), 0, '셋 다 없으면 0');
});

test('3.3 — 포럼 외 섬은 원자료를 섬 안 최댓값으로 누른다. 사건이 없어도 든다', () => {
  const input = {
    islands: [island('TELEGRAM')],
    territories: [
      territory('c1', 'TELEGRAM', 'dark', { raw: 6199 }),
      territory('c2', 'TELEGRAM', 'dark', { raw: 454 }),
      territory('c3', 'TELEGRAM', 'dark', { raw: null }),
    ],
    events: [],
  };
  const r = computeMap(input, D);
  const act = r.territories.map((m) => m.activity);
  assert.deepEqual(act, [100, 70, 0], '정본 TER-0150 과 같은 70');
  assert.deepEqual(r.territories.map((m) => m.activityWeight), [1, 0.85, 0.5]);
});

/* ── 3.4 영토 점수 · 3.5 칸 수 ─────────────────────────────────── */

test('3.4 — 영토 점수 = (사건 지수 + 기본점 20) × w. 사건이 없어도 20 × w 를 받는다', () => {
  const input = {
    islands: [island('TELEGRAM')],
    territories: [
      territory('c1', 'TELEGRAM', 'dark', { raw: 100 }),
      territory('c2', 'TELEGRAM', 'dark', { raw: 100 }),
    ],
    events: [ev('c1', '2026-09-10T00:00:00Z', 'high')],
  };
  const m = computeMap(input, D).territories;
  assert.equal(m[0].eventIndex, 100, '사건이 있는 유일한 곳이라 100');
  close(m[0].score, 120, 1e-12);
  assert.equal(m[1].eventIndex, 0);
  close(m[1].score, 20, 1e-12, '사건이 없어도 기본점 20 × w 1.0');
});

test('3.5 — 칸 수 합이 정확히 800 이다 (섬 몫 → 섬 안 최대 나머지)', () => {
  const t9 = Array.from({ length: 9 }, (_, i) => territory(`t${i}`, 'FORUM'));
  const r9 = computeMap({ islands: [island('FORUM')], territories: t9, events: [] }, D);
  assert.equal(r9.webCells.dark, 800);
  // 800 / 9 = 88.89 → 88 씩 아홉이면 792. 남는 8칸을 앞선 여덟이 받는다
  assert.deepEqual(r9.territories.map((m) => m.cells), [89, 89, 89, 89, 89, 89, 89, 89, 88]);
});

test('3.5 — 섬 비중 지수로 섬 몫을 누른다. 영토가 많은 섬이 지도를 다 갖지 않는다', () => {
  const many = Array.from({ length: 9 }, (_, i) => territory(`r${i}`, 'RANSOMWARE'));
  const input = {
    islands: [island('FORUM'), island('RANSOMWARE')],
    territories: [territory('f1', 'FORUM'), ...many],
    events: [],
  };
  const r = computeMap(input, D);
  const by = new Map(r.islands.map((i) => [i.islandId, i]));
  // 점수 비는 1 : 9 인데 α = 0.6 을 매기면 1 : 3.74 가 된다
  assert.equal(by.get('FORUM').target, 169);
  assert.equal(by.get('RANSOMWARE').target, 631);
  assert.equal(by.get('FORUM').cells + by.get('RANSOMWARE').cells, 800);
});

test('3.5 — 오픈웹과 다크웹은 따로 800칸씩 나눈다', () => {
  const islands = [island('FORUM', 'dark'), island('OTHER', 'open')];
  const territories = [territory('d1', 'FORUM', 'dark'), territory('o1', 'OTHER', 'open')];
  const r = computeMap({ islands, territories, events: [] }, D);
  assert.equal(r.webCells.dark, 800);
  assert.equal(r.webCells.open, 800);
});

/* ── 3.7 사건 수와 상태 · 3.8 급상승 ───────────────────────────── */

test('3.7 — 최근 30일 · 직전 30일 건수, 변화율, 상태', () => {
  const events = [
    ...evs(2, 't1', '2026-09-20T00:00:00Z', 'high'), // 최근 30일 2건
    ...evs(4, 't1', '2026-08-20T00:00:00Z', 'high'), // 직전 30일 4건
  ];
  const m = metricOf({ ...ONE, events }, 't1');
  assert.equal(m.eventCount, 6);
  assert.equal(m.recent30, 2);
  assert.equal(m.prev30, 4);
  close(m.countChangeRate30d, -50, 1e-9);
  assert.equal(m.status, '활성');

  const old = metricOf({ ...ONE, events: [ev('t1', '2026-01-01T00:00:00Z', 'high')] }, 't1');
  assert.equal(old.status, '관측 중');
  assert.equal(old.countChangeRate30d, null, '직전 30일이 0건이면 나눌 수 없다');
});

test('3.8 — 급상승 폭은 최근 7일 점수 − 직전 7일 점수. 폭이 0 이하면 순위에 없다', () => {
  const input = {
    islands: [island('FORUM')],
    territories: [territory('t1', 'FORUM'), territory('t2', 'FORUM')],
    events: [
      ...evs(2, 't1', '2026-09-28T00:00:00Z', 'high'), // 최근 7일
      ...evs(1, 't1', '2026-09-20T00:00:00Z', 'high'), // 그 앞 7일
    ],
  };
  const r = computeMap(input, D);
  assert.equal(r.territories[0].surge7d, 1);
  assert.deepEqual(topSurges(r, 3), [{ territoryId: 't1', surge: 1 }], '사건이 없는 t2 는 빠진다');
});

/* ── 영토가 지도에 나오는 때 ───────────────────────────────────── */

test('영토는 첫 사건이 있는 때부터 나온다. 사건이 없는 명부 영토는 이번 분기에만 나온다', () => {
  const today = new Date('2026-09-22T12:00:00Z');
  const old = territory('old', 'FORUM', 'dark', { since: '2025-03-01T00:00:00Z' });
  const fresh = territory('fresh', 'FORUM', 'dark');
  const q2 = endOfMonthUTC(2026, 6);
  assert.equal(presentAt(old, q2, today), true);
  assert.equal(presentAt(fresh, q2, today), false, '지난 분기에는 없다');
  assert.equal(presentAt(fresh, D, today), true, '이번 분기에는 있다');
  assert.equal(presentAt(old, endOfMonthUTC(2024, 12), today), false, '첫 사건 전에는 없다');
  assert.equal(presentAt(fresh, q2), true, '오늘을 모르면 늘 있다고 본다');

  const r = computeMap({ islands: [island('FORUM')], territories: [old, fresh], events: [], today }, q2);
  assert.deepEqual(r.territories.map((m) => m.cells), [800, 0], '없는 영토는 칸을 안 받는다');
});

test('운영 종료 날짜가 있으면 그 날짜가 든 분기까지만 나온다', () => {
  // 2026-09-30 최현서 — 압수된 곳은 압수 전 분기에만
  const today = new Date('2026-09-22T12:00:00Z');
  const seized = territory('seized', 'FORUM', 'dark', { since: '2024-03-01T00:00:00Z', until: '2025-05-15' });
  assert.equal(presentAt(seized, endOfMonthUTC(2025, 3), today), true, '종료 전 분기에는 있다');
  assert.equal(presentAt(seized, endOfMonthUTC(2025, 6), today), true, '종료 날짜가 든 분기(끝이 날짜 뒤)에도 있다');
  assert.equal(presentAt(seized, endOfMonthUTC(2025, 9), today), false, '다음 분기부터 없다');
  assert.equal(presentAt(seized, D, today), false, '이번 분기에도 없다');
  assert.equal(presentAt(seized, endOfMonthUTC(2025, 9)), false, '오늘을 몰라도 종료 날짜는 지킨다');
  assert.equal(presentAt(seized, endOfMonthUTC(2023, 12), today), false, '첫 사건 전에는 여전히 없다');
  const quarterEdge = territory('edge', 'FORUM', 'dark', { since: '2024-03-01T00:00:00Z', until: '2025-07-01' });
  assert.equal(presentAt(quarterEdge, endOfMonthUTC(2025, 9), today), true, '분기 첫날에 끝나면 그 분기까지 있다');

  const r = computeMap(
    { islands: [island('FORUM')], territories: [seized], events: evs(2, 'seized', '2025-04-01T00:00:00Z', 'high'), today },
    endOfMonthUTC(2025, 9),
  );
  assert.equal(r.territories[0].present, false);
  assert.equal(r.territories[0].cells, 0, '끝난 분기 뒤에는 칸도 사건도 없다');
  assert.equal(r.territories[0].eventCount, 0);
});

test('분기가 바뀌어 새 분기 사건이 아직 없어도 이번 분기를 고를 수 있고, 명부 영토가 남는다', () => {
  // 2026-09-23 검토에서 나온 것. 마지막 사건의 분기에서 끊으면 10월 1일부터
  // 기본 화면이 지난 분기가 되어 사건 없는 명부 영토가 모두 빠졌다
  const today = new Date('2026-10-02T03:00:00Z');
  const events = [ev('f1', '2026-09-18T00:00:00Z', 'high')];
  const qs = quartersOf(events, today);
  assert.equal(qs.at(-1), '2026-Q4', '오늘이 든 분기까지 있다');
  const territories = [
    territory('f1', 'FORUM', 'dark', { since: '2026-09-18T00:00:00Z' }),
    territory('t1', 'TELEGRAM', 'dark', { raw: 100 }),
  ];
  const r = computeMap(
    { islands: [island('FORUM'), island('TELEGRAM')], territories, events, today },
    quarterEnd('2026-Q4', today),
  );
  assert.ok(r.territories.find((m) => m.territoryId === 't1').cells > 0, '사건 없는 명부 영토가 칸을 받는다');
});

/* ── 3.9 관계 건수 ─────────────────────────────────────────────── */

test('3.9 — 관계 건수와 섬 쌍', () => {
  const territories = [territory('f1', 'FORUM'), territory('r1', 'RANSOMWARE'), territory('r2', 'RANSOMWARE')];
  const events = [
    ev('r1', '2026-09-10T00:00:00Z', 'high'),
    ev('r1', '2026-09-11T00:00:00Z', 'false'), // 허위 → 빠진다
    ev('r1', '2026-09-12T00:00:00Z', 'high', 'unknown', false, true), // 반출 제외 → 빠진다
    ev('r2', '2026-10-05T00:00:00Z', 'high'), // 기준일 이후 → 빠진다
  ];
  const rel = {
    id: 'R1', from: 'r1', to: 'f1', kind: 'leak', confidence: 'confirmed',
    evidence: events.map((e) => e.id),
  };
  assert.equal(relationCount(rel, events, D), 1);

  // **근거가 없으면 1로 둔다** (설계서 3.9). 「연결된 곳」 칸에서
  // 만든 관계선은 근거 사건이 없을 수 있는데, 화면에 「0건」이 찍히면
  // 관계가 없는 것처럼 보인다
  const rel2 = { id: 'R2', from: 'r2', to: 'f1', kind: 'contact', confidence: 'estimated', evidence: [] };
  assert.equal(relationCount(rel2, events, D), 1, '근거 0건이면 1로 센다');

  // **근거가 있는데 기준일에 하나도 안 들면 0 이다.** 그 분기에는 아직
  // 없던 관계라 1로 올리면 안 된다 — 과거 스냅샷에 미래의 선이 그려진다
  const rel3 = { id: 'R3', from: 'r2', to: 'f1', kind: 'leak', confidence: 'estimated', evidence: [events[3].id] };
  assert.equal(relationCount(rel3, events, D), 0, '근거가 모두 기준일 뒤면 0');

  const pair = islandPair(
    [rel, rel2, rel3], territories, events, D,
    islandKey('RANSOMWARE', 'dark'), islandKey('FORUM', 'dark'),
  );
  assert.deepEqual(pair, { pairs: 2, count: 2 }, '엔티티 쌍 수는 관계 개수, 건수는 1+1. 0건인 관계는 안 센다');
});

test('3.9 — 처음·마지막 본 날은 기준일에 지도에 든 근거 사건에서 센다', () => {
  const events = [
    ev('r1', '2026-08-02T00:00:00Z', 'high'),
    ev('r1', '2026-07-15T00:00:00Z', 'unverified'),
    ev('r1', '2026-06-01T00:00:00Z', 'false'), // 허위 → 처음 본 날이 안 된다
    ev('r1', '2026-10-05T00:00:00Z', 'high'), // 기준일 뒤 → 마지막 본 날이 안 된다
  ];
  const rel = {
    id: 'R1', from: 'r1', to: 'f1', kind: 'leak', confidence: 'confirmed',
    evidence: events.map((e) => e.id),
  };
  assert.deepEqual(relationSpan(rel, events, D), {
    first: '2026-07-15T00:00:00Z',
    last: '2026-08-02T00:00:00Z',
  });
  const none = { ...rel, evidence: [] };
  assert.deepEqual(relationSpan(none, events, D), { first: null, last: null }, '근거가 없으면 둘 다 비운다');
});

/* ── 3.10 위험도 ───────────────────────────────────────────────── */

test('3.10 — 위험도 (제안)', () => {
  assert.equal(riskLevel({ immediateAbuse: 'possible', hasResidentId: false, hasCardFinance: false }), '높음');
  assert.equal(riskLevel({ immediateAbuse: 'none', hasResidentId: true, hasCardFinance: false }), '높음');
  assert.equal(riskLevel({ immediateAbuse: 'none', hasResidentId: false, hasCardFinance: true }), '높음');
  assert.equal(
    riskLevel({ immediateAbuse: 'conditional', hasResidentId: true, hasCardFinance: false }),
    '높음',
    "'또는' 이라 조건부라도 주민번호가 있으면 높음",
  );
  assert.equal(riskLevel({ immediateAbuse: 'conditional', hasResidentId: false, hasCardFinance: false }), '중간');
  assert.equal(riskLevel({ immediateAbuse: 'none', hasResidentId: false, hasCardFinance: false }), '낮음');
});

/* ── 기준일 · 결정성 ───────────────────────────────────────────── */

test('3.1 — 달의 마지막 날 끝', () => {
  assert.equal(endOfMonthUTC(2026, 9).toISOString(), '2026-09-30T23:59:59.999Z');
  assert.equal(endOfMonthUTC(2026, 2).toISOString(), '2026-02-28T23:59:59.999Z');
  assert.equal(endOfMonthUTC(2024, 2).toISOString(), '2024-02-29T23:59:59.999Z', '윤년');
  assert.equal(endOfMonthUTC(2026, 12).toISOString(), '2026-12-31T23:59:59.999Z');
  assert.equal(minusDays(endOfMonthUTC(2026, 9), 30).toISOString(), '2026-08-31T23:59:59.999Z');
});

test('같은 입력이면 같은 출력이다', () => {
  const input = {
    islands: [island('FORUM'), island('RANSOMWARE')],
    territories: [territory('f1', 'FORUM', 'dark', { raw: 10 }), territory('r1', 'RANSOMWARE', 'dark', { raw: 5 })],
    events: [...evs(3, 'f1', '2026-09-10T00:00:00Z', 'high'), ev('r1', '2026-09-12T00:00:00Z', 'low')],
  };
  const a = computeMap(input, D);
  const b = computeMap(input, D);
  assert.deepEqual(JSON.parse(JSON.stringify(a)), JSON.parse(JSON.stringify(b)));
});
