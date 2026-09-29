/**
 * 타임라인 탭 — 설계서 4.3.7.
 *
 * 연도 칩으로 시점을 옮기고, 그 시점의 지도와 섬별 누적 추이를 본다.
 * **모든 값이 누적이다.** 그 시점까지의 사건 전부를 센다.
 *
 * **판 1.2 에서 단위가 해에서 분기로 바뀌었다** (설계서 4.3.7 「단위는 분기.
 * 한 해에 4 시점」). 연도 칩은 남아 있고 누르면 그 해 3분기로 간다. 그 해에
 * 3분기가 없으면(첫 해 · 올해) 데이터 안에서 가장 가까운 분기다 (`chipQuarter`).
 * ◀ / ▶▶ 는 한 해씩, 재생은 한 분기씩 옮긴다.
 *
 * 설계서는 「기준 시점은 스냅샷 바와 같은 값」이라고 적었다. 여기서 시점을
 * 옮기면 지도 탭의 기준일도 같이 움직인다.
 *
 * **시점 비교(⑦-9c)** 를 켜면 지도 두 장을 나란히 놓고 오른쪽 열이 변화 요약으로
 * 바뀐다. 연도 칩을 누르면 A → B 차례로 찍히고, 끄면 B 시점 한 장짜리로 돌아온다.
 * 비교 상태는 제목 옆 설명(「시점 비교 · A … ↔ B …」)도 읽어 화면(page)이 들고 있다.
 */

"use client";

import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";

import MapCanvas, { type MapSelection, type MapView } from "./MapCanvas";
import PlayGlyph from "./PlayGlyph";
import { islandToken } from "@/lib/islands";
import type { MapLayout } from "@/lib/layout";
import { parseQuarter, quarterText } from "@/lib/quarter";
import type { IslandCode } from "@/lib/types";
import {
  comparePick,
  compareStart,
  diff,
  growth,
  peakOf,
  stepYear,
  canPick,
  centerBox,
  thumbBoxes,
  yearCards,
  yearChips,
  type Compare,
  type Diff,
  type Snapshot,
} from "@/lib/timeline";

/** 재생 속도. 설계서 4.3.7 의 1× / 2× / 4× 다. 1× 가 1초에 한 분기 */
const SPEEDS = [1, 2, 4] as const;

export type TimelineTabProps = {
  snaps: Snapshot[];
  /** 지금 보고 있는 분기 (`2026-Q3`) */
  current: string;
  onPick: (q: string) => void;
  /** 시점 비교 상태. 꺼져 있으면 null (설계서 4.3.7 L811-816) */
  compare: Compare | null;
  onCompare: (c: Compare | null) => void;
  playing: boolean;
  onPlaying: (v: boolean) => void;
  speed: number;
  onSpeed: (v: number) => void;
  /** 섬 코드 → 이름 */
  nameOf: (islandId: string) => string;
  /**
   * 모든 분기를 합친 지도 크기 (`boxSize`). Historical Map 과 시점 비교 A/B 가 이 크기 틀로
   * 그려 분기마다 축척이 같다 (G-10 묶음 4). 없으면 분기마다 제 칸에 맞춘다
   */
  mapSize?: { w: number; h: number };
  /**
   * 지도에서 고른 것. 타임라인 지도(Historical Map · 시점 비교)도 같은 선택을 쓰고, 누르면
   * 지도처럼 고른다 — 「블록의 기능은 2D 지도와 같다」 (2026-09-28 최현서 3번)
   */
  selection: MapSelection;
  onSelect: (s: MapSelection) => void;
  /** 분기 → 영토 최근 관측일(`MM-DD`). 툴팁 다섯째 줄 */
  lastSeenAt: (ym: string) => Record<string, string>;
  /** 타임라인 지도 줌 · 이동. Historical Map 과 시점 비교 A · B 가 같이 쓴다 — 두 장이 같이 움직인다 */
  view: MapView;
  onView: (v: MapView) => void;
};

const NO_SELECTION: MapSelection = { kind: "none" };

/** 타임라인 지도 힌트. 관계선은 안 그리므로 지도 탭 문구와 다르다 */
function timelineHint(sel: MapSelection): string {
  if (sel.kind === "territory") return `${sel.name} 선택됨 · 오른쪽 패널에 정보`;
  if (sel.kind === "island") return `${sel.name} 섬 선택됨`;
  return "영토에 마우스를 올리면 정보 · 누르면 선택";
}

