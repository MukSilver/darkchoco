/**
 * 육각 지도 SVG.
 *
 * **칸을 하나씩 그리지 않고 영토 단위로 묶어 그린다.** 400칸을 각각 `<polygon>`
 * 으로 두면 노드가 400개가 되고, 호버·선택 때마다 전부 다시 칠해진다. 영토
 * 하나가 `<path>` 하나(그 영토 칸을 다 담은 단일 경로)라 노드가 열 몇 개로 준다.
 *
 * 칸 사이 경계선은 그 경로 안에 육각 테두리를 같이 그려 낸다 — 채움과 테두리를
 * 한 경로에 담으면 칸 경계가 안 보이므로, 채움용 경로와 격자용 경로를 나눈다.
 */

import { useLayoutEffect, useRef, useState } from "react";
import { cellToXY, hexPoints } from "@/lib/hex";
import type { MapLayout, TerritoryShape } from "@/lib/layout";
import { labelT, NAME_FS, NAME_H, NAME_TOP, nameW, pickLabels } from "@/lib/mapui";
import { boxOrigin, boxUnder, flipFrom, flipTo, growFrom, islandBoxes, parseMs, type IslandBox } from "@/lib/motion";
import { CONF_DASH, KIND_NAME, type RelView } from "@/lib/relations";

/** 섬이 옮겨 가는 이징. 토큰 `--ease-out` 과 같은 곡선이다 */
const EASE = "cubic-bezier(0.2, 0, 0, 1)";

/**
 * 관계선 번짐 — 섬이 60% 옮겨 온 뒤에 나온다(이징 뒤 진행도라 곧 섬이 옮겨 온 몫이다). 선은 처음부터
 * 새 자리라 먼저 보이면 선 끝이 허공에 떴다. 80% 로 두면 4× 재생(250ms)에서 거의 안 보여 60% 로 낮췄다
 * (2026-09-29 검토)
 */
const FADE: Keyframe[] = [{ opacity: 0 }, { opacity: 0, offset: 0.6 }, { opacity: 1 }];

/** 요소에 지금 걸린 CSS 행렬. 없으면 null */
function matrixOf(el: Element): DOMMatrixReadOnly | null {
  const t = getComputedStyle(el).transform;
  return t && t !== "none" ? new DOMMatrixReadOnly(t) : null;
}

/** 칸 하나의 육각 경로 */
function hexPath(col: number, row: number, size: number): string {
  const c = cellToXY(col, row, size);
  const pts = hexPoints(c.x, c.y, size);
  return `M${pts.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join("L")}Z`;
}

/** 영토가 가진 칸을 다 담은 하나의 경로 */
function cellsPath(t: TerritoryShape, size: number): string {
  return t.cells.map(([c, r]) => hexPath(c, r, size)).join("");
}

/**
 * 떠오른 영토의 입체 (설계서 4.2.3 「영토가 떠오르고」, 피그마 ⑦-11b · ⑦-3).
 *
 * 윗면을 `LIFT` 만큼 올리고, 같은 칸을 `DEPTH` 만큼 내려 옆면 색으로 먼저 깐다.
 * 둘 사이로 옆면이 드러난다. 피그마 ⑦-11b 에서 옆면 두께가 칸 반지름의 절반쯤
 * (Qilin 칸 반지름 21px 에 옆면 11~13px)이라 합을 5 로 둔다 — viewBox 칸 반지름이
 * 10 이다 (`layout.ts` HEX). 윗면만 올리면 옆면이 얇아 입체로 안 읽히고, 옆면만
 * 내리면 아래 칸을 너무 덮는다
 */
const LIFT = 2;
const DEPTH = 3;

/**
 * 알약 폭을 재려고 글자 너비를 어림한다.
 *
 * SVG 는 글자가 그려지기 전에는 실제 폭을 모른다. 한글은 글꼴 크기만큼 넓고
 * 라틴 글자는 그 60% 쯤이라 글자 수로만 세면 「랜섬웨어 공지 채널」 같은
 * 이름이 알약 밖으로 나간다. 두 가지를 따로 센다.
 */
function textWidth(s: string, fontSize: number): number {
  let w = 0;
  for (const ch of s) w += /[가-힣ㄱ-ㆎ]/.test(ch) ? 1 : 0.58;
  return w * fontSize;
}


