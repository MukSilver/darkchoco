/**
 * 정본 엑셀의 계산 결과를 코드가 그대로 내는지 본다.
 *
 * 기준 자료는 `fixtures/canon_20260922.json` 이다. 정본 온톨로지판 엑셀에서
 * 숫자 칸만 뽑았고 (`tools/canon_fixture.py`), 이름 · 핸들 · 주소는 없다.
 * 영토는 영토 번호(TER-xxxx)로만 가리킨다.
 *
 * 두 무리로 나눈다 (2026-09-23 최현서 결정).
 *
 *   1. 활동도와 무관한 값 — 사건 수 · 사건 점수 합 · 사건 지수
 *   2. 설계서 3.5 실측 표 — 활동도 · 영토 점수 · 칸 수까지 전부
 *
 * 활동도 계산이 또 바뀌면 둘째 무리만 깨진다. 첫째가 같이 깨지면 사건을
 * 모으는 쪽이 틀린 것이다.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { computeMap, excelRound, allocateCells, islandTargets } from './score.ts';

const FX = JSON.parse(readFileSync(new URL('./fixtures/canon_20260922.json', import.meta.url), 'utf8'));

const W = {
  totalCells: { open: FX.weights.totalCells, dark: FX.weights.totalCells },
  trust: FX.weights.trust,
  size: FX.weights.size,
  base: FX.weights.base,
  activityMin: FX.weights.activityMin,
  islandAlpha: FX.weights.islandAlpha,
  activityWindowDays: FX.weights.recentDays,
  surgeWindowDays: FX.weights.surgeDays,
};

const ISLANDS = ['FORUM', 'RANSOMWARE', 'TELEGRAM', 'ACTOR'].map((id) => ({
  id, web: 'dark', name: id, hex: '#000000', legend: '#000000',
}));

const TERRITORIES = FX.territories.map((t) => ({
  id: t.id, name: t.id, islandId: t.island, web: 'dark',
  raw: t.raw ?? null, posts: t.posts ?? null, threads: t.threads ?? null, since: t.since,
}));

const EVENTS = FX.events.map((e) => ({
  id: e.id,
  territoryId: e.t ?? '',
  ...(e.a ? { actorTerritoryId: e.a } : {}),
  postedAt: e.at ?? '',
  verdict: e.v,
  size: e.s,
  repost: false,
  excluded: e.x,
}));

const INPUT = { islands: ISLANDS, territories: TERRITORIES, events: EVENTS };
const endOf = (day) => new Date(`${day}T23:59:59.999Z`);
const D = endOf(FX.weights.asOf);
const RESULT = computeMap(INPUT, D, W);
const byId = new Map(RESULT.territories.map((m) => [m.territoryId, m]));

function close(actual, expected, eps, msg) {
  assert.ok(Math.abs(actual - expected) <= eps, `${msg} — 받은 값 ${actual}, 기대 ${expected}`);
}

/* ── 1. 활동도와 무관한 값 ─────────────────────────────────────── */

test('정본 — 지도에 든 사건이 170건이다 (행위자 섬에서 한 번 더 센 것은 빼고)', () => {
  const expected = FX.events.filter((e) => e.O === 1).length;
  assert.equal(expected, 170);
  assert.equal(RESULT.eventCount.dark, expected);
});

test('정본 — 영토 178곳의 사건 수가 엑셀 영토!H 와 같다 (합 217 = 170 + 행위자 47)', () => {
  let sum = 0;
  for (const [id, x] of Object.entries(FX.expect.territories)) {
    assert.equal(byId.get(id).eventCount, x.H, `${id} 사건 수`);
    sum += x.H;
  }
  assert.equal(sum, 217);
});

test('정본 — 영토 178곳의 사건 점수 합이 엑셀 영토!I 와 같다', () => {
  for (const [id, x] of Object.entries(FX.expect.territories)) {
    close(byId.get(id).eventScoreSum, x.I, 1e-9, `${id} 사건 점수 합`);
  }
});

