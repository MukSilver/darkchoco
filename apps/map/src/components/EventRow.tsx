/**
 * 사건 한 줄 — 패널 [사건] 탭(피그마 ⑦-4)과 엔티티 탭 「최근 주요 이벤트」(⑦-7)가 같이 쓴다.
 *
 *   ○ 05-14 06:58  [데이터 게시]
 *     [KR · 유통 · 2026-05-14 · 255GB]
 *     Darkforums · 규모 큼
 *
 * 한 번 누르면 강조한다 (설계서 4.3.2). 더블클릭 보고서 팝업(4.3.4)은 아직 없다.
 */

"use client";

import { Chip } from "./RelBits";
import { EV_KIND_LABEL, EV_KIND_TONE, eventTitle, stampOf } from "@/lib/events";
import { SIZE_LABEL } from "@/lib/relations";
import type { Ev } from "@/lib/types";

export default function EventRow({
  e,
  where,
  on,
  onClick,
}: {
  e: Ev;
  /** 올라온 곳 이름. 행위자 사건이면 「행위자 → 영토」 */
  where: string;
  on: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={[
        "flex w-full gap-s3 rounded-[12px] border px-s3 py-s3 text-left",
        on ? "border-[var(--t-accent)] bg-row-selected" : "border-transparent hover:bg-card",
      ].join(" ")}
    >
      <span
        aria-hidden
        className="mt-[5px] size-[9px] shrink-0 rounded-full border-2"
        style={{
          borderColor: on ? "var(--t-accent)" : "var(--t-info)",
          background: on ? "var(--t-accent)" : "transparent",
        }}
      />
      <span className="flex min-w-0 flex-1 flex-col gap-s1">
        <span className="flex items-center gap-s2">
          <span
            className="font-mono text-[11px] tabular-nums"
            style={{ color: on ? "var(--t-accent)" : "var(--t-text-label)" }}
          >
            {stampOf(e)}
          </span>
          {e.kind && <Chip tone={EV_KIND_TONE[e.kind]}>{EV_KIND_LABEL[e.kind]}</Chip>}
        </span>
        <span className="truncate text-[13px] font-semibold text-title">{eventTitle(e)}</span>
        <span className="truncate text-[11px] text-label">
          {where} · {SIZE_LABEL[e.size]}
        </span>
      </span>
    </button>
  );
}