export type HexMapProps = {
  layout: MapLayout;
  /**
   * 그릴 틀. 없으면 `layout.viewBox`(그 분기에 그려진 칸에 맞춘 틀). 지도 탭 · 타임라인은
   * 모든 분기를 합친 크기 틀(`centerBox`)을 넘겨 분기마다 축척이 같다 (G-10 묶음 4)
   */
  viewBox?: string;
  /** 고른 영토. 있으면 그 영토만 진하고 나머지는 흐리다 (설계서 4.2.3) */
  selectedTerritory?: string;
  /** 고른 섬. 그 섬 전체가 진하다 */
  selectedIsland?: string;
  /** 마우스를 올린 영토. 진하게 칠한다 (설계서 4.2.3 「영토 진하게」) */
  hovered?: string | null;
  onHoverTerritory?: (id: string | null) => void;
  /**
   * 진하게 남길 영토. 영토를 고르면 그 영토와 관계로 이어진 영토다
   * (설계서 4.2.3 「연결된 영토만 표시 중」). 없으면 위 두 값으로 가른다.
   * **이 영토들은 떠오른다** — 피그마 ⑦-11b · ⑦-3 에서 고른 영토와 이어진 영토가
   * 같이 입체로 떠 있다
   */
  lit?: ReadonlySet<string>;
  /** 떠오르게 할 영토. [연결] 행을 고르면 상대 영토도 뜬다 (4.3.3) */
  raised?: ReadonlySet<string>;
  /** 이어진 섬. 여기 없는 섬은 이름표와 번짐을 흐리게 한다 (4.2.3 「연결 없는 섬은 흐리게」) */
  litIslands?: ReadonlySet<string>;
  /**
   * 지금 배율(%). 관계선 라벨과 이어진 영토 이름표를 몇 개까지 달지 정한다 — 줄이면 주요
   * 관계만, 키우면 모두 (2026-09-28 최현서 5번 · 코드 분석, 관계도와 같은 규칙). 없으면 100
   */
  zoom?: number;
  /** 그릴 관계선. 영토를 골랐을 때만 온다 */
  lines?: readonly RelView[];
  /** 섬마다 이름표를 다는 영토 수. 없으면 `NAME_TOP`(열) — 타임라인 블록은 둘 (`MapCanvas`) */
  nameTop?: number;
};

/**
 * 관계선 곡선. 두 영토 이름표 자리를 잇고 가운데를 옆으로 민다.
 *
 * 같은 두 영토 사이에 관계가 여럿이면(종류가 다르면 관계도 다르다) `k` 번째
 * 선을 조금씩 더 밀어 겹치지 않게 한다. 라벨은 곡선의 한가운데(t = 0.5)에 앉는다.
 */
function curve(
  a: { x: number; y: number },
  b: { x: number; y: number },
  k: number,
): { d: string; mid: { x: number; y: number } } {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const bend = len * 0.12 + k * 22;
  const cx = mx - (dy / len) * bend;
  const cy = my + (dx / len) * bend;
  const lt = labelT(k);
  return {
    d: `M${a.x.toFixed(1)},${a.y.toFixed(1)}Q${cx.toFixed(1)},${cy.toFixed(1)} ${b.x.toFixed(1)},${b.y.toFixed(1)}`,
    mid: {
      x: (1 - lt) ** 2 * a.x + 2 * lt * (1 - lt) * cx + lt ** 2 * b.x,
      y: (1 - lt) ** 2 * a.y + 2 * lt * (1 - lt) * cy + lt ** 2 * b.y,
    },
  };
}

/** 관계선 라벨 알약 폭 (viewBox 단위). 겹침 판정과 그리기가 같이 쓴다 */
/**
 * 관계선 알약 글자 크기 (viewBox 단위, 칸 반지름 10). 종류 11 · 건수 10 · 높이 22 — 전에는 8 · 7 · 16 이라 100%
 * 에서도 글자가 안 읽혔다 (2026-09-29 최현서 v2 5번). 확대하면 화면에서 100% 때 크기를 지킨다(`ls`)
 */
const PILL_NAME = 11;
const PILL_COUNT = 10;
const PILL_H = 22;

function lineLabelW(v: RelView): number {
  return textWidth(KIND_NAME[v.rel.kind], PILL_NAME) + textWidth(`${v.count}건`, PILL_COUNT) + 24;
}

/**
 * 지도 위 선의 점선 간격. 범례(`CONF_DASH`)는 화면 픽셀 기준인데 지도는
 * viewBox 단위라(칸 반지름 10) 그대로 쓰면 점이 너무 굵다. 줄여서 쓴다
 */
function mapDash(dash: string): string | undefined {
  if (!dash) return undefined;
  return dash
    .split(" ")
    .map((n) => String(Number(n) * 0.6))
    .join(" ");
}

/**
 * **고르는 일은 여기서 안 한다.** 각 도형에 `data-pick` 과 `data-id` 만 달고
 * `MapCanvas` 가 `pointerup` 한 곳에서 판정한다. 캔버스가 드래그 때문에
 * 포인터를 캡처하는데, 캡처 중에는 `click` 이 캡처한 쪽으로 가 버려서
 * 도형에 건 `onClick` 이 안 불린다.
 */