test('정본 — 영토 178곳의 사건 지수가 엑셀 영토!J 와 같다', () => {
  for (const [id, x] of Object.entries(FX.expect.territories)) {
    assert.equal(byId.get(id).eventIndex, x.J, `${id} 사건 지수`);
  }
});

test('정본 — 최근 · 직전 30일 건수, 변화율, 상태, 급상승 폭이 엑셀과 같다', () => {
  for (const [id, x] of Object.entries(FX.expect.territories)) {
    const m = byId.get(id);
    assert.equal(m.recent30, x.AB, `${id} 최근 30일`);
    assert.equal(m.prev30, x.AC, `${id} 직전 30일`);
    if (x.AD === null) assert.equal(m.countChangeRate30d, null, `${id} 변화율 빈칸`);
    else close(m.countChangeRate30d, x.AD * 100, 1e-9, `${id} 변화율`);
    assert.equal(m.status, x.AE, `${id} 상태`);
    close(m.surge7d, x.AH, 1e-9, `${id} 급상승 폭`);
  }
});

test('정본 — 첫 사건 · 마지막 사건이 엑셀과 같다 (1초 안)', () => {
  const sec = (s) => (s ? Date.parse(s) / 1000 : null);
  for (const [id, x] of Object.entries(FX.expect.territories)) {
    const m = byId.get(id);
    for (const [got, want, what] of [[m.firstEventAt, x.AL, '첫'], [m.lastEventAt, x.AM, '마지막']]) {
      if (want === null) assert.equal(got, null, `${id} ${what} 사건 빈칸`);
      else close(sec(got), sec(want), 1, `${id} ${what} 사건`);
    }
  }
});

/* ── 2. 설계서 3.5 실측 표 ─────────────────────────────────────── */

test('정본 3.5 — 설계서 표의 다섯 줄이 그대로 나온다', () => {
  // [영토 번호, 사건 수, 사건 점수 합, 사건 지수, 활동도, w, 영토 점수, 섬 안 비중 %, 칸 수]
  const rows = [
    ['TER-0001', 40, 41.34, 100, 80, 0.9, 108.0, 13.4, 25],
    ['TER-0161', 30, 28.84, 100, 100, 1.0, 120.0, 22.5, 33],
    ['TER-0038', 28, 22.8, 100, 100, 1.0, 120.0, 4.7, 18],
    ['TER-0007', 0, 0, 0, 95, 0.975, 19.5, 2.4, 5],
    ['TER-0002', 4, 3.6, 41, 81, 0.905, 55.205, 6.8, 13],
  ];
  for (const [id, h, i, j, s, t, u, v, aa] of rows) {
    const m = byId.get(id);
    assert.equal(m.eventCount, h, `${id} 사건 수`);
    close(m.eventScoreSum, i, 1e-9, `${id} 사건 점수 합`);
    assert.equal(m.eventIndex, j, `${id} 사건 지수`);
    assert.equal(m.activity, s, `${id} 활동도`);
    close(m.activityWeight, t, 1e-12, `${id} w`);
    close(m.score, u, 1e-9, `${id} 영토 점수`);
    close(excelRound(m.shareInIsland, 1), v, 1e-9, `${id} 섬 안 비중`);
    assert.equal(m.cells, aa, `${id} 칸 수`);
  }
});

test('정본 3.5 — 섬 칸이 랜섬웨어 380 · 포럼 190 · 행위자 148 · 텔레그램 82, 합 800', () => {
  const want = { FORUM: 190, RANSOMWARE: 380, TELEGRAM: 82, ACTOR: 148 };
  for (const isl of RESULT.islands) {
    assert.equal(isl.target, want[isl.islandId], `${isl.islandId} 섬 칸 목표`);
    assert.equal(isl.cells, want[isl.islandId], `${isl.islandId} 칸 수 합`);
    const x = FX.expect.islands[isl.islandId];
    close(isl.score, x.score, 1e-9, `${isl.islandId} 섬 점수`);
    assert.equal(isl.avgActivity, x.avgActivity, `${isl.islandId} 평균 활동도`);
  }
  assert.equal(RESULT.webCells.dark, 800);
});

