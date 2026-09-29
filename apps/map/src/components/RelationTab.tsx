/**
 * 관계 탭 — 설계서 4.3.3 · 4.3.6, 피그마 ⑦-8 · ⑦-8e · ⑦-8g.
 *
 * 한 영토를 가운데 두고 **바로 이어진 영토만** 그린다 (1단계). 노드 집합은
 * 그 영토의 패널 [연결] 탭 행과 같다 — 두 화면이 `relations.ts` 의 같은 목록을 쓴다.
 *
 *   주변 노드 클릭     그 영토가 새 중심
 *   관계선 · 라벨 클릭  그 선을 고른다. 나머지는 흐려지고 근거 팝오버가 뜬다
 *   빈 곳 클릭         선택 해제
 *
 * **강조와 선택은 다르다** (4.3.3 ①). [연결] 행 더블클릭 · 검색 · 섬 간 보기에서
 * 넘어오면 그 관계를 **강조**만 한다 — 선과 라벨 테두리가 진하고 나머지는 흐리며,
 * 패널 관계 연혁에서 그 항목이 강조된다. 근거 팝오버는 안 뜬다. 강조된 선이나
 * 「근거 보기」를 눌러야 **선택**(근거 화면, ⑦-8e)이 된다 (4.3.3 「강조된 관계선이나
 * '근거 보기' 클릭 시 근거 화면」).
 *
 * **섬 간 보기**(4.3.3 ②)도 여기서 그린다. [연결] 탭의 「유형 간 연결」 행을
 * 더블클릭하면 온다. 왼쪽에 출발 섬 영토, 오른쪽에 도착 섬 영토를 세우고 그
 * 섬 쌍의 선만 긋는다. 선을 누르면 보통 관계 탭(①)으로 넘어간다.
 *
 * **「추정 관계 포함」 · 「2단계로 확장」**은 피그마 ⑦-8g 관계 없음 화면의 두 단추다.
 * 관계가 있을 때도 켜고 끌 수 있어야 해서 판 오른쪽 위에도 둔다 — 2단계로 넓힌
 * 뒤에는 관계 없음 화면이 사라져 되돌릴 단추가 없어진다. 그 자리는 피그마 ⑦-8 의
 * 「전체 관계 보기」 스위치 자리인데, 그 스위치는 보류라 비어 있다.
 *
 * 안 만든 것
 *
 *   「전체 관계 보기」 스위치 · 단추   설계서 4.2.7 · 6.3 이 보류로 정했다 (지도 탭과 같다)
 *   로고                            굽기가 로고를 안 싣는다. 노드는 섬 색 육각형이다
 *
 * 근거 사건 없이 명부 「연결된 곳」에서 만든 관계선은 팝오버에 그 칸의 원문을
 * 보인다 (4.3.6). 굽기가 상대 이름이 든 항목만 골라 `note` 로 싣는다.
 *
 * **판은 지도처럼 줌 · 끌기가 된다** (2026-09-28 최현서 5번). 줌 규칙은 지도와 같은
 * `zoom.ts` 다 (50~200%, 25% 단위, 휠은 모아서 한 단계씩). 끌고 놓은 것은 고르기로 치지
 * 않는다. 중심이 바뀌거나 섬 간 보기로 들어가면 처음 값(100%, 가운데)으로 돌아온다.
 * 선은 배율과 상관없이 늘 그리고, 라벨은 배율에 따라 단다 — 규칙은 `relgraph.ts` 머리말.
 */

"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent, type ReactNode } from "react";

import { Chip, KindDot, TeamMark, hexPoints } from "./RelBits";
import { useWheelSteps } from "./useWheelSteps";
import type { MapLayout, TerritoryShape } from "@/lib/layout";
import { islandName } from "@/lib/islands";
import { parseQuarter, type QuarterKey } from "@/lib/quarter";
import {
  CONF_CHIP,
  CONF_DASH,
  CONF_LABEL,
  KIND_LABEL,
  KIND_HELP,
  KIND_NAME,
  KIND_ORDER,
  centerChips,
  expandHops,
  historyText,
  josa,
  pairViews,
  type Hops,
  type RelView,
} from "@/lib/relations";
import {
  boardFit,
  labelScale,
  legendFit,
  nodeBoxes,
  placeLabels,
  textWidth,
  type Pt,
  type Rect,
} from "@/lib/relgraph";
import { ZOOM_MAX, ZOOM_MIN, ZOOM_STEP, clampZoom } from "@/lib/zoom";

export type RelPair = { from: string; to: string };

export type RelationTabProps = {
  layout: MapLayout;
  /** 기준일에 그릴 관계 전부 (`relationsAt`). 「추정 관계 포함」을 끄면 추정을 뺀 목록 */
  views: RelView[];
  center: string | null;
  onCenter: (territoryId: string) => void;
  /** 고른 관계선 id — 근거 화면 (⑦-8e) */
  selected: string | null;
  onSelect: (relationId: string | null) => void;
  /** 강조한 관계선 id — [연결] · 검색 · 섬 간 보기에서 넘어온 관계 (4.3.3 ①) */
  highlight: string | null;
  /** 섬 간 보기 필터. 있으면 섬 간 보기로 그린다 */
  pair: RelPair | null;
  onClearPair: () => void;
  /** 섬 간 보기에서 선을 눌렀을 때 — 보통 관계 탭(①)으로 넘어간다 */
  onPairPick: (v: RelView) => void;
  /**
   * 들어올 때의 출발 화면. `label` 은 돌아가기 단추 글이다 (`backLabel`). 출발에서
   * 영토를 골라 두었으면 `id` 가 그 영토라 칩에 점을 찍는다 (4.3.3 ①)
   */
  origin: { id: string | null; label: string } | null;
  onBack: () => void;
  /** 관계가 없을 때 관계가 처음 생기는 분기. 「기준일 옮기기」 단추에 쓴다 (4.3.3 예외) */
  moveTo: QuarterKey | null;
  onMove: () => void;
  /** 추정 관계 포함 (피그마 ⑦-8g) */
  est: boolean;
  onEst: (on: boolean) => void;
  /** 몇 단계까지 그리나. 2 면 이웃의 이웃까지 (피그마 ⑦-8g 「2단계로 확장」) */
  depth: 1 | 2;
  onDepth: (depth: 1 | 2) => void;
  /** 추정 관계 포함을 꺼서 가린 중심의 관계 수. 관계 없음 안내 문안이 갈린다 */
  hiddenEst: number;
  /** 고른 중심이 이 기준일 지도에 아직 없다 — 노드를 못 그리고 안내만 한다 (v2 9번) */
  centerAbsent?: boolean;
  /** 이 기준일 지도에 없는 영토의 이름 (명부). 칩 · 안내가 id 대신 쓴다 */
  fallbackName?: (id: string) => string;
  /** 지도에 없는 영토의 섬 색 토큰 (명부) — 칩 색이 늘 행위자 회색이었다 (검토) */
  fallbackToken?: (id: string) => string;
  /** 중심이 지도에 없는 까닭 — 「2025 Q2에 운영 종료」 · 「첫 사건이 2026 Q1」 · 「사건이 없어 가장 최근 분기에만 나오는 영토」 */
  absentWhy?: string;
};

/* 그래프 판 크기. viewBox 단위라 화면 크기와 무관하다 */
const W = 1000;
const H = 620;
const CX = W / 2;
const CY = H / 2 - 10;

/** 라벨 알약 높이 (viewBox 단위, 100%) */
const LABEL_H = 26;

/** 범례 상자가 덮는 판 왼쪽 폭 (px) — `left-s4` 16 + 폭 190 + 틈 12 */
const LEGEND_COVER = 218;

/** 줌 · 이동의 처음 값. 이동은 화면 px 다 (지도와 같다) */
const VIEW_HOME = { zoom: 100, x: 0, y: 0 };

