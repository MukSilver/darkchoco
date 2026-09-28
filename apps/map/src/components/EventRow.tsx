/**
 * 사건 한 줄 — 패널 [사건] 탭(피그마 ⑦-4)과 엔티티 탭 「최근 주요 이벤트」(⑦-7)가 같이 쓴다.
 *
 *   ○ 05-14 06:58  [데이터 게시]
 *     [KR · 유통 · 2026-05-14 · 255GB]
 *     Darkforums · 규모 큼
 *
 * 같은 사고로 특정된 공식 발표 사고가 있는 게시는 종류 칩 뒤에 「공식 발표」 와 외부
 * 확인 값 칩이 붙는다 (설계서 사건 칸 「공식 발표 여부」, G-9).
 *
 * **한 번 누르면 그 줄을 강조하고 보고서 팝업(4.3.4)을 연다** (2026-09-28 최현서 9번 —
 * 「더블클릭이 아니라 한 번 클릭으로」). 설계서 4.3.2 L587 · 4.3.3 L607 · 4.3.4 · 4.3.5 ·
 * 4.3.6 은 「클릭: 강조 / 더블클릭: 보고서 팝업」이었다 — README 「설계서와 다른 곳」.
 * 강조는 팝업을 닫은 뒤에도 남아 지도 · 그래프에 그 사건의 관계선이 보인다.
 * 팝업이 없는 자리(`onOpen` 없음)는 전처럼 강조만 켜고 끈다.
 *
 * 키보드는 Enter 가 팝업(누르기와 같다), Space 가 강조 켜고 끄기다.
 * `side` 는 칩 줄 오른쪽 끝 자리다 — 관계 패널 근거 사건이 신뢰도 칩을 둔다(전에는 줄 위에
 * 띄워서 칩이 늘면 겹쳤다)
 */

"use client";

import type { ReactNode } from "react";

import { Chip } from "./RelBits";
import { CONFIRM_TONE, EV_KIND_LABEL, EV_KIND_TONE, eventTitle, stampOf } from "@/lib/events";
import { SIZE_LABEL } from "@/lib/relations";
import type { Ev } from "@/lib/types";

export default function EventRow({
  e,
  where,
  on,
  onClick,
  onOpen,
  side,
}: {
  e: Ev;
  /** 올라온 곳 이름. 행위자 사건이면 「행위자 → 영토」 */
  where: string;
  on: boolean;
  /** 강조 켜고 끄기. 팝업이 없는 자리에서는 누르기, 있는 자리에서는 Space */
  onClick: () => void;
  /** 그 줄을 강조하고 보고서 팝업을 연다. 있으면 한 번 누르기 · Enter 가 이것이다 */
  onOpen?: () => void;
  /** 칩 줄 오른쪽 끝에 둘 것 */
  side?: ReactNode;
}) {
  return (
    <button
      type="button"
      data-ev={e.id}
      onClick={() => (onOpen ? onOpen() : onClick())}
      onKeyDown={(ev) => {
        // Space 는 강조만. 단추 기본 동작(누르기 = 팝업)을 막는다
        if (ev.key === " " && onOpen) {
          ev.preventDefault();
          onClick();
        }
      }}
      onKeyUp={(ev) => {
        if (ev.key === " " && onOpen) ev.preventDefault();
      }}
      title={onOpen ? "누르면 사건 보고서" : undefined}
      // 한 번 클릭이 팝업이라 켜고 끄는 단추가 아니다 — 강조된 줄은 「지금 것」으로 알린다 (2026-09-28 검토)
      aria-current={on ? "true" : undefined}
      className={[
        "flex w-full select-none gap-s3 rounded-[12px] border px-s3 py-s3 text-left",
        // 마우스 올림은 공통 줄 규칙(`hover-row`) — 전에는 패널 바탕과 거의 같은 bg-card 라 없는 셈이었다
        on ? "border-[var(--t-accent)] bg-row-selected" : "border-transparent hover-row hover:border-edge-strong",
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
        <span className="flex flex-wrap items-center gap-s2">
          <span
            className="font-mono text-[11px] tabular-nums"
            style={{ color: on ? "var(--t-accent)" : "var(--t-text-label)" }}
          >
            {stampOf(e)}
          </span>
          {e.kind && <Chip tone={EV_KIND_TONE[e.kind]}>{EV_KIND_LABEL[e.kind]}</Chip>}
          {/* 공식 발표 여부 (G-9) — 같은 사고로 특정된 공식 발표 사고가 있는 게시 */}
          {e.incident && (
            <>
              <Chip tone={EV_KIND_TONE.official}>{EV_KIND_LABEL.official}</Chip>
              <Chip tone={CONFIRM_TONE[e.incident.confirm] ?? "neutral"}>{e.incident.confirm}</Chip>
            </>
          )}
          {side && <span className="ml-auto shrink-0">{side}</span>}
        </span>
        <span className="truncate text-[13px] font-semibold text-title">{eventTitle(e)}</span>
        <span className="truncate text-[11px] text-label">
          {where} · {SIZE_LABEL[e.size]}
        </span>
      </span>
    </button>
  );
}
