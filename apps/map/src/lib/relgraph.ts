/**
 * 관계도(`RelationTab`) 판 규칙 — 배율에 따른 라벨 고르기, 노드 이름 자리, 범례를 피하는 밀기.
 *
 * **라벨은 배율에 따라 단다** (2026-09-28 최현서 5번 — 「선과 관계는 늘 보이되, 확대했을 땐
 * 모두 보이고, 줄였을 땐 주요 관계만 글자를 표시」).
 *
 *   100% 미만    1단계 선 가운데 건수 상위 `LABEL_TOP` 개만
 *   100%         지금까지 규칙 — 1단계 선 전부, 2단계 바깥 선은 안 단다
 *   125% 이상    2단계 바깥 선도 전부
 *   강조 · 고른 선은 배율 · 겹침과 상관없이 늘 단다
 *
 * 선은 이 규칙과 상관없이 늘 그린다. 여기는 알약(「Recruitment 14건」)만 고른다.
 *
 * **확대하면 알약은 그림만큼 커지지 않는다** (`labelScale`). 판이 통째로 커지면 알약도 같이
 * 커져 겹침이 그대로라, 확대해서 다 보이게 한다는 말이 안 선다. 알약은 화면에서 설계 크기
 * (13px 글자)까지만 커지고 그다음은 제 크기로 남아, 그림이 커지는 만큼 사이가 벌어진다.
 * 작은 창(1366 급)에서는 100% 의 글자가 설계보다 작아서 먼저 설계 크기까지 키운다 — 확대해도
 * 글자가 그대로면 읽으려고 확대한 사람이 못 읽는다. 줄일 때는 그림과 같이 줄인다.
 *
 * **겹치면 뺀다.** 강조 · 고른 선 → 1단계 선 → 바깥 선 차례로, 같은 무리 안에서는 건수가 큰
 * 것부터 놓는다. 1단계를 먼저 놓는 것은 확대했을 때 100% 에서 보이던 1단계 라벨이 바깥 선
 * 라벨에 밀려 사라지지 않게 하려는 것이다. 자리마다 선을 따라 앞뒤로 옮긴 후보(`spots`)가 있어
 * 첫 자리가 막히면 다음 자리를 본다. 노드 이름 · 육각형(`nodeBoxes`)도 피한다. 끝까지 못 피하면
 * 뺀다 — 다만 강조 · 고른 선은 늘 달고, 1단계 건수 상위(주요 관계)는 줄였을 때(100% 미만)만
 * 이름에 걸쳐도 단다. 줄였을 때도 주요 관계는 글자가 있어야 한다.
 */

export type Pt = { x: number; y: number };

/** 왼쪽 위 기준 사각형 (viewBox 단위) */
export type Rect = { x: number; y: number; w: number; h: number };

export type LabelCand = {
  /** 관계 id */
  id: string;
  /** 건수 n(R) */
  count: number;
  /** 2단계 바깥 선 — 중심에 닿지 않은 선 */
  outer: boolean;
  /** 강조 · 고른 선. 배율 · 겹침과 상관없이 단다 */
  force: boolean;
  /** 100% 에서의 알약 크기 (viewBox 단위) */
  w: number;
  h: number;
  /** 앉힐 자리 후보 (알약 가운데). 첫째가 기본 자리다 */
  spots: Pt[];
};

/** 줄였을 때 라벨을 다는 1단계 선 수 */
export const LABEL_TOP = 4;

/** 알약 둘레 틈. 양쪽이 더해져 알약 사이는 이것의 두 배가 벌어진다 */
export const LABEL_GAP = 3;

/** 이 배율 이상이면 2단계 바깥 선 라벨도 단다 */
export const OUTER_ZOOM = 125;

/**
 * 이름 · 육각형 자리는 글자 폭 어림이라 가장자리에 이만큼 걸치는 것은 봐준다 (viewBox 단위).
 * 안 봐주면 1단계 5곳 배치에서 왼쪽 선의 긴 라벨(「Infrastructure」)이 이웃 이름 끝에 몇 단위
 * 걸쳐 100% 에서 빠졌다 — 전에는 달려 있던 라벨이다
 */
export const NAME_SLACK = 3;

/** 글자 폭 어림 (viewBox 단위). 한글은 1em, 나머지는 0.6em */
export function textWidth(s: string, fontSize: number): number {
  let w = 0;
  for (const ch of s) w += /[가-힣ㄱ-ㆎ]/.test(ch) ? 1 : 0.6;
  return w * fontSize;
}

/**
 * 알약 크기 배수 (viewBox 단위, 100% 알약 대비).
 *
 * `fit` 은 판이 viewBox 를 몇 배로 그리나다 (판 px ÷ viewBox, 가운데 맞춤). 100% 에서 알약
 * 글자는 화면에서 13 × `fit` px 이다. 확대하면 화면 크기가 13px(설계 크기)에 닿을 때까지는
 * 그림과 같이 키우고(배수 1), 그다음은 그 크기를 지키도록 줄인다. 100% 에서 이미 13px 를
 * 넘는 큰 판은 100% 크기를 지킨다. 100% 이하에서는 1 — 판과 같이 줄어든다
 */
