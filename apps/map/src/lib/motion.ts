/**
 * 시점을 옮길 때 섬이 옮겨 가는 움직임 — 계산만 (그리기는 `HexMap`).
 *
 * 2026-09-28 최현서 7번 「슬라이더를 잡고 당겼을 때 지구본에서 대륙이 이동하는 것처럼 자연스럽게」.
 * 분기마다 칸 배치를 새로 계산해서(`layoutMap`) 칸 하나하나를 이어 움직일 수는 없다. 대신
 * **섬 단위로** 앞 분기의 자리 · 크기에서 새 자리 · 크기로 옮겨 간다(FLIP — 새 모양을 앞 자리에
 * 놓고 시작해 제자리로 돌아온다). 새로 생긴 섬은 제자리에서 번져 나온다.
 *
 * 지도 탭 슬라이더 · 재생 · 「기준일로」, 타임라인의 연도 칩 · 스냅샷 카드 · ◀ ▶▶ · 슬라이더가
 * 모두 `HexMap` 하나를 거치므로 같은 움직임을 쓴다.
 */

import { cellToXY } from "./hex.ts";
import { HEX, type MapLayout } from "./layout.ts";

/** 섬이 차지한 자리 (viewBox 단위). 가운데와 폭 · 높이 */
export type IslandBox = { cx: number; cy: number; w: number; h: number };

/** 섬마다 칸 가운데들을 다 담는 상자 */
export function islandBoxes(layout: Pick<MapLayout, "islands">): Map<string, IslandBox> {
  const out = new Map<string, IslandBox>();
  for (const isl of layout.islands) {
    let x0 = Infinity;
    let y0 = Infinity;
    let x1 = -Infinity;
    let y1 = -Infinity;
    for (const [c, r] of isl.cells) {
      const p = cellToXY(c, r, HEX);
      x0 = Math.min(x0, p.x);
      y0 = Math.min(y0, p.y);
      x1 = Math.max(x1, p.x);
      y1 = Math.max(y1, p.y);
    }
    if (!Number.isFinite(x0)) continue;
    out.set(isl.islandKey, { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: Math.max(HEX, x1 - x0), h: Math.max(HEX, y1 - y0) });
  }
  return out;
}

/** viewBox 글자의 왼쪽 위 */
export function boxOrigin(viewBox: string): { x: number; y: number } {
  const [x, y] = viewBox.split(/\s+/).map(Number);
  return { x: x || 0, y: y || 0 };
}

/**
 * 새 모양을 앞 자리 · 크기에 놓는 CSS transform. 이 값에서 `none` 으로 옮겨 가면 섬이 앞 자리에서
 * 새 자리로 옮겨 간다.
 *
 * SVG 요소의 CSS transform 은 viewBox 의 사용자 좌표(원점 0,0)에서 먹고 1px = 1단위다. 틀(viewBox)이
 * 분기마다 제 가운데로 옮겨 가므로(`centerBox`) 앞 자리를 새 틀 기준으로 옮겨 적는다 — 틀 크기가
 * 같으면 화면 자리는 (점 − 틀 원점)에 비례한다. 크기 비는 폭 · 높이 비의 평균이고 너무 크게
 * 튀지 않게 0.4~2.5 로 자른다
 */
export function flipFrom(
  was: IslandBox,
  now: IslandBox,
  wasOrigin: { x: number; y: number },
  nowOrigin: { x: number; y: number },
): string {
  const ax = was.cx - wasOrigin.x + nowOrigin.x;
  const ay = was.cy - wasOrigin.y + nowOrigin.y;
  const s = Math.min(2.5, Math.max(0.4, (was.w / now.w + was.h / now.h) / 2));
  return `translate(${r2(ax)}px, ${r2(ay)}px) scale(${r3(s)}) translate(${r2(-now.cx)}px, ${r2(-now.cy)}px)`;
}

/** 새로 생긴 섬이 번져 나오는 첫 모양 — 제자리에서 조금 작게 */
export function growFrom(now: IslandBox, s = 0.85): string {
  return `translate(${r2(now.cx)}px, ${r2(now.cy)}px) scale(${s}) translate(${r2(-now.cx)}px, ${r2(-now.cy)}px)`;
}

/** CSS 시간 글자(`480ms` · `0.3s` · `0ms`)를 밀리초로. 못 읽으면 0 */
export function parseMs(v: string): number {
  const m = /^\s*([\d.]+)\s*(ms|s)?\s*$/.exec(v);
  if (!m) return 0;
  const n = Number(m[1]);
  return m[2] === "s" ? n * 1000 : n;
}

const r2 = (n: number) => Math.round(n * 100) / 100;
const r3 = (n: number) => Math.round(n * 1000) / 1000;