test('정본 3.5 — 영토 178곳의 활동도 · w · 영토 점수 · 비중 · 칸 수가 엑셀 영토 탭과 같다', () => {
  for (const [id, x] of Object.entries(FX.expect.territories)) {
    const m = byId.get(id);
    assert.equal(m.activity, x.S, `${id} 활동도`);
    close(m.activityWeight, x.T, 1e-12, `${id} w`);
    close(m.score, x.U, 1e-9, `${id} 영토 점수`);
    // 엑셀 캐시의 비중은 소수 10자리에서 잘려 있다
    close(m.shareInIsland, x.V * 100, 1e-6, `${id} 섬 안 비중`);
    close(m.shareInWeb, x.W * 100, 1e-6, `${id} 전체 비중`);
    assert.equal(m.cells, x.AA, `${id} 칸 수`);
  }
});

/* ── 분기별 (영토분기별 · 섬분기별 탭) ─────────────────────────── */

/**
 * **한 묶음만 뺀다 — 2026-Q2 행위자.** 나머지가 똑같은 두 영토(TER-0166 ·
 * TER-0170)를 엑셀 분기별 탭은 「순번」(섬 안 이름 차례)으로 가르고, 코드는
 * 영토 탭처럼 영토 번호로 가른다. 그래서 6/5 와 5/6 이 뒤집힌다. 50개 묶음
 * 가운데 결과가 달라지는 곳은 여기 하나다. 어느 기준이 맞는지는 팀에 물을 것
 * 으로 `DEV.md` 에 적어 두었다.
 */
const TIE_GROUP = { q: '2026-Q2', island: 'ACTOR' };

test('정본 분기별 — 543줄의 사건 · 활동도 · 영토 점수 · 칸 수가 엑셀과 같다', () => {
  const byQ = new Map();
  for (const r of FX.expect.quarters) {
    if (!byQ.has(r.q)) byQ.set(r.q, []);
    byQ.get(r.q).push(r);
  }
  const island = new Map(FX.territories.map((t) => [t.id, t.island]));
  let checked = 0;
  for (const [q, rows] of byQ) {
    const res = computeMap(INPUT, endOf(rows[0].d), W);
    const got = new Map(res.territories.map((m) => [m.territoryId, m]));
    // 그 분기에 있는 영토가 엑셀 줄과 같다
    const here = new Set(res.territories.filter((m) => m.present).map((m) => m.territoryId));
    assert.deepEqual([...here].sort(), rows.map((r) => r.t).sort(), `${q} 영토 목록`);
    for (const r of rows) {
      const m = got.get(r.t);
      assert.equal(m.eventCount, r.H, `${q} ${r.t} 누적 사건 수`);
      close(m.eventScoreSum, r.I, 1e-9, `${q} ${r.t} 누적 점수`);
      assert.equal(m.activity, r.S, `${q} ${r.t} 활동도`);
      assert.equal(m.eventIndex, r.J, `${q} ${r.t} 사건 지수`);
      close(m.score, r.U, 1e-9, `${q} ${r.t} 크기 점수`);
      assert.equal(m.recent30, r.AB, `${q} ${r.t} 최근 30일`);
      assert.equal(m.prev30, r.AC, `${q} ${r.t} 직전 30일`);
      if (!(q === TIE_GROUP.q && island.get(r.t) === TIE_GROUP.island)) {
        assert.equal(m.cells, r.AA, `${q} ${r.t} 칸 수`);
      }
      checked += 1;
    }
    assert.equal(res.webCells.dark, 800, `${q} 칸 합`);
  }
  assert.equal(checked, 543);
});

