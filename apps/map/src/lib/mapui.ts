/**
 * 지도 조작의 자리 계산 — 설계서 4.2.3 · 4.2.5.
 *
 * 부품(`MapCanvas` · `HoverTip` · `SnapshotBar`)이 그리기 전에 필요한 숫자만
 * 모았다. DOM 을 안 만지므로 시험으로 잡힌다. 부품은 잰 크기를 넘기고 결과로
 * 그린다.
 */

import type { QuarterKey } from "./quarter.ts";

export type Pt = { x: number; y: number };
export type Size = { w: number; h: number };

/** 줌(%)과 이동(px). `MapCanvas` 의 `MapView` 와 같은 꼴이다 */
export type ViewState = { zoom: number; pan: Pt };

/**
 * 지도가 앉는 판. 캔버스 크기(px)와 위아래 여백이다 — 아래 여백은 힌트 알약과
 * 줌 단추 자리라 지도가 거기까지 안 내려간다 (`MapCanvas`)
 */
export type Stage = { w: number; h: number; top: number; bottom: number };

function parseViewBox(vb: string): { x: number; y: number; w: number; h: number } {
  const [x = 0, y = 0, w = 100, h = 100] = vb.split(/\s+/).map(Number);
  return { x, y, w: w || 1, h: h || 1 };
}

/**
 * viewBox 안의 점이 캔버스 어디(px)에 그려지는가.
 *
 * `MapCanvas` 의 겹을 그대로 따른다. SVG 는 여백을 뺀 판에 `xMidYMid meet` 로
 * 맞춰 앉고(가운데 정렬, 짧은 쪽에 맞춤), 그 판을 가운데 기준으로 줌만큼 키운 뒤
 * 이동만큼 민다.
 */
export function toCanvas(p: Pt, viewBox: string, stage: Stage, view: ViewState): Pt {
  const vb = parseViewBox(viewBox);
  const cw = stage.w;
  const ch = Math.max(0, stage.h - stage.top - stage.bottom);
  const s = Math.min(cw / vb.w, ch / vb.h);
  const ux = (cw - vb.w * s) / 2 + (p.x - vb.x) * s;
  const uy = (ch - vb.h * s) / 2 + (p.y - vb.y) * s;
  const z = view.zoom / 100;
  return {
    x: cw / 2 + (ux - cw / 2) * z + view.pan.x,
    y: stage.top + ch / 2 + (uy - ch / 2) * z + view.pan.y,
  };
}

/**
 * 고른 영토가 화면 밖이면 보이게 옮길 이동값 — 설계서 4.2.3 「영토 선택 시 줌 유지,
 * 화면 밖이면 보이는 위치로 이동」.
 *
 * 영토 이름표 자리(`TerritoryShape.label`)가 가장자리 `margin` 안쪽이면 그대로
 * 둔다(`null`). 밖이면 **줌은 두고 이동만 바꿔** 그 자리를 판 한가운데로 가져온다.
 * 가장자리에 겨우 걸치게 옮기면 이름표가 또 잘리고, 검색으로 멀리서 왔을 때
 * 어디로 왔는지 눈으로 못 쫓는다.
 *
 * 판이 아주 작으면 여백이 판을 다 먹지 않게 줄인다.
 */
export function revealPan(
  p: Pt,
  viewBox: string,
  stage: Stage,
  view: ViewState,
  margin = 48,
): Pt | null {
  const ch = Math.max(0, stage.h - stage.top - stage.bottom);
  const mx = Math.min(margin, stage.w / 4);
  const my = Math.min(margin, ch / 4);
  const at = toCanvas(p, viewBox, stage, view);
  const inside =
    at.x >= mx &&
    at.x <= stage.w - mx &&
    at.y >= stage.top + my &&
    at.y <= stage.top + ch - my;
  if (inside) return null;
  return {
    x: Math.round(view.pan.x + (stage.w / 2 - at.x)),
    y: Math.round(view.pan.y + (stage.top + ch / 2 - at.y)),
  };
}

/**
 * 툴팁 자리 (피그마 컴포넌트 시트 `Map Tooltip`, 255 × 141).
 *
 * 커서 오른쪽 아래에 띄우고, 캔버스 오른쪽 · 아래를 넘으면 커서 반대쪽으로
 * 뒤집는다. 뒤집어도 모자라면(캔버스가 툴팁보다 작다) 왼쪽 · 위 끝에 붙인다.
 */
export function tipPlace(
  at: Pt,
  tip: Size,
  box: Size,
  gap = 14,
): { left: number; top: number } {
  const flip = (c: number, len: number, room: number) => {
    if (c + gap + len <= room) return c + gap;
    const back = c - gap - len;
    return back >= 0 ? back : Math.max(0, Math.min(c + gap, room - len));
  };
  return { left: flip(at.x, tip.w, box.w), top: flip(at.y, tip.h, box.h) };
}

/**
 * 스냅샷 바에서 이름표를 달 눈금 번호 — 설계서 4.2.5.
 *
 * 눈금 자체는 분기마다 긋고, 이름표만 `max` 개 안쪽으로 건너뛴다. 오른쪽 끝(가장
 * 최근 분기)은 늘 단다. 건너뛰는 간격에 안 맞아 끝 바로 앞 이름표와 반 간격도 안
 * 떨어지면 앞의 것을 뺀다 — 둘이 겹쳐 글자가 안 읽힌다.
 */
export function labelTicks(n: number, max: number): number[] {
  if (n <= 0) return [];
  const last = n - 1;
  const step = Math.max(1, Math.ceil(n / Math.max(1, max)));
  const out: number[] = [];
  for (let k = 0; k < n; k += step) out.push(k);
  if (out[out.length - 1] !== last) {
    if (out.length > 1 && last - out[out.length - 1] < step / 2) out.pop();
    out.push(last);
  }
  return out;
}

/**
 * 지나간 분기를 보고 있으면 그 이름(`2025 Q3`), 가장 최근 분기면 `null`.
 *
 * 피그마 ⑦-1a · ⑦-1b 가 제목 옆 · 패널 머리글 · 지도 힌트에 「2024-09 스냅샷」을
 * 적는다. 판 1.2 에서 단위가 분기가 되어 스냅샷 바 제목과 같은 꼴로 적는다.
 * 「기준일로」가 돌아가는 가장 최근 분기는 스냅샷이 아니라 지금이라 안 적는다.
 */
export function pastSnapshot(value: QuarterKey, latest: QuarterKey): string | null {
  return value === latest ? null : value.replace("-", " ");
}