export function labelScale(zoom: number, fit = 1): number {
  const s = zoom / 100;
  if (s <= 1) return 1;
  const f = fit > 0 ? fit : 1;
  const screen = Math.max(f, Math.min(1, f * s));
  return screen / (f * s);
}

/** 노드 이름을 붙인 모양 — `RelationTab` 이 노드를 그리는 자리와 같다 */
export type NameSpot = {
  x: number;
  y: number;
  r: number;
  /** 이름을 붙인 쪽 */
  side: "below" | "left" | "right";
  /** 2단계 바깥 고리 — 이름 한 줄만 작게 */
  outer: boolean;
  /** 중심 노드 — 이름 글자가 크다 */
  center: boolean;
  name: string;
  /** 둘째 글. 아래에 붙이면 「섬 · 활동도 N」 둘째 줄, 옆에 붙이면 이름 뒤 「활동도 N」 */
  sub: string;
};

/**
 * 노드 육각형과 이름 글자 자리 — 라벨이 피할 곳 (viewBox 단위, 배율과 상관없이 그대로).
 * 글줄마다 따로 잡는다 — 이름 줄과 둘째 줄을 한 상자로 묶으면 좁은 이름 옆 빈자리까지 막혀
 * 라벨이 괜히 빠진다. 육각형은 꼭짓점을 빼고 안쪽만 잡는다 — 모서리 끝에 조금 걸치는
 * 것까지 빼면 짧은 선의 라벨이 거의 다 빠진다
 */
export function nodeBoxes(n: NameSpot): Rect[] {
  const h = n.r * 0.75;
  const hex = { x: n.x - h, y: n.y - h, w: 2 * h, h: 2 * h };
  // 글자 한 줄 — 가운데 x, 글자 밑줄 y, 크기. 굵은 글자는 조금 넓게 본다
  const line = (cx: number, base: number, fs: number, w: number): Rect => ({
    x: cx - w / 2,
    y: base - fs * 0.8,
    w,
    h: fs * 1.05,
  });
  if (n.side === "below" && n.outer) {
    return [hex, line(n.x, n.y + n.r + 16, 12, textWidth(n.name, 12) * 1.05)];
  }
  if (n.side === "below") {
    const fs = n.center ? 16 : 14;
    return [
      hex,
      line(n.x, n.y + n.r + 20, fs, textWidth(n.name, fs) * 1.05),
      line(n.x, n.y + n.r + 37, 12, textWidth(n.sub, 12)),
    ];
  }
  const w = textWidth(n.name, 13) * 1.05 + 6 + textWidth(n.sub, 11);
  const x = n.side === "left" ? n.x - n.r - 10 - w : n.x + n.r + 10;
  return [hex, { x, y: n.y + 4 - 13 * 0.8, w, h: 13 * 1.05 }];
}

/** 1단계 선을 건수 큰 순으로 세운 앞 `top` 개 id. 건수가 같으면 들어온 차례 */
export function topInner(cands: readonly LabelCand[], top = LABEL_TOP): Set<string> {
  const inner = cands
    .map((c, i) => ({ c, i }))
    .filter(({ c }) => !c.outer)
    .sort((a, b) => b.c.count - a.c.count || a.i - b.i);
  return new Set(inner.slice(0, top).map(({ c }) => c.id));
}

/** 이 배율에서 라벨을 달 후보. 겹침은 아직 안 본다 */
export function wantedLabels(cands: readonly LabelCand[], zoom: number, top = LABEL_TOP): Set<string> {
  const major = topInner(cands, top);
  const out = new Set<string>();
  for (const c of cands) {
    const want = c.force || (zoom < 100 ? !c.outer && major.has(c.id) : zoom < OUTER_ZOOM ? !c.outer : true);
    if (want) out.add(c.id);
  }
  return out;
}

function hits(a: Rect, b: Rect): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

/**
 * 라벨 자리 정하기. 단 라벨의 id → 알약 가운데 자리. 없는 id 는 안 단다.
 * `obstacles` 는 노드 이름 · 육각형 자리(`nodeBoxes`), `fit` 은 `labelScale` 과 같다
 */
