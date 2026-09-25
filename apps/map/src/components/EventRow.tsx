/**
 * 사건 한 줄 — 패널 [사건] 탭(피그마 ⑦-4)과 엔티티 탭 「최근 주요 이벤트」(⑦-7)가 같이 쓴다.
 *
 *   ○ 05-14 06:58  [데이터 게시]
 *     [KR · 유통 · 2026-05-14 · 255GB]
 *     Darkforums · 규모 큼
 *
 * 한 번 누르면 강조하고, 두 번 누르면 보고서 팝업(4.3.4)을 연다 (설계서 4.3.2 L587
 * 「클릭: 강조 / 더블클릭: 보고서 팝업」, 4.3.3 L607 「한 번은 미리보기, 두 번은 상세」).
 *
 * **더블클릭은 click 두 번 뒤에 온다.** 두 번째 click 까지 강조를 뒤집으면 켜졌다
 * 꺼진 채 팝업이 열린다. 그래서 두 번째 click(`detail` 2 이상)은 버린다 — 강조가
 * 켜진 채로 팝업이 뜬다. 키보드는 [연결] 탭 줄(`LinksTab`)과 같다 — Enter 가 팝업,
 * Space 가 강조다.
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
  onOpen,
}: {
  e: Ev;
  /** 올라온 곳 이름. 행위자 사건이면 「행위자 → 영토」 */
  where: string;
  on: boolean;
  onClick: () => void;
  /** 보고서 팝업 열기. 없으면 더블클릭 · Enter 가 아무 일도 안 한다 */
  onOpen?: () => void;
}) {
  return (
    <button
      type="button"
      data-ev={e.id}
      onClick={(ev) => {
        if (ev.detail > 1) return;
        onClick();
      }}
      onDoubleClick={onOpen}
      onKeyDown={(ev) => {
        if (ev.key === "Enter" && onOpen) {
          ev.preventDefault();
          onOpen();
        }
      }}
      aria-pressed={on}
      className={[
        "flex w-full select-none gap-s3 rounded-[12px] border px-s3 py-s3 text-left",
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
