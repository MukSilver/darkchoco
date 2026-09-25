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
 * **섬 간 보기**(4.3.3 ②)도 여기서 그린다. [연결] 탭의 「유형 간 연결」 행을
 * 더블클릭하면 온다. 왼쪽에 출발 섬 영토, 오른쪽에 도착 섬 영토를 세우고 그
 * 섬 쌍의 선만 긋는다. 선을 누르면 보통 관계 탭(①)으로 넘어간다.
 *
 * 안 만든 것
 *
 *   「전체 관계 보기」 스위치   설계서 4.2.7 · 6.3 이 보류로 정했다 (지도 탭과 같다)
 *   로고                      굽기가 로고를 안 싣는다. 노드는 섬 색 육각형이다
 *   근거 사건 더블클릭 → 보고서 팝업   팝업(4.3.4)이 아직 없다
 *
 * 근거 사건 없이 명부 「연결된 곳」에서 만든 관계선은 팝오버에 그 칸의 원문을
 * 보인다 (4.3.6). 굽기가 상대 이름이 든 항목만 골라 `note` 로 싣는다.
 */

"use client";

import { useMemo, type MouseEvent } from "react";

import { Chip, KindDot, TeamMark, hexPoints } from "./RelBits";
import type { MapLayout, TerritoryShape } from "@/lib/layout";
import { parseQuarter, type QuarterKey } from "@/lib/quarter";
import {
  CONF_CHIP,
  CONF_DASH,
  CONF_LABEL,
  KIND_NAME,
  KIND_ORDER,
  centerChips,
  josa,
  pairViews,
  partnerOf,
  touching,
  type RelView,
} from "@/lib/relations";

export type RelPair = { from: string; to: string };

export type RelationTabProps = {
  layout: MapLayout;
  /** 기준일에 그릴 관계 전부 (`relationsAt`) */
  views: RelView[];
  center: string | null;
  onCenter: (territoryId: string) => void;
  /** 고른 관계선 id */
  selected: string | null;
  onSelect: (relationId: string | null) => void;
  /** 섬 간 보기 필터. 있으면 섬 간 보기로 그린다 */
  pair: RelPair | null;
  onClearPair: () => void;
  /** 섬 간 보기에서 선을 눌렀을 때 — 보통 관계 탭(①)으로 넘어간다 */
  onPairPick: (v: RelView) => void;
  /** [연결] 탭에서 넘어왔으면 출발 영토. 칩에 점을 찍고 돌아가기를 띄운다 (4.3.3 ①) */
  origin: { id: string; name: string } | null;
  onBack: () => void;
  /** 관계가 없을 때 관계가 처음 생기는 분기. 「기준일 옮기기」 단추에 쓴다 (4.3.3 예외) */
  moveTo: QuarterKey | null;
  onMove: () => void;
};

/* 그래프 판 크기. viewBox 단위라 화면 크기와 무관하다 */
const W = 1000;
const H = 620;
const CX = W / 2;
const CY = H / 2 - 10;

function textWidth(s: string, fontSize: number): number {
  let w = 0;
  for (const ch of s) w += /[가-힣ㄱ-ㆎ]/.test(ch) ? 1 : 0.6;
  return w * fontSize;
}

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
};

type Edge = {
  v: RelView;
  d: string;
  mid: { x: number; y: number };
};

/**
 * 두 노드 사이 선. 노드 가장자리에서 시작해 화살촉 자리만큼 떨어져 끝난다.
 * 같은 두 노드 사이에 관계가 여럿이면 `bend` 만큼 휘어 겹치지 않게 하고,
 * 라벨도 곡선 위 `t` 자리를 달리해 앉힌다 — 휘기만 하면 라벨 폭이 휜 거리보다
 * 넓어 서로 덮는다.
 */
