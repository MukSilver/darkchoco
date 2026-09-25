/**
 * src/lib/panel.ts 시험 — 우측 패널 [개요] (설계서 4.3.1 · 4.3.2 · 4.3.8, 피그마 ⑦-11b).
 *
 *   node --experimental-strip-types --test src/lib/panel.test.mjs
 *
 * 작은 지도 하나를 실제 계산(`computeMap` → `layoutMap` → `relationsAt`)으로 만들어
 * 패널이 읽는 값과 같은 자리에서 대조한다.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { DARK_ISLANDS } from './islands.ts';
import { layoutMap } from './layout.ts';
import {
  actorInfoRows,
  actorSentence,
  allIslandPairs,
  ecosystemView,
  islandView,
  monthTicks,
  officialOf,
  rawText,
  territorySentence,
  territoryView,
} from './panel.ts';
import { islandPairs, relationsAt, withActivity } from './relations.ts';
import { computeMap } from './score.ts';

/* ── 재료 ─────────────────────────────────────────────────────── */

const D = new Date('2026-09-30T23:59:59Z');

let seq = 0;
function ev(territoryId, postedAt, extra = {}) {
  seq += 1;
  return {
    id: `p${seq}`, territoryId, postedAt, verdict: 'high', size: 'unknown',
    repost: false, excluded: false, ...extra,
  };
}

// since 와 today 를 안 주면 모든 영토가 지도에 있다 (score.ts presentAt)
const TERR = [
  { id: 'bf', name: 'BreachForums', islandId: 'FORUM', web: 'dark', raw: 6972 },
  { id: 'xss', name: 'XSS.is', islandId: 'FORUM', web: 'dark' },
  { id: 'qilin', name: 'Qilin', islandId: 'RANSOMWARE', web: 'dark', raw: 711.4 },
  { id: 'chan', name: '랜섬웨어 공지 채널', islandId: 'TELEGRAM', web: 'dark', raw: 1500 },
  {
    id: 'hex', name: 'hexbreaker', islandId: 'ACTOR', web: 'dark',
    actor: { roles: ['판매자'], firstSeen: '2024-03-01', deals: '계정 · DB', otherNames: [] },
  },
];

const Q1 = ev('qilin', '2026-03-10T00:00:00+09:00', { kind: 'official', country: 'KR', industry: '유통', sizeValue: 255, sizeUnit: 'GB' });
const Q2 = ev('qilin', '2026-08-01T09:00:00+09:00', { kind: 'official', country: 'KR' });
const Q3 = ev('qilin', '2026-10-05T09:00:00+09:00', { kind: 'official' }); // 기준일 뒤
const Q4 = ev('qilin', '2026-09-10T09:00:00+09:00', { kind: 'claim' });
const Q5 = ev('qilin', '2026-09-11T09:00:00+09:00', { kind: 'official', verdict: 'false' }); // 허위
const H1 = ev('bf', '2026-09-05T09:00:00+09:00', { actorTerritoryId: 'hex' });
const H2 = ev('bf', '2026-07-05T09:00:00+09:00', { actorTerritoryId: 'hex' });
const H3 = ev('xss', '2026-09-15T09:00:00+09:00', { actorTerritoryId: 'hex' });
const C1 = ev('chan', '2026-09-01T09:00:00+09:00');
const EVENTS = [Q1, Q2, Q3, Q4, Q5, H1, H2, H3, C1];

const RELS = withActivity(
  [
    { id: 'R1', from: 'qilin', to: 'bf', kind: 'affiliate', confidence: 'confirmed', evidence: [Q4.id] },
    { id: 'R2', from: 'chan', to: 'qilin', kind: 'contact', confidence: 'estimated', evidence: [C1.id] },
    // 명부 「연결된 곳」 에서 만든 관계 — 근거가 없어 1건이다
    { id: 'R3', from: 'qilin', to: 'chan', kind: 'leak', confidence: 'confirmed', evidence: [] },
  ],
  EVENTS,
);

const REG = new Map(TERR.map((t) => [t.id, t]));

// registry 에 null 을 주면 명부 없이 만든다 (undefined 는 기본값을 부른다)
function build(d = D, registry = (id) => REG.get(id)) {
  const result = computeMap({ islands: DARK_ISLANDS, territories: TERR, events: EVENTS }, d);
  const layout = layoutMap({ islands: DARK_ISLANDS, territories: TERR, web: 'dark' }, result);
  const present = new Set(layout.territories.map((t) => t.territoryId));
  const rels = relationsAt(RELS, EVENTS, d, present);
  return { layout, result, events: EVENTS, d, rels, lastSeen: {}, registry: registry ?? undefined };
}

