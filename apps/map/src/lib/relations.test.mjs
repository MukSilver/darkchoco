/**
 * src/lib/relations.ts 시험 — 관계 탭 · [연결] 탭 · 지도 관계선이 쓰는 묶음.
 *
 *   node --experimental-strip-types --test src/lib/relations.test.mjs
 *
 * 건수 자체(설계서 3.9)는 `score.test.mjs` 가 본다. 여기는 그 건수를 세 화면이
 * 같은 값으로 받는지, 차례와 거르기가 설계서대로인지 본다.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  backLabel,
  centerChips,
  confOfVerdict,
  connectedIslandCount,
  defaultCenter,
  expandHops,
  historyOrder,
  historyText,
  islandPairs,
  josa,
  kindMix,
  linkRows,
  linksOf,
  pairViews,
  partnerCount,
  relationsAt,
  selectedText,
  summaryText,
  withActivity,
  withEstimated,
} from './relations.ts';

/* ── 재료 ─────────────────────────────────────────────────────── */

const D = new Date('2026-09-30T23:59:59Z');

let seq = 0;
function ev(territoryId, postedAt, extra = {}) {
  seq += 1;
  return {
    id: `e${seq}`, territoryId, postedAt, verdict: 'high', size: 'unknown',
    repost: false, excluded: false, ...extra,
  };
}

function rel(id, from, to, kind, evidence = [], confidence = 'estimated') {
  return { id, from, to, kind, confidence, evidence };
}

const ISLAND = { f1: 'FORUM', f2: 'FORUM', r1: 'RANSOMWARE', r2: 'RANSOMWARE', t1: 'TELEGRAM', a1: 'ACTOR' };
const islandOf = (id) => ISLAND[id];
const nameOf = (id) => ({ f1: 'Darkforums', f2: 'PwnForums', r1: 'Qilin', r2: 'Play', t1: 'BF Vouch', a1: 'hexvior' })[id] ?? id;
const ALL = new Set(Object.keys(ISLAND));

/* ── 활동 관계 ────────────────────────────────────────────────── */

test('활동 관계는 사건에서 만든다 — DB 줄은 번호와 신뢰도만 살린다 (설계서 3.9 · 4.3.8)', () => {
  const events = [
    ev('f1', '2026-05-01T00:00:00Z', { actorTerritoryId: 'a1' }),
    ev('f1', '2026-06-01T00:00:00Z', { actorTerritoryId: 'a1' }),
    ev('f2', '2026-07-01T00:00:00Z', { actorTerritoryId: 'a1' }),
    ev('f2', '2026-07-02T00:00:00Z'), // 행위자 없음 → 활동 관계가 안 생긴다
  ];
  const db = [
    rel('REL-9', 'a1', 'f1', 'activity', [events[0].id], 'high'),
    rel('REL-1', 'r1', 'f1', 'affiliate'),
  ];
  const out = withActivity(db, events);
  assert.equal(out.length, 3);

  const kept = out.find((r) => r.id === 'REL-9');
  assert.equal(kept.confidence, 'high', 'DB 줄의 신뢰도를 그대로 쓴다');
  assert.deepEqual(kept.evidence.sort(), [events[0].id, events[1].id].sort(), '근거는 그 영토에 올린 사건 전부');

  const made = out.find((r) => r.from === 'a1' && r.to === 'f2');
  assert.equal(made.kind, 'activity');
  assert.equal(made.confidence, 'confirmed');
  assert.deepEqual(made.evidence, [events[2].id]);
  assert.ok(out.includes(db[1]), '활동이 아닌 관계는 손대지 않는다');
});

/* ── 기준일의 관계 ────────────────────────────────────────────── */

test('기준일에 그릴 관계 — 양 끝이 지도에 있고 건수 1 이상 (설계서 2.5 · 3.9)', () => {
  const events = [
    ev('r1', '2026-03-01T00:00:00Z'),
    ev('r1', '2026-08-01T00:00:00Z'),
    ev('r2', '2026-11-01T00:00:00Z'), // 기준일 뒤
  ];
  const rels = [
    rel('R1', 'r1', 'f1', 'affiliate', [events[0].id, events[1].id]),
    rel('R2', 'r2', 'f1', 'affiliate', [events[2].id]), // 근거가 모두 기준일 뒤 → 0건
    rel('R3', 't1', 'f1', 'contact'), // 근거 없음 → 1건
    rel('R4', 'r1', 'gone', 'leak'), // 한쪽 끝이 지도에 없음
  ];
  const views = relationsAt(rels, events, D, ALL);
  assert.deepEqual(views.map((v) => v.rel.id), ['R1', 'R3']);

  const r1 = views[0];
  assert.equal(r1.count, 2);
  assert.equal(r1.first, '2026-03-01T00:00:00Z');
  assert.equal(r1.last, '2026-08-01T00:00:00Z');
  assert.deepEqual(r1.evidence.map((e) => e.id), [events[1].id, events[0].id], '근거 목록은 최근 것이 앞');
  assert.equal(r1.fromRegistry, false);

  const r3 = views[1];
  assert.equal(r3.count, 1);
  assert.equal(r3.fromRegistry, true, '근거가 처음부터 없으면 「연결된 곳」 칸에서 만든 관계');
});

