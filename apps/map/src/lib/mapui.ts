/**
 * 지도 조작의 자리 계산 — 설계서 4.2.3 · 4.2.5.
 *
 * 부품(`MapCanvas` · `HoverTip` · `SnapshotBar`)이 그리기 전에 필요한 숫자만
 * 모았다. DOM 을 안 만지므로 시험으로 잡힌다. 부품은 잰 크기를 넘기고 결과로
 * 그린다.
 */

import { quarterText, type QuarterKey } from "./quarter.ts";

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

/** 이름표 사이 최소 틈 (px) */
const TICK_GAP = 4;

/**
 * 폭(px)에 맞춰 이름표를 달 눈금 — `labelTicks` 의 개수를 줄여 가며 이름표끼리 안 겹치는 것을 고른다.
 * 이름표 하나를 `labelW` 로 본다. 양 끝 이름표는 줄 끝에 맞추고 가운데 것은 제 눈금 가운데에 앉는다.
 * 눈금 자리는 스냅샷 바 `tickLeft` 와 같다(양 끝 8px 안쪽). 전에는 분기 수로만 정해 슬라이더가
 * 좁아지면 이름표가 겹쳤다 (2026-09-29 묶음 6 검토)
 */
export function fitTicks(n: number, width: number, labelW: number, max: number): number[] {
  const span = (k: number): [number, number] => {
    if (k === 0) return [0, labelW];
    if (k === n - 1) return [width - labelW, width];
    const x = 8 + ((width - 16) * k) / (n - 1);
    return [x - labelW / 2, x + labelW / 2];
  };
  for (let m = max; m > 2; m--) {
    const ks = labelTicks(n, m);
    if (ks.every((k, j) => j === 0 || span(ks[j - 1])[1] + TICK_GAP <= span(k)[0])) return ks;
  }
  return n > 1 ? [0, n - 1] : labelTicks(n, 1);
}

/**
 * 지나간 분기를 보고 있으면 그 이름(`2025 Q3`), 가장 최근 분기면 `null`.
 *
 * 피그마 ⑦-1a · ⑦-1b 가 제목 옆 · 패널 머리글 · 지도 힌트에 「2024-09 스냅샷」을
 * 적는다. 판 1.2 에서 단위가 분기가 되어 스냅샷 바 제목과 같은 꼴로 적는다.
 * 「기준일로」가 돌아가는 가장 최근 분기는 스냅샷이 아니라 지금이라 안 적는다.
 */
export function pastSnapshot(value: QuarterKey, latest: QuarterKey): string | null {
  return value === latest ? null : quarterText(value);
}

/**
 * 같은 두 영토 사이 k 번째 선의 알약 자리 — 곡선 위 진행도. 첫 선은 가운데(0.5), 다음은 0.33 · 0.67 · 0.16 …
 * 로 번갈아 비킨다. 곡선을 더 휘기만 하면 알약 가운데가 11 만 비켜나 늘 겹쳐 둘째 알약이 안 나왔다
 * (G-10 남은 결함). 0.16 ~ 0.84 안에서 멈춘다
 */
export function labelT(k: number): number {
  if (k <= 0) return 0.5;
  const step = Math.ceil(k / 2) * 0.17;
  return Math.min(0.84, Math.max(0.16, 0.5 + (k % 2 === 1 ? -step : step)));
}

/** 섬마다 이름표를 다는 영토 수 — 점수 상위 (2026-10-01 팀 피드백 2 「상위 10개만 보이면 분포가 깔끔해진다」) */
export const NAME_TOP = 10;
/**
 * 영토 이름표 글자 크기 · 알약 높이 (viewBox 단위, 칸 반지름 10). 전에는 8 · 14 라 100% 에서 화면 4~6px 로
 * 안 읽혔다 — 팀 피드백 2 「너무 작은 라벨 글씨도 키울 수 있다」. 확대하면 화면에서 100% 때 크기를 지킨다
 */
export const NAME_FS = 12;
export const NAME_H = 20;

/** 영토 이름표 알약 폭 (viewBox 단위, 100%). 한글은 글자 크기만큼, 나머지는 0.58 배로 어림한다(`HexMap`) */
export function nameW(name: string): number {
  let w = 0;
  for (const ch of name) w += /[가-힣ㄱ-ㆎ]/.test(ch) ? 1 : 0.58;
  return w * NAME_FS + 14;
}

/** 이름표를 고를 때 보는 영토 꼴 — `layout.ts` `TerritoryShape` 의 일부 */
export type NameCand = {
  territoryId: string;
  name: string;
  islandKey: string;
  cells: readonly unknown[];
  label: Pt;
  metrics: { score: number };
};

/**
 * 이름표를 달 영토를 고른다 — **섬마다 점수 상위 `top` 곳까지, 겹치지 않는 만큼**.
 *
 * 영토는 다 그리고(점수 · 칸 계산 그대로) 이름표만 줄인다 (2026-10-01 팀 피드백 2, 기본안). 점수가 큰
 * 것부터 놓고 앞서 놓은 이름표와 겹치면 뺀다 — 작은 영토가 몰린 곳은 열 곳이 다 안 든다. 확대하면
 * 알약이 판 단위로 작아져(`ls`) 더 든다. 이름표가 없는 영토는 마우스를 올리면 툴팁이 이름을 보인다.
 * 전에는 섬마다 칸이 많은 둘(고른 섬은 넷)이었다 (피그마 ⑦-1 · ⑦-2)
 */
export function pickLabels<T extends NameCand>(territories: readonly T[], ls = 1, top = NAME_TOP): T[] {
  const byIsland = new Map<string, T[]>();
  for (const t of territories) {
    const list = byIsland.get(t.islandKey) ?? [];
    list.push(t);
    byIsland.set(t.islandKey, list);
  }
  const out: T[] = [];
  const placed: { x0: number; y0: number; x1: number; y1: number }[] = [];
  for (const list of byIsland.values()) {
    const ranked = [...list].sort(
      (a, b) =>
        b.metrics.score - a.metrics.score ||
        b.cells.length - a.cells.length ||
        a.territoryId.localeCompare(b.territoryId),
    );
    let n = 0;
    for (const t of ranked) {
      if (n >= top) break;
      const w = (nameW(t.name) * ls) / 2;
      const h = (NAME_H * ls) / 2;
      const b = { x0: t.label.x - w, y0: t.label.y - h, x1: t.label.x + w, y1: t.label.y + h };
      if (placed.some((o) => o.x0 < b.x1 && b.x0 < o.x1 && o.y0 < b.y1 && b.y0 < o.y1)) continue;
      placed.push(b);
      out.push(t);
      n += 1;
    }
  }
  return out;
}