const I = build();
const metrics = (input, id) => input.layout.territories.find((t) => t.territoryId === id).metrics;

/* ── 영토 [개요] ─────────────────────────────────────────────── */

test('영토 머리글은 「섬 이름 섬 · 사건 · 활동도 · 연결된 섬」 이다 (⑦-11b)', () => {
  const v = territoryView(I, 'qilin');
  const m = metrics(I, 'qilin');
  assert.equal(v.kindLabel, 'TERRITORY');
  assert.equal(m.eventCount, 3);
  assert.equal(v.subtitle, `랜섬웨어 섬 · 사건 3건 · 활동도 ${m.activity} · 연결된 섬 2`);
});

test('활동도 카드는 섬별 단위로 원자료를 적고 ▲▼ 줄은 그대로 둔다', () => {
  const q = territoryView(I, 'qilin').stats[0];
  assert.equal(q.raw, '피해 약 711건 (6개월)');
  assert.equal(q.note, '지난 30일');
  assert.equal(territoryView(I, 'bf').stats[0].raw, '회원 6,972명');
  assert.equal(territoryView(I, 'xss').stats[0].raw, '회원 —');
  assert.equal(territoryView(I, 'chan').stats[0].raw, '구독자 1,500명');
  // 명부를 못 받았으면 원자료 줄이 없다
  assert.equal(territoryView(build(D, null), 'bf').stats[0].raw, undefined);
});

test('영토 자동 문장은 피그마 꼴이고 검증된 관계는 확인됨 관계 수다', () => {
  // R1 · R3 이 확인됨, R2 는 추정
  assert.equal(
    territoryView(I, 'qilin').description,
    'Qilin은 랜섬웨어 섬에 속한 엔티티로, 사건 3건과 검증된 관계 2건이 관측되었습니다. ' +
      '영토를 클릭하면 관계선과 연결된 섬만 강조됩니다.',
  );
  assert.equal(territorySentence('Darkforums', '포럼', 5, 0).slice(0, 14), 'Darkforums는 포럼');
});

test('공식 발표 사고 절은 기준일까지의 건수와 공표일이 가장 늦은 1건이다', () => {
  const o = territoryView(I, 'qilin').official;
  // Q3 은 기준일 뒤, Q5 는 허위라 빠진다
  assert.equal(o.count, 2);
  assert.deepEqual(o.latest, { id: Q2.id, title: '[KR · 2026-08-01]', day: '2026-08-01', size: null });
  // 기준일을 앞으로 옮기면 그때까지만 센다
  const early = officialOf(EVENTS, 'qilin', new Date('2026-06-30T23:59:59Z'));
  assert.equal(early.count, 1);
  assert.equal(early.latest.size, '255GB');
  assert.deepEqual(territoryView(I, 'bf').official, { count: 0, latest: null });
});

test('섬 · 생태계 패널에는 공식 발표 · 행위자 절이 없다', () => {
  const eco = ecosystemView(I);
  const isl = islandView(I, I.layout.islands[0].islandKey);
  assert.equal(eco.official, null);
  assert.equal(eco.actor, null);
  assert.equal(isl.official, null);
  assert.equal(isl.actor, null);
});

test('지나간 분기면 생태계 머리글이 「스냅샷 · 사건」 이다 (⑦-1a · ⑦-1b)', () => {
  const eco = ecosystemView(I);
  assert.match(eco.subtitle, /^섬 \d+ · 엔티티 \d+ · 연결 \d+$/);
  const past = ecosystemView({ ...I, snapshot: '2025 Q3' });
  assert.equal(past.subtitle, `2025 Q3 스냅샷 · 사건 ${eco.eventCount}건`);
  // 머리글만 바뀌고 숫자는 그대로다
  assert.deepEqual(past.stats, eco.stats);
});

test('섬 고정 설명은 네 섬 모두 있다 (포럼 확정, 나머지 초안)', () => {
  for (const isl of I.layout.islands) {
    const v = islandView(I, isl.islandKey);
    assert.match(v.description, /유형/, isl.islandId);
  }
});

/* ── 행위자 [개요] ───────────────────────────────────────────── */

test('행위자는 ACTOR 머리글에 핸들 · 사건 · 활동도 · 활동 영토 수다', () => {
  const v = territoryView(I, 'hex');
  const m = metrics(I, 'hex');
  assert.equal(v.kindLabel, 'ACTOR');
  assert.equal(v.stateLabel, '선택됨');
  assert.equal(v.title, 'hexbreaker');
  assert.equal(v.subtitle, `사건 3건 · 활동도 ${m.activity} · 활동 영토 2곳`);
  assert.equal(v.descTitle, '행위자 설명');
  assert.equal(v.official, null);
  assert.equal(v.stats[0].raw, '사건 3건');
  // [연결] 배지는 활동한 영토 수
  assert.equal(v.linkCount, 2);
});

