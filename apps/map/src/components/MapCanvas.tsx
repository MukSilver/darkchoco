/**
 * 지도 캔버스 — 설계서 4.2.3.
 *
 * 줌은 50~200%, 25% 단위다. 휠과 +/− 단추 둘 다 받는다. 드래그로 옮기고
 * 「전체 보기」로 처음 자리(100%, 가운데)로 돌아온다.
 *
 * **포인터를 캡처하지 않는다.** 드래그 중 포인터가 캔버스를 벗어나도 따라오게
 * 하려고 `setPointerCapture` 를 걸었더니, 캡처가 걸린 뒤로는 `pointerup` 과
 * `click` 의 `target` 이 캡처한 요소로 고정돼 **무엇을 눌렀는지 알 수 없었다.**
 * 섬 이름표를 눌러도 선택이 안 됐다. 캡처를 걷고 `pointermove` 에서 단추가
 * 눌린 상태인지(`e.buttons`)로 드래그를 가른다.
 *
 * **d3-zoom 을 안 쓰고 직접 했다.** 설계서가 요구하는 것은 25% 단위 이산
 * 확대와 드래그뿐이라 변환 하나면 끝난다. d3-zoom 을 끼우면 그 쪽이 갖는
 * 연속 배율과 우리 25% 단위를 맞추는 코드가 더 길어진다. 관성이나 더블클릭
 * 확대가 필요해지면 그때 바꾼다.
 *
 * **「전체 관계 보기」 토글은 안 만들었다.** 피그마 기본 화면 우측 상단에
 * 보이지만, 설계서 4.2.7 이 「1차 개발 범위에서 제외」라고 못박았고 피그마
 * 그림 캡션도 「(보류)」다. 둘이 같은 말을 한다.
 *
 * **고른 영토가 화면 밖이면 옮긴다** (설계서 4.2.3 「영토 선택 시 줌 유지, 화면
 * 밖이면 보이는 위치로 이동」 · 4.2.2 「지도 이동 후 영토 선택」). 부모가 `reveal`
 * 에 영토 id 를 주면 그림이 끝난 뒤 이름표 자리를 재 보고, 밖이면 이동만 바꿔
 * `onRevealed` 로 돌려준다. 옮기기 · 줌 · 전체 보기는 `--dur-base` 동안 옮겨 간다(끄는 동안은
 * 끈다, 2026-09-28 최현서 1 · 7번). 움직임 줄이기를 켠 사람에게는 단번이다.
 * 기준일을 옮기며 고른 경우(검색)도 새 배치로 재야 해서 그림 뒤에 잰다.
 */

"use client";

import { useCallback, useEffect, useEffectEvent, useRef, useState } from "react";

import HexMap from "./HexMap";
import HoverTip from "./HoverTip";
import type { MapLayout } from "@/lib/layout";
import { revealPan } from "@/lib/mapui";
import type { RelView } from "@/lib/relations";

/** 설계서 4.2.3 — 50%~200%, 25% 단위 */
const ZOOM_MIN = 50;
const ZOOM_MAX = 200;
const ZOOM_STEP = 25;

/**
 * 지도 판의 위아래 여백 (px). 아래는 힌트 알약과 줌 단추가 앉을 자리다 — 안 두면
 * 섬이 가린다. 화면 밖 판정(`revealPan`)이 같은 값을 써야 해서 상수로 둔다
 */
const PAD_TOP = 16;
const PAD_BOTTOM = 64;

export type MapSelection =
  | { kind: "none" }
  | { kind: "island"; key: string; name: string }
  | { kind: "territory"; id: string; name: string };

/**
 * 지도 아래 힌트 문구 — 설계서 4.2.3.
 *
 * **설계서의 그 표는 칸이 한 줄씩 밀려 있다.** 글자만 뽑으면 「선택 없음」
 * 줄에 섬 선택 문구가 붙어 보인다. 피그마 기본 화면(선택 없음)의 힌트가
 * 「섬 이름 클릭 → …」이므로 한 줄씩 당겨 읽은 것이 맞다.
 *
 * **지나간 분기를 보고 있으면 선택 없음 문구가 스냅샷 안내로 바뀐다** (피그마
 * ⑦-1a · ⑦-1b 「2024-09 기준 · 슬라이더를 옮기면 누적 사건만큼 칸이 늘어남」).
 * 고른 것이 있으면 선택 문구가 먼저다 — 그쪽이 지금 무엇이 보이는지를 말한다.
 */