export function placeLabels(
  cands: readonly LabelCand[],
  zoom: number,
  obstacles: readonly Rect[],
  { fit = 1, top = LABEL_TOP }: { fit?: number; top?: number } = {},
): Map<string, Pt> {
  const want = wantedLabels(cands, zoom, top);
  const major = topInner(cands, top);
  const k = labelScale(zoom, fit);
  const m = LABEL_GAP * k;
  const order = cands
    .map((c, i) => ({ c, i }))
    .filter(({ c }) => want.has(c.id) && c.spots.length > 0)
    .sort(
      (a, b) =>
        Number(b.c.force) - Number(a.c.force) ||
        Number(a.c.outer) - Number(b.c.outer) ||
        b.c.count - a.c.count ||
        a.i - b.i,
    );

  const placed: Rect[] = [];
  const out = new Map<string, Pt>();
  for (const { c } of order) {
    const box = (s: Pt): Rect => ({
      x: s.x - (c.w * k) / 2 - m,
      y: s.y - (c.h * k) / 2 - m,
      w: c.w * k + 2 * m,
      h: c.h * k + 2 * m,
    });
    const clearOfLabels = (s: Pt) => !placed.some((r) => hits(box(s), r));
    // 이름과는 틈 없이 알약 자체만 보고, 이름 자리도 `NAME_SLACK` 만큼 안으로 줄여 본다
    const clearOfNames = (s: Pt) => {
      const b = box(s);
      const pill = { x: b.x + m + NAME_SLACK, y: b.y + m + NAME_SLACK, w: b.w - 2 * (m + NAME_SLACK), h: b.h - 2 * (m + NAME_SLACK) };
      return !obstacles.some((r) => hits(pill, r));
    };
    let at = c.spots.find((s) => clearOfLabels(s) && clearOfNames(s));
    // 못 피했을 때 — 강조 · 고른 선은 기본 자리에 그대로. 주요 관계는 **줄였을 때만** 이름에 걸쳐도
    // 라벨끼리만 피해 단다. 100% 이상에서 걸치게 두면 2단계에서 라벨이 노드 이름 · 부제를 덮었다
    // (2026-09-28 최현서 5번이 짚은 바로 그것) — 확대하면 사이가 벌어져 다시 보인다
    if (!at && c.force) at = c.spots[0];
    if (!at && zoom < 100 && major.has(c.id)) at = c.spots.find(clearOfLabels);
    if (!at) continue;
    placed.push(box(at));
    out.set(c.id, at);
  }
  return out;
}

/** 판이 viewBox 를 몇 배로 그리나 (가운데 맞춤). 판 크기를 모르면 1 */
export function boardFit(board: { w: number; h: number } | null, vb: { w: number; h: number }): number {
  if (!board || board.w <= 0 || board.h <= 0) return 1;
  return Math.min(board.w / vb.w, board.h / vb.h);
}

/**
 * 범례 상자를 피해 그래프를 오른쪽으로 밀 거리 (viewBox 단위).
 *
 * 판(`board`, px)에 viewBox(`vb`)가 가운데 맞춤(meet)으로 앉는다고 보고, 왼쪽 `cover` px 를
 * 덮는 범례 밑으로 들어간 만큼 민다. 오른쪽 끝(`span.max`)이 viewBox 밖으로 나가지 않을
 * 만큼까지만 민다 — 2단계처럼 넓은 그래프는 덜 밀린다. 판 크기를 모르면 안 민다
 */
export function legendShift(
  board: { w: number; h: number } | null,
  cover: number,
  span: { min: number; max: number },
  vb: { w: number; h: number },
): number {
  if (!board || board.w <= 0 || board.h <= 0) return 0;
  const f = boardFit(board, vb);
  const off = (board.w - vb.w * f) / 2;
  const covered = (cover - off) / f;
  return Math.max(0, Math.min(covered - span.min, vb.w - span.max));
}

/**
 * 범례를 피하는 그래프 옮기기 — 밀기만으로 모자라면 줄이기까지 (G-10 남은 결함, 2026-09-29).
 *
 * `legendShift` 는 오른쪽 끝이 viewBox 밖으로 나가지 않을 만큼만 밀어서, 섬 간 보기 · 2단계처럼 넓은
 * 그래프는 1280 창에서 왼쪽 노드가 범례 밑에 남았다. 밀기로 다 비킬 수 있으면 그대로 밀고(`s` 1),
 * 모자라면 그래프 폭을 범례 오른쪽 ~ viewBox 오른쪽 끝에 맞게 줄인다. 줄일 때는 세로 가운데를 지켜
 * 위아래로 쏠리지 않게 한다. 너무 작아지지 않게 0.6 배에서 멈춘다. 그리기는
 * `translate(dx dy) scale(s)` 다
 */
export function legendFit(
  board: { w: number; h: number } | null,
  cover: number,
  span: { min: number; max: number },
  vb: { w: number; h: number },
): { dx: number; dy: number; s: number } {
  const shift = legendShift(board, cover, span, vb);
  if (!board || board.w <= 0 || board.h <= 0) return { dx: shift, dy: 0, s: 1 };
  const f = boardFit(board, vb);
  const off = (board.w - vb.w * f) / 2;
  const covered = (cover - off) / f;
  if (span.min + shift >= covered || span.max <= span.min) return { dx: shift, dy: 0, s: 1 };
  const s = Math.max(0.6, Math.min(1, (vb.w - covered) / (span.max - span.min)));
  return { dx: covered - s * span.min, dy: ((1 - s) * vb.h) / 2, s };
}