/* ── [연결] 탭 · 관계 탭 노드 ─────────────────────────────────── */

function sample() {
  const e = (t, d) => ev(t, d);
  const a = [e('r1', '2025-02-01T00:00:00Z'), e('r1', '2026-05-01T00:00:00Z'), e('r1', '2026-06-01T00:00:00Z')];
  const b = [e('r2', '2024-01-10T00:00:00Z')];
  const c = [e('t1', '2025-09-01T00:00:00Z'), e('t1', '2025-10-01T00:00:00Z')];
  const events = [...a, ...b, ...c];
  const rels = [
    rel('REL-1', 'r1', 'f1', 'affiliate', a.map((x) => x.id), 'confirmed'),
    rel('REL-2', 'r2', 'f1', 'affiliate', b.map((x) => x.id)),
    rel('REL-3', 't1', 'f1', 'contact', c.map((x) => x.id), 'high'),
    rel('REL-4', 'f2', 'f1', 'successor'), // 근거 없음
    rel('REL-5', 'r1', 't1', 'leak', [a[0].id]),
  ];
  return { events, views: relationsAt(rels, events, D, ALL) };
}

test('[연결] 탭 행은 건수 많은 순이고, 배지는 상대 엔티티 수다 (설계서 4.3.2)', () => {
  const { views } = sample();
  assert.deepEqual(linkRows(views, 'f1').map((v) => v.rel.id), ['REL-1', 'REL-3', 'REL-2', 'REL-4']);
  assert.equal(partnerCount(views, 'f1'), 4);
  assert.equal(partnerCount(views, 'r1'), 2);
  assert.equal(connectedIslandCount(views, 'f1', islandOf), 3, '랜섬웨어 · 텔레그램 · 포럼');
});

test('관계 탭 중심과 칩 줄 — 관계 건수 순, 중심이 밖이면 맨 앞 (설계서 4.3.6)', () => {
  const { views } = sample();
  // 건수 합: f1 7 · r1 4 · t1 3 · r2 1 · f2 1
  assert.equal(defaultCenter(views, nameOf), 'f1');
  assert.deepEqual(centerChips(views, 'f1', nameOf, 3), ['f1', 'r1', 't1']);
  assert.deepEqual(centerChips(views, 'r2', nameOf, 3), ['r2', 'f1', 'r1', 't1'], '중심이 상위 밖이면 맨 앞에 붙인다');
  assert.equal(defaultCenter([], nameOf), null, '관계가 없으면 중심도 없다');
});

test('관계 유형 구성과 연혁 차례 (설계서 4.3.6)', () => {
  const { views } = sample();
  const mine = linkRows(views, 'f1');
  assert.deepEqual(kindMix(mine), [
    { kind: 'affiliate', count: 4 },
    { kind: 'contact', count: 2 },
    { kind: 'successor', count: 1 },
  ]);
  // 최초 관측 순. 처음 본 날을 모르는 관계(근거 없음)는 맨 뒤
  assert.deepEqual(historyOrder(mine).map((v) => v.rel.id), ['REL-2', 'REL-1', 'REL-3', 'REL-4']);
});

test('섬 간 요약은 다른 섬 사이만 방향별로 묶는다 (설계서 3.9 · 4.3.1)', () => {
  const { views } = sample();
  const rows = islandPairs(views, islandOf, 'RANSOMWARE');
  assert.deepEqual(
    rows.map((r) => [r.from, r.to, r.pairs, r.count, r.topKind]),
    [
      ['RANSOMWARE', 'FORUM', 2, 4, 'affiliate'],
      ['RANSOMWARE', 'TELEGRAM', 1, 1, 'leak'],
    ],
  );
  assert.equal(rows[0].last, '2026-06-01T00:00:00Z');
  // 포럼 → 포럼(REL-4)은 같은 섬 안이라 포럼 요약에도 안 든다
  assert.ok(islandPairs(views, islandOf, 'FORUM').every((r) => r.from !== r.to));
  assert.deepEqual(pairViews(views, islandOf, 'RANSOMWARE', 'FORUM').map((v) => v.rel.id), ['REL-1', 'REL-2']);
});

/* ── 자동 문장 ────────────────────────────────────────────────── */