function hintText(sel: MapSelection, snapshot: string | null): string {
  if (sel.kind === "island") {
    return `${sel.name} 섬 선택됨 · 영토를 클릭하면 관계선 표시`;
  }
  if (sel.kind === "territory") {
    return `${sel.name} 선택됨 · 연결된 영토만 표시 중`;
  }
  if (snapshot) {
    // 칸 총수는 분기와 상관없이 800 이라(설계서 3.1) 「칸이 늘어남」은 계산과 맞지 않았다.
    // 늘거나 주는 것은 섬 · 영토의 칸 비중이다 (2026-09-28 코드 분석, 피그마 ⑦-1a 문구를 고침)
    return `${snapshot} 기준 · 슬라이더를 옮기면 누적 사건만큼 칸 비중이 바뀜`;
  }
  return "섬 이름 클릭 → 섬 정보 · 영토 클릭 → 관계선";
}

/** 줌과 이동. 관계 탭에서 돌아올 때 그대로 되살리려고 부모가 들고 있는다 (설계서 4.3.3) */
export type MapView = { zoom: number; pan: { x: number; y: number } };

export const MAP_VIEW_HOME: MapView = { zoom: 100, pan: { x: 0, y: 0 } };

export type MapCanvasProps = {
  layout: MapLayout;
  /** 그릴 틀. 모든 분기를 합친 크기 틀이다(`centerBox`). 없으면 `layout.viewBox` */
  viewBox?: string;
  selection: MapSelection;
  onSelect: (sel: MapSelection) => void;
  /** 영토 id → 최근 관측일 `MM-DD`. 툴팁 다섯째 줄에 쓴다 */
  lastSeen: Record<string, string>;
  view: MapView;
  onView: (v: MapView) => void;
  /** 관계선과 진하기. `HexMap` 에 그대로 넘긴다 (설계서 4.2.3 · 4.3.3) */
  lines?: readonly RelView[];
  lit?: ReadonlySet<string>;
  raised?: ReadonlySet<string>;
  litIslands?: ReadonlySet<string>;
  /** 힌트 문구를 바꿔 낼 때. 검색 결과로 왔을 때 쓴다 (피그마 ⑦-10b) */
  hint?: string;
  /** 지나간 분기 스냅샷 이름(`2025 Q3`). 가장 최근 분기면 없다. 선택 없음 힌트가 쓴다 */
  snapshot?: string | null;
  /** 화면 밖이면 보이게 옮길 영토 id. 고를 때마다 부모가 채운다 */
  reveal?: string | null;
  /** `reveal` 을 다 봤다. 옮겨야 했으면 새 줌 · 이동, 아니면 `null` */
  onRevealed?: (v: MapView | null) => void;
};

/** 마우스 자리와 그때의 캔버스 크기 (px). 툴팁이 가장자리에서 뒤집을 때 쓴다 */
type At = { x: number; y: number; w: number; h: number };