function quarterText(q: QuarterKey): string {
  const { year, q: n } = parseQuarter(q);
  return `${year} Q${n}`;
}

type Node = {
  id: string;
  x: number;
  y: number;
  r: number;
  t: TerritoryShape;
  islandName: string;
  actor: boolean;
  /** 이름을 붙일 자리. 섬 간 보기는 세로로 촘촘해서 옆에 붙인다 */
  side: "below" | "left" | "right";
  /** 2단계 바깥 고리. 자리가 좁아 이름만 작게 붙인다 */
  outer: boolean;
};

type Edge = {
  v: RelView;
  d: string;
  /** 라벨 자리 후보. 첫째가 곡선 위 `t` 자리, 나머지는 선을 따라 앞뒤로 옮긴 자리 */
  spots: Pt[];
};

/**
 * 노드 이름 · 육각형 자리 — 라벨이 피할 곳 (`placeLabels`). 둘째 글은 아래 노드 그리기의
 * 글과 같아야 한다 (아래에 붙이면 「섬 · 활동도 N」, 옆에 붙이면 「활동도 N」)
 */
function boxesOf(n: Node, center: boolean): Rect[] {
  const sub = n.side === "below" ? `${n.islandName} · 활동도 ${n.t.metrics.activity}` : `활동도 ${n.t.metrics.activity}`;
  return nodeBoxes({ x: n.x, y: n.y, r: n.r, side: n.side, outer: n.outer, center, name: n.t.name, sub });
}

/** 라벨 알약 폭 (viewBox 단위, 100%) — 「Recruitment 14건」 */
function labelWidth(v: RelView): number {
  return textWidth(KIND_NAME[v.rel.kind], 13) + textWidth(`${v.count}건`, 12) + 34;
}

/**
 * 두 노드 사이 선. 노드 가장자리에서 시작해 화살촉 자리만큼 떨어져 끝난다.
 * 같은 두 노드 사이에 관계가 여럿이면 `bend` 만큼 휘어 겹치지 않게 하고,
 * 라벨도 곡선 위 `t` 자리를 달리해 앉힌다 — 휘기만 하면 라벨 폭이 휜 거리보다
 * 넓어 서로 덮는다.
 */
function edgePath(a: Node, b: Node, bend: number, t = 0.5): { d: string; spots: Pt[] } {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  // 이름을 노드 아래에 단 노드는 아래쪽으로 드나드는 선이 이름을 가로지른다.
  // 그 방향이면 이름 글씨 아래에서 시작하고 끝낸다 (피그마 ⑦-8 의 Qilin · Play 선)
  const startPad = a.r + 6 + (a.side === "below" && uy > 0.55 ? 42 : 0);
  const endPad = b.r + 10 + (b.side === "below" && uy < -0.55 ? 42 : 0);
  const sx = a.x + ux * startPad;
  const sy = a.y + uy * startPad;
  const ex = b.x - ux * endPad;
  const ey = b.y - uy * endPad;
  const mx = (sx + ex) / 2 - uy * bend;
  const my = (sy + ey) / 2 + ux * bend;
  // 조절점은 곡선 가운데가 (mx, my) 를 지나도록 잡는다
  const qx = 2 * mx - (sx + ex) / 2;
  const qy = 2 * my - (sy + ey) / 2;
  const at = (s: number): Pt => {
    const u = 1 - s;
    return { x: u * u * sx + 2 * u * s * qx + s * s * ex, y: u * u * sy + 2 * u * s * qy + s * s * ey };
  };
  // 기본 자리가 이름이나 다른 라벨에 막히면 선을 따라 앞뒤로 옮겨 본다. 양 끝 노드에는
  // 붙지 않게 가운데 쪽으로 가둔다 (2026-09-28 최현서 5번 — 2단계에서 라벨과 이름이 겹쳤다)
  const ts = [t, t + 0.12, t - 0.12, t + 0.24, t - 0.24].map((s) => Math.min(0.85, Math.max(0.15, s)));
  return {
    d: `M${sx.toFixed(1)},${sy.toFixed(1)}Q${qx.toFixed(1)},${qy.toFixed(1)} ${ex.toFixed(1)},${ey.toFixed(1)}`,
    spots: [...new Set(ts)].map(at),
  };
}

function buildEdges(views: RelView[], nodes: Map<string, Node>, tBase = 0.5): Edge[] {
  const groups = new Map<string, RelView[]>();
  for (const v of views) {
    const k = [v.rel.from, v.rel.to].sort().join("|");
    groups.set(k, [...(groups.get(k) ?? []), v]);
  }
  const out: Edge[] = [];
  for (const list of groups.values()) {
    list.forEach((v, j) => {
      const a = nodes.get(v.rel.from);
      const b = nodes.get(v.rel.to);
      if (!a || !b) return;
      // 방향이 반대인 선은 법선이 뒤집히므로 부호를 맞춘다
      const sign = v.rel.from < v.rel.to ? 1 : -1;
      const k = j - (list.length - 1) / 2;
      // 라벨 폭(120 남짓)보다 넓게 벌려야 옆 라벨과 안 겹친다
      const bend = k * 150 * sign;
      // 라벨 자리도 한 줄 방향 기준으로 갈라 둔다 (반대 방향 선은 t 가 거꾸로 간다)
      const t = tBase + k * 0.1 * sign;
      out.push({ v, ...edgePath(a, b, bend, t) });
    });
  }
  return out;
}

/**
 * 켜고 끄는 단추 — 피그마 ⑦-8 오른쪽 위 스위치 모양 (둥근 통 + 손잡이 + 글).
 * 판 위 도구 줄과 관계 없음 안내가 같이 쓴다
 */
function Toggle({
  on,
  onClick,
  disabled,
  title,
  est,
  children,
}: {
  on: boolean;
  onClick: () => void;
  disabled?: boolean;
  title?: string;
  /** 「추정 관계 포함」 스위치 표시. 바뀌어 붙은 뒤 초점을 옮길 자리를 찾는 데 쓴다 */
  est?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      data-est-toggle={est ? "" : undefined}
      type="button"
      role="switch"
      aria-checked={on}
      disabled={disabled}
      title={title}
      onClick={onClick}
      className="flex items-center gap-s2 rounded-[10px] border border-edge bg-panel px-s3 py-s2 text-[12px] text-body hover-edge disabled:cursor-not-allowed disabled:opacity-50"
    >
      {/* 손잡이와 통 색은 번져 옮겨 간다 — 전에는 딱 바뀌었다. 타임라인 「시점 비교」 스위치와 같다 (최현서 1번) */}
      <span
        aria-hidden
        className="relative h-[16px] w-[28px] shrink-0 rounded-full transition-[background-color] duration-[var(--dur-base)] ease-[var(--ease-out)]"
        style={{ background: on ? "var(--t-accent)" : "var(--t-border-strong)" }}
      >
        <span
          className="absolute top-[2px] size-[12px] rounded-full transition-[left] duration-[var(--dur-base)] ease-[var(--ease-out)]"
          style={{ left: on ? 14 : 2, background: "var(--t-text-on-accent)" }}
        />
      </span>
      {children}
    </button>
  );
}