test('조사는 끝소리를 따른다', () => {
  assert.equal(josa('Qilin', '은', '는'), '은');
  assert.equal(josa('Darkforums', '은', '는'), '는');
  assert.equal(josa('랜섬웨어 공지 채널', '은', '는'), '은');
  assert.equal(josa('포럼', '은', '는'), '은');
  assert.equal(josa('Play', '은', '는'), '는');
  assert.equal(josa('Lockbit', '은', '는'), '은');
});

test('연혁 설명 · 요약 · 고른 관계 문장 (피그마 ⑦-8 · ⑦-8e 문안)', () => {
  const { views } = sample();
  const r1 = views.find((v) => v.rel.id === 'REL-1');
  assert.equal(
    historyText(r1, nameOf),
    'Qilin은 2025년 2월부터 Darkforums에서 제휴자를 모집해 왔습니다. ' +
      '관련 사건은 3건 수집되었고, 가장 최근 관측은 2026년 6월입니다. 관계가 확인되었습니다.',
  );
  const r4 = views.find((v) => v.rel.id === 'REL-4');
  assert.match(historyText(r4, nameOf), /「연결된 곳」 칸에서 만든 관계입니다/);

  const mine = linkRows(views, 'f1');
  assert.equal(
    summaryText('Darkforums', mine, 4, 3),
    'Darkforums는 엔티티 4곳, 섬 3곳과 관계가 있습니다. 제휴자 모집 관계가 4건으로 가장 많으며, ' +
      '관계는 2024년 1월에 처음 관측되어 가장 최근 활동은 2026년 6월에 기록되었습니다.',
  );
  assert.match(
    selectedText(r1, 'f1', mine, nameOf),
    /^선택한 관계 Qilin → Darkforums는 제휴자 모집 3건으로, Darkforums의 관계 중 사건이 가장 많습니다\./,
  );
});

test('행위자는 활동 관계만 본다 — [연결] 목록 · 배지 · 지도 선이 같게 (설계서 4.3.8)', () => {
  const e1 = ev('f1', '2026-05-01T00:00:00Z', { actorTerritoryId: 'a1' });
  const rels = withActivity([rel('R9', 'a1', 't1', 'contact')], [e1]);
  const views = relationsAt(rels, [e1], D, ALL);
  assert.deepEqual(linksOf(views, 'a1', true).map((v) => v.rel.kind), ['activity']);
  assert.equal(linksOf(views, 'a1', false).length, 2, '행위자가 아니면 모든 종류');
  assert.equal(partnerCount(linksOf(views, 'a1', true), 'a1'), 1);
});

/* ── 관계 탭 들어오기 · 관계 없음 (설계서 4.3.3 · 4.3.6, 피그마 ⑦-8g) ── */

/** 기준일 계산을 거치지 않은 관계 한 줄. 그래프 모양만 볼 때 쓴다 */
function view(id, from, to, count, confidence = 'confirmed') {
  return {
    rel: { id, from, to, kind: 'affiliate', confidence, evidence: ['x'] },
    count, first: null, last: null, evidence: [], fromRegistry: false,
  };
}

test('출발 영토도 칩 줄에 둔다 — 점을 찍을 칩이 있어야 한다 (설계서 4.3.3 ①)', () => {
  const { views } = sample();
  // 건수 합 상위 3: f1 · r1 · t1
  assert.deepEqual(centerChips(views, 'f1', nameOf, 3, 'r2'), ['r2', 'f1', 'r1', 't1'], '출발이 상위 밖이면 앞에 붙인다');
  assert.deepEqual(centerChips(views, 'f2', nameOf, 3, 'r2'), ['f2', 'r2', 'f1', 'r1', 't1'], '중심 다음 자리');
  assert.deepEqual(centerChips(views, 'f1', nameOf, 3, 'r1'), ['f1', 'r1', 't1'], '상위 안이면 그대로');
  assert.deepEqual(centerChips(views, 'r2', nameOf, 3, 'r2'), ['r2', 'f1', 'r1', 't1'], '중심과 같으면 한 번만');
});

test('돌아가기 단추 — 고른 것이 없으면 출발 탭 이름 (설계서 4.3.3 ① · 4.2.2)', () => {
  assert.equal(backLabel('map', 'Qilin'), 'Qilin 연결로 돌아가기');
  assert.equal(backLabel('entity', '포럼'), '포럼 연결로 돌아가기');
  assert.equal(backLabel('map', null), '지도로 돌아가기');
  assert.equal(backLabel('entity', null), '엔티티로 돌아가기');
  assert.equal(backLabel('timeline', null), '타임라인으로 돌아가기');
});

test('사건 판정 → 신뢰도 칩. 허위는 칩이 없다 (설계서 2.3)', () => {
  assert.equal(confOfVerdict('confirmed'), 'confirmed');
  assert.equal(confOfVerdict('high'), 'high');
  assert.equal(confOfVerdict('false'), null);
  for (const v of ['unverified', 'unknown', 'low']) assert.equal(confOfVerdict(v), 'estimated', v);
});

