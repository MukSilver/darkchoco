/**
 * src/lib/report.ts 시험 — 사건 보고서 팝업 한 장 (설계서 4.3.4).
 *
 *   node --experimental-strip-types --test src/lib/report.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { SOURCE_NOTE, eventReport, eventSummary, linkedOf, reportJson } from './report.ts';

let seq = 0;
function ev(extra = {}) {
  seq += 1;
  return {
    id: `LEAK-${seq}`, territoryId: 'qilin', postedAt: '2026-09-10T21:40:00Z', verdict: 'confirmed', size: 'large',
    repost: false, excluded: false, ...extra,
  };
}

const NAMES = {
  nameOf: (id) => ({ qilin: 'Qilin', bf: 'BreachForums', ash: 'Ash_22', tg: 'Leak Channel' })[id] ?? id,
  islandOf: (id) => ({ qilin: '랜섬웨어', bf: '포럼', ash: '행위자', tg: '텔레그램' })[id] ?? '',
};

test('연결된 사건은 어느 쪽 줄에 적혀도 잇고, 화면에 없는 사건과 자기 자신은 뺀다', () => {
  const a = ev({ postedAt: '2026-09-10T00:00:00Z' });
  const b = ev({ postedAt: '2026-09-11T00:00:00Z', linked: [a.id] }); // b 쪽에만 적혔다
  const c = ev({ postedAt: '2026-09-12T00:00:00Z' });
  const gone = ev({ verdict: 'false', linked: [a.id] });
  const hidden = ev({ excluded: true, linked: [a.id] });
  a.linked = [c.id, a.id];
  const got = linkedOf([a, b, c, gone, hidden], a);
  assert.deepEqual(got.map((x) => x.id), [c.id, b.id], '최신순이고 허위 · 반출 제외 · 자기 자신은 없다');
  assert.deepEqual(linkedOf([a, b, c], b).map((x) => x.id), [a.id], '반대쪽에서 열어도 이어진다');
  assert.deepEqual(linkedOf([a, b, c], ev()), [], '같은 사건이 없으면 빈 목록');
});

test('보통 사건 — 칩 넷, 정보 표 다섯 칸. 피해 조직 · 활동도 영향 줄은 없다 (2026-09-26 결정, L697)', () => {
  const e = ev({
    kind: 'data_post', risk: 'high', verdict: 'unverified', actorTerritoryId: 'ash',
    country: 'KR', industry: '의료', sizeValue: 1.2, sizeUnit: 'TB', leakItems: ['이름', '주민번호'],
  });
  const m = eventReport(e, NAMES, [], []);
  assert.equal(m.official, false);
  assert.equal(m.title, '[KR · 의료 · 2026-09-10 · 1.2TB]');
  assert.equal(m.meta, 'Qilin · 랜섬웨어 섬 · 2026-09-10 21:40 UTC');
  assert.deepEqual(m.chips.map((c) => [c.label, c.tone]), [
    ['데이터 게시', 'warning'],
    ['추정', 'neutral'],
    ['위험도 높음', 'danger'],
    [e.id, 'neutral'],
  ], '검증 전은 신뢰도 「추정」 이다 (confOfVerdict)');
  assert.ok(m.chips[3].tag, '사건 번호는 태그');
  assert.deepEqual(m.fields.map((f) => f.label), ['발생 일시', '엔티티', '게시 위치', '유출 규모', '유출 항목']);
  const [when, entity, where, size, items] = m.fields;
  assert.equal(when.value, '2026-09-10 21:40 UTC');
  assert.equal(entity.value, 'Qilin (랜섬웨어)');
  assert.equal(entity.territoryId, 'qilin', '영토 칸은 누르면 지도로 간다 (L704)');
  assert.equal(where.value, 'Ash_22 → Qilin', '행위자 사건은 「행위자 → 영토」');
  assert.equal(size.value, '1.2TB');
  assert.deepEqual(items.items, ['이름', '주민번호']);
  assert.equal(m.source.type, '수집 소스 · 랜섬웨어 섬');
  assert.equal(m.source.meta, '게시 2026-09-10 · 판정 검증 전');
});

test('규모 숫자가 없으면 등급, 항목이 없으면 「기록 없음」, 신뢰도 · 위험도가 없으면 칩을 뺀다', () => {
  const m = eventReport(ev({ size: 'medium', verdict: 'false' }), NAMES, [], []);
  assert.equal(m.fields[3].value, '규모 중간');
  assert.equal(m.fields[4].value, '기록 없음');
  assert.equal(m.fields[4].items, undefined);
  assert.deepEqual(m.chips.map((c) => c.label), [m.id], '종류 · 신뢰도(허위) · 위험도가 없으면 번호 태그만');
  assert.equal(m.fields[2].value, 'Qilin', '행위자가 없으면 영토만');
});

test('공식 발표 변형 (L698) — 칩은 공식 발표 · 외부 확인, 표는 사고 시점 · 공표 시점 · 유출 규모 · 유출 항목', () => {
  const e = ev({
    id: 'INC-7', kind: 'official', risk: 'high', confirm: '규제기관 확정', sourceKind: '언론 보도',
    occurredAt: '2026-08-30', sizeValue: 120, sizeUnit: '만', leakItems: ['이메일'],
  });
  const m = eventReport(e, NAMES, [], []);
  assert.equal(m.official, true);
  assert.deepEqual(m.chips.map((c) => [c.label, c.tone]), [
    ['공식 발표', 'info'],
    ['외부 확인 · 규제기관 확정', 'success'],
    ['INC-7', 'neutral'],
  ]);
  assert.deepEqual(m.fields.map((f) => [f.label, f.value]), [
    ['사고 시점', '2026-08-30'],
    ['공표 시점', '2026-09-10 21:40 UTC'],
    ['유출 규모', '120만'],
    ['유출 항목', '이메일'],
  ]);
  assert.ok(m.fields.every((f) => !f.territoryId));
  assert.equal(m.source.type, '출처 종류 · 언론 보도');
  const bare = eventReport(ev({ kind: 'official' }), NAMES, [], []);
  assert.equal(bare.fields[0].value, '기록 없음', '사고 시점이 없으면 그렇게 적는다');
  assert.equal(bare.source.type, '출처 종류 · 기록 없음');
  assert.deepEqual(bare.chips.map((c) => c.label), ['공식 발표', bare.id]);
});

test('설명은 분류 칸으로만 짓는다 — 자유 글 칸은 섞이지 않는다', () => {
  const e = ev({
    kind: 'sale', verdict: 'high', actorTerritoryId: 'ash', territoryId: 'bf', country: 'KR', industry: '유통',
    sizeValue: 3400000, sizeUnit: '건',
    // 굽기가 안 싣는 칸이 섞여 들어와도 문장과 파일에 나오면 안 된다
    title: '비밀 조직 고객 DB', note: '비밀 메모',
  });
  assert.equal(
    eventSummary(e, NAMES),
    'Ash_22가 BreachForums에 올린 판매 사건입니다. 대상 분류는 KR · 유통입니다. 주장 규모는 3,400,000건입니다. 검증 판정은 「신뢰성 높음」입니다.',
  );
  assert.equal(
    eventSummary(ev({ size: 'unknown' }), NAMES),
    'Qilin에 올라온 사건입니다. 규모는 확인되지 않았습니다. 검증 판정은 「확인됨」입니다.',
  );
  assert.equal(
    eventSummary(ev({ kind: 'official', confirm: '언론 보도', size: 'small' }), NAMES),
    'Qilin에 유출 위치가 보도된 공식 발표 사고입니다. 규모 등급은 작음입니다. 외부 확인은 「언론 보도」입니다.',
  );
  const json = JSON.stringify(reportJson(eventReport(e, NAMES, [], [])));
  assert.ok(!json.includes('비밀'), '모형 밖 칸은 JSON 에도 없다');
});

test('연결된 사건 · 관계 줄 — 신뢰도 칩, 관계는 종류 차례', () => {
  const e = ev({ actorTerritoryId: 'ash' });
  const other = ev({ territoryId: 'tg', verdict: 'high', country: 'KR' });
  const rels = [
    { id: 'REL-0002', from: 'qilin', to: 'bf', kind: 'leak', confidence: 'high', evidence: [e.id] },
    { id: 'ACT-ash-qilin', from: 'ash', to: 'qilin', kind: 'activity', confidence: 'confirmed', evidence: [e.id] },
    { id: 'REL-0001', from: 'qilin', to: 'tg', kind: 'affiliate', confidence: 'estimated', evidence: [e.id] },
  ];
  const m = eventReport(e, NAMES, [other], rels);
  assert.deepEqual(m.linked, [{ id: other.id, title: '[KR · 2026-09-10]', place: 'Leak Channel', conf: 'high' }]);
  assert.deepEqual(
    m.relations.map((r) => [r.id, r.route, r.kind, r.conf]),
    [
      ['REL-0001', 'Qilin → Leak Channel', '제휴자 모집', 'estimated'],
      ['REL-0002', 'Qilin → BreachForums', '데이터 유출', 'high'],
      ['ACT-ash-qilin', 'Ash_22 → Qilin', '활동', 'confirmed'],
    ],
  );
});

test('JSON 내보내기는 팝업에 보인 글자 그대로다 (L707) — 칩 색 같은 그리기 값은 없다', () => {
  const e = ev({ kind: 'claim', risk: 'low', leakItems: ['계정'] });
  const m = eventReport(e, NAMES, [], [
    { id: 'REL-0003', from: 'qilin', to: 'bf', kind: 'contact', confidence: 'confirmed', evidence: [e.id] },
  ]);
  const j = reportJson(m);
  assert.deepEqual(Object.keys(j), ['id', 'title', 'meta', 'chips', 'fields', 'description', 'linked', 'relations', 'source']);
  assert.deepEqual(j.chips, ['피해 주장', '확인됨', '위험도 낮음', e.id]);
  assert.deepEqual(j.fields, m.fields.map((f) => ({ label: f.label, value: f.value })));
  assert.deepEqual(j.relations, [{ id: 'REL-0003', route: 'Qilin → BreachForums', kind: '공지·연락', confidence: '확인됨' }]);
  assert.deepEqual(j.source, { ...m.source, note: SOURCE_NOTE });
  assert.ok(!JSON.stringify(j).includes('tone'), '칩 색은 화면에만');
  assert.ok(!j.fields.some((f) => f.label === '피해 조직' || f.label === '활동도 영향'));
});