test('주 활동 영토는 사건이 가장 많은 곳이고 나머지는 많은 순이다', () => {
  const a = territoryView(I, 'hex').actor;
  assert.deepEqual(a.main, { territoryId: 'bf', name: 'BreachForums', token: 'forum', count: 2 });
  assert.deepEqual(a.others.map((r) => [r.territoryId, r.count]), [['xss', 1]]);
  assert.equal(
    territoryView(I, 'hex').description,
    'hexbreaker는 사건 3건을 올린 행위자로, 주 활동 영토는 BreachForums입니다. BreachForums 외에 1곳에서도 활동했습니다.',
  );
});

test('행위자 활동 영토는 기준일까지의 사건으로 센다', () => {
  const v = territoryView(build(new Date('2026-08-31T23:59:59Z')), 'hex');
  assert.equal(v.actor.main.territoryId, 'bf');
  assert.equal(v.actor.main.count, 1);
  assert.deepEqual(v.actor.others, []);
  assert.match(v.subtitle, /활동 영토 1곳$/);
});

test('행위자 정보는 설계서 차례로 내고 빈 칸은 줄째 뺀다', () => {
  assert.deepEqual(
    territoryView(I, 'hex').actor.info.map((r) => r.label),
    ['역할', '처음 본 날', '다루는 것'],
  );
  assert.deepEqual(
    actorInfoRows({ otherNames: ['hexb', 'hex_b'], roles: ['판매자', '운영자'], countries: ['러시아'], firstSeen: '2024-03-01', deals: 'DB' }),
    [
      { label: '다른 이름', value: 'hexb, hex_b' },
      { label: '역할', value: '판매자 · 운영자' },
      { label: '국가', value: '러시아' },
      { label: '처음 본 날', value: '2024-03-01' },
      { label: '다루는 것', value: 'DB' },
    ],
  );
  assert.deepEqual(actorInfoRows(undefined), []);
  assert.deepEqual(territoryView(build(D, null), 'hex').actor.info, []);
});

test('행위자 자동 문장은 사건이 없거나 활동 영토가 하나면 짧아진다', () => {
  assert.equal(actorSentence('Qilin', 0, null, 0), 'Qilin은 이 기준일까지 올린 사건이 없습니다.');
  assert.equal(actorSentence('hex', 2, 'XSS.is', 1), 'hex는 사건 2건을 올린 행위자로, 주 활동 영토는 XSS.is입니다.');
});

/* ── 작은 계산 ───────────────────────────────────────────────── */

test('원자료 글은 섬마다 단위가 다르고 다른 섬은 없다', () => {
  assert.equal(rawText('RANSOMWARE', 1234.6), '피해 약 1,235건 (6개월)');
  assert.equal(rawText('TELEGRAM', null), '구독자 —');
  assert.equal(rawText('ACTOR', 10), undefined);
});

test('월별 막대 축 이름표는 피그마처럼 12개월에 넷이다', () => {
  assert.deepEqual(monthTicks(12), [0, 3, 6, 11]);
  assert.deepEqual(monthTicks(4), [0, 3]);
  assert.deepEqual(monthTicks(1), [0]);
  assert.deepEqual(monthTicks(0), []);
});

test('선택 없음 [연결] 은 섬 쌍 요약 전부이고 섬 [연결] 줄과 같다', () => {
  const islandOf = (id) => I.layout.territories.find((t) => t.territoryId === id)?.islandKey;
  const keys = I.layout.islands.map((i) => i.islandKey);
  const all = allIslandPairs(I.rels, islandOf, keys);
  const k = all.map((r) => `${r.from}>${r.to}`);
  assert.equal(new Set(k).size, k.length);
  // 랜섬→포럼, 텔레→랜섬, 랜섬→텔레, 행위자→포럼(bf · xss 두 쌍)
  assert.equal(all.length, 4);
  const actorRow = all.find((r) => r.from === 'dark:ACTOR');
  assert.equal(actorRow.pairs, 2);
  assert.equal(actorRow.count, 3);
  for (const r of all) {
    assert.deepEqual(islandPairs(I.rels, islandOf, r.from).find((x) => x.to === r.to), r);
  }
  // 건수 많은 순
  assert.ok(all.every((r, i) => i === 0 || all[i - 1].count >= r.count));
});