function edgePath(a: Node, b: Node, bend: number, t = 0.5): { d: string; mid: { x: number; y: number } } {
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
  const u = 1 - t;
  return {
    d: `M${sx.toFixed(1)},${sy.toFixed(1)}Q${qx.toFixed(1)},${qy.toFixed(1)} ${ex.toFixed(1)},${ey.toFixed(1)}`,
    mid: { x: u * u * sx + 2 * u * t * qx + t * t * ex, y: u * u * sy + 2 * u * t * qy + t * t * ey },
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

export default function RelationTab(p: RelationTabProps) {
  const byId = useMemo(() => new Map(p.layout.territories.map((t) => [t.territoryId, t])), [p.layout]);
  const islandById = useMemo(() => new Map(p.layout.islands.map((i) => [i.islandKey, i])), [p.layout]);
  const nameOf = (id: string) => byId.get(id)?.name ?? id;
  const islandOf = (id: string) => byId.get(id)?.islandKey;

  const node = (id: string, x: number, y: number, r: number, side: Node["side"] = "below"): Node | null => {
    const t = byId.get(id);
    if (!t) return null;
    const isl = islandById.get(t.islandKey);
    return { id, x, y, r, t, islandName: isl?.name ?? "", actor: isl?.islandId === "ACTOR", side };
  };

  /* ── 그릴 것 ─────────────────────────────────────────── */

  const graph = useMemo(() => {
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
      return { nodes, edges: buildEdges(list, nodes, 0.3), list };
    }
    if (!p.center) return { nodes, edges: [], list: [] };
    const list = touching(p.views, p.center);
    // 건수가 큰 상대가 맨 위에 오도록 세운다
    const weight = new Map<string, number>();
    for (const v of list) {
      const o = partnerOf(v, p.center);
      weight.set(o, (weight.get(o) ?? 0) + v.count);
    }
    const partners = [...weight.keys()].sort(
      (a, b) => (weight.get(b) ?? 0) - (weight.get(a) ?? 0) || nameOf(a).localeCompare(nameOf(b)),
    );
    const n = partners.length;
    const R = n <= 4 ? 210 : n <= 8 ? 235 : 250;
    const r = n <= 8 ? 26 : 20;
    const c = node(p.center, CX, CY, 34);
    if (c) nodes.set(p.center, c);
    partners.forEach((id, i) => {
      const a = ((-90 + (i * 360) / n) * Math.PI) / 180;
      const nd = node(id, CX + R * Math.cos(a), CY + R * Math.sin(a) * 0.86, r);
      if (nd) nodes.set(id, nd);
    });
    return { nodes, edges: buildEdges(list, nodes), list };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.views, p.center, p.pair, byId, islandById]);

  const sel = graph.edges.find((e) => e.v.rel.id === p.selected)?.v ?? null;
  const onSel = (id: string) => sel && (sel.rel.from === id || sel.rel.to === id);
  const empty = !p.pair && graph.list.length === 0;
  const centerName = p.center ? nameOf(p.center) : "";

  const chips = p.pair ? [] : centerChips(p.views, p.center, nameOf);

  /* ── 그리기 ─────────────────────────────────────────── */

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-s4">
      <div className="flex shrink-0 flex-wrap items-center gap-s3">
        {p.origin && (
          <button
            type="button"
            onClick={p.onBack}
            className="rounded-full border border-edge bg-card px-s3 py-s1 text-[12px] text-body hover:text-title"
          >
            ‹ {p.origin.name} 연결로 돌아가기
          </button>
        )}
        {p.pair ? (
          <>
            <span className="text-[12px] text-label">섬 간 필터</span>
            <span className="flex items-center gap-s2 rounded-full border border-[var(--t-accent)] bg-accent-subtle px-s4 py-s1 text-[13px] text-title">
              {islandById.get(p.pair.from)?.name} → {islandById.get(p.pair.to)?.name}
              <button type="button" aria-label="섬 간 필터 해제" onClick={p.onClearPair} className="text-label hover:text-title">
                ×
              </button>
            </span>
          </>
        ) : (
          chips.length > 0 && (
            <>
              <span className="text-[12px] text-label">중심 엔티티</span>
              {chips.map((id) => {
                const t = byId.get(id);
                const on = id === p.center;
                const token = t?.token ?? "actor";
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => p.onCenter(id)}
                    aria-pressed={on}
                    className="flex items-center gap-s2 rounded-full border px-s4 py-s1 text-[13px]"
                    style={{
                      borderColor: on ? `var(--t-island-${token})` : "var(--t-border-card)",
                      background: on ? `color-mix(in srgb, var(--t-island-${token}) 14%, transparent)` : "var(--t-surface-card)",
                      color: on ? `var(--t-island-${token})` : "var(--t-text-body)",
                      fontWeight: on ? 600 : 400,
                    }}
                  >
                    <span aria-hidden className="size-[8px] rounded-full" style={{ background: `var(--t-island-${token})` }} />
                    {nameOf(id)}
                    {p.origin?.id === id && (
                      <span aria-label="출발 영토" className="size-[6px] rounded-full" style={{ background: "var(--t-accent)" }} />
                    )}
                  </button>
                );
              })}
            </>
          )
        )}
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden rounded-[14px] border border-edge bg-canvas">
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            backgroundImage: "radial-gradient(var(--t-border-card) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
            opacity: 0.35,
          }}
        />

        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="absolute inset-0 size-full"
          role="img"
          aria-label={p.pair ? "섬 간 관계 그래프" : `${centerName} 중심 관계 그래프`}
          onClick={() => p.onSelect(null)}
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

          {/* 선 */}
          {graph.edges.map(({ v, d }) => {
            const on = sel?.rel.id === v.rel.id;
            const dimmed = sel && !on;
            const pick = (e: MouseEvent) => {
              e.stopPropagation();
              if (p.pair) p.onPairPick(v);
              else p.onSelect(on ? null : v.rel.id);
            };
            return (
              <g key={v.rel.id} className="cursor-pointer" onClick={pick}>
                <path d={d} fill="none" stroke="transparent" strokeWidth={16} />
                <path
                  d={d}
                  fill="none"
                  stroke={`var(--t-rel-${v.rel.kind})`}
                  strokeWidth={on ? 3 : 1.8}
                  strokeDasharray={CONF_DASH[v.rel.confidence] || undefined}
                  strokeLinecap="round"
                  markerEnd={`url(#rel-arrow-${v.rel.kind})`}
                  opacity={dimmed ? 0.15 : on ? 1 : 0.85}
                />
              </g>
            );
          })}

          {/* 선 라벨 — 「Recruitment 14건」 (설계서 4.3.6) */}
          {graph.edges.map(({ v, mid }) => {
            const on = sel?.rel.id === v.rel.id;
            const name = KIND_NAME[v.rel.kind];
            const w = textWidth(name, 13) + textWidth(`${v.count}건`, 12) + 34;
            return (
              <g
                key={`l-${v.rel.id}`}
                transform={`translate(${mid.x - w / 2} ${mid.y - 13})`}
                className="cursor-pointer"
                opacity={sel && !on ? 0.3 : 1}
                onClick={(e) => {
                  e.stopPropagation();
                  if (p.pair) p.onPairPick(v);
                  else p.onSelect(on ? null : v.rel.id);
                }}
              >
                <rect
                  width={w}
                  height={26}
                  rx={6}
                  fill={on ? `var(--t-rel-${v.rel.kind})` : "var(--t-surface-panel)"}
                  stroke={on ? `var(--t-rel-${v.rel.kind})` : "var(--t-border-card)"}
                />
                {!on && <circle cx={13} cy={13} r={3.5} fill={`var(--t-rel-${v.rel.kind})`} />}
                <text x={on ? 12 : 23} y={17.5} fontSize={13} fontWeight={600}>
                  <tspan fill={on ? "var(--t-text-on-accent)" : "var(--t-text-title)"}>{name}</tspan>
                  <tspan dx={6} fontSize={12} fontWeight={400} fill={on ? "var(--t-text-on-accent)" : "var(--t-text-label)"}>
                    {v.count}건
                  </tspan>
                </text>
              </g>
            );
          })}

          {/* 노드 */}
          {[...graph.nodes.values()].map((n) => {
            const isCenter = n.id === p.center && !p.pair;
            const c = `var(--t-island-${n.t.token})`;
            const faded = sel && !onSel(n.id);
            return (
              <g
                key={n.id}
                className={isCenter ? "" : "cursor-pointer"}
                opacity={faded ? 0.35 : 1}
                onClick={(e) => {
                  e.stopPropagation();
                  if (!isCenter) p.onCenter(n.id);
                }}
              >
                <title>{isCenter ? n.t.name : `${n.t.name} — 눌러서 중심으로`}</title>
                {isCenter && (
                  <polygon points={hexPoints(n.x, n.y, n.r + 6)} fill="none" stroke={c} strokeWidth={2} opacity={0.9} />
                )}
                {n.actor ? (
                  <>
                    <polygon points={hexPoints(n.x, n.y, n.r)} fill="var(--t-surface-card)" stroke={c} strokeWidth={1.5} />
                    <TeamMark cx={n.x} cy={n.y} size={n.r} />
                  </>
                ) : (
                  <polygon
                    points={hexPoints(n.x, n.y, n.r)}
                    fill={c}
                    stroke="var(--t-border-hex)"
                    strokeWidth={1}
                    strokeDasharray={empty && isCenter ? "4 3" : undefined}
                    fillOpacity={empty && isCenter ? 0.25 : 1}
                  />
                )}
                {n.side === "below" ? (
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
        </svg>

        {/* 범례 — 관계 종류 일곱, 신뢰도 셋 (설계서 4.3.6) */}
        <div className="pointer-events-none absolute left-s4 top-s4 flex w-[190px] flex-col gap-s3 rounded-[12px] border border-edge bg-panel px-s4 py-s4">
          <h3 className="text-[11px] text-label">관계 유형</h3>
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
        </div>

        {/* 근거 팝오버 — 피그마 ⑦-8e 「선택한 관계 · Evidence」 */}
        {sel && (
          <div className="absolute right-s4 top-s4 flex w-[330px] flex-col gap-s3 rounded-[12px] border border-edge bg-panel px-s5 py-s4 shadow-lg">
            <p className="text-[11px] text-label">선택한 관계 · Evidence</p>
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
              <dt className="text-label">근거 사건</dt>
              <dd className="text-title tabular-nums">{sel.fromRegistry ? "없음" : `${sel.evidence.length}건`}</dd>
            </dl>
            {sel.fromRegistry && sel.rel.note ? (
              <div className="flex flex-col gap-s1">
                <p className="text-[11px] text-label">명부 「연결된 곳」 원문</p>
                <p className="break-all rounded-[8px] bg-card px-s3 py-s2 font-mono text-[12px] leading-[1.6] text-body">
                  {sel.rel.note}
                </p>
              </div>
            ) : (
              <p className="text-[12px] leading-[1.7] text-body">
                {sel.fromRegistry
                  ? "근거 사건 없이 명부의 「연결된 곳」 칸에서 만든 관계입니다."
                  : "근거 사건 목록은 오른쪽 패널에 있습니다."}
              </p>
            )}
          </div>
        )}

        {/* 관계 없음 — 피그마 ⑦-8g */}
        {empty && (
          <div className="absolute bottom-[84px] left-1/2 flex w-[440px] -translate-x-1/2 flex-col items-center gap-s3 rounded-[14px] border border-edge bg-panel px-s6 py-s5 text-center">
            <h3 className="text-[15px] font-semibold text-title">
              {p.center ? "관계가 없습니다" : "이 기준일에 기록된 관계가 없습니다"}
            </h3>
            <p className="text-[12px] leading-[1.7] text-body">
              {p.center
                ? `${centerName}${josa(centerName, "과", "와")} 연결된 관계가 이 기준일에는 없습니다. 위 칩 줄에서 다른 영토를 골라 보세요.`
                : "기준일을 옮기면 관계가 보일 수 있습니다."}
            </p>
            {p.moveTo && (
              <button
                type="button"
                onClick={p.onMove}
                className="rounded-[8px] px-s4 py-s2 text-[13px] font-semibold text-on-accent"
                style={{ background: "var(--t-accent)" }}
              >
                {quarterText(p.moveTo)} 부터 관계 확인 · 기준일 옮기기
              </button>
            )}
          </div>
        )}

        <div
          className="pointer-events-none absolute left-s5 flex items-center gap-s2 rounded-full border border-edge bg-panel px-s4 text-[12px] text-body"
          style={{ bottom: "var(--s-5)", height: "var(--h-hint)" }}
        >
          <span aria-hidden className="size-[6px] rounded-full" style={{ background: "var(--t-accent)" }} />
          {empty
            ? "관계 없음 · 칩 줄에서 다른 영토를 고르세요"
            : p.pair
              ? "섬 간 보기 · 선을 누르면 그 관계로 이동"
              : sel
                ? "선택한 관계선 강조 · 나머지 흐리게 · 근거 팝오버"
                : "관계선 클릭 → 근거(Evidence) 표시"}
        </div>
      </div>
    </div>
  );
}