export default function HexMap({
  layout,
  viewBox,
  selectedTerritory,
  selectedIsland,
  hovered,
  onHoverTerritory,
  lit,
  raised,
  litIslands,
  lines = [],
  zoom = 100,
  nameTop = NAME_TOP,
}: HexMapProps) {
  const hasSelection = Boolean(selectedTerritory || selectedIsland);
  /**
   * 누를 수 있는 지도인가. 고르기는 `MapCanvas` 가 받으므로 마우스 올림을 받는 쪽(=캔버스 안)만
   * 손가락 커서를 준다 — 전에는 타임라인 지도처럼 눌러도 아무 일이 없는 자리도 손가락이었다
   */
  const interactive = Boolean(onHoverTerritory);
  const pointer = interactive ? "cursor-pointer" : "";
  // 마우스를 올린 섬 이름표. 테두리를 섬 색으로 바꾼다 (2026-09-28 코드 분석 — hover 가 없었다)
  const [hoverIsland, setHoverIsland] = useState<string | null>(null);
  // 키보드로 초점이 온 평지 영토 (`keyProps`)
  const [focusFlat, setFocusFlat] = useState<string | null>(null);

  /*
   * 시점을 옮길 때 섬이 옮겨 간다 (2026-09-28 최현서 7번 — 「지구본에서 대륙이 이동하는 것처럼」,
   * `lib/motion.ts`). 판(layout)이 바뀌면 섬마다 새 모양을 앞 분기 자리 · 크기에 놓고 시작해
   * `--dur-slow` 동안 제자리로 돌아온다. 새로 생긴 섬은 번져 나오고, 관계선은 다시 번져 나온다.
   * 움직임 줄이기를 켠 사람은 `--dur-slow` 가 0 이라 안 움직인다. 웹 애니메이션 API 를 써서
   * 다시 그리지 않는다 — 판이 바뀐 직후 한 번만 돈다
   */
  const frame = viewBox ?? layout.viewBox;
  const svgRef = useRef<SVGSVGElement>(null);
  const prevFrame = useRef<{ boxes: Map<string, IslandBox>; origin: { x: number; y: number } } | null>(null);
  // 지금 도는 움직임 — 섬마다 [첫 모양, 도착 모양]. 도중에 새로 붙는 섬 요소를 같은 움직임에 태운다
  const motion = useRef<{ start: number; ms: number; frames: Map<string, [string, string]> } | null>(null);
  useLayoutEffect(() => {
    const svg = svgRef.current;
    const now = { boxes: islandBoxes(layout), origin: boxOrigin(frame) };
    const before = prevFrame.current;
    prevFrame.current = now;
    if (!svg || !before || typeof svg.animate !== "function") return;
    const ms = parseMs(getComputedStyle(svg).getPropertyValue("--dur-slow"));
    if (ms <= 0) return;
    const opts: KeyframeAnimationOptions = { duration: ms, easing: EASE };
    const frames = new Map<string, [string, string]>();
    for (const [key, box] of now.boxes) {
      const els = [...svg.querySelectorAll<SVGElement>(`[data-island="${CSS.escape(key)}"]`)];
      const old = before.boxes.get(key);
      // 앞 움직임이 아직 돌고 있으면 지금 그려진 자리에서 이어 간다 (`boxUnder`)
      const moving = els.find((el) => el.getAnimations().length > 0);
      const m = moving ? matrixOf(moving) : null;
      const was = old && m ? boxUnder(m, old) : old;
      const from = was ? flipFrom(was, box, before.origin, now.origin) : growFrom(box);
      const to = flipTo(box);
      frames.set(key, [from, to]);
      for (const el of els) {
        // 새 섬은 투명에서, 번지다 끊긴 섬은 지금 진하기에서 제 진하기로 간다. 번짐 경로처럼 제
        // opacity 가 있는 도형을 1 까지 올렸다 뚝 떨어뜨리지 않는다 (2026-09-29 묶음 6 검토)
        const cur = getComputedStyle(el).opacity;
        el.getAnimations().forEach((a) => a.cancel());
        const base = getComputedStyle(el).opacity;
        const o0 = was ? cur : "0";
        el.animate(
          o0 === base
            ? [{ transform: from }, { transform: to }]
            : [
                { transform: from, opacity: o0 },
                { transform: to, opacity: base },
              ],
          opts,
        );
      }
    }
    motion.current = { start: performance.now(), ms, frames };
    // 관계선은 섬이 옮겨 온 뒤에 번져 나온다(`FADE`). 앞 번짐은 끊는다 (2026-09-29 묶음 6 검토)
    svg.querySelectorAll<SVGElement>('[data-flip="fade"]').forEach((el) => {
      // 앞 번짐이 도는 중(빠른 재생)이면 0 으로 되돌리지 않고 지금 진하기에서 이어 간다 — 4× 재생(250ms)
      // 에서는 다 번지기 전에 다음 분기가 와 선이 옅게 깜박였다 (G-10 남은 결함)
      const running = el.getAnimations().length > 0;
      const cur = getComputedStyle(el).opacity;
      el.getAnimations().forEach((a) => a.cancel());
      el.animate(running ? [{ opacity: cur }, { opacity: 1 }] : FADE, opts);
    });
  }, [layout, frame]);

  // 움직이는 도중에 새로 붙은 섬 요소(마우스 올림 덮개, 고를 때 떠오른 겹, 새 이름표)도 같은 움직임에
  // 같은 진행 시각으로 태운다. 안 그러면 섬이 옮겨 오는 동안 그것만 도착 자리에 먼저 그려졌다
  // (2026-09-29 묶음 6 검토). 그릴 때마다 돌지만 움직임이 끝났으면 바로 나간다
  useLayoutEffect(() => {
    const svg = svgRef.current;
    const m = motion.current;
    if (!svg || !m) return;
    const t = performance.now() - m.start;
    if (t >= m.ms) {
      motion.current = null;
      return;
    }
    svg.querySelectorAll<SVGElement>("[data-island]").forEach((el) => {
      const f = m.frames.get(el.getAttribute("data-island") ?? "");
      if (!f || el.getAnimations().length > 0) return;
      const a = el.animate([{ transform: f[0] }, { transform: f[1] }], { duration: m.ms, easing: EASE });
      a.currentTime = t;
    });
    // 도중에 처음 영토를 골라 새로 붙은 관계선 묶음도 같은 번짐에 태운다 — 안 그러면 바로 진하게 나와
    // 선 끝이 옮겨 오는 섬과 떨어져 보였다
    svg.querySelectorAll<SVGElement>('[data-flip="fade"]').forEach((el) => {
      if (el.getAnimations().length > 0) return;
      const a = el.animate(FADE, { duration: m.ms, easing: EASE });
      a.currentTime = t;
    });
  });

  /** 떠오르는가 — 고른 영토, 이어진 영토, [연결] 행의 상대 영토 */
  const isUp = (t: TerritoryShape) =>
    t.territoryId === selectedTerritory ||
    Boolean(lit?.has(t.territoryId)) ||
    Boolean(raised?.has(t.territoryId));
  const flat = layout.territories.filter((t) => !isUp(t));
  // 고른 영토를 맨 뒤에 그린다. 떠오른 이웃과 맞닿은 테두리가 고른 쪽 색으로 남는다
  const up = layout.territories
    .filter(isUp)
    .sort(
      (a, b) =>
        Number(a.territoryId === selectedTerritory) -
        Number(b.territoryId === selectedTerritory),
    );
  const hoveredFlat = flat.find((t) => t.territoryId === hovered);
  // Tab 멈춤은 지도 하나에 하나 — 고른 영토, 없으면 첫 영토. 나머지 영토 · 섬 이름표는 화살표로 옮긴다
  // (`MapCanvas`). 전에는 도형 186개가 다 Tab 차례라 줌 단추 · 스냅샷 바에 닿기 어려웠다 (2026-09-29 검토)
  const entryId =
    up.find((t) => t.territoryId === selectedTerritory)?.territoryId ?? flat[0]?.territoryId ?? up[0]?.territoryId;
  /** 이름표와 관계선 끝 자리. 떠오른 영토는 윗면이 올라간 만큼 같이 올린다 */
  const anchor = (t: TerritoryShape) =>
    isUp(t) ? { x: t.label.x, y: t.label.y - LIFT } : t.label;
  /**
   * 키보드로 고를 수 있게 — Enter · Space 로 고르고 화살표로 옮긴다 (`MapCanvas` 가 받는다, 2026-09-28
   * 코드 분석). `entry` 만 Tab 차례(0)이고 나머지는 −1 이다. 떠오른 영토는 윗면에만 단다(옆면까지 달면
   * 같은 영토에 두 번 멈춘다)
   */
  const keyProps = (name: string, entry = false, id?: string) =>
    interactive
      ? {
          tabIndex: entry ? 0 : -1,
          role: "button" as const,
          "aria-label": name,
          // 키보드로 옮겨 온 평지 영토는 경계선 위에 윤곽을 한 겹 더 긋는다 — 경계선이 초점 윤곽을 덮었다 (검토)
          ...(id
            ? {
                onFocus: (e: { currentTarget: Element }) =>
                  setFocusFlat(e.currentTarget.matches(":focus-visible") ? id : null),
                onBlur: () => setFocusFlat(null),
              }
            : {}),
        }
      : {};
  const hoverProps = (id: string) => ({
    onMouseEnter: () => onHoverTerritory?.(id),
    onMouseLeave: () => onHoverTerritory?.(null),
  });

  /** 고른 것이 있으면 나머지는 흐리다. 없으면 다 같은 진하기다 */
  const dim = (t: TerritoryShape) => {
    if (lit) return !lit.has(t.territoryId);
    if (!hasSelection) return false;
    if (selectedTerritory) return t.territoryId !== selectedTerritory;
    return t.islandKey !== selectedIsland;
  };
  const dimIsland = (key: string) => (litIslands ? !litIslands.has(key) : false);

  const byId = new Map(layout.territories.map((t) => [t.territoryId, t]));
  const pairSeen = new Map<string, number>();
  const drawn = lines.flatMap((v) => {
    const a = byId.get(v.rel.from);
    const b = byId.get(v.rel.to);
    if (!a || !b) return [];
    const key = [v.rel.from, v.rel.to].sort().join("|");
    const k = pairSeen.get(key) ?? 0;
    pairSeen.set(key, k + 1);
    return [{ v, ...curve(anchor(a), anchor(b), k) }];
  });

  /*
   * 라벨을 달 선. **건수가 큰 것부터 배율에 맞는 개수까지만 단다** — 전에는 관계가 많은 영토를
   * 고르면 알약과 이름표가 개수 제한 없이 붙어 겹쳤다 (2026-09-28 코드 분석). 100% 미만은 4개,
   * 150% 미만은 8개, 그 이상은 전부다. 마우스를 올린 영토에 닿은 선은 늘 단다 — 고른 영토는
   * 빼고. 지도 탭에서는 선이 다 고른 영토에 닿아서, 누른 직후 커서가 그 위에 있으면 개수 제한이
   * 통째로 꺼졌다 (2026-09-29 묶음 5 검토). 알약끼리 겹치면 뒤(건수가 작은) 것을 빼고, 빈 자리를
   * 개수 밖 선으로 채우지 않는다 — 채우면 끝 이름이 개수를 넘어 늘었다 (2026-09-29 묶음 7 검토)
   */
  const cap = zoom < 100 ? 4 : zoom < 150 ? 8 : Infinity;
  // 알약은 확대해도 화면에서 100% 때 크기를 넘지 않는다 — 그림과 같이 커지면 겹침이 그대로라
  // 확대해도 더 보이는 라벨이 없다. 그래서 확대할수록 판 단위로는 작아진다
  const ls = Math.min(1, 100 / zoom);
  const shownLines = new Set<string>();
  const placed: { x0: number; y0: number; x1: number; y1: number }[] = [];
  const byCount = [...drawn].sort((x, y) => y.v.count - x.v.count || x.v.rel.id.localeCompare(y.v.rel.id));
  // 라벨 · 끝 이름을 달 수 있는 선 — 건수 상위 `cap` 개
  const topLines = new Set(byCount.slice(0, cap).map((d) => d.v.rel.id));
  for (const d of byCount) {
    const onHover =
      hovered != null && hovered !== selectedTerritory && (d.v.rel.from === hovered || d.v.rel.to === hovered);
    if (!onHover && !topLines.has(d.v.rel.id)) continue;
    const w = lineLabelW(d.v) * ls;
    const b = { x0: d.mid.x - w / 2, y0: d.mid.y - (PILL_H / 2) * ls, x1: d.mid.x + w / 2, y1: d.mid.y + (PILL_H / 2) * ls };
    if (!onHover && placed.some((o) => o.x0 < b.x1 && b.x0 < o.x1 && o.y0 < b.y1 && b.y0 < o.y1)) continue;
    placed.push(b);
    shownLines.add(d.v.rel.id);
  }

  // 이름표는 섬마다 점수 상위 열 곳까지다(겹치면 뺀다). 관계로 이어진 영토는 그 밖이어도 이름을 단다 — 선 끝에 이름이
  // 없으면 어디로 이어졌는지 모른다 (피그마 ⑦-3). 다만 건수 상위 개수 안 선과 마우스를 올린 영토
  // 선의 끝, 고른 · 떠오른 영토만 단다 (위 개수 규칙과 같이 간다). 알약이 겹쳐 빠진 선도 개수
  // 안이면 끝 이름은 단다 — 전에는 관계가 셋뿐이어도 알약이 겹치면 선 끝이 이름 없이 남았다
  const namedEnds = new Set(
    drawn
      .filter((d) => shownLines.has(d.v.rel.id) || topLines.has(d.v.rel.id))
      .flatMap((d) => [d.v.rel.from, d.v.rel.to]),
  );
  const keepName = (t: TerritoryShape) =>
    t.territoryId === selectedTerritory ||
    t.territoryId === hovered ||
    Boolean(raised?.has(t.territoryId)) ||
    namedEnds.has(t.territoryId) ||
    lines.length === 0;
  // 섬마다 점수 상위 열 곳까지, 겹치지 않는 만큼 (2026-10-01 팀 피드백 2, `mapui.ts` `pickLabels`)
  const picked = pickLabels(layout.territories, ls, nameTop);
  // 고른 영토는 `lit` 이 없어도 이름을 단다 — 타임라인 지도는 `lit` 을 안 넘겨서, 섬의 큰 둘에 못 든
  // 영토를 고르면 떠오르기만 하고 이름이 없었다 (2026-09-29 묶음 5 검토)
  const labelled = [
    ...picked,
    ...layout.territories.filter(
      (t) =>
        (lit?.has(t.territoryId) || t.territoryId === selectedTerritory) && !picked.includes(t) && keepName(t),
    ),
  ];

  return (
    <svg
      ref={svgRef}
      viewBox={frame}
      className="size-full"
      // 누를 수 있는 지도면 안의 영토 · 섬 이름표가 단추라 그림 한 장(img)이 아니다
      role={interactive ? "group" : "img"}
      aria-label="다크웹 섬 지도"
    >
      <defs>
        {/* 섬마다 은은한 번짐. 피그마에서 섬 둘레가 제 색으로 빛난다 */}
        {layout.islands.map((i) => (
          <filter
            key={i.islandKey}
            id={`glow-${i.token}`}
            x="-25%"
            y="-25%"
            width="150%"
            height="150%"
          >
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        ))}
        {/* 떠오른 영토 아래 그림자. 피그마 ⑦-11b 에서 떠오른 덩어리 아래가 어둡다 */}
        <filter id="raise-shadow" x="-10%" y="-10%" width="120%" height="130%">
          <feDropShadow dx={0} dy={2.5} stdDeviation={2} floodOpacity={0.45} />
        </filter>
      </defs>

      {/* 1층 — 번짐. 섬 테두리를 제 색으로 흐리게 한 번 더 그린다 */}
      <g aria-hidden>
        {layout.islands.map((i) => (
          <path
            key={i.islandKey}
            data-island={i.islandKey}
            d={i.outline}
            fill="none"
            stroke={`var(--t-island-${i.token})`}
            strokeWidth={6}
            opacity={dimIsland(i.islandKey) ? 0.08 : 0.28}
            filter={`url(#glow-${i.token})`}
          />
        ))}
      </g>

      {/*
        2층 — 영토 채움. 이것이 지도의 본체다. 떠오른 영토는 3층이 그린다.
        흐린 칸은 섬마다 정해진 흐림색으로 불투명하게 칠한다 (피그마 ⑦-11b · ⑦-3 ·
        ⑦-10b, `tokens.css` 「흐린 칸」). 전에는 섬 색을 25% 로 깔아 바탕이 비쳤다
      */}
      <g>
        {flat.map((t) => (
          <path
            key={t.territoryId}
            data-pick="territory"
            data-id={t.territoryId}
            data-island={t.islandKey}
            d={cellsPath(t, layout.size)}
            fill={dim(t) ? `var(--t-island-${t.token}-dim)` : `var(--t-island-${t.token})`}
            // 같은 영토 안 칸 사이는 옆면 색으로 가늘게 — 떠오른 영토 윗면과 같은 결이다. 행위자 섬은 옅은 회색.
            // 영토 사이는 아래 경계선이 검게 덮는다 (2026-10-02 최현서, `tokens.css` 「영토 안 칸 선과 영토 경계」)
            stroke={dim(t) ? "var(--t-border-hex)" : `var(--t-island-${t.token}-cell)`}
            strokeWidth={1}
            className={`${pointer} transition-colors`}
            {...keyProps(t.name, t.territoryId === entryId, t.territoryId)}
            {...hoverProps(t.territoryId)}
          />
        ))}
        {/*
          영토 경계 — 같은 섬 안의 영토도 가른다. 전에는 섬 칸이 모두 같은 색이라 이름표만 떠 있고 영토마다의
          크기와 시점을 옮길 때의 변화를 알 수 없었다 (2026-09-29 최현서 v2 2번). 검은 칸 선 색으로 영토
          둘레를 굵게 한 번 더 긋고, 영토 안 칸 선은 위에서 옆면 색으로 가늘게 둔다 (2026-10-02 최현서 — 10/01
          의 밝은 경계선은 한 칸짜리 영토가 많아 섬 전체가 밝은 격자로 보였다). 포인터는 안 받는다
        */}
        {flat.map((t) => (
          <path
            key={`edge-${t.territoryId}`}
            aria-hidden
            data-island={t.islandKey}
            d={t.outline}
            fill="none"
            // 영토 사이 선은 칸 선보다 조금 굵고 조금 밝다 — 1.6 굵기 칸 선 색은 두껍고 검게 보였다 (2026-10-02 최현서).
            // 흐린 영토는 흐린 칸 선과 같은 검은 칸 선 색이다 — 전에는 밝은 회색(`--t-border-strong` 70%)이라 영토를 고르면
            // 흐린 칸마다 흰 테두리가 남았다 (2026-10-03 최현서). 섬 색으로 그으면 흐린 칸 둘레에 섬 색이 되살아난다(9/29 검토)
            stroke={dim(t) ? "var(--t-border-hex)" : "var(--t-territory-edge)"}
            strokeWidth={1.2}
            strokeLinejoin="round"
            className="pointer-events-none"
          />
        ))}
        {/*
          마우스를 올린 영토 (설계서 4.2.3 「영토 진하게」, 컴포넌트 시트 `DW/Hex v2`
          Hover — 한 단계 진한 채움에 옆면 색 테두리). 흐려진 영토도 올리면 진하다.

          **제자리 경로의 색을 바꾸지 않고 위에 한 겹 덮는다.** 이웃 영토가 뒤에
          그려져 테두리 반쪽을 덮기 때문이다. 덮는 겹은 포인터를 안 받는다 — 받으면
          올린 순간 아래 경로에서 `mouseleave` 가 나서 호버가 깜박인다
        */}
        {hoveredFlat && (
          <path
            // 영토마다 새 요소 — 같은 요소를 다시 쓰면 다른 섬으로 옮겨 가도 앞 섬의 움직임이 남았다
            key={hoveredFlat.territoryId}
            aria-hidden
            data-island={hoveredFlat.islandKey}
            d={cellsPath(hoveredFlat, layout.size)}
            fill={`var(--t-island-${hoveredFlat.token}-hover)`}
            stroke="var(--t-hex-hover-edge)"
            strokeWidth={1.4}
            className="pointer-events-none"
          />
        )}
        {(() => {
          const f = focusFlat ? flat.find((t) => t.territoryId === focusFlat) : undefined;
          return f ? (
            <path
              key={`focus-${f.territoryId}`}
              aria-hidden
              data-island={f.islandKey}
              d={f.outline}
              fill="none"
              stroke="var(--t-hex-selected-edge)"
              strokeWidth={2.5}
              strokeLinejoin="round"
              className="pointer-events-none"
            />
          ) : null;
        })()}
      </g>

      {/*
        3층 — 떠오른 영토 (설계서 4.2.3 · 4.3.3, 피그마 ⑦-11b · ⑦-3, `DW/Hex v2`
        Selected · Linked). 고른 영토와 이어진 영토, [연결] 행의 상대 영토다.

        **옆면을 다 깐 뒤 윗면을 다 올린다.** 떠오른 영토끼리 맞닿으면 위쪽 영토의
        옆면이 아래쪽 영토 윗면을 덮지 않아야 한다. 고른 영토의 윗면은 마우스를
        올린 것처럼 한 단계 진하다 — 시트에서 Selected 윗면이 Hover 색이다.
        클릭은 두 겹 다 받는다. 옆면도 그 영토로 보이기 때문이다
      */}
      {up.length > 0 && (
        <g>
          <g filter="url(#raise-shadow)">
            {up.map((t) => (
              // 시점을 옮길 때 섬째 움직이는 겹(`data-island`). transform 속성이 있는 도형은 CSS
              // 움직임이 그 속성을 덮으므로 한 겹 감싼다
              <g key={t.territoryId} data-island={t.islandKey}>
                <path
                  data-pick="territory"
                  data-id={t.territoryId}
                  d={cellsPath(t, layout.size)}
                  transform={`translate(0 ${DEPTH})`}
                  fill={`var(--t-island-${t.token}-side)`}
                  stroke={`var(--t-island-${t.token}-side)`}
                  strokeWidth={1}
                  className={pointer}
                  {...hoverProps(t.territoryId)}
                />
              </g>
            ))}
          </g>
          {up.map((t) => (
            <g key={t.territoryId} data-island={t.islandKey}>
            <path
              data-pick="territory"
              data-id={t.territoryId}
              d={cellsPath(t, layout.size)}
              transform={`translate(0 ${-LIFT})`}
              // 마우스를 올리면 밝아지고, 고른 영토는 밝은 윤곽선으로 이어진 영토와 가른다
              // (2026-09-28 최현서 6번 · 코드 분석 — 전에는 고른 것과 이어진 것의 윗면이 거의 같았다)
              fill={t.territoryId === hovered ? `var(--t-island-${t.token}-hover)` : `var(--t-island-${t.token})`}
              stroke={
                t.territoryId === selectedTerritory
                  ? "var(--t-hex-selected-edge)"
                  : t.territoryId === hovered
                    ? "var(--t-hex-hover-edge)"
                    : // 윗면 칸 사이는 고른 것이 없을 때의 영토 안 선과 같은 색 — 행위자 섬만 옆면이 거의 검정이라
                      // 고를 때 검은 선으로 달라 보였다 (2026-10-02 최현서, `tokens.css` `-cell`)
                      `var(--t-island-${t.token}-cell)`
              }
              strokeWidth={t.territoryId === selectedTerritory ? 2 : t.territoryId === hovered ? 1.4 : 1}
              className={pointer}
              {...keyProps(t.name, t.territoryId === entryId)}
              aria-pressed={interactive ? t.territoryId === selectedTerritory : undefined}
              {...hoverProps(t.territoryId)}
            />
            </g>
          ))}
          {/*
            마우스를 올린 떠오른 영토의 밝은 테두리를 맨 위에 한 겹 더 긋는다 — 나중에 그려지는
            떠오른 이웃이 맞닿은 변에서 테두리를 덮었다 (2026-09-28 검토). 평지의 덮는 겹과 같다
          */}
          {up
            .filter((t) => t.territoryId === hovered && t.territoryId !== selectedTerritory)
            .map((t) => (
              <g key={`hover-${t.territoryId}`} data-island={t.islandKey}>
                <path
                  aria-hidden
                  d={cellsPath(t, layout.size)}
                  transform={`translate(0 ${-LIFT})`}
                  fill="none"
                  stroke="var(--t-hex-hover-edge)"
                  strokeWidth={1.4}
                  className="pointer-events-none"
                />
              </g>
            ))}
        </g>
      )}

      {/*
        관계선 층. 영토를 골랐을 때 그 영토의 선만 그린다 (설계서 4.2.3). 피그마
        ⑦-3 처럼 옅은 회색 선에 신뢰도별 모양이고, 라벨은 「종류 건수」 알약이다.
        클릭은 안 받는다 — 선 위를 눌러도 아래 영토가 골라진다
      */}
      {drawn.length > 0 && (
        // 시점을 옮기면 선은 섬을 따라가지 않고 다시 번져 나온다 (`data-flip="fade"`)
        <g aria-hidden className="pointer-events-none" data-flip="fade">
          {drawn.map(({ v, d }) => (
            <path
              key={v.rel.id}
              d={d}
              fill="none"
              stroke="var(--t-text-body)"
              strokeWidth={1.1}
              strokeDasharray={mapDash(CONF_DASH[v.rel.confidence])}
              strokeLinecap="round"
              opacity={0.85}
            />
          ))}
          {drawn.filter(({ v }) => shownLines.has(v.rel.id)).map(({ v, mid }) => {
            const name = KIND_NAME[v.rel.kind];
            const w = lineLabelW(v);
            return (
              <g
                key={`l-${v.rel.id}`}
                transform={`translate(${mid.x} ${mid.y}) scale(${ls}) translate(${-w / 2} ${-PILL_H / 2})`}
              >
                <rect width={w} height={PILL_H} rx={5} fill="var(--t-surface-panel)" stroke="var(--t-border-card)" strokeWidth={0.9} />
                <text x={9} y={15} fontSize={PILL_NAME} fontWeight={600}>
                  <tspan fill="var(--t-text-title)">{name}</tspan>
                  <tspan dx={5} fontSize={PILL_COUNT} fill="var(--t-text-label)">
                    {v.count}건
                  </tspan>
                </text>
              </g>
            );
          })}
        </g>
      )}

      {/* 4층 — 섬 이름표. 덩어리 위에 알약으로 뜬다 */}
      <g>
        {layout.islands.map((i) => {
          const w = textWidth(i.name, 9) + textWidth(`${i.eventCount}건`, 8) + 30;
          return (
            <g key={i.islandKey} data-island={i.islandKey}>
            <g
              data-pick="island"
              data-id={i.islandKey}
              transform={`translate(${i.label.x - w / 2} ${i.label.y - 9})`}
              opacity={dimIsland(i.islandKey) ? 0.4 : 1}
              className={pointer}
              {...keyProps(`${i.name} 섬 · ${i.eventCount}건`)}
              onMouseEnter={interactive ? () => setHoverIsland(i.islandKey) : undefined}
              onMouseLeave={interactive ? () => setHoverIsland(null) : undefined}
            >
              <rect
                width={w}
                height={18}
                rx={9}
                fill={hoverIsland === i.islandKey ? "var(--t-surface-track)" : "var(--t-surface-panel)"}
                stroke={hoverIsland === i.islandKey ? `var(--t-island-${i.token})` : "var(--t-border-card)"}
              />
              <circle cx={11} cy={9} r={3} fill={`var(--t-island-${i.token})`} />
              <text x={19} y={12.5} fontSize={9} fontWeight={600}>
                <tspan fill="var(--t-text-strong)">{i.name}</tspan>
                <tspan dx={5} fontSize={8} fill="var(--t-text-label)">
                  {i.eventCount}건
                </tspan>
              </text>
            </g>
            </g>
          );
        })}
      </g>

      {/*
        5층 — 영토 이름표. 덩어리 안쪽에 알약으로 앉는다.

        **`pointer-events: none` 이 꼭 있어야 한다.** 없으면 이름표가 덮은
        자리에서 클릭이 이름표로 가고, 그 `<g>` 에는 `data-pick` 이 없어서
        「빈 곳을 눌렀다」로 읽혀 선택이 풀린다. 이름표는 보여 주기만 한다
      */}
      <g aria-hidden className="pointer-events-none">
        {labelled
          .filter((t) => !dim(t))
          .map((t) => {
            // 글자 12 · 높이 20 (전에는 8 · 14). 확대하면 화면에서 100% 때 크기를 지킨다(`ls`) — 팀 피드백 2
            const w = nameW(t.name);
            const at = anchor(t);
            return (
              <g key={t.territoryId} data-island={t.islandKey}>
              <g transform={`translate(${at.x} ${at.y}) scale(${ls}) translate(${-w / 2} ${-NAME_H / 2})`}>
                <rect
                  width={w}
                  height={NAME_H}
                  rx={5}
                  fill="var(--t-surface-app)"
                  opacity={0.88}
                />
                <text
                  x={w / 2}
                  y={NAME_H / 2 + NAME_FS * 0.36}
                  fontSize={NAME_FS}
                  fontWeight={600}
                  textAnchor="middle"
                  fill="var(--t-text-title)"
                >
                  {t.name}
                </text>
              </g>
              </g>
            );
          })}
      </g>
    </svg>
  );
}
