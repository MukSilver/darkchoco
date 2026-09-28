/**
 * 패널 [사건] 탭 — 설계서 4.3.1 · 4.3.2 · 4.3.8, 피그마 ⑦-4.
 *
 *   영토     그 영토의 사건
 *   섬       섬에 속한 모든 영토의 사건. 행마다 영토 이름
 *   행위자   그 행위자가 올린 사건. 행마다 올라온 영토 이름
 *   선택 없음 지도에 있는 영토 전부의 사건. 행마다 영토 이름 (피그마 ⑦-1 탭 「사건 N」)
 *
 * 유출 사고 DB 의 공식 발표 사고도 같은 목록에 「공식 발표」 칩으로 섞여 나온다
 * (설계서 4.3.2). 날짜는 공표 시점, 제목은 다른 사건처럼 분류 칸으로 짓는다 —
 * 조직명은 안 싣는다 (2026-09-26).
 *
 * 기본은 최근 90일 · 최신순 · 월별 묶음이다. 7일 · 30일 · 90일 · 전체로 바꾸고
 * 날짜 범위도 정할 수 있다. **끝은 기준일이다** — 기준일을 옮긴 상태면 그
 * 날짜까지의 90일이다. 헤더 오른쪽과 탭 배지에 지금 기간의 건수를 적는다.
 *
 * 검색에서 행위자를 고르면 그 행위자 사건만 남기고 「행위자: 핸들 ×」 칩을 단다.
 * 사건을 고르면 그 사건을 강조하고 그 자리로 굴린다 (설계서 4.2.2 결과 선택).
 *
 * 행을 한 번 누르면 강조하고 지도에 그 사건의 관계선만 남긴다 (피그마 ⑦-4 「선택한
 * 사건의 관계선만 표시 중」). **강조는 부르는 쪽이 들고 있다** — 지도가 같은 값을
 * 봐야 해서다. 누르면 보고서 팝업(4.3.4)이 열린다 (`EventRow`, 한 번 클릭 — 최현서 9번).
 *
 * 「사기 의심」은 칩 없이 여기 거르기로만 쓴다 (설계서 2.3 L98). 기본은 다 보이고,
 * 이 기간에 사기 의심 사건이 있을 때만 「사기 의심 숨기기」 칸이 건수와 함께 나온다. 거르는
 * 것도 부르는 쪽이 한다 — 헤더 건수와 탭 배지가 거른 뒤 목록과 같아야 한다.
 */

"use client";

import { useEffect, useState } from "react";

import EventRow from "./EventRow";
import { byMonth, periodDays, periodLabel, type Period } from "@/lib/events";
import type { Ev } from "@/lib/types";

const CHOICES: { label: string; p: Period }[] = [
  { label: "7일", p: { kind: "days", days: 7 } },
  { label: "30일", p: { kind: "days", days: 30 } },
  { label: "90일", p: { kind: "days", days: 90 } },
  { label: "전체", p: { kind: "all" } },
];

function same(a: Period, b: Period): boolean {
  if (a.kind !== b.kind) return false;
  if (a.kind === "days" && b.kind === "days") return a.days === b.days;
  return a.kind === "all";
}

