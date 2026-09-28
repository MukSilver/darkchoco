/**
 * src/lib/events.ts 시험 — 사건 제목, 기간 거르기, 월별 묶음, 위험도 칩, UTC 시각, 사건이 근거인 관계.
 *
 *   node --experimental-strip-types --test src/lib/events.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  RISK_LABEL,
  RISK_TONE,
  byMonth,
  eventTitle,
  eventsIn,
  gapText,
  periodBounds,
  periodDays,
  sizeText,
  stampOf,
  touchesEvent,
  utcStamp,
} from './events.ts';

let seq = 0;
function ev(postedAt, extra = {}) {
  seq += 1;
  return {
    id: `e${seq}`, territoryId: 't1', postedAt, verdict: 'high', size: 'unknown',
    repost: false, excluded: false, ...extra,
  };
}

const D = new Date('2026-09-30T23:59:59Z');

test('사건 제목은 국가 · 산업 분야 · 날짜 · 규모다 (2026-09-25 결정)', () => {
  const e = ev('2026-05-14T06:58:00.000+09:00', { country: 'KR', industry: '유통', sizeValue: 255, sizeUnit: 'GB' });
  assert.equal(eventTitle(e), '[KR · 유통 · 2026-05-14 · 255GB]');
  assert.equal(eventTitle(ev('2026-05-27')), '[2026-05-27]', '모르는 조각은 빼고 날짜는 늘 있다');
  assert.equal(eventTitle(ev('2026-05-27', { country: 'KR', sizeValue: 1.2, sizeUnit: 'TB' })), '[KR · 2026-05-27 · 1.2TB]');
});

test('규모와 시각 표기', () => {
  assert.equal(sizeText({ sizeValue: 3400000, sizeUnit: '건' }), '3,400,000건');
  assert.equal(sizeText({ sizeValue: 120, sizeUnit: '만' }), '120만');
  assert.equal(sizeText({}), null);
  assert.equal(stampOf({ postedAt: '2026-01-31T06:58:00.000+09:00' }), '01-31 06:58', '노션이 적은 시각 그대로');
  assert.equal(stampOf({ postedAt: '2026-05-27' }), '05-27');
});

test('기간은 기준일에서 거슬러 센다 (설계서 4.3.2)', () => {
  const list = [
    ev('2026-09-29T00:00:00Z'),
    ev('2026-08-15T00:00:00Z'),
    ev('2026-05-01T00:00:00Z'),
    ev('2026-10-02T00:00:00Z'), // 기준일 뒤
    ev('2026-09-20T00:00:00Z', { verdict: 'false' }), // 허위
    ev('2026-09-21T00:00:00Z', { excluded: true }), // 반출 제외
  ];
  const all = () => true;
  assert.deepEqual(eventsIn(list, D, { kind: 'days', days: 30 }, all).map((e) => e.postedAt.slice(0, 10)), ['2026-09-29']);
  assert.deepEqual(
    eventsIn(list, D, { kind: 'days', days: 90 }, all).map((e) => e.postedAt.slice(0, 10)),
    ['2026-09-29', '2026-08-15'],
    '최신순',
  );
  assert.equal(eventsIn(list, D, { kind: 'all' }, all).length, 3, '전체도 기준일 뒤 · 허위 · 반출 제외는 뺀다');
  assert.deepEqual(
    eventsIn(list, D, { kind: 'range', from: '2026-05-01', to: '2026-08-15' }, all).map((e) => e.postedAt.slice(0, 10)),
    ['2026-08-15', '2026-05-01'],
    '날짜 범위는 양 끝 날을 다 넣는다',
  );
  const { to } = periodBounds({ kind: 'range', from: '2026-01-01', to: '2027-01-01' }, D);
  assert.equal(to, D.getTime(), '날짜 범위도 기준일을 넘지 않는다');
});

test('월별 묶음은 최신순을 지킨다', () => {
  const list = eventsIn(
    [ev('2026-09-02T00:00:00Z'), ev('2026-08-30T00:00:00Z'), ev('2026-09-14T00:00:00Z')],
    D,
    { kind: 'all' },
    () => true,
  );
  assert.deepEqual(
    byMonth(list).map((g) => [g.month, g.items.length]),
    [['2026-09', 2], ['2026-08', 1]],
  );
});

test('날짜 범위는 노션이 적은 날짜로 거른다 — +09:00 새벽 사건 (머지 전 검토)', () => {
  const a = ev('2026-05-01T06:58:00.000+09:00'); // UTC 로는 4월 30일
  const b = ev('2026-06-01T03:00:00.000+09:00'); // UTC 로는 5월 31일
  const got = eventsIn([a, b], D, { kind: 'range', from: '2026-05-01', to: '2026-05-31' }, () => true);
  assert.deepEqual(got.map((e) => e.id), [a.id], '화면에 5월 1일로 보이는 사건이 들고, 6월 1일로 보이는 사건은 빠진다');
});

test('기준일 뒤로 간 날짜 범위는 뒤집지 않고 기본 90일로 물러선다', () => {
  const d = new Date('2026-06-30T23:59:59Z');
  const p = { kind: 'range', from: '2026-07-01', to: '2026-09-20' };
  const list = [ev('2026-06-15T00:00:00Z'), ev('2026-07-05T00:00:00Z')];
  assert.deepEqual(eventsIn(list, d, p, () => true).map((e) => e.postedAt.slice(0, 10)), ['2026-06-15']);
  const [from, to] = periodDays(p, d);
  assert.ok(from <= to, '화면에 적는 시작일이 끝날보다 늦지 않다');
  assert.equal(to, '2026-06-30');
  assert.deepEqual(periodDays({ kind: 'range', from: '2026-06-01', to: '2026-09-20' }, d), ['2026-06-01', '2026-06-30'], '끝날은 기준일로 자른다');
});

test('월별 묶음은 노션 날짜 글자 차례라 같은 달 머리글이 두 번 안 나온다', () => {
  const list = eventsIn(
    [ev('2026-06-01T03:00:00.000+09:00'), ev('2026-05-31T20:00:00Z'), ev('2026-06-02T00:00:00Z')],
    D,
    { kind: 'all' },
    () => true,
  );
  assert.deepEqual(byMonth(list).map((g) => g.month), ['2026-06', '2026-05']);
});

test('위험도 칩 이름과 색 (설계서 3.10, 피그마 ⑦-4 하단 모달 「위험도 높음」 은 danger)', () => {
  assert.deepEqual(RISK_LABEL, { high: '높음', medium: '중간', low: '낮음' });
  assert.equal(RISK_TONE.high, 'danger');
  assert.deepEqual(Object.keys(RISK_TONE).sort(), Object.keys(RISK_LABEL).sort(), '세 등급 모두 색이 있다');
});

test('게시와 공표 사이 — 음수는 발표 전 게시, 하루 안쪽은 같은 날 무렵 (G-9)', () => {
  assert.equal(gapText(-3), '발표 3일 전 게시');
  assert.equal(gapText(9), '발표 9일 뒤 게시');
  for (const n of [-1, 0, 1]) assert.equal(gapText(n), '같은 날 무렵');
});

test('보고서 팝업 게시 시각은 UTC 로 옮긴다 — 시각이 없으면 날짜만', () => {
  assert.equal(utcStamp('2026-05-14T06:58:00.000+09:00'), '2026-05-13 21:58 UTC', '+09:00 새벽은 UTC 로 전날이다');
  assert.equal(utcStamp('2026-09-10T21:40:00Z'), '2026-09-10 21:40 UTC');
  assert.equal(utcStamp('2026-05-27'), '2026-05-27', '날짜만 적힌 사건은 옮길 시각이 없다');
  assert.equal(utcStamp('2026-05-27Tbroken'), '2026-05-27', '깨진 시각은 날짜로 물러선다');
});

test('사건이 근거인 관계 — 근거 목록, 또는 행위자 → 영토 활동 관계', () => {
  const e = ev('2026-09-01T00:00:00Z', { territoryId: 'forum', actorTerritoryId: 'actor' });
  const rel = (extra) => ({ id: 'R', from: 'a', to: 'b', kind: 'leak', confidence: 'high', evidence: [], ...extra });
  assert.ok(touchesEvent(rel({ evidence: ['x', e.id] }), e), '근거 목록에 있으면 잇는다');
  assert.ok(!touchesEvent(rel({ evidence: ['x'] }), e));
  assert.ok(
    touchesEvent(rel({ kind: 'activity', from: 'actor', to: 'forum' }), e),
    '근거가 안 합쳐진 활동 줄도 행위자 → 영토 쌍이면 잇는다',
  );
  assert.ok(!touchesEvent(rel({ kind: 'activity', from: 'actor', to: 'other' }), e), '다른 영토의 활동 관계는 아니다');
  assert.ok(!touchesEvent(rel({ kind: 'leak', from: 'actor', to: 'forum' }), e), '활동 관계가 아니면 쌍만으로는 안 잇는다');
  const plain = ev('2026-09-01T00:00:00Z', { territoryId: 'forum' });
  assert.ok(!touchesEvent(rel({ kind: 'activity', from: 'actor', to: 'forum' }), plain), '행위자가 없는 사건');
});