export default function MapCanvas({
  layout,
  viewBox,
  selection,
  onSelect,
  lastSeen,
  view,
  onView,
  lines,
  lit,
  raised,
  litIslands,
  hint,
  snapshot = null,
  reveal = null,
  onRevealed,
}: MapCanvasProps) {
  const { zoom, pan } = view;
  const setPan = (p: MapView["pan"]) => onView({ zoom, pan: p });
  const [hover, setHover] = useState<({ id: string } & At) | null>(null);
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(
    null,
  );
  const moved = useRef(false);
  // 왼쪽 단추로 판을 쥐고 있나. 커서 모양과 전환을 끄고 켜는 데 쓴다 (`drag` 는 다시 그리지 않는 값이다)
  const [grabbing, setGrabbing] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  /**
   * 마지막 마우스 자리. 툴팁이 **처음 뜰 때** 여기 뜬다.
   *
   * 호버가 시작되는 순간에는 아직 `pointermove` 가 안 와서 좌표를 모른다.
   * 0,0 으로 두면 툴팁이 캔버스 왼쪽 위에 붙었다가 다음 움직임에 튄다.
   */
  const at = useRef<At>({ x: 0, y: 0, w: 0, h: 0 });

  const hovered = hover
    ? layout.territories.find((t) => t.territoryId === hover.id)
    : undefined;
  const hoveredIsland = hovered
    ? layout.islands.find((i) => i.islandKey === hovered.islandKey)
    : undefined;

  const reset = useCallback(() => onView(MAP_VIEW_HOME), [onView]);

  /**
   * 고른 영토가 판 밖이면 옮긴다 (설계서 4.2.3). 그림이 끝난 뒤에 재야 캔버스
   * 크기와 새 배치가 맞다. 그 사이 선택이 바뀌었으면(Esc 따위) 옮기지 않고 다 본
   * 것으로 돌려준다 — 안 돌려주면 다음에 지도 탭으로 올 때 엉뚱한 곳으로 옮긴다
   */
  const revealNow = useEffectEvent((id: string) => {
    const el = box.current;
    const t = layout.territories.find((x) => x.territoryId === id);
    const picked = selection.kind === "territory" && selection.id === id;
    const next =
      el && t && picked
        ? revealPan(
            t.label,
            viewBox ?? layout.viewBox,
            { w: el.clientWidth, h: el.clientHeight, top: PAD_TOP, bottom: PAD_BOTTOM },
            view,
          )
        : null;
    onRevealed?.(next ? { zoom, pan: next } : null);
  });
  useEffect(() => {
    if (reveal) revealNow(reveal);
  }, [reveal]);

  const step = (by: number) =>
    onView({ pan, zoom: Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom + by)) });

  return (
    <div
      ref={box}
      className="relative flex-1 overflow-hidden rounded-[14px] border border-edge bg-canvas"
    >
      {/* 점 격자 바탕. 피그마 캔버스에 깔려 있다 */}
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(var(--t-border-card) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
          opacity: 0.35,
        }}
      />

      {/* 아래쪽 여백은 힌트 알약과 줌 단추가 앉을 자리다 (`PAD_BOTTOM`) */}
      {/*
        끄는 판. 손 커서(끄는 동안 쥔 손)로 끌 수 있다는 것을 알린다 (2026-09-28 코드 분석).
        영토 · 섬 이름표 위에서는 손가락 커서가 이긴다
      */}
      <div
        className={"absolute inset-0 touch-none " + (grabbing ? "cursor-grabbing" : "cursor-grab")}
        style={{ paddingTop: PAD_TOP, paddingBottom: PAD_BOTTOM }}
        onWheel={(e) => step(e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP)}
        onPointerDown={(e) => {
          drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y };
          moved.current = false;
          if (e.buttons & 1) setGrabbing(true);
        }}
        onPointerMove={(e) => {
          const r = box.current?.getBoundingClientRect();
          if (r) {
            at.current = {
              x: e.clientX - r.left,
              y: e.clientY - r.top,
              w: r.width,
              h: r.height,
            };
            setHover((h) => (h ? { ...h, ...at.current } : h));
          }
          const d = drag.current;
          // 왼쪽 단추를 놓은 채 지나가는 것은 드래그가 아니다. 캔버스 밖에서
          // 놓고 돌아온 경우도 여기서 걸러진다
          if (!d || (e.buttons & 1) === 0) {
            drag.current = null;
            setGrabbing(false);
            return;
          }
          if (Math.hypot(e.clientX - d.x, e.clientY - d.y) > 3) {
            moved.current = true;
          }
          setPan({ x: d.px + (e.clientX - d.x), y: d.py + (e.clientY - d.y) });
        }}
        onPointerUp={() => {
          drag.current = null;
          setGrabbing(false);
        }}
        onPointerLeave={() => {
          drag.current = null;
          setGrabbing(false);
        }}
        onClick={(e) => {
          // 끌고 놓은 것은 클릭이 아니다
          if (moved.current) return;
          const hit =
            e.target instanceof Element
              ? e.target.closest("[data-pick]")
              : null;
          const id = hit?.getAttribute("data-id") ?? "";

          if (hit?.getAttribute("data-pick") === "island") {
            const i = layout.islands.find((x) => x.islandKey === id);
            if (i) onSelect({ kind: "island", key: id, name: i.name });
            return;
          }
          if (hit?.getAttribute("data-pick") === "territory") {
            const tt = layout.territories.find((x) => x.territoryId === id);
            if (tt) onSelect({ kind: "territory", id, name: tt.name });
            return;
          }
          // 설계서 4.2.3 — 빈 곳 클릭이면 선택 해제
          onSelect({ kind: "none" });
        }}
      >
        {layout.islands.length === 0 && (
          // 스냅샷을 수집 시작 전으로 옮기면 그릴 것이 없다. 빈 캔버스만
          // 두면 고장난 것처럼 보인다
          <p className="flex size-full items-center justify-center text-[13px] text-label">
            이 기준일까지 올라온 사건이 없습니다
          </p>
        )}
        <div
          className="size-full"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom / 100})`,
            transformOrigin: "center center",
            // 줌 · 전체 보기 · 화면 밖 영토로 옮기기는 짧게 옮겨 간다. 끄는 동안은 손을 바로
            // 따라가야 해서 끈다 (2026-09-28 최현서 1 · 7번 — 전에는 한 번에 뛰었다)
            transition: grabbing ? "none" : "transform var(--dur-base) var(--ease-out)",
          }}
        >
          <HexMap
            layout={layout}
            viewBox={viewBox}
            selectedTerritory={
              selection.kind === "territory" ? selection.id : undefined
            }
            selectedIsland={
              selection.kind === "island" ? selection.key : undefined
            }
            hovered={hover?.id ?? null}
            onHoverTerritory={(id) =>
              setHover(id ? { id, ...at.current } : null)
            }
            lines={lines}
            lit={lit}
            raised={raised}
            litIslands={litIslands}
          />
        </div>
      </div>

      {hovered && hoveredIsland && hover && (
        <HoverTip
          territory={hovered}
          islandName={hoveredIsland.name}
          lastSeen={lastSeen[hovered.territoryId] ?? null}
          at={{ x: hover.x, y: hover.y }}
          box={{ w: hover.w, h: hover.h }}
        />
      )}

      <div
        className="pointer-events-none absolute left-s5 flex items-center gap-s2 rounded-full border border-edge bg-panel px-s4 text-[12px] text-body"
        style={{ bottom: "var(--s-5)", height: "var(--h-hint)" }}
      >
        <span
          aria-hidden
          className="size-[6px] rounded-full"
          style={{ background: "var(--t-accent)" }}
        />
        {hint ?? hintText(selection, snapshot)}
      </div>

      <div
        className="absolute right-s5 flex items-center gap-s3"
        style={{ bottom: "var(--s-5)" }}
      >
        <div
          className="flex items-center rounded-full border border-edge bg-panel"
          style={{ height: "var(--h-zoom)" }}
        >
          <button
            type="button"
            aria-label="축소"
            disabled={zoom <= ZOOM_MIN}
            onClick={() => step(-ZOOM_STEP)}
            className="h-full rounded-l-full px-s4 text-[13px] text-body hover-seg disabled:text-disabled"
          >
            −
          </button>
          <span className="w-[52px] text-center text-[12px] tabular-nums text-body">
            {zoom}%
          </span>
          <button
            type="button"
            aria-label="확대"
            disabled={zoom >= ZOOM_MAX}
            onClick={() => step(ZOOM_STEP)}
            className="h-full rounded-r-full px-s4 text-[13px] text-body hover-seg disabled:text-disabled"
          >
            +
          </button>
        </div>
        <button
          type="button"
          onClick={reset}
          className="flex items-center gap-s2 rounded-full border border-edge bg-panel px-s4 text-[12px] text-body hover-edge"
          style={{ height: "var(--h-zoom)" }}
        >
          <span aria-hidden>⛶</span>
          전체 보기
        </button>
      </div>
    </div>
  );
}