test('추정 관계 포함을 끄면 추정 신뢰도 관계만 빠진다 (피그마 ⑦-8g)', () => {
  const { views } = sample();
  assert.equal(withEstimated(views, true).length, views.length);
  assert.deepEqual(withEstimated(views, false).map((v) => v.rel.id), ['REL-1', 'REL-3'], '확인됨 · 높은 신뢰는 남는다');
});

test('1단계는 중심에 닿은 관계뿐, 2단계는 이웃의 이웃을 더한다 (설계서 4.3.6, 피그마 ⑦-8g)', () => {
  const { views } = sample();

  // f1 중심: 1단계 넷. 건수가 같은 Play(r2) · PwnForums(f2) 는 이름 순
  const one = expandHops(views, 'f1', 1, nameOf);
  assert.deepEqual(one.hop1, ['r1', 't1', 'r2', 'f2']);
  assert.deepEqual(one.hop2, []);
  assert.deepEqual(one.views.map((v) => v.rel.id).sort(), ['REL-1', 'REL-2', 'REL-3', 'REL-4'], '1단계끼리 선(REL-5)은 안 그린다');

  // f1 은 모두와 이어져 2단계로 넓힐 곳이 없다. 대신 1단계끼리 선이 든다
  const fTwo = expandHops(views, 'f1', 2, nameOf);
  assert.deepEqual(fTwo.hop2, []);
  assert.ok(fTwo.views.some((v) => v.rel.id === 'REL-5'), '1단계끼리 선');

  // r2 중심: 1단계 f1 하나, 2단계는 f1 의 이웃 셋. 건수 합 순
  const two = expandHops(views, 'r2', 2, nameOf);
  assert.deepEqual(two.hop1, ['f1']);
  assert.deepEqual(two.hop2, ['r1', 't1', 'f2']);
  assert.deepEqual([...two.via.values()], ['f1', 'f1', 'f1']);
  assert.equal(two.rest, 0);
  assert.ok(!two.views.some((v) => v.rel.id === 'REL-5'), '2단계끼리 선(r1 → t1)은 중심에서 세 걸음이라 뺀다');
  assert.deepEqual(two.views.map((v) => v.rel.id).sort(), ['REL-1', 'REL-2', 'REL-3', 'REL-4']);

  // 자리가 모자라면 건수 합이 큰 곳만 남기고 뺀 수를 적는다. 뺀 곳의 선도 빠진다
  const cut = expandHops(views, 'r2', 2, nameOf, 2);
  assert.deepEqual(cut.hop2, ['r1', 't1']);
  assert.equal(cut.rest, 1);
  assert.ok(!cut.views.some((v) => v.rel.id === 'REL-4'));

  // 관계가 없는 영토는 2단계로 넓혀도 비어 있다 — 관계 없음 화면의 「2단계로 확장」이 할 일이 없다
  const none = expandHops(views, 'nowhere', 2, nameOf);
  assert.deepEqual([none.hop1, none.hop2, none.views], [[], [], []]);
});

test('2단계 영토는 건수가 가장 큰 1단계 영토 곁에 선다', () => {
  const views = [
    view('A', 'c', 'a', 5),
    view('B', 'c', 'b', 1),
    view('XA', 'x', 'a', 1),
    view('XB', 'x', 'b', 3),
    view('YA', 'y', 'a', 2),
    view('YB', 'y', 'b', 2),
  ];
  const h = expandHops(views, 'c', 2, (id) => id);
  assert.deepEqual(h.hop1, ['a', 'b']);
  assert.deepEqual(h.hop2, ['x', 'y'], '둘 다 건수 합 4 — 이름 순');
  assert.equal(h.via.get('x'), 'b', '건수 3 쪽');
  assert.equal(h.via.get('y'), 'a', '같으면 1단계 차례가 앞선 쪽');
});

test('관계 없음 요약 — 가린 추정 관계뿐이면 피그마 ⑦-8g 문안', () => {
  assert.equal(
    summaryText('Exploit.in', [], 0, 0, 2),
    'Exploit.in은 아직 확인된 관계가 없습니다. 추정 관계를 포함하면 연결 후보를 확인할 수 있습니다.',
  );
  assert.equal(summaryText('Exploit.in', [], 0, 0), 'Exploit.in은 이 기준일에 기록된 관계가 없습니다.');
});

test('중심에 닿지 않은 선을 고르면 중심의 관계와 견주지 않는다 (2단계 확장)', () => {
  const ca = view('CA', 'c', 'a', 1);
  const xa = view('XA', 'x', 'a', 9);
  const text = selectedText(xa, 'c', [ca], (id) => id);
  assert.match(text, /^선택한 관계 x → a는 제휴자 모집 9건입니다\./);
  assert.doesNotMatch(text, /가장 많습니다/);
});