export default function TimelineTab({
  snaps,
  current,
  onPick,
  compare,
  onCompare,
  playing,
  onPlaying,
  speed,
  onSpeed,
  nameOf,
  mapSize,
  selection,
  onSelect,
  lastSeenAt,
  view,
  onView,
}: TimelineTabProps) {
  /** 분기 지도의 틀. 합친 크기가 있으면 그 크기로 넓혀 제 가운데에 놓는다 */
  const boxOf = (layout: MapLayout) => (mapSize ? centerBox(layout.viewBox, mapSize) : layout.viewBox);
  // 지도 판을 쥐고 있나 — 시점 비교 A · B 가 같이 써서 끄는 동안 두 장이 함께 움직인다
  const [grab, setGrab] = useState(false);

  /**
   * 분기 지도 한 장 — 지도 탭과 같은 캔버스(줌 · 끌기 · 툴팁 · 고르기). 전에는 그림만 그려서 줌도
   * 툴팁도 없고, 영역 이름표만 있는 영토(hive · lockbit2 따위)는 어디까지인지 알 수 없었다
   * (최현서 3번). 그 분기 지도에 없는 선택은 없는 것으로 본다(지도 탭 `liveSelection` 과 같게).
   * `badge` 는 힌트 알약 자리에 대신 낸다(「재생 중」). 판을 쥔 상태(`grab`)는 A · B 가 같이 쓴다
   */
  const mapOf = (snap: Snapshot, label: string, badge?: ReactNode) => {
    const has =
      selection.kind === "territory"
        ? snap.layout.territories.some((t) => t.territoryId === selection.id)
        : selection.kind === "island"
          ? snap.layout.islands.some((i) => i.islandKey === selection.key)
          : true;
    const sel = has ? selection : NO_SELECTION;
    return (
      <MapCanvas
        layout={snap.layout}
        viewBox={boxOf(snap.layout)}
        selection={sel}
        onSelect={onSelect}
        lastSeen={lastSeenAt(snap.ym)}
        view={view}
        onView={onView}
        framed={false}
        label={label}
        hint={timelineHint(sel)}
        badge={badge}
        grab={grab}
        onGrab={setGrab}
      />
    );
  };
  const at = Math.max(
    0,
    snaps.findIndex((s) => s.ym === current),
  );
  const now = snaps[at];

  const keys = useMemo(() => snaps.map((s) => s.ym), [snaps]);
  /** 연도 칩 — 해마다 그 해 3분기(없으면 가장 가까운 분기) (설계서 4.3.7 L797) */
  const chips = useMemo(() => yearChips(snaps), [snaps]);
  /** 시점별 스냅샷 카드 — 해마다 한 장, 최신이 위 (L807, 피그마 ⑦-9b) */
  const cards = useMemo(() => {
    const list = yearCards(snaps);
    const boxes = thumbBoxes(list.map((c) => c.snap.layout.viewBox));
    return list.map((c, i) => ({ ...c, box: boxes[i] })).reverse();
  }, [snaps]);
  /** 추이 그래프 세로축과 성장 요약 막대가 같은 눈금을 쓴다 (피그마 ⑦-9b 막대 = 축 140 기준) */
  const peak = useMemo(() => peakOf(snaps), [snaps]);
  const info = useMemo(
    () => (id: string) => ({
      name: nameOf(id),
      token: islandToken(id as IslandCode),
    }),
    [nameOf],
  );

  const cmpA = compare ? snaps.find((s) => s.ym === compare.a) : undefined;
  const cmpB = compare ? snaps.find((s) => s.ym === compare.b) : undefined;

  const 변화 = useMemo(
    () => (cmpA && cmpB ? diff(cmpA, cmpB, info) : null),
    [cmpA, cmpB, info],
  );

  /*
   * **비교 중에는 기준 시점이 곧 B 다.** B 를 옮길 때마다 기준 시점도 옮겨 둔다.
   * 그래야 끄거나 탭을 옮겼을 때 따로 맞출 것 없이 B 시점 화면이다 (L816), 옆 패널도
   * B 시점 값을 보인다.
   */
  const toggleCompare = () => {
    if (compare) {
      // 끄면 B 시점 한 장짜리로 돌아간다 (설계서 4.3.7 L816)
      onPick(compare.b);
      onCompare(null);
      return;
    }
    // 처음 켤 때 A 는 3년 전 같은 분기, B 는 최근 분기 (L813)
    const c = compareStart(keys);
    if (!c) return;
    onCompare(c);
    onPick(c.b);
    onPlaying(false);
  };

  /**
   * 연도 칩. 비교 중이면 지금 고르는 쪽(A · B 고르기 단추)을 그 시점으로 바꾼다 — 설계서 L812 는
   * 「첫 번째 클릭이 A, 두 번째가 B」였다 (2026-09-28 최현서 8번). 못 찍는 칩은 꺼져 있다
   */
  const pickYear = (q: string) => {
    if (!compare) {
      onPick(q);
      return;
    }
    const c = comparePick(compare, q);
    onCompare(c);
    onPick(c.b);
  };

  /**
   * 재생 — 한 분기씩 넘기고 끝에서 멈춘다 (설계서 4.3.7).
   *
   * 비교 중에는 안 넘긴다. 두 시점을 견주는 중에 시점이 저절로 움직이면
   * 사람이 무엇을 보고 있는지 놓친다. 단추도 꺼 둔다 (피그마 ⑦-9c).
   */
  useEffect(() => {
    if (!playing || compare) return;
    if (at >= snaps.length - 1) {
      onPlaying(false);
      return;
    }
    const id = setTimeout(() => onPick(snaps[at + 1].ym), 1000 / speed);
    return () => clearTimeout(id);
  }, [playing, compare, at, snaps, speed, onPick, onPlaying]);

  /** 성장 요약. 평소에는 첫 시점 → 지금, 비교 중에는 A → B (L809, 피그마 ⑦-9c) */
  const rows = useMemo(() => {
    if (변화) return growth(변화.a, 변화.b, info);
    return now ? growth(snaps[0], now, info) : [];
  }, [변화, snaps, now, info]);

  if (!now) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-[14px] border border-edge bg-canvas text-[13px] text-label">
        시점을 만들 사건이 없습니다
      </div>
    );
  }

  // ◀ / ▶▶ 는 한 해씩 (L798). 비교 중에는 연도 칩으로만 A · B 를 옮긴다 (피그마 ⑦-9c)
  const prevYear = stepYear(keys, now.ym, -1);
  const nextYear = stepYear(keys, now.ym, 1);
  const last = snaps[snaps.length - 1];
  /** 눈금 이름표를 앉힐 자리 — 연도 칩이 가리키는 분기 */
  const ticks = chips.map((c) => ({ year: c.year, i: keys.indexOf(c.snap.ym) }));
  /** 굵게 낼 해. 평소에는 지금 해, 비교 중에는 A 와 B 의 해 */
  const boldYears = 변화 ? [변화.a.year, 변화.b.year] : [now.year];

  return (
    <div className="flex min-h-0 flex-1 gap-s4 overflow-hidden">
      {/*
        왼쪽 칸은 폭이 바뀐다 — 상세 패널이 탭을 옮겨도 펼쳐진 채 남아서(최현서 2번) 1280 창에서는
        약 400px 이다. 칸 폭을 보고(`@container`) 아래 줄을 쌓는다 (2026-09-28 검토)
      */}
      <div className="@container flex min-h-0 min-w-0 flex-1 flex-col gap-s4 overflow-y-auto">
        {/*
          연도 칩 · 재생 줄. 좁으면 재생 줄이 다음 줄로 내려간다 — 전에는 연도 칩이 못 줄어
          「시점 비교」 글자가 접혔다 (2026-09-28 코드 분석, 1280 창)
        */}
        <div className="flex shrink-0 flex-wrap items-center gap-s4">
          <nav
            aria-label="시점 고르기"
            className="flex min-w-0 max-w-full gap-s1 overflow-x-auto rounded-[12px] bg-track p-[3px] [scrollbar-width:thin] [scrollbar-color:var(--t-border-strong)_transparent]"
          >
            {chips.map(({ year, snap }) => {
              const marks = compare
                ? [
                    parseQuarter(compare.a).year === year ? "A" : null,
                    parseQuarter(compare.b).year === year ? "B" : null,
                  ].filter(Boolean)
                : [];
              const on = compare ? marks.length > 0 : now.year === year;
              // 지금 고르는 쪽에 못 찍는 칩 — 같은 시점이거나 A 가 B 보다 늦어진다. 누르기를 막고,
              // 마우스를 올리거나 키보드 초점이 오면 붉게 바뀌어 안 된다는 것을 알린다 (최현서 8번
              // 「해제 전에 안 된다는 것을 색 변화로」). disabled 로 끄면 키보드 초점에서 빠져 안내가
              // 안 닿았다 (2026-09-29 묶음 7 검토)
              const side = compare?.active ?? "a";
              const own = compare ? (side === "a" ? compare.a : compare.b) === snap.ym : false;
              const blocked = compare ? !own && !canPick(compare, snap.ym) : false;
              return (
                <button
                  key={year}
                  type="button"
                  aria-current={on ? "page" : undefined}
                  aria-disabled={blocked || undefined}
                  onClick={() => {
                    if (!blocked) pickYear(snap.ym);
                  }}
                  title={
                    compare
                      ? blocked
                        ? side === "a"
                          ? `A 는 B(${quarterText(compare.b)})보다 앞선 시점이어야 합니다 · B 를 먼저 옮기세요`
                          : `B 는 A(${quarterText(compare.a)})보다 뒤 시점이어야 합니다 · A 를 먼저 옮기세요`
                        : `${side === "a" ? "A" : "B"} 시점으로 찍기 · ${quarterText(snap.ym)}`
                      : quarterText(snap.ym)
                  }
                  // 고른 칸은 화면 탭(`ViewTabs`)처럼 테두리 있는 패널색 칸이다 — 전에는 bg-selected 가
                  // 통 색과 거의 같아 흐렸다. 안 고른 칸은 글자색을 단추가 들고 안쪽 줄이 물려받아
                  // 마우스를 올리면 두 줄이 같이 밝아진다 (2026-09-28 코드 분석, 최현서 1번)
                  className={[
                    "shrink-0 rounded-[10px] border px-s4 py-s2 text-center",
                    on ? "border-edge bg-panel" : "border-transparent text-label hover-seg",
                    "aria-disabled:cursor-not-allowed aria-disabled:text-disabled",
                    "aria-disabled:hover:border-danger aria-disabled:hover:text-danger",
                    "aria-disabled:focus-visible:border-danger aria-disabled:focus-visible:text-danger",
                  ].join(" ")}
                >
                  <div
                    className={
                      "text-[14px] tabular-nums " +
                      // 막힌 칩은 글자색을 단추에서 물려받아 붉게 바뀐다 — 반대쪽 시점을 든 칩도
                      (on ? "font-semibold " + (blocked ? "" : "text-strong") : "")
                    }
                  >
                    {year}
                  </div>
                  {/* 비교 중에는 건수 자리에 A · B 를 적는다 (피그마 ⑦-9c) */}
                  <div
                    className={
                      "text-[10px] tabular-nums " +
                      (marks.length ? "font-semibold " + (blocked ? "" : "text-accent") : on ? "text-label" : "")
                    }
                  >
                    {marks.length ? marks.join(" ") : `${snap.events}건`}
                  </div>
                </button>
              );
            })}
          </nav>

          {/*
            「시점 비교」 스위치 — 연도 칩 바로 뒤에 고정한다. 전에는 재생 조작 끝에 있어 비교를 켜면
          A · B 고르기 묶음이 칩 뒤에 끼어들며 스위치가 다음 줄로 밀려 자리가 바뀌었다 (2026-09-29 최현서
          v2 8번 「A · B 선택 단추와 자리를 바꾸면」). 마우스를 올리면 글자가 밝아지고 통이 한 단계 진해진다 — 전에는
            아무것도 안 바뀌었다 (2026-09-28 코드 분석, 최현서 1번). 글자색은 단추가 들고 글이
            물려받는다. 꺼진 단추는 안 바뀐다(`enabled`). 손잡이 · 통 전환은 토큰 시간이다
          */}
          {/* 높이 30 칸 — 재생 조작과 한 줄이든 혼자 한 줄이든 같은 자리에 앉는다 */}
          <div className="flex h-[30px] shrink-0 items-center">
          <button
            type="button"
            onClick={toggleCompare}
            disabled={snaps.length < 2}
            aria-pressed={compare !== null}
            className={[
              "group flex items-center gap-s2 text-[12px] enabled:hover:text-title disabled:text-disabled",
              compare ? "text-strong" : "text-label",
            ].join(" ")}
          >
            <span
              aria-hidden
              className={[
                "relative h-[16px] w-[30px] rounded-full transition-[background-color,filter] duration-[var(--dur-base)] ease-[var(--ease-out)]",
                compare
                  ? "bg-accent group-enabled:group-hover:brightness-110"
                  : "bg-track group-enabled:group-hover:bg-edge-strong",
              ].join(" ")}
            >
              <span
                className="absolute top-[2px] size-[12px] rounded-full bg-white transition-[left] duration-[var(--dur-base)] ease-[var(--ease-out)]"
                style={{ left: compare ? 16 : 2 }}
              />
            </span>
            <span>시점 비교</span>
          </button>
          </div>

          <div className="flex-1" />

          {/*
            재생 단추 줄 — 피그마 ⑦-9b · ⑦-9c, 시트 `07 / 02 Playback Control`.
            30px 네모 단추(모서리 8px) 넷을 6px 씩 띄운다. ◀ · ▶▶ 는 테두리 단추,
            재생은 강조색 채움이다. 꺼진 단추는 통째로 40% 로 흐린다 — ⑦-9c 에서 꺼진
            ◀ 의 테두리 · 그림이 둘 다 바탕과 40% 로 섞인 색이다.
            마우스 올림은 공통 규칙이다 — 테두리 단추는 hover-edge, 재생은 hover-accent (최현서 1번)
          */}
          <div className="flex shrink-0 items-center gap-[6px] whitespace-nowrap">
            <button
              type="button"
              aria-label="1년 전"
              disabled={compare !== null || prevYear === null}
              onClick={() => prevYear && onPick(prevYear)}
              className="grid size-[30px] place-items-center rounded-[8px] border border-edge text-body hover-edge disabled:opacity-40"
            >
              <PlayGlyph kind="prev" />
            </button>
            <button
              type="button"
              aria-label={playing ? "정지" : at >= snaps.length - 1 ? "처음부터 재생" : "재생"}
              title={!playing && at >= snaps.length - 1 ? "처음 시점부터 재생" : undefined}
              disabled={compare !== null}
              onClick={() => {
                // 끝(가장 최근 시점)에서 누르면 첫 시점으로 되감고 재생한다. 첫 화면이 끝이라
                // 전에는 첫 틱에 「끝이다」로 보고 바로 멈췄다 (2026-09-28 코드 분석). 스냅샷 바와 같은 규칙
                if (!playing && at >= snaps.length - 1 && snaps.length > 1) onPick(snaps[0].ym);
                onPlaying(!playing);
              }}
              className="grid size-[30px] place-items-center rounded-[8px] bg-accent text-on-accent hover-accent disabled:opacity-40"
            >
              <PlayGlyph kind={playing ? "pause" : "play"} />
            </button>
            <button
              type="button"
              aria-label="1년 후"
              disabled={compare !== null || nextYear === null}
              onClick={() => nextYear && onPick(nextYear)}
              className="grid size-[30px] place-items-center rounded-[8px] border border-edge text-body hover-edge disabled:opacity-40"
            >
              <PlayGlyph kind="next" />
            </button>
            {/*
              재생 속도 — 피그마는 세 값을 늘어놓지 않고 「2× ▾」 펼침 하나다. 고르는 값과
              동작(1× · 2× · 4×)은 그대로라 브라우저 기본 펼침(select)을 쓴다. 테두리는
              재생 중에만 강조색이다 — ⑦-9b(재생 중)는 붉은 테두리, ⑦-9c(멈춤)는 보통 테두리다
            */}
            <div
              className={[
                // 재생 중 강조 테두리를 마우스 올림이 지우지 않게 멈춰 있을 때만 hover 를 단다
                "relative h-[30px] rounded-[8px] border",
                playing ? "border-accent" : "border-edge hover:border-edge-strong",
              ].join(" ")}
            >
              <select
                aria-label="재생 속도"
                value={speed}
                onChange={(e) => onSpeed(Number(e.target.value))}
                className="h-full cursor-pointer appearance-none rounded-[8px] bg-transparent pl-[9px] pr-[20px] text-[12px] tabular-nums text-body"
              >
                {SPEEDS.map((v) => (
                  <option key={v} value={v} className="bg-panel text-body">
                    {v}×
                  </option>
                ))}
              </select>
              <span
                aria-hidden
                className="pointer-events-none absolute right-[8px] top-1/2 -translate-y-1/2 text-[8px] text-body"
              >
                ▾
              </span>
            </div>
            {/*
              시점 비교에서 연도 칩이 채울 쪽 — A 고르기 · B 고르기 (2026-09-28 최현서 8번 「A · B 각각의
              버튼을 두거나」). 고른 쪽은 테두리 있는 패널색 칸이다. 재생 조작 끝에 둔다(v2 8번 — 스위치와 자리를 바꿈)
            */}
            {compare && (
              <div
                role="group"
                aria-label="연도 칩이 채울 쪽"
                className="flex shrink-0 items-center gap-s1 rounded-[10px] bg-track p-[3px]"
              >
                {(["a", "b"] as const).map((k) => {
                  const onSide = compare.active === k;
                  return (
                    <button
                      key={k}
                      type="button"
                      aria-pressed={onSide}
                      onClick={() => onCompare({ ...compare, active: k })}
                      title={`연도 칩이 ${k.toUpperCase()} 시점을 바꿉니다`}
                      className={[
                        // 높이 30 을 안 넘게(재생 조작 줄과 같은 높이) — 넘으면 줄 높이가 바뀌어 옆 단추가 들썩인다
                      "flex items-center gap-s2 whitespace-nowrap rounded-[8px] border px-s3 py-[2px] text-[12px] leading-[16px] tabular-nums",
                        onSide ? "border-edge bg-panel font-semibold text-strong" : "border-transparent text-label hover-seg",
                      ].join(" ")}
                    >
                      <span
                        aria-hidden
                        className="grid size-[16px] place-items-center rounded-[4px] text-[10px] font-bold text-on-accent"
                        style={{ background: "var(--t-accent)" }}
                      >
                        {k.toUpperCase()}
                      </span>
                      {quarterText(k === "a" ? compare.a : compare.b)} 고르기
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {변화 ? (
          <div className="grid shrink-0 grid-cols-1 gap-s4 @min-[560px]:grid-cols-2">
            <SideMap mark="A" snap={변화.a}>
              {mapOf(변화.a, `A ${quarterText(변화.a.ym)} 지도`)}
            </SideMap>
            <SideMap mark="B" snap={변화.b}>
              {mapOf(변화.b, `B ${quarterText(변화.b.ym)} 지도`)}
            </SideMap>
          </div>
        ) : (
        <section
          className="relative flex h-[min(100cqw,640px)] min-h-[320px] shrink-0 resize-y flex-col overflow-hidden rounded-[14px] border border-edge bg-canvas p-s5"
          title="오른쪽 아래 모서리를 끌어 높이를 바꿀 수 있습니다"
        >
          {/*
            블록 높이는 기본이 정사각형(칸 폭, 640 까지)이고, 오른쪽 아래 모서리를 끌어 바꿀 수 있다(resize).
            아래 추이 · 성장 요약은 칸을 굴려 본다 (2026-09-29 최현서 v2 4번 — 전에는 400 고정이라 지도가
            작게 들어갔다). 시점마다 들쭉날쭉하지 않은 것은 그대로다(3번). 틀도 모든 분기를 합친 크기라 축척이 같다
          */}
          <header className="z-10 flex shrink-0 flex-wrap items-center gap-s3">
            <h2 className="whitespace-nowrap text-[15px] font-semibold text-title">
              Historical Map
            </h2>
            <Chip label="사건" value={`${now.events}건`} />
            {/* 한 해 앞 같은 분기와 견준다 (L806). 첫 해는 견줄 시점이 없어 안 낸다 */}
            {now.delta !== null && (
              <Chip
                label="전년 대비"
                value={
                  now.delta === 0
                    ? "0"
                    : `${now.delta > 0 ? "▲" : "▼"} ${Math.abs(now.delta)}`
                }
                tone={now.delta > 0 ? "up" : now.delta < 0 ? "down" : undefined}
              />
            )}
            {/* 직전 분기 대비 새로 사건이 생긴 영토 (`freshIds` — 비교의 「신규 영토」와 같은 기준) */}
            {/* 기준은 마우스를 올리면 — 이름에 적으면 1366 창에서 머리줄이 두 줄로 접혔다 (묶음 7 검토) */}
            {now.fresh !== null && (
              <Chip
                label="신규"
                value={String(now.fresh)}
                title="직전 분기에는 사건이 없었는데 이번 분기에 사건이 생긴 영토 수"
              />
            )}
          </header>

          <span
            aria-hidden
            className="pointer-events-none absolute left-s5 top-[54px] text-[46px] font-bold leading-none tabular-nums"
            style={{ color: "var(--t-border-card)", opacity: 0.55 }}
          >
            {quarterText(now.ym)}
          </span>

          {/* 큰 분기 글씨(워터마크)는 지도 밑에 깐다 — 전에는 지도 위층에 칠해졌다 */}
          <div className="relative z-[1] flex min-h-0 flex-1 flex-col">
            {/*
              재생 중에는 힌트 대신 「재생 중」 배지다. 캔버스의 힌트 자리에 넣어 줌 단추와 안 겹친다 —
              전에는 블록 기준으로 따로 떠서 좁은 캔버스에서 줌 단추 아래쪽을 덮었다 (2026-09-29 묶음 5 검토)
            */}
            {mapOf(
              now,
              `${quarterText(now.ym)} 지도`,
              playing ? (
                <div
                  className="flex min-w-0 items-center gap-s2 rounded-full px-s4 text-[12px] text-on-accent"
                  style={{ background: "var(--t-accent)", height: "var(--h-hint)" }}
                >
                  <span aria-hidden className="size-[6px] shrink-0 rounded-full bg-white" />
                  <span className="truncate">
                    재생 중 · {speed}× · {quarterText(now.ym)}
                    {at < snaps.length - 1 && ` → ${quarterText(snaps[at + 1].ym)}`}
                  </span>
                </div>
              ) : undefined,
            )}
          </div>

          <TimeSlider
            at={at}
            count={snaps.length}
            onChange={(i) => onPick(snaps[i].ym)}
            ticks={ticks}
            boldYears={boldYears}
          />
        </section>
        )}

        <div className="grid shrink-0 grid-cols-1 gap-s4 @min-[720px]:grid-cols-[minmax(0,1fr)_320px]">
          <TrendChart
            snaps={snaps}
            at={at}
            peak={peak}
            ticks={ticks}
            boldYears={boldYears}
            nameOf={nameOf}
            band={
              변화
                ? [
                    keys.indexOf(변화.a.ym),
                    keys.indexOf(변화.b.ym),
                  ]
                : undefined
            }
          />

          <section className="rounded-[14px] border border-edge bg-card px-s5 py-s4">
            <h3 className="text-[12px] font-semibold text-strong">
              성장 요약 ·{" "}
              {변화
                ? `${quarterText(변화.a.ym)} → ${quarterText(변화.b.ym)}`
                : `${quarterText(snaps[0].ym)} → ${quarterText(now.ym)}`}
            </h3>
            <ul className="mt-s4 flex flex-col gap-s4">
              {rows.map((r) => (
                <li key={r.islandId} className="flex flex-col gap-s2">
                  <div className="flex items-baseline gap-s2">
                    <span className="flex-1 text-[12px] font-semibold text-strong">
                      {r.name}
                    </span>
                    <span className="text-[11px] tabular-nums text-label">
                      {r.from}→{r.to}
                    </span>
                    {r.rate !== null && r.rate !== 0 && (
                      <span
                        className="text-[11px] tabular-nums"
                        style={{
                          color:
                            r.rate > 0
                              ? "var(--t-trend-up)"
                              : "var(--t-trend-down)",
                        }}
                      >
                        {r.rate > 0 ? "▲" : "▼"}
                        {Math.abs(Math.round(r.rate))}%
                      </span>
                    )}
                  </div>
                  {/*
                    막대 둘을 겹친다 — 어두운 쪽이 처음, 밝은 쪽이 지금이다 (피그마 ⑦-9b).
                    길이는 추이 그래프 세로축과 같은 눈금이라 재생하면 자라는 것이 보인다.
                    시점을 옮기면 길이가 번져 자란다 — 전에는 딱 바뀌었다 (최현서 1번)
                  */}
                  <div className="relative h-[5px] overflow-hidden rounded-full bg-bar-track">
                    <div
                      className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-[var(--dur-base)] ease-[var(--ease-out)]"
                      style={{
                        width: `${pctOf(r.to, peak)}%`,
                        background: `var(--t-island-${r.token})`,
                      }}
                    />
                    <div
                      className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-[var(--dur-base)] ease-[var(--ease-out)]"
                      style={{
                        width: `${pctOf(Math.min(r.from, r.to), peak)}%`,
                        background: `var(--t-island-${r.token})`,
                        filter: "brightness(0.7)",
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>

      <aside className="flex w-[240px] shrink-0 flex-col gap-s3 overflow-y-auto">
        {/* 비교 중에는 이 열이 변화 요약이다 (피그마 ⑦-9c) */}
        {변화 ? (
          <ChangeSummary d={변화} />
        ) : (
          <>
            <h3 className="shrink-0 text-[12px] font-semibold text-strong">
              시점별 스냅샷
            </h3>
            {cards.map((c) => {
              const on = c.year === now.year;
              /*
               * 지금 시점보다 뒤의 해. **흐리게 하는 것은 재생 중에만이다** (피그마 ⑦-9b 재생 중
               * 2025 · 2026 카드). 멈춰 있을 때는 글자색만 한 단계 낮춘다 — 전에는 늘 50% 라 꺼진
               * 단추(같은 화면 40%)처럼 보였는데 누르면 그 시점으로 옮겨 갔다 (2026-09-28 코드 분석)
               */
              const later = c.year > now.year;
              return (
                <button
                  key={c.year}
                  type="button"
                  onClick={() => onPick(c.snap.ym)}
                  aria-current={on ? "true" : undefined}
                  // 안 고른 카드는 공통 규칙(`hover-edge`) — 테두리가 진해지고 바탕이 한 단계 밝다 (최현서 1번)
                  className={[
                    "flex shrink-0 items-center gap-s3 rounded-[12px] border p-s2 pr-s4 text-left",
                    on ? "border-accent bg-row-selected" : "border-edge bg-card hover-edge",
                    later && playing ? "opacity-50" : "",
                  ].join(" ")}
                >
                  <Thumb layout={c.snap.layout} viewBox={c.box} />
                  <span className="min-w-0">
                    <span
                      className={
                        "block text-[14px] tabular-nums " +
                        (on ? "font-semibold text-accent" : later ? "text-body" : "text-strong")
                      }
                    >
                      {quarterText(c.snap.ym)}
                    </span>
                    <span className="mt-s1 block text-[11px] tabular-nums text-label">
                      {c.snap.events}건
                      {c.snap.delta !== null &&
                        c.snap.delta !== 0 &&
                        ` · ${c.snap.delta > 0 ? "▲" : "▼"}${Math.abs(c.snap.delta)}`}
                      {c.snap.ym === last.ym && " · 현재"}
                    </span>
                  </span>
                </button>
              );
            })}
          </>
        )}
      </aside>
    </div>
  );
}

/**
 * 스냅샷 카드의 섬 썸네일 (피그마 ⑦-9b, 컴포넌트 시트 「Snapshot List Item」).
 * 섬 테두리 경로만 섬 색으로 채운다. viewBox 를 카드끼리 맞춰 해마다 자라는 것이 보인다
 */
function Thumb({ layout, viewBox }: { layout: MapLayout; viewBox: string }) {
  return (
    <span
      aria-hidden
      // 테두리를 둘러 카드에 마우스를 올려 바탕이 트랙 색이 되어도 틀이 묻히지 않게 한다
      className="block h-[44px] w-[60px] shrink-0 rounded-[8px] border border-edge bg-track p-[4px]"
    >
      <svg viewBox={viewBox} className="block size-full">
        {layout.islands.map((i) => (
          <path
            key={i.islandKey}
            d={i.outline}
            fill={`var(--t-island-${i.token})`}
          />
        ))}
      </svg>
    </span>
  );
}

/**
 * 슬라이더 모양. 트랙 4px, 노브 16px 고리.
 *
 * 크롬 계열은 지나온 구간을 트랙 배경 그라디언트로 칠한다 — 노브 자리를 `--fill`
 * 로 받는다. 파이어폭스는 `::-moz-range-progress` 가 알아서 칠한다.
 */
const SLIDER = [
  "block h-[16px] w-full cursor-pointer appearance-none bg-transparent",
  "[&::-webkit-slider-runnable-track]:h-[4px] [&::-webkit-slider-runnable-track]:rounded-full",
  "[&::-webkit-slider-runnable-track]:bg-[linear-gradient(to_right,var(--t-accent)_var(--fill),var(--t-surface-track)_var(--fill))]",
  "[&::-webkit-slider-thumb]:-mt-[6px] [&::-webkit-slider-thumb]:box-border [&::-webkit-slider-thumb]:size-[16px]",
  "[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full",
  "[&::-webkit-slider-thumb]:border-[3px] [&::-webkit-slider-thumb]:border-accent [&::-webkit-slider-thumb]:bg-panel",
  "[&::-moz-range-track]:h-[4px] [&::-moz-range-track]:rounded-full [&::-moz-range-track]:bg-track",
  "[&::-moz-range-progress]:h-[4px] [&::-moz-range-progress]:rounded-full [&::-moz-range-progress]:bg-accent",
  "[&::-moz-range-thumb]:box-border [&::-moz-range-thumb]:size-[16px] [&::-moz-range-thumb]:rounded-full",
  "[&::-moz-range-thumb]:border-[3px] [&::-moz-range-thumb]:border-accent [&::-moz-range-thumb]:bg-panel",
].join(" ");

/**
 * 시점 슬라이더 (피그마 ⑦-9b, 컴포넌트 시트 「Snapshot bar」).
 *
 * 강조색으로 지나온 구간을 칠하고 노브는 16px 고리(속은 패널색)다. 브라우저
 * 기본 모양은 판마다 색이 달라 토큰을 못 탄다.
 *
 * 눈금 이름표는 연도만, 연도 칩이 가리키는 분기 자리에 둔다. 분기 스무 개에
 * 이름표를 다 달면 글자가 붙는다. 노브 중심은 양 끝에서 반지름(8px)만큼 안쪽이라
 * 이름표 자리도 같은 식으로 잡는다.
 */
function TimeSlider({
  at,
  count,
  onChange,
  ticks,
  boldYears,
}: {
  at: number;
  count: number;
  onChange: (i: number) => void;
  ticks: { year: number; i: number }[];
  boldYears: number[];
}) {
  const frac = (i: number) => (count <= 1 ? 0 : i / (count - 1));
  const knob = (f: number) => `calc(8px + ${f} * (100% - 16px))`;
  return (
    <div className="z-10 mt-s3 shrink-0">
      <input
        type="range"
        min={0}
        max={Math.max(0, count - 1)}
        step={1}
        value={at}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label="시점"
        style={{ "--fill": knob(frac(at)) } as CSSProperties}
        className={SLIDER}
      />
      <div className="relative mt-s1 h-[14px] text-[10px] tabular-nums">
        {ticks.map((t, k) => {
          const bold = boldYears.includes(t.year);
          // 양 끝 이름표는 가운데 맞춤하면 틀 밖으로 나가 끝에 붙인다
          const edge = k === 0 ? "first" : k === ticks.length - 1 ? "last" : "mid";
          return (
            <span
              key={t.year}
              className={[
                "absolute top-0 whitespace-nowrap",
                edge === "first" ? "left-0" : edge === "last" ? "right-0" : "-translate-x-1/2",
                bold ? "font-semibold text-strong" : "text-label",
              ].join(" ")}
              style={edge === "mid" ? { left: knob(frac(t.i)) } : undefined}
            >
              {t.year}
            </span>
          );
        })}
      </div>
    </div>
  );
}

/** 비교 모드의 지도 한 장. A 와 B 를 나란히 놓는다 (피그마 ⑦-9c) */
/**
 * 시점 비교 한 장. A · B 가 같은 크기 틀이라 축척이 같고(전에는 섬이 적은 A 가 크게 확대됐다),
 * 줌 · 이동을 같이 쓴다. 지도는 부모가 `children` 으로 넘긴다
 */
function SideMap({ mark, snap, children }: { mark: "A" | "B"; snap: Snapshot; children: ReactNode }) {
  return (
    <section className="relative flex h-[340px] flex-col rounded-[14px] border border-edge bg-canvas p-s5">
      <header className="z-10 flex shrink-0 flex-wrap items-center gap-s3">
        <span
          className="grid size-[20px] place-items-center rounded-[6px] text-[11px] font-bold text-on-accent"
          style={{ background: "var(--t-accent)" }}
        >
          {mark}
        </span>
        <span className="whitespace-nowrap text-[15px] font-semibold tabular-nums text-title">
          {quarterText(snap.ym)}
        </span>
        <Chip label="사건" value={`${snap.events}건`} />
      </header>

      <span
        aria-hidden
        className="pointer-events-none absolute left-s5 top-[46px] text-[34px] font-bold leading-none tabular-nums"
        style={{ color: "var(--t-border-card)", opacity: 0.5 }}
      >
        {quarterText(snap.ym)}
      </span>

      <div className="relative z-[1] flex min-h-0 flex-1 flex-col">{children}</div>
    </section>
  );
}

/** 「변화 · A → B」 요약 (설계서 4.3.7 시점 비교) */
function ChangeSummary({ d }: { d: Diff }) {
  return (
    <section className="flex flex-col gap-s3">
      <h3 className="shrink-0 text-[12px] font-semibold text-strong">
        변화 · {quarterText(d.a.ym)} → {quarterText(d.b.ym)}
      </h3>

      <div className="shrink-0 rounded-[14px] border border-edge bg-card px-s5 py-s4">
        <div className="text-[11px] text-label">누적 사건</div>
        <div
          className="mt-s1 text-[30px] font-bold leading-none tabular-nums"
          style={{
            color:
              d.deltaEvents >= 0 ? "var(--t-accent)" : "var(--t-trend-down)",
          }}
        >
          {d.deltaEvents >= 0 ? "+" : ""}
          {d.deltaEvents}건
        </div>
        <div className="mt-s2 text-[11px] tabular-nums text-label">
          {d.a.events} → {d.b.events}
          {d.times !== null && ` · ×${d.times.toFixed(1)}`}
        </div>
      </div>

      <ul className="flex shrink-0 flex-col gap-s2">
        {d.islands.map((i) => (
          <li
            key={i.islandId}
            className="flex items-center gap-s3 rounded-[12px] border border-edge bg-card px-s4 py-s3"
          >
            <span
              aria-hidden
              className="size-[8px] shrink-0 rounded-full"
              style={{
                background: `var(--t-island-${i.token}-legend, var(--t-island-${i.token}))`,
              }}
            />
            <span className="flex-1 text-[12px] font-semibold text-strong">
              {i.name}
            </span>
            <span className="text-[11px] tabular-nums text-label">
              {i.from}→{i.to}
            </span>
            {i.delta !== 0 && (
              <span
                className="text-[11px] font-semibold tabular-nums"
                style={{
                  color:
                    i.delta > 0
                      ? "var(--t-trend-up)"
                      : "var(--t-trend-down)",
                }}
              >
                {i.delta > 0 ? "+" : ""}
                {i.delta}
              </span>
            )}
          </li>
        ))}
      </ul>

      {d.fresh.length > 0 && (
        <div className="shrink-0 rounded-[12px] border border-edge bg-card px-s4 py-s3">
          <div className="text-[11px] text-label">
            신규 영토 ({quarterText(d.a.ym)} 뒤 첫 사건)
          </div>
          <p className="mt-s2 text-[12px] leading-[1.7] text-body">
            {d.fresh.join(" · ")}
          </p>
        </div>
      )}
    </section>
  );
}

/** 막대 길이 (%). 눈금은 추이 그래프 세로축과 같다 */
function pctOf(v: number, peak: number): number {
  return Math.round((v / Math.max(1, peak)) * 100);
}

function Chip({
  label,
  value,
  tone,
  title,
}: {
  label: string;
  value: string;
  tone?: "up" | "down";
  title?: string;
}) {
  return (
    <span title={title} className="rounded-[8px] bg-card px-s3 py-[3px] text-[11px]">
      <span className="text-label">{label} </span>
      <span
        className="font-semibold tabular-nums"
        style={{
          color:
            tone === "up"
              ? "var(--t-trend-up)"
              : tone === "down"
                ? "var(--t-trend-down)"
                : "var(--t-text-strong)",
        }}
      >
        {value}
      </span>
    </span>
  );
}

/**
 * 섬별 누적 사건 추이 — 설계서 4.3.7 L808 의 선 그래프.
 *
 * 세로선이 지금 보고 있는 시점이다. 비교 중에는 A · B 두 줄과 그 사이 음영이다.
 *
 * **섬 넷을 다 그린다.** 전에는 한 번도 사건이 없던 섬을 뺐는데, 설계서가 「섬 4개
 * 선 그래프」라 0건 섬도 바닥선으로 둔다 (피그마 ⑦-9b 범례 넷).
 */
function TrendChart({
  snaps,
  at,
  peak,
  ticks,
  boldYears,
  nameOf,
  band,
}: {
  snaps: Snapshot[];
  at: number;
  peak: number;
  /** 연도 이름표 자리. 슬라이더와 같다 */
  ticks: { year: number; i: number }[];
  boldYears: number[];
  nameOf: (id: string) => string;
  /** 시점 비교 중이면 A~B 구간을 음영으로 덮는다 (설계서 4.3.7) */
  band?: [number, number];
}) {
  const W = 620;
  const H = 180;
  const PAD = { l: 34, r: 12, t: 12, b: 22 };

  // 섬 목록 차례 그대로 (`Snapshot.byIsland`). 0건 섬도 든다
  const ids = Object.keys(snaps[0]?.byIsland ?? {});
  const max = peak;
  const x = (i: number) =>
    PAD.l +
    (snaps.length <= 1
      ? 0
      : (i / (snaps.length - 1)) * (W - PAD.l - PAD.r));
  const y = (v: number) => H - PAD.b - (v / max) * (H - PAD.t - PAD.b);
  /** 세로선과 큰 점을 찍을 시점. 평소에는 지금, 비교 중에는 A · B */
  const marks = band && band[0] >= 0 && band[1] >= 0 ? band : [at];

  return (
    <section className="rounded-[14px] border border-edge bg-card px-s5 py-s4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-s4 gap-y-s1">
        <h3 className="text-[12px] font-semibold text-strong">
          섬별 누적 사건 추이
        </h3>
        <ul className="flex flex-wrap gap-x-s4 gap-y-s1">
          {ids.map((id) => (
            <li key={id} className="flex items-center gap-s2 whitespace-nowrap text-[11px]">
              <span
                aria-hidden
                className="size-[7px] rounded-full"
                style={{
                  background: `var(--t-island-${islandToken(id as IslandCode)})`,
                }}
              />
              <span className="text-label">{nameOf(id)}</span>
            </li>
          ))}
        </ul>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="mt-s3 w-full" role="img"
           aria-label="섬별 누적 사건 추이">
        {[0, max / 2, max].map((v) => (
          <g key={v}>
            <line
              x1={PAD.l}
              y1={y(v)}
              x2={W - PAD.r}
              y2={y(v)}
              stroke="var(--t-border-divider)"
            />
            <text
              x={PAD.l - 6}
              y={y(v) + 3}
              fontSize={9}
              textAnchor="end"
              fill="var(--t-text-label)"
            >
              {Math.round(v)}
            </text>
          </g>
        ))}

        {marks.length === 2 && (
          <rect
            x={x(Math.min(...marks))}
            y={PAD.t}
            width={Math.abs(x(marks[1]) - x(marks[0]))}
            height={H - PAD.t - PAD.b}
            fill="var(--t-accent)"
            opacity={0.12}
          />
        )}

        {marks.map((i, k) => (
          <line
            // A 와 B 가 같은 시점일 수 있어 자리 번호를 열쇠로 쓴다
            key={k}
            x1={x(i)}
            y1={PAD.t}
            x2={x(i)}
            y2={H - PAD.b}
            stroke="var(--t-accent)"
            strokeWidth={1}
          />
        ))}

        {ids.map((id) => {
          const pts = snaps.map((s, i) => [x(i), y(s.byIsland[id] ?? 0)]);
          const color = `var(--t-island-${islandToken(id as IslandCode)})`;
          return (
            <g key={id}>
              <polyline
                points={pts.map(([a, b]) => `${a},${b}`).join(" ")}
                fill="none"
                stroke={color}
                strokeWidth={2}
                strokeLinejoin="round"
              />
              {pts.map(([a, b], i) => {
                const big = marks.includes(i);
                return (
                  <circle
                    key={i}
                    cx={a}
                    cy={b}
                    r={big ? 4 : 2.5}
                    fill={big ? color : "var(--t-surface-card)"}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                );
              })}
            </g>
          );
        })}

        {/* 연도 이름표 — 연도 칩이 가리키는 분기 자리. 슬라이더 눈금과 같다 */}
        {ticks.map((t) => {
          const bold = boldYears.includes(t.year);
          return (
            <text
              key={t.year}
              x={x(t.i)}
              y={H - 6}
              fontSize={9}
              textAnchor="middle"
              fontWeight={bold ? 700 : 400}
              fill={bold ? "var(--t-text-strong)" : "var(--t-text-label)"}
            >
              {t.year}
            </text>
          );
        })}
      </svg>
    </section>
  );
}