test('정본 분기별 — 섬 칸 목표가 엑셀 섬분기별 탭과 같다 (2026-Q1 끝전 +1 포함)', () => {
  const cache = new Map();
  for (const r of FX.expect.islandQuarters) {
    const row = FX.expect.quarters.find((x) => x.q === r.q);
    if (!cache.has(r.q)) cache.set(r.q, computeMap(INPUT, endOf(row.d), W));
    const isl = cache.get(r.q).islands.find((i) => i.islandId === r.island);
    assert.equal(isl.target, r.target, `${r.q} ${r.island} 섬 칸 목표`);
  }
});

/* ── 엑셀이 한 번도 안 탄 갈래 (합성 자료) ─────────────────────── */

test('엑셀 ROUND — 0.5 는 0 에서 먼 쪽으로, 부동소수 오차에 안 흔들린다', () => {
  assert.equal(excelRound(8.5), 9);
  assert.equal(excelRound(62.5), 63);
  assert.equal(excelRound(54.5), 55);
  assert.equal(excelRound(1.005, 2), 1.01);
  assert.equal(excelRound(-2.5), -3);
  assert.equal(excelRound(25.4585830000001, 6), 25.458583);
});

test('칸 배분 — 칸이 넘치면 2칸 이상인 곳에서 나머지 작은 순으로 뺀다', () => {
  // 목표 6칸에 영토 다섯. 작은 셋이 1칸으로 올라가 7칸이 된다.
  // 2칸짜리 둘의 나머지가 같아 앞선 곳에서 뺀다
  const { cells } = allocateCells([50, 50, 1, 1, 1], 6);
  assert.deepEqual(cells, [1, 2, 1, 1, 1]);
});

test('칸 배분 — 한 영토에서는 1칸만 뺀다. 그래서 목표를 못 맞출 수 있다 (엑셀과 같다)', () => {
  // 엑셀 영토!AA 는 영토마다 −1 을 한 번만 한다. 2칸 이상인 곳이 모자란 칸
  // 수보다 적으면 합이 목표를 넘는다. 정본에 이 경우의 규칙이 없다
  assert.deepEqual(allocateCells([100, 1, 1, 1], 5).cells, [3, 1, 1, 1]);
  assert.deepEqual(allocateCells([1, 1, 1], 2).cells, [1, 1, 1]);
});

test('섬 칸 목표 — 조정 점수가 같은 섬이 둘이면 목록에서 앞선 섬이 끝전을 받는다', () => {
  const got = islandTargets(['A', 'B', 'C'], new Map([['A', 1], ['B', 1], ['C', 1]]), 800, 0.6);
  // 800 ÷ 3 = 266.67 → 셋 다 267 이라 합 801. 끝전 −1 을 A 가 받는다
  assert.deepEqual([...got.values()], [266, 267, 267]);
});

test('날짜를 대신 넣은 사건 — 점수 · 칸에는 들고 창 · 상태 · 급상승에서는 빠진다', () => {
  const ts = [
    { id: 'f1', name: 'f1', islandId: 'FORUM', web: 'dark', raw: 100 },
    { id: 'f2', name: 'f2', islandId: 'FORUM', web: 'dark', raw: 10 },
  ];
  const e = (id, sub) => ({
    id, territoryId: 'f1', postedAt: '2026-09-20T00:00:00Z', verdict: 'high', size: 'unknown',
    repost: false, excluded: false, ...(sub ? { dateSubstituted: true } : {}),
  });
  const res = computeMap({ islands: ISLANDS, territories: ts, events: [e('a', true), e('b', false)] }, D, W);
  const m = res.territories[0];
  assert.equal(m.eventCount, 2, '사건 수에는 든다');
  close(m.eventScoreSum, 2, 1e-12, '점수에도 든다');
  assert.equal(m.recent30, 1, '최근 30일에서는 빠진다');
  close(m.surge7d, 1, 1e-12, '급상승에서도 빠진다');
});