export default function RelationTab(p: RelationTabProps) {
  // 「추정 관계 포함」을 누르면 관계가 비거나 다시 생겨 판 위 스위치와 안내 상자 스위치가 서로
  // 바뀌어 붙는다. 누른 스위치가 사라지면 초점이 문서 맨 앞으로 빠지므로 새 스위치로 옮긴다
  const estFocus = useRef(false);
  const toggleEst = () => {
    estFocus.current = true;
    p.onEst(!p.est);
  };
  useEffect(() => {
    if (!estFocus.current) return;
    estFocus.current = false;
    document.querySelector<HTMLElement>("[data-est-toggle]")?.focus();
  }, [p.est]);
  /*
   * 마우스를 올린 관계선(선 · 라벨이 같은 id)과 노드. 선은 굵고 진해지고, 노드는 테두리가 밝아진다 —
   * 전에는 손가락 커서 말고 아무 표시가 없어 어느 선을 누르게 될지 몰랐다 (2026-09-28 코드 분석,
   * 최현서 1번). 떠날 때는 제 id 일 때만 지운다 — 선에서 라벨로 옮겨 가도 켜진 채 남는다
   */
  const [hoverEdge, setHoverEdge] = useState<string | null>(null);
  const [hoverNode, setHoverNode] = useState<string | null>(null);
  const edgeHover = (id: string) => ({
    onMouseEnter: () => setHoverEdge(id),
    onMouseLeave: () => setHoverEdge((h) => (h === id ? null : h)),
  });

  /*
   * 줌 · 이동 (2026-09-28 최현서 5번 — 「관계도도 확대/축소」). 전에는 viewBox 1000×620 고정이라
   * 2단계에서 라벨과 이름이 겹쳐도 볼 방법이 없었다. 지도처럼 판을 통째로 옮기고 키운다.
   * 중심이 바뀌거나 섬 간 보기로 들어가면 처음 값으로 — 그리는 그래프가 통째로 바뀐다.
   * 효과 대신 그리는 중에 앞 값과 견준다 (효과 안 setState 는 한 번 더 그린다)
   */
  const [view, setView] = useState(VIEW_HOME);
  const viewKey = p.pair ? `pair:${p.pair.from}>${p.pair.to}` : `center:${p.center ?? ""}`;
  const [viewOf, setViewOf] = useState(viewKey);
  if (viewOf !== viewKey) {
    setViewOf(viewKey);
    setView(VIEW_HOME);
  }
  const zoomBy = (by: number) => setView((v) => ({ ...v, zoom: clampZoom(v.zoom + by) }));
  // 휠은 모아서 문턱을 넘을 때 한 단계씩 — 트랙패드 한 번에 끝까지 튀지 않게. 페이지 스크롤은
  // 막는다 (`useWheelSteps`, 지도와 같다)
  const pad = useRef<HTMLDivElement>(null);
  useWheelSteps(
    pad,
    (n) => zoomBy(n * ZOOM_STEP),
    (dir) => (dir > 0 ? view.zoom >= ZOOM_MAX : view.zoom <= ZOOM_MIN),
  );
  // 끌기. 3px 넘게 움직였으면 놓을 때의 클릭을 고르기로 치지 않는다 (지도 `MapCanvas` 와 같다)
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null);
  const moved = useRef(false);
  const [grabbing, setGrabbing] = useState(false);
  const endDrag = () => {
    drag.current = null;
    setGrabbing(false);
  };

  /*
   * 범례 접기. 펼친 범례가 1366 급 창에서 1단계 왼쪽 노드를 덮었다 (2026-09-28 코드 분석).
   * 펼쳐 두면 그래프를 범례 밑에서 비켜 오른쪽으로 민다 — 얼마나 밀지는 판 크기로 정해서
   * (`legendShift`) 판을 재 둔다. 알약 크기(`labelScale`)도 이 크기를 쓴다
   */
  const [legendOpen, setLegendOpen] = useState(true);
  // 범례 「?」 에 마우스를 올리거나 키보드 초점이 왔다 — 관계 종류 설명을 띄운다 (v2 3번)
  const [kindHelp, setKindHelp] = useState(false);
  const boardRef = useRef<HTMLDivElement>(null);
  const [board, setBoard] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    const el = boardRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setBoard({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const byId = useMemo(() => new Map(p.layout.territories.map((t) => [t.territoryId, t])), [p.layout]);
  const islandById = useMemo(() => new Map(p.layout.islands.map((i) => [i.islandKey, i])), [p.layout]);
  const nameOf = (id: string) => byId.get(id)?.name ?? p.fallbackName?.(id) ?? id;
  const islandOf = (id: string) => byId.get(id)?.islandKey;

  const node = (id: string, x: number, y: number, r: number, side: Node["side"] = "below", outer = false): Node | null => {
    const t = byId.get(id);
    if (!t) return null;
    const isl = islandById.get(t.islandKey);
    return { id, x, y, r, t, islandName: isl?.name ?? "", actor: isl?.islandId === "ACTOR", side, outer };
  };

  /* ── 그릴 것 ─────────────────────────────────────────── */

  const graph = useMemo((): { nodes: Map<string, Node>; edges: Edge[]; list: RelView[]; hops: Hops | null } => {
    const nodes = new Map<string, Node>();
    if (p.pair) {
      const list = pairViews(p.views, islandOf, p.pair.from, p.pair.to);
      const left = [...new Set(list.map((v) => v.rel.from))];
      const right = [...new Set(list.map((v) => v.rel.to))];
      // 왼쪽 범례 상자를 피해 가운데로 당겨 세운다. 이름은 바깥쪽에 붙인다
      const place = (ids: string[], x: number, side: Node["side"]) => {
        const r = ids.length > 6 ? 15 : 22;
        ids.forEach((id, i) => {
          const y = ids.length === 1 ? CY : 60 + (i * (H - 120)) / (ids.length - 1);
          const n = node(id, x, y, r, side);
          if (n) nodes.set(id, n);
        });
      };
      place(left, 400, "left");
      place(right, 760, "right");
      // 선이 오른쪽으로 모이므로 라벨은 왼쪽(퍼져 있는 쪽)에 앉힌다
      return { nodes, edges: buildEdges(list, nodes, 0.3), list, hops: null };
    }
    if (!p.center) return { nodes, edges: [], list: [], hops: null };
    // 건수가 큰 상대가 맨 위에 오도록 세운다
    const hops = expandHops(p.views, p.center, p.depth, nameOf);
    const n1 = hops.hop1.length;
    const c = node(p.center, CX, CY, p.depth === 2 ? 30 : 34);
    if (c) nodes.set(p.center, c);

    if (p.depth === 1) {
      const R = n1 <= 4 ? 210 : n1 <= 8 ? 235 : 250;
      const r = n1 <= 8 ? 26 : 20;
      hops.hop1.forEach((id, i) => {
        const a = ((-90 + (i * 360) / n1) * Math.PI) / 180;
        const nd = node(id, CX + R * Math.cos(a), CY + R * Math.sin(a) * 0.86, r);
        if (nd) nodes.set(id, nd);
      });
      return { nodes, edges: buildEdges(hops.views, nodes), list: hops.views, hops };
    }

    // 2단계 — 1단계는 안쪽 고리, 이웃의 이웃은 바깥 고리
    const deg1 = new Map<string, number>();
    hops.hop1.forEach((id, i) => {
      const deg = -90 + (i * 360) / n1;
      deg1.set(id, deg);
      const a = (deg * Math.PI) / 180;
      const nd = node(id, CX + 180 * Math.cos(a), CY + 140 * Math.sin(a), n1 <= 8 ? 22 : 18);
      if (nd) nodes.set(id, nd);
    });
    // 바깥 고리는 이어 준 1단계 영토의 각도 차례로 줄 세우고 고르게 벌린 뒤, 그 자리를
    // 통째로 돌려 저마다 이어 준 영토 쪽에 가깝게 앉힌다 (돌릴 각은 어긋남의 원형 평균)
    const want = hops.hop2
      .map((id) => ({ id, deg: deg1.get(hops.via.get(id) ?? "") ?? -90 }))
      .sort((a, b) => a.deg - b.deg);
    const step = 360 / Math.max(want.length, 1);
    let sx = 0;
    let sy = 0;
    want.forEach((w, i) => {
      const off = ((w.deg - i * step) * Math.PI) / 180;
      sx += Math.cos(off);
      sy += Math.sin(off);
    });
    const shift = want.length ? (Math.atan2(sy, sx) * 180) / Math.PI : -90;
    want.forEach((w, i) => {
      const a = ((shift + i * step) * Math.PI) / 180;
      const nd = node(w.id, CX + 390 * Math.cos(a), CY + 250 * Math.sin(a), 15, "below", true);
      if (nd) nodes.set(w.id, nd);
    });
    return { nodes, edges: buildEdges(hops.views, nodes), list: hops.views, hops };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.views, p.center, p.pair, p.depth, byId, islandById]);

  const sel = graph.edges.find((e) => e.v.rel.id === p.selected)?.v ?? null;
  // 골라 둔 선이 있으면 그쪽이 앞선다. 강조는 들어올 때 한 번 건다
  const hi = sel ? null : (graph.edges.find((e) => e.v.rel.id === p.highlight)?.v ?? null);
  const focus = sel ?? hi;
  const onFocus = (id: string) => focus && (focus.rel.from === id || focus.rel.to === id);
  /** 중심에 닿지 않은 선 — 2단계로 넓혔을 때만 있다 */
  const outerEdge = (v: RelView) => !p.pair && !!p.center && v.rel.from !== p.center && v.rel.to !== p.center;
  const empty = !p.pair && graph.list.length === 0;
  // 섬 간 보기에서 스냅샷 바로 두 섬 사이 관계가 없던 분기로 갔다 — 전에는 안내 없이 판만 비었다
  const pairEmpty = !!p.pair && graph.list.length === 0;
  const centerName = p.center ? nameOf(p.center) : "";
  const rest = graph.hops?.rest ?? 0;

  /* ── 라벨 자리 · 범례 밀기 (2026-09-28 최현서 5번) ───────────── */

  // 판이 viewBox 를 몇 배로 그리나. 알약 크기(`labelScale`)가 화면 글자 크기를 보고 정한다
  const fit = boardFit(board, { w: W, h: H });
  const obstacles = useMemo(
    () => [...graph.nodes.values()].flatMap((n) => boxesOf(n, n.id === p.center && !p.pair)),
    [graph, p.center, p.pair],
  );
  // 단 라벨의 id → 알약 가운데. 없는 선은 라벨 없이 선만 그린다. 늘 다는 선은 위 `focus` 와
  // 같은 규칙(고른 선이 먼저, 없으면 강조한 선)으로 id 에서 바로 고른다
  const labelAt = useMemo(() => {
    const drawn = (id: string | null) => !!id && graph.edges.some((e) => e.v.rel.id === id);
    const focusId = drawn(p.selected) ? p.selected : drawn(p.highlight) ? p.highlight : null;
    return placeLabels(
      graph.edges.map((e) => ({
        id: e.v.rel.id,
        count: e.v.count,
        outer: !p.pair && !!p.center && e.v.rel.from !== p.center && e.v.rel.to !== p.center,
        force: e.v.rel.id === focusId,
        w: labelWidth(e.v),
        h: LABEL_H,
        spots: e.spots,
      })),
      view.zoom,
      obstacles,
      { fit },
    );
  }, [graph, obstacles, view.zoom, fit, p.selected, p.highlight, p.pair, p.center]);
  // 알약은 확대해도 그림만큼 커지지 않는다 — 화면에서 설계 크기에 닿으면 그 크기를 지킨다 (`labelScale`)
  const labelK = labelScale(view.zoom, fit);
  // 범례를 피해 민다. 밀기로 모자라면(섬 간 보기 · 2단계처럼 넓은 그래프) 범례 오른쪽에 맞게 조금 줄인다
  // (`legendFit`) — 전에는 1280 창에서 왼쪽 노드가 범례 밑에 남았다 (G-10 남은 결함)
  const shift = useMemo(() => {
    if (!legendOpen || obstacles.length === 0) return { dx: 0, dy: 0, s: 1 };
    const span = {
      min: Math.min(...obstacles.map((r) => r.x)),
      max: Math.max(...obstacles.map((r) => r.x + r.w)),
    };
    return legendFit(board, LEGEND_COVER, span, { w: W, h: H });
  }, [legendOpen, obstacles, board]);

  // 출발 영토가 지도에 있으면 칩 줄에 둔다 — 점을 찍을 칩이 있어야 한다 (4.3.3 ①)
  const originId = p.origin?.id && byId.has(p.origin.id) ? p.origin.id : null;
  const chips = p.pair ? [] : centerChips(p.views, p.center, nameOf, 6, originId);

  const withName = `${centerName}${josa(centerName, "과", "와")}`;
  const emptyBody = !p.center
    ? "기준일을 옮기면 관계가 보일 수 있습니다."
    : p.centerAbsent
      ? `${centerName}${josa(centerName, "은", "는")} 이 기준일에는 지도에 없습니다${p.absentWhy ? `(${p.absentWhy})` : ""}. ` +
        (p.moveTo ? "기준일을 옮기면 관계가 보입니다." : "위 칩 줄에서 다른 영토를 골라 보세요.")
    : p.hiddenEst > 0
      ? `${withName} 연결된 관계는 추정 관계 ${p.hiddenEst}개뿐입니다. 추정 관계를 포함하면 연결 후보를 확인할 수 있습니다.`
      : `${withName} 연결된 관계가 이 기준일에는 관측되지 않았습니다. ` +
        (p.moveTo ? "기준일을 옮기면 관계가 보일 수 있습니다." : "위 칩 줄에서 다른 영토를 골라 보세요.");

  /* ── 그리기 ─────────────────────────────────────────── */

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-s4">
      {/*
        칩 줄은 한 줄 가로 스크롤 — 전에는 줄바꿈이라 칩 수 · 이름 길이에 따라 한두 줄이 되어 아래 판
        높이와 배율이 바뀌었다 (2026-09-28 코드 분석). 높이를 박아 두어 스크롤 막대가 생겨도 판이
        그대로다. 좌우 여백은 첫 칩의 초점 테두리가 잘리지 않게 둔다
      */}
      <div className="-mx-s1 flex h-[42px] shrink-0 flex-nowrap items-center gap-s3 overflow-x-auto overflow-y-hidden px-s1 [scrollbar-width:thin] [scrollbar-color:var(--t-border-strong)_transparent]">
        {p.origin && (
          // 테두리 단추의 공통 마우스 올림(`hover-edge`) — 전에는 글자색만 한 단계 바뀌었다 (최현서 1번)
          <button
            type="button"
            onClick={p.onBack}
            className="shrink-0 whitespace-nowrap rounded-full border border-edge bg-card px-s3 py-s1 text-[12px] text-body hover-edge"
          >
            ‹ {p.origin.label}
          </button>
        )}
        {p.pair ? (
          <>
            <span className="shrink-0 whitespace-nowrap text-[12px] text-label">섬 간 필터</span>
            <span className="flex shrink-0 items-center gap-s2 whitespace-nowrap rounded-full border border-[var(--t-accent)] bg-accent-subtle px-s4 py-s1 text-[13px] text-title">
              {islandById.get(p.pair.from)?.name ?? islandName(p.pair.from)} →{" "}
              {islandById.get(p.pair.to)?.name ?? islandName(p.pair.to)}
              <button type="button" aria-label="섬 간 필터 해제" onClick={p.onClearPair} className="text-label hover:text-title">
                ×
              </button>
            </span>
          </>
        ) : (
          chips.length > 0 && (
            <>
              <span className="shrink-0 whitespace-nowrap text-[12px] text-label">중심 엔티티</span>
              {chips.map((id) => {
                const t = byId.get(id);
                const on = id === p.center;
                const token = t?.token ?? p.fallbackToken?.(id) ?? "actor";
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => p.onCenter(id)}
                    aria-pressed={on}
                    /*
                     * 섬 색만 CSS 변수(`--chip`)로 넘기고 모양은 고정 클래스로 쓴다. 전에는 테두리 · 바탕 ·
                     * 글자색을 인라인 style 로 줘서 마우스 올림 클래스가 먹지 않았다. 안 고른 칩은 테두리
                     * 단추의 공통 규칙(`hover-edge`)이다 (2026-09-28 코드 분석, 최현서 1번)
                     */
                    className={[
                      "flex shrink-0 items-center gap-s2 whitespace-nowrap rounded-full border px-s4 py-s1 text-[13px]",
                      on
                        ? "border-[color:var(--chip)] bg-[color:color-mix(in_srgb,var(--chip)_14%,transparent)] font-semibold text-[color:var(--chip)]"
                        : "border-edge bg-card text-body hover-edge",
                    ].join(" ")}
                    style={{ "--chip": `var(--t-island-${token})` } as CSSProperties}
                  >
                    <span aria-hidden className="size-[8px] rounded-full" style={{ background: "var(--chip)" }} />
                    {nameOf(id)}
                    {originId === id && (
                      <span aria-label="출발 영토" className="size-[6px] rounded-full" style={{ background: "var(--t-accent)" }} />
                    )}
                  </button>
                );
              })}
            </>
          )
        )}
      </div>

      <div
        ref={boardRef}
        className="relative min-h-0 flex-1 overflow-hidden rounded-[14px] border border-edge bg-canvas"
        // 판 밖으로 걸친 선 · 노드에 초점이 가면 브라우저가 이 틀을 스스로 굴려 범례 · 줌 단추가
        // 밀렸다. 굴림은 줌 · 끌기로만 한다 (2026-09-29 검토)
        onScroll={(e) => {
          e.currentTarget.scrollTop = 0;
          e.currentTarget.scrollLeft = 0;
        }}
      >
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            backgroundImage: "radial-gradient(var(--t-border-card) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
            opacity: 0.35,
          }}
        />

        {/*
          끄는 판. 손 커서(끄는 동안 쥔 손)로 끌 수 있다는 것을 알린다. 선 · 라벨 · 노드 위에서는
          손가락 커서가 이긴다. 포인터를 캡처하지 않는다 — 캡처하면 클릭 대상이 판으로 고정돼
          무엇을 눌렀는지 모른다 (지도 `MapCanvas` 머리말). 끌고 놓은 클릭은 캡처 단계에서 끊어
          선 · 노드 고르기와 빈 곳 해제 어느 쪽에도 안 간다 (2026-09-28 최현서 5번)
        */}
        <div
          ref={pad}
          className={"absolute inset-0 touch-none select-none " + (grabbing ? "cursor-grabbing" : "cursor-grab")}
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            drag.current = { x: e.clientX, y: e.clientY, px: view.x, py: view.y };
            moved.current = false;
            setGrabbing(true);
          }}
          onPointerMove={(e) => {
            const d = drag.current;
            if (!d) return;
            // 판 밖에서 단추를 놓고 돌아온 경우 — 끌기가 아니다
            if ((e.buttons & 1) === 0) return endDrag();
            const dx = e.clientX - d.x;
            const dy = e.clientY - d.y;
            // 누르는 동안의 작은 떨림은 옮기지 않는다. 3px 를 넘어야 끌기다
            if (!moved.current && Math.hypot(dx, dy) <= 3) return;
            moved.current = true;
            setView((v) => ({ ...v, x: d.px + dx, y: d.py + dy }));
          }}
          onPointerUp={endDrag}
          onPointerLeave={endDrag}
          onClickCapture={(e) => {
            if (moved.current) e.stopPropagation();
          }}
          // 빈 곳 클릭이면 선택 해제. 선 · 라벨 · 노드는 제 클릭을 여기까지 안 올린다
          onClick={() => p.onSelect(null)}
        >
          <div
            className="size-full"
            style={{
              transform: `translate(${view.x}px, ${view.y}px) scale(${view.zoom / 100})`,
              transformOrigin: "center center",
              // 줌 · 전체 보기는 짧게 옮겨 간다. 끄는 동안은 손을 바로 따라가야 해서 끈다 (지도와 같다)
              transition: grabbing ? "none" : "transform var(--dur-base) var(--ease-out)",
            }}
          >
            <svg
              viewBox={`0 0 ${W} ${H}`}
              className="block size-full"
              // 안의 선 · 노드가 단추라 그림 한 장(img)이 아니다. 이웃 노드를 키보드로 중심으로 삼으면
              // 그 노드가 단추가 아니게 되어 초점을 여기로 옮긴다
              role="group"
              tabIndex={-1}
              aria-label={p.pair ? "섬 간 관계 그래프" : `${centerName} 중심 관계 그래프`}
            >
              <defs>
                {KIND_ORDER.map((k) => (
                  <marker
                    key={k}
                    id={`rel-arrow-${k}`}
                    viewBox="0 0 10 10"
                    refX="2"
                    refY="5"
                    markerWidth="9"
                    markerHeight="9"
                    markerUnits="userSpaceOnUse"
                    orient="auto"
                  >
                    <path d="M0,0 L10,5 L0,10 z" fill={`var(--t-rel-${k})`} />
                  </marker>
                ))}
              </defs>

              {/* 펼친 범례를 비켜 민 자리 (`legendShift`). 접으면 0 이다 */}
              <g
                transform={
                  shift.dx || shift.dy || shift.s !== 1
                    ? `translate(${shift.dx.toFixed(1)} ${shift.dy.toFixed(1)})${shift.s !== 1 ? ` scale(${shift.s.toFixed(3)})` : ""}`
                    : undefined
                }
              >
                {/*
                  선. 마우스를 올리면 굵고 진해진다 — 흐려진 선도 반쯤 살아나 누를 수 있는 것이 보인다.
                  굵기 · 흐려짐은 번져 바뀐다 (최현서 1번). `d` 는 전환에 안 넣는다 — 중심이 바뀔 때
                  선이 날아다니지 않게
                */}
                {graph.edges.map(({ v, d }) => {
                  const on = focus?.rel.id === v.rel.id;
                  const picked = sel?.rel.id === v.rel.id;
                  const dimmed = focus && !on;
                  const hover = hoverEdge === v.rel.id;
                  const pick = (e: MouseEvent) => {
                    e.stopPropagation();
                    if (p.pair) p.onPairPick(v);
                    else p.onSelect(picked ? null : v.rel.id);
                  };
                  return (
                    <g
                      key={v.rel.id}
                      className="cursor-pointer"
                      onClick={pick}
                      // 키보드로도 고른다 — Tab 으로 옮겨 Enter · Space (2026-09-28 코드 분석)
                      data-edge=""
                      tabIndex={0}
                      role="button"
                      aria-label={`${KIND_LABEL[v.rel.kind]} · ${nameOf(v.rel.from)} → ${nameOf(v.rel.to)}`}
                      aria-pressed={picked}
                      onKeyDown={(e) => {
                        if (e.key !== "Enter" && e.key !== " ") return;
                        e.preventDefault();
                        e.stopPropagation();
                        if (p.pair) p.onPairPick(v);
                        else p.onSelect(picked ? null : v.rel.id);
                      }}
                      {...edgeHover(v.rel.id)}
                    >
                      <path d={d} fill="none" stroke="transparent" strokeWidth={16} />
                      <path
                        d={d}
                        fill="none"
                        stroke={`var(--t-rel-${v.rel.kind})`}
                        strokeWidth={on ? 3 : hover ? 2.6 : 1.8}
                        strokeDasharray={CONF_DASH[v.rel.confidence] || undefined}
                        strokeLinecap="round"
                        markerEnd={`url(#rel-arrow-${v.rel.kind})`}
                        opacity={dimmed ? (hover ? 0.5 : 0.15) : on || hover ? 1 : outerEdge(v) ? 0.5 : 0.85}
                        className="transition-[stroke-width,opacity] duration-[var(--dur-base)] ease-[var(--ease-out)]"
                      />
                    </g>
                  );
                })}

                {/*
                  선 라벨 — 「Recruitment 14건」 (설계서 4.3.6). 고른 선은 칠하고, 강조한 선은
                  테두리만 진하게 한다 (4.3.3 ① 「'Recruitment 14건' 강조 테두리」).
                  어느 선에 라벨을 달지는 배율이 정한다 (`placeLabels` — 100% 는 지금까지처럼 1단계 선 전부,
                  줄이면 건수 상위만, 125% 이상은 2단계 바깥 선까지. 강조 · 고른 선은 늘). 라벨끼리나
                  노드 이름과 겹치면 선을 따라 옮기고, 못 옮기면 뺀다 (2026-09-28 최현서 5번).
                  마우스를 올리면(선이든 라벨이든) 바탕이 한 단계 밝고 테두리가 관계 색이 된다 (최현서 1번)
                */}
                {graph.edges.map(({ v }) => {
                  const at = labelAt.get(v.rel.id);
                  if (!at) return null;
                  const on = focus?.rel.id === v.rel.id;
                  const picked = sel?.rel.id === v.rel.id;
                  const hover = hoverEdge === v.rel.id;
                  const name = KIND_NAME[v.rel.kind];
                  const w = labelWidth(v);
                  return (
                    <g
                      key={`l-${v.rel.id}`}
                      transform={`translate(${at.x.toFixed(1)} ${at.y.toFixed(1)})`}
                      className="cursor-pointer transition-opacity duration-[var(--dur-base)] ease-[var(--ease-out)]"
                      opacity={focus && !on ? (hover ? 0.75 : 0.3) : 1}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (p.pair) p.onPairPick(v);
                        else p.onSelect(picked ? null : v.rel.id);
                      }}
                      {...edgeHover(v.rel.id)}
                    >
                      {/*
                        확대하면 알약은 화면에서 설계 크기까지만 커지고 그다음은 그 크기를 지킨다
                        (`labelScale`). 판의 줌 전환과 같은 시간으로 번져 바뀌어 도중에 튀지 않는다. 자리
                        옮김(바깥 g)은 전환에 안 넣는다 — 중심이 바뀔 때 라벨이 날아다니지 않게
                      */}
                      <g
                        style={{
                          transform: `scale(${labelK})`,
                          transformBox: "fill-box",
                          transformOrigin: "center",
                          transition: "transform var(--dur-base) var(--ease-out)",
                        }}
                      >
                        <g transform={`translate(${(-w / 2).toFixed(1)} ${-LABEL_H / 2})`}>
                          <rect
                            width={w}
                            height={LABEL_H}
                            rx={6}
                            fill={
                              picked
                                ? `var(--t-rel-${v.rel.kind})`
                                : hover
                                  ? "var(--t-surface-track)"
                                  : "var(--t-surface-panel)"
                            }
                            stroke={on || hover ? `var(--t-rel-${v.rel.kind})` : "var(--t-border-card)"}
                            strokeWidth={on && !picked ? 2 : hover && !picked ? 1.5 : 1}
                            className="transition-[fill,stroke,stroke-width] duration-[var(--dur-fast)] ease-[var(--ease-out)]"
                          />
                          {!picked && <circle cx={13} cy={13} r={3.5} fill={`var(--t-rel-${v.rel.kind})`} />}
                          <text x={picked ? 12 : 23} y={17.5} fontSize={13} fontWeight={600}>
                            <tspan fill={picked ? "var(--t-text-on-accent)" : "var(--t-text-title)"}>{name}</tspan>
                            <tspan dx={6} fontSize={12} fontWeight={400} fill={picked ? "var(--t-text-on-accent)" : "var(--t-text-label)"}>
                              {v.count}건
                            </tspan>
                          </text>
                        </g>
                      </g>
                    </g>
                  );
                })}

                {/*
                  노드. 누를 수 있는 노드(중심이 아닌 것)에 마우스를 올리면 테두리가 지도 영토와 같은
                  밝은 색(`--t-hex-hover-edge`)으로 굵어지고, 흐려진 노드도 반쯤 살아난다 (최현서 1번)
                */}
                {[...graph.nodes.values()].map((n) => {
                  const isCenter = n.id === p.center && !p.pair;
                  const c = `var(--t-island-${n.t.token})`;
                  const faded = focus && !onFocus(n.id);
                  const hover = !isCenter && hoverNode === n.id;
                  return (
                    <g
                      key={n.id}
                      className={
                        isCenter
                          ? "transition-opacity duration-[var(--dur-base)] ease-[var(--ease-out)]"
                          : "cursor-pointer transition-opacity duration-[var(--dur-base)] ease-[var(--ease-out)]"
                      }
                      opacity={faded ? (hover ? 0.7 : 0.35) : 1}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (!isCenter) p.onCenter(n.id);
                      }}
                      // 이웃 노드는 키보드로도 중심으로 삼는다 — Tab 으로 옮겨 Enter · Space
                      data-node=""
                      tabIndex={isCenter ? undefined : 0}
                      role={isCenter ? undefined : "button"}
                      aria-label={isCenter ? undefined : `${n.t.name} — 중심으로`}
                      onKeyDown={
                        isCenter
                          ? undefined
                          : (e) => {
                              if (e.key !== "Enter" && e.key !== " ") return;
                              e.preventDefault();
                              e.stopPropagation();
                              const svg = e.currentTarget.ownerSVGElement;
                              p.onCenter(n.id);
                              setTimeout(() => svg?.focus({ preventScroll: true }), 0);
                            }
                      }
                      onMouseEnter={isCenter ? undefined : () => setHoverNode(n.id)}
                      // 떠나기는 중심 노드에도 단다 — 노드를 눌러 중심이 되면 떠나기 듣개가 빠져 hover 가
                      // 남았다가, 다시 이웃이 되면 마우스가 없는데도 밝게 그려졌다 (2026-09-28 검토)
                      onMouseLeave={() => setHoverNode((h) => (h === n.id ? null : h))}
                    >
                      <title>{isCenter ? n.t.name : `${n.t.name} — 눌러서 중심으로`}</title>
                      {isCenter && (
                        <polygon points={hexPoints(n.x, n.y, n.r + 6)} fill="none" stroke={c} strokeWidth={2} opacity={0.9} />
                      )}
                      {n.actor ? (
                        <>
                          <polygon
                            points={hexPoints(n.x, n.y, n.r)}
                            fill="var(--t-surface-card)"
                            stroke={hover ? "var(--t-hex-hover-edge)" : c}
                            strokeWidth={hover ? 2.5 : 1.5}
                            className="transition-[stroke,stroke-width] duration-[var(--dur-fast)] ease-[var(--ease-out)]"
                          />
                          <TeamMark cx={n.x} cy={n.y} size={n.r} />
                        </>
                      ) : (
                        <polygon
                          points={hexPoints(n.x, n.y, n.r)}
                          fill={c}
                          stroke={hover ? "var(--t-hex-hover-edge)" : "var(--t-border-hex)"}
                          strokeWidth={hover ? 2 : 1}
                          strokeDasharray={empty && isCenter ? "4 3" : undefined}
                          fillOpacity={empty && isCenter ? 0.25 : 1}
                          className="transition-[stroke,stroke-width] duration-[var(--dur-fast)] ease-[var(--ease-out)]"
                        />
                      )}
                      {n.side === "below" && n.outer ? (
                        <text x={n.x} y={n.y + n.r + 16} textAnchor="middle" fontSize={12} fontWeight={600} fill="var(--t-text-title)">
                          {n.t.name}
                        </text>
                      ) : n.side === "below" ? (
                        <>
                          <text
                            x={n.x}
                            y={n.y + n.r + 20}
                            textAnchor="middle"
                            fontSize={isCenter ? 16 : 14}
                            fontWeight={700}
                            fill={isCenter ? c : "var(--t-text-title)"}
                          >
                            {n.t.name}
                          </text>
                          <text x={n.x} y={n.y + n.r + 37} textAnchor="middle" fontSize={12} fill="var(--t-text-label)">
                            {n.islandName} · 활동도 {n.t.metrics.activity}
                          </text>
                        </>
                      ) : (
                        <text
                          x={n.side === "left" ? n.x - n.r - 10 : n.x + n.r + 10}
                          y={n.y + 4}
                          textAnchor={n.side === "left" ? "end" : "start"}
                          fontSize={13}
                          fontWeight={700}
                          fill="var(--t-text-title)"
                        >
                          {n.t.name}
                          <tspan dx={6} fontSize={11} fontWeight={400} fill="var(--t-text-label)">
                            활동도 {n.t.metrics.activity}
                          </tspan>
                        </text>
                      )}
                    </g>
                  );
                })}
              </g>
            </svg>
          </div>
        </div>

        {/*
          범례 — 관계 종류 일곱, 신뢰도 셋 (설계서 4.3.6). 접었다 펼 수 있다 — 펼친 채로는 1366 급
          창에서 1단계 왼쪽 노드를 덮었다 (2026-09-28 코드 분석). 접기 단추는 두 모양이 한 요소다 —
          눌러서 모양이 바뀌어도 초점이 그 자리에 남는다
        */}
        <div
          className={
            legendOpen
              // 판이 낮으면(스냅샷 바가 들어온 1280×720) 힌트 알약 위에서 멈추고 안에서 굴린다 — 전에는
              // 아래 줄이 힌트에 덮였다 (2026-09-29 검토). 굴려야 해서 포인터를 받는다
              ? "absolute left-s4 top-s4 flex max-h-[calc(100%-80px)] w-[190px] flex-col gap-s3 overflow-y-auto rounded-[12px] border border-edge bg-panel px-s4 py-s4 [scrollbar-width:thin] [scrollbar-color:var(--t-border-strong)_transparent]"
              : "absolute left-s4 top-s4"
          }
        >
          <div className="flex items-center justify-between gap-s2">
            {legendOpen && (
              <h3 className="flex items-center gap-s2 text-[11px] text-label">
                관계 유형
                {/*
                  물음표 — 올리면 종류마다의 뜻을 판 위에 띄운다. 범례 상자는 안에서 굴러가 설명을 그 밖에
                  둔다 (2026-09-29 최현서 v2 3번)
                */}
                <button
                  type="button"
                  aria-label="관계 유형 설명"
                  aria-expanded={kindHelp}
                  onMouseEnter={() => setKindHelp(true)}
                  onMouseLeave={() => setKindHelp(false)}
                  onFocus={() => setKindHelp(true)}
                  onBlur={() => setKindHelp(false)}
                  className="pointer-events-auto flex size-[16px] items-center justify-center rounded-full border border-edge text-[10px] leading-none text-label hover-edge"
                >
                  ?
                </button>
              </h3>
            )}
            <button
              type="button"
              aria-expanded={legendOpen}
              aria-label={legendOpen ? "범례 접기" : undefined}
              title={legendOpen ? "범례 접기" : "범례 펼치기"}
              onClick={() => setLegendOpen(!legendOpen)}
              className={
                legendOpen
                  ? "pointer-events-auto -my-s1 flex size-[22px] items-center justify-center rounded-[6px] border border-edge bg-panel text-[12px] leading-none text-label hover-edge"
                  : "flex items-center gap-s2 rounded-[10px] border border-edge bg-panel px-s3 py-s2 text-[12px] text-body hover-edge"
              }
            >
              {legendOpen ? (
                <span aria-hidden>‹</span>
              ) : (
                <>
                  관계 유형
                  <span aria-hidden>›</span>
                </>
              )}
            </button>
          </div>
          {legendOpen && (
            <>
              <ul className="flex flex-col gap-s2">
                {KIND_ORDER.map((k) => (
                  <li key={k} className="flex items-center gap-s2 text-[12px] text-body">
                    <KindDot kind={k} />
                    {KIND_NAME[k]}
                  </li>
                ))}
              </ul>
              <div className="h-px bg-divider" />
              <ul className="flex flex-col gap-s2">
                {(["confirmed", "high", "estimated"] as const).map((c) => (
                  <li key={c} className="flex items-center gap-s3 text-[12px] text-body">
                    <svg aria-hidden width="34" height="2" viewBox="0 0 34 2" className="shrink-0 overflow-visible">
                      <line x1="0" y1="1" x2="34" y2="1" stroke="var(--t-text-label)" strokeWidth="1.5" strokeDasharray={CONF_DASH[c] || undefined} strokeLinecap="round" />
                    </svg>
                    {CONF_LABEL[c]}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        {/*
          판 위 도구 — 피그마 ⑦-8g 의 두 단추. 관계 없음이면 안내 상자가 대신 띄운다.
          섬 간 보기에는 안 둔다 — 중심이 없어 2단계가 뜻이 없고, 오른쪽 줄 이름을 가린다.
          섬 간 보기는 들어올 때마다 추정을 포함한 기본값이다
        */}
        {!empty && !p.pair && (
          <div className="absolute right-s4 top-s4 flex items-center gap-s2">
            <Toggle on={p.est} onClick={toggleEst} est>
              추정 관계 포함
            </Toggle>
            <Toggle on={p.depth === 2} onClick={() => p.onDepth(p.depth === 2 ? 1 : 2)}>
              2단계로 확장
            </Toggle>
          </div>
        )}

        {/*
          근거 팝오버 — 피그마 ⑦-8e 「선택한 관계 · Evidence」. 도구 줄 아래에 띄운다.
          닫기(×)를 둔다 — 전에는 닫을 길이 빈 곳 클릭뿐이라 오른쪽 노드를 덮은 채 남았다. 같은
          내용이 오른쪽 패널에도 있어 폭을 330 → 300 으로 줄이고, 길어지면 줌 단추 위에서 끊어
          안에서 스크롤한다 (2026-09-28 코드 분석)
        */}
        {sel && (
          <div className="absolute right-s4 top-[64px] flex max-h-[calc(100%-142px)] w-[300px] flex-col gap-s3 overflow-y-auto rounded-[12px] border border-edge bg-panel px-s5 py-s4 shadow-lg">
            <div className="flex items-center justify-between gap-s2">
              <p className="text-[11px] text-label">선택한 관계 · Evidence</p>
              <button
                type="button"
                aria-label="근거 닫기"
                onClick={() => p.onSelect(null)}
                className="-my-s1 -mr-s2 flex size-[24px] shrink-0 items-center justify-center rounded-[6px] text-[15px] leading-none text-label hover-seg"
              >
                ×
              </button>
            </div>
            <div className="flex items-center gap-s2">
              <span className="text-[15px] font-semibold text-title">
                {nameOf(sel.rel.from)} → {nameOf(sel.rel.to)}
              </span>
              <Chip tone={CONF_CHIP[sel.rel.confidence]}>{CONF_LABEL[sel.rel.confidence]}</Chip>
            </div>
            <dl className="grid grid-cols-[1fr_auto] gap-x-s4 gap-y-s2 text-[12px]">
              <dt className="text-label">관계 유형</dt>
              <dd className="font-mono text-title">{KIND_NAME[sel.rel.kind]}</dd>
              <dt className="text-label">신뢰도</dt>
              <dd className="text-title">{CONF_LABEL[sel.rel.confidence]}</dd>
              <dt className="text-label">First Seen</dt>
              <dd className="font-mono text-title">{sel.first ? sel.first.slice(0, 7) : "—"}</dd>
              <dt className="text-label">Last Seen</dt>
              <dd className="font-mono text-title">{sel.last ? sel.last.slice(0, 7) : "—"}</dd>
              {/* 출처는 근거 사건이다. 명부에서 만든 관계는 그 칸 하나가 출처다 */}
              <dt className="text-label">출처 수</dt>
              <dd className="text-title tabular-nums">{sel.fromRegistry ? "명부 칸" : `${sel.evidence.length}건`}</dd>
            </dl>
            {/* 설명 — 관계 연혁과 같은 자동 문장 (설계서 4.3.6 「설명」) */}
            <p className="text-[12px] leading-[1.7] text-body">{historyText(sel, nameOf)}</p>
            {sel.fromRegistry && sel.rel.note && (
              <div className="flex flex-col gap-s1">
                <p className="text-[11px] text-label">명부 「연결된 곳」 원문</p>
                <p className="break-all rounded-[8px] bg-card px-s3 py-s2 font-mono text-[12px] leading-[1.6] text-body">
                  {sel.rel.note}
                </p>
              </div>
            )}
          </div>
        )}

        {/*
          관계 없음 — 피그마 ⑦-8g. 「2단계로 확장」은 바로 이어진 영토가 없으면 넓힐 곳이
          없어 끈다. 2단계로 넓힌 채 여기 왔으면 되돌릴 수 있게 켜 둔다.
          「전체 관계 보기」는 보류라 안 둔다 (설계서 4.2.7)
        */}
        {/* 관계 유형 설명 — 범례 「?」 에 올렸을 때 범례 오른쪽에 뜬다 (v2 3번) */}
        {legendOpen && kindHelp && (
          <div
            role="tooltip"
            // 판이 낮은 1280×720 에서도 판 안에 들도록 넓고 촘촘하게 둔다
            className="pointer-events-none absolute left-[214px] top-s4 z-10 flex max-h-[calc(100%-32px)] w-[380px] max-w-[calc(100%-230px)] flex-col gap-s2 overflow-hidden rounded-[12px] border border-edge bg-panel px-s4 py-s3 shadow-lg"
          >
            <h3 className="text-[11px] text-label">관계 유형 — 무엇을 뜻하나</h3>
            <ul className="flex flex-col gap-s2">
              {KIND_ORDER.map((k) => (
                <li key={k} className="flex gap-s2 text-[11px] leading-[1.45] text-body">
                  <span className="mt-[4px]">
                    <KindDot kind={k} />
                  </span>
                  <span>
                    <span className="font-semibold text-title">{KIND_LABEL[k]}</span>
                    <span className="text-label"> · {KIND_NAME[k]}</span>
                    <br />
                    {KIND_HELP[k]}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {pairEmpty && (
          <div className="absolute bottom-[84px] left-1/2 flex w-[460px] max-w-[calc(100%-32px)] -translate-x-1/2 flex-col items-center gap-s3 rounded-[14px] border border-edge bg-panel px-s6 py-s5 text-center">
            <h3 className="text-[15px] font-semibold text-title">이 기준일에는 두 섬 사이 관계가 없습니다</h3>
            <p className="text-[12px] leading-[1.7] text-body">
              스냅샷 바로 기준일을 옮기거나 섬 간 필터를 풀어 보세요.
            </p>
          </div>
        )}
        {empty && (
          <div className="absolute bottom-[84px] left-1/2 flex w-[460px] max-w-[calc(100%-32px)] -translate-x-1/2 flex-col items-center gap-s3 rounded-[14px] border border-edge bg-panel px-s6 py-s5 text-center">
            <h3 className="text-[15px] font-semibold text-title">
              {p.centerAbsent
                ? "이 기준일 지도에 없는 영토입니다"
                : p.center
                  ? "확인된 관계가 없습니다"
                  : "이 기준일에 기록된 관계가 없습니다"}
            </h3>
            <p className="text-[12px] leading-[1.7] text-body">{emptyBody}</p>
            <div className="flex flex-wrap items-center justify-center gap-s2">
              {p.center && (
                <>
                  <Toggle on={p.est} onClick={toggleEst} est>
                    추정 관계 포함
                  </Toggle>
                  <Toggle
                    on={p.depth === 2}
                    disabled={p.depth === 1}
                    title={p.depth === 1 ? "바로 이어진 영토가 없어 2단계로 넓힐 곳이 없습니다" : undefined}
                    onClick={() => p.onDepth(p.depth === 2 ? 1 : 2)}
                  >
                    2단계로 확장
                  </Toggle>
                </>
              )}
              {p.moveTo && (
                // 강조색 단추의 공통 마우스 올림(`hover-accent`) — 전에는 없었다 (최현서 1번)
                <button
                  type="button"
                  onClick={p.onMove}
                  className="rounded-[8px] px-s4 py-s2 text-[13px] font-semibold text-on-accent hover-accent"
                  style={{ background: "var(--t-accent)" }}
                >
                  {quarterText(p.moveTo)} 부터 관계 확인 · 기준일 옮기기
                </button>
              )}
            </div>
          </div>
        )}

        {/*
          힌트 알약. 오른쪽 줌 단추 자리를 비워 두고 넘치면 말줄임한다 — 좁은 창에서 2단계 문구가
          줌 단추 밑으로 들어갔다. 배율에 따라 라벨이 줄고 느는 것도 여기서 알린다 (2026-09-28 최현서 5번)
        */}
        <div
          className="pointer-events-none absolute left-s5 flex max-w-[calc(100%-310px)] items-center gap-s2 rounded-full border border-edge bg-panel px-s4 text-[12px] text-body"
          style={{ bottom: "var(--s-5)", height: "var(--h-hint)" }}
        >
          <span aria-hidden className="size-[6px] shrink-0 rounded-full" style={{ background: "var(--t-accent)" }} />
          <span className="min-w-0 truncate">
            {empty
              ? "관계 없음 상태 · 액션으로 탐색 확장"
              : pairEmpty
                ? "관계 없음 상태 · 스냅샷 바로 기준일 옮기기"
              : p.pair
                ? "섬 간 보기 · 선을 누르면 그 관계로 이동"
                : sel
                  ? "선택한 관계선 강조 · 나머지 흐리게 · 근거 팝오버"
                  : hi
                    ? "강조된 관계선 클릭 → 근거(Evidence) 표시"
                    : view.zoom < 100
                      ? "줄여 보는 중 · 건수가 큰 관계만 라벨 표시"
                      : p.depth === 2
                        ? view.zoom >= 125
                          ? `2단계 확장 · 바깥 선 라벨까지 표시${rest ? ` · 건수가 적은 ${rest}곳은 뺐습니다` : ""}`
                          : `2단계 확장 · 바깥 선은 누르거나 125% 이상 확대하면 라벨 표시${rest ? ` · 건수가 적은 ${rest}곳은 뺐습니다` : ""}`
                        : "관계선 클릭 → 근거(Evidence) 표시"}
          </span>
        </div>

        {/*
          줌 단추 — 지도와 같은 모양과 자리 (− 배율 + · 전체 보기) (2026-09-28 최현서 5번).
          관계 없음일 때도 둔다 — 키운 채 관계가 비면 되돌릴 단추가 없어진다
        */}
        <div className="absolute right-s5 flex items-center gap-s3" style={{ bottom: "var(--s-5)" }}>
          <div className="flex items-center rounded-full border border-edge bg-panel" style={{ height: "var(--h-zoom)" }}>
            <button
              type="button"
              aria-label="축소"
              disabled={view.zoom <= ZOOM_MIN}
              onClick={() => zoomBy(-ZOOM_STEP)}
              className="h-full rounded-l-full px-s4 text-[13px] text-body hover-seg disabled:text-disabled"
            >
              −
            </button>
            <span className="w-[52px] text-center text-[12px] tabular-nums text-body">{view.zoom}%</span>
            <button
              type="button"
              aria-label="확대"
              disabled={view.zoom >= ZOOM_MAX}
              onClick={() => zoomBy(ZOOM_STEP)}
              className="h-full rounded-r-full px-s4 text-[13px] text-body hover-seg disabled:text-disabled"
            >
              +
            </button>
          </div>
          <button
            type="button"
            onClick={() => setView(VIEW_HOME)}
            className="flex items-center gap-s2 rounded-full border border-edge bg-panel px-s4 text-[12px] text-body hover-edge"
            style={{ height: "var(--h-zoom)" }}
          >
            <span aria-hidden>⛶</span>
            화면에 맞춤
          </button>
        </div>
      </div>
    </div>
  );
}