function isoDay(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

export default function EventsTab({
  list,
  d,
  period,
  onPeriod,
  whereOf,
  actor,
  onClearActor,
  focus,
  picked,
  onPick,
  onOpen,
  scamCount,
  hideScam,
  onHideScam,
}: {
  /** 지금 기간의 사건. 최신순 (`eventsIn`). 사기 의심을 숨겼으면 뺀 뒤다 */
  list: Ev[];
  d: Date;
  period: Period;
  onPeriod: (p: Period) => void;
  /** 행 아래 「올라온 곳」 글씨 */
  whereOf: (e: Ev) => string;
  /** 검색에서 고른 행위자 핸들. 있으면 칩을 단다 (목록은 부르는 쪽이 이미 걸렀다) */
  actor?: string | null;
  onClearActor?: () => void;
  /**
   * 검색에서 고른 사건. 그 줄로 굴린다 — 강조는 부르는 쪽이 `picked` 로 같이 건다.
   * **부르는 쪽이 이 값을 `key` 로도 넘긴다** — 바뀌면 새로 마운트돼 새 사건으로 굴린다
   */
  focus?: string | null;
  /** 강조한 사건. 지도가 그 사건의 관계선만 그린다 */
  picked: string | null;
  onPick: (id: string | null) => void;
  /** 보고서 팝업 열기 (설계서 4.3.4) */
  onOpen: (id: string) => void;
  /** 이 기간의 사기 의심 사건 수 — 숨기기 전 건수다 */
  scamCount: number;
  hideScam: boolean;
  onHideScam: (hide: boolean) => void;
}) {
  useEffect(() => {
    if (!focus) return;
    document.querySelector(`[data-ev="${CSS.escape(focus)}"]`)?.scrollIntoView({ block: "center" });
  }, [focus]);
  const [editing, setEditing] = useState(false);
  // 화면에 적는 기간은 거르기와 같은 규칙으로 낸다 (`periodDays`). 전체면 가장 이른 사건 날짜다.
  // 끝은 기준일이지만, 노션이 적은 날짜로는 기준일 다음 날인 사건(분기 끝 새벽 +09:00)이
  // 목록에 들 수 있어 그 날까지 넓혀 적는다 — 머리글이 목록과 어긋나지 않게
  const [start, end] = periodDays(period, d);
  const latest = list.length ? list[0].postedAt.slice(0, 10) : end;
  const toDay = latest > end ? latest : end;
  const earliest = list.length ? list[list.length - 1].postedAt.slice(0, 10) : toDay;
  const fromDay = start ?? (earliest < toDay ? earliest : toDay);
  const [fromIn, setFromIn] = useState(fromDay);
  const [toIn, setToIn] = useState(end);

  return (
    <section className="flex flex-col gap-s3">
      <div className="flex items-baseline justify-between">
        {/* 피그마 ⑦-4 머리글 문안 그대로 */}
        <h3 className="text-[12px] text-label">사건 타임라인 · 누르면 상세</h3>
        <span className="text-[11px] tabular-nums text-label">
          {periodLabel(period, d)} · {list.length}건
        </span>
      </div>

      {(scamCount > 0 || hideScam) && (
        <label className="flex cursor-pointer items-center gap-s2 self-start text-[11px] text-label hover:text-body">
          <input
            type="checkbox"
            checked={hideScam}
            onChange={(ev) => onHideScam(ev.target.checked)}
            className="size-[12px] accent-[var(--t-accent)]"
          />
          사기 의심 숨기기
          <span className="tabular-nums">{scamCount}건</span>
        </label>
      )}

      {actor && (
        <div>
          <button
            type="button"
            onClick={onClearActor}
            aria-label={`행위자 필터 ${actor} 풀기`}
            // 누르면 풀린다는 것이 보이게 테두리를 강조색으로, × 를 밝게 (2026-09-28 최현서 1번)
            className="group inline-flex items-center gap-s1 rounded-full border border-accent-edge bg-accent-subtle px-s3 py-[2px] text-[12px] text-title hover:border-accent"
          >
            행위자: {actor}
            <span aria-hidden className="text-label transition-colors duration-[var(--dur-fast)] ease-[var(--ease-out)] group-hover:text-title">
              ×
            </span>
          </button>
        </div>
      )}

      <div role="group" aria-label="기간" className="flex rounded-[10px] bg-track p-[3px]">
        {CHOICES.map((c) => {
          const on = same(c.p, period);
          return (
            <button
              key={c.label}
              type="button"
              aria-pressed={on}
              onClick={() => onPeriod(c.p)}
              // 고른 칸은 화면 탭(`ViewTabs`)처럼 테두리 있는 패널색 칸이다. 전에는 bg-selected 라
              // 통 색(bg-track)과 거의 같아 무엇을 골랐는지 흐렸다 (2026-09-28 코드 분석)
              className={[
                "flex-1 rounded-[8px] border py-s2 text-[12px]",
                on ? "border-edge bg-panel font-semibold text-strong" : "border-transparent text-label hover-seg",
              ].join(" ")}
            >
              {c.label}
            </button>
          );
        })}
      </div>

      <div className="flex flex-col gap-s2 rounded-[10px] border border-edge px-s3 py-s2">
        <div className="flex items-center gap-s2 text-[12px]">
          <span className="font-mono tabular-nums text-body">
            {fromDay} — {toDay}
          </span>
          <span className="flex-1" />
          <button
            type="button"
            aria-expanded={editing}
            onClick={() => {
              // 열 때마다 지금 기간으로 채운다
              setFromIn(fromDay);
              setToIn(end);
              setEditing((v) => !v);
            }}
            // 글자 단추도 바탕이 떠서 눌리는 자리가 보이게. 여백만큼 오른쪽을 당겨 글자 자리는 그대로다
            className="-mr-s1 rounded-[6px] px-s1 text-[11px] text-label hover-row hover:text-title"
          >
            변경 {editing ? "▲" : "▼"}
          </button>
        </div>
        {editing && (
          /*
            날짜 칸 둘을 세로로 쌓는다. 한 줄에 두면 패널 폭(264)에서 칸이 80px 남짓이라
            날짜가 잘렸다 (2026-09-28 코드 분석)
          */
          <form
            className="flex flex-col gap-s2"
            onSubmit={(ev) => {
              ev.preventDefault();
              const from = fromIn || fromDay;
              const to = toIn || end;
              onPeriod({ kind: "range", from: from <= to ? from : to, to: from <= to ? to : from });
              setEditing(false);
            }}
          >
            <div className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-s2 gap-y-s1 text-[11px] text-label">
              <span aria-hidden>시작</span>
              <input
                name="from"
                type="date"
                value={fromIn}
                onChange={(ev) => setFromIn(ev.target.value)}
                max={toIn || end}
                aria-label="시작일"
                className="w-full min-w-0 rounded-[6px] border border-edge-input bg-input px-s2 py-[2px] text-[12px] text-body"
              />
              <span aria-hidden>끝</span>
              <input
                name="to"
                type="date"
                value={toIn}
                onChange={(ev) => setToIn(ev.target.value)}
                min={fromIn || undefined}
                max={isoDay(d.getTime())}
                aria-label="끝날"
                className="w-full min-w-0 rounded-[6px] border border-edge-input bg-input px-s2 py-[2px] text-[12px] text-body"
              />
            </div>
            <button
              type="submit"
              className="self-end rounded-[6px] border border-edge px-s2 py-[2px] text-[11px] text-body hover-edge"
            >
              적용
            </button>
          </form>
        )}
      </div>

      {list.length === 0 ? (
        <p className="rounded-[12px] border border-edge bg-card px-s4 py-s4 text-[12px] text-label">
          이 기간에 올라온 사건이 없습니다. 기간을 넓혀 보세요.
        </p>
      ) : (
        byMonth(list).map((g) => (
          <div key={g.month} className="flex flex-col gap-s1">
            <h4 className="font-mono text-[12px] tabular-nums text-body">{g.month}</h4>
            {g.items.map((e) => (
              <EventRow
                key={e.id}
                e={e}
                where={whereOf(e)}
                on={picked === e.id}
                onClick={() => onPick(picked === e.id ? null : e.id)}
                // 누르면 그 줄을 강조하고 팝업을 연다 (한 번 클릭). Space 는 강조만 켜고 끈다
                onOpen={() => {
                  onPick(e.id);
                  onOpen(e.id);
                }}
              />
            ))}
          </div>
        ))
      )}
    </section>
  );
}
