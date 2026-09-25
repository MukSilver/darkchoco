/**
 * 패널 [사건] 탭 — 설계서 4.3.1 · 4.3.2 · 4.3.8, 피그마 ⑦-4.
 *
 *   영토     그 영토의 사건
 *   섬       섬에 속한 모든 영토의 사건. 행마다 영토 이름
 *   행위자   그 행위자가 올린 사건. 행마다 올라온 영토 이름
 *
 * 기본은 최근 90일 · 최신순 · 월별 묶음이다. 7일 · 30일 · 90일 · 전체로 바꾸고
 * 날짜 범위도 정할 수 있다. **끝은 기준일이다** — 기준일을 옮긴 상태면 그
 * 날짜까지의 90일이다. 헤더 오른쪽과 탭 배지에 지금 기간의 건수를 적는다.
 *
 * 안 만든 것: 공식 발표 사고(유출 사고 DB 를 안 읽는다), 행위자 필터 칩
 * (검색에 행위자 묶음이 없다), 더블클릭 보고서 팝업(4.3.4).
 */

"use client";

import { useState } from "react";

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
}: {
  /** 지금 기간의 사건. 최신순 (`eventsIn`) */
  list: Ev[];
  d: Date;
  period: Period;
  onPeriod: (p: Period) => void;
  /** 행 아래 「올라온 곳」 글씨 */
  whereOf: (e: Ev) => string;
}) {
  const [picked, setPicked] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  // 화면에 적는 기간은 거르기와 같은 규칙으로 낸다 (`periodDays`). 전체면 가장 이른 사건 날짜다
  const [start, toDay] = periodDays(period, d);
  const fromDay = start ?? (list.length ? list[list.length - 1].postedAt.slice(0, 10) : toDay);

  return (
    <section className="flex flex-col gap-s3">
      <div className="flex items-baseline justify-between">
        <h3 className="text-[12px] text-label">사건 타임라인</h3>
        <span className="text-[11px] tabular-nums text-label">
          {periodLabel(period)} · {list.length}건
        </span>
      </div>

      <div role="group" aria-label="기간" className="flex rounded-[10px] bg-track p-[3px]">
        {CHOICES.map((c) => {
          const on = same(c.p, period);
          return (
            <button
              key={c.label}
              type="button"
              aria-pressed={on}
              onClick={() => onPeriod(c.p)}
              className={[
                "flex-1 rounded-[8px] py-s2 text-[12px]",
                on ? "bg-selected font-semibold text-strong" : "text-label hover:text-body",
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
            onClick={() => setEditing((v) => !v)}
            className="text-[11px] text-label hover:text-title"
          >
            변경 {editing ? "▲" : "▼"}
          </button>
        </div>
        {editing && (
          <form
            className="flex items-center gap-s2"
            onSubmit={(ev) => {
              ev.preventDefault();
              const f = new FormData(ev.currentTarget);
              const from = String(f.get("from") || fromDay);
              const to = String(f.get("to") || toDay);
              onPeriod({ kind: "range", from: from <= to ? from : to, to: from <= to ? to : from });
              setEditing(false);
            }}
          >
            <input
              name="from"
              type="date"
              defaultValue={fromDay}
              max={toDay}
              aria-label="시작일"
              className="min-w-0 flex-1 rounded-[6px] border border-edge-input bg-input px-s2 py-[2px] text-[12px] text-body"
            />
            <span className="text-label">—</span>
            <input
              name="to"
              type="date"
              defaultValue={toDay}
              max={isoDay(d.getTime())}
              aria-label="끝날"
              className="min-w-0 flex-1 rounded-[6px] border border-edge-input bg-input px-s2 py-[2px] text-[12px] text-body"
            />
            <button type="submit" className="rounded-[6px] border border-edge px-s2 py-[2px] text-[11px] text-body">
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
                onClick={() => setPicked((x) => (x === e.id ? null : e.id))}
              />
            ))}
          </div>
        ))
      )}
    </section>
  );
}
