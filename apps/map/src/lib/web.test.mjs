/**
 * src/lib/web.ts 시험 — 검색 결과 줄의 웹 표시 (설계서 4.2.2 · 5.3).
 *
 *   node --experimental-strip-types --test src/lib/web.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { DARK_ISLANDS, OPEN_ISLANDS } from './islands.ts';
import { WEB_LABEL, webOfIsland } from './web.ts';

test('다크웹 섬 넷은 다크웹이다', () => {
  for (const i of DARK_ISLANDS) assert.equal(webOfIsland(i.id), 'dark', i.id);
});

test('오픈웹 섬 여덟은 오픈웹이다 — OTHER 도 (판 1.2 뒤로 오픈웹에만 있다)', () => {
  for (const i of OPEN_ISLANDS) assert.equal(webOfIsland(i.id), 'open', i.id);
  assert.equal(webOfIsland('OTHER'), 'open');
});

test('섬 정의의 web 과 어긋나지 않는다', () => {
  for (const i of [...DARK_ISLANDS, ...OPEN_ISLANDS]) assert.equal(webOfIsland(i.id), i.web, i.id);
});

test('웹 이름은 머리띠 웹 전환 탭과 같은 글이다', () => {
  assert.equal(WEB_LABEL.dark, '다크웹');
  assert.equal(WEB_LABEL.open, '오픈웹');
});
