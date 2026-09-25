/**
 * 오른쪽 패널의 틀 — 폭 312, 접힘 48 (설계서 4.2.4).
 *
 * 지도 · 엔티티 · 타임라인 탭은 `DetailPanel` 이, 관계 탭은 `RelationPanel`
 * 이 이 틀을 쓴다. 두 패널은 머리글 모양과 접는 법이 같고 본문만 다르다
 * (설계서 4.3.6 「우측 패널 (중심 영토 기준)」).
 */

"use client";

import type { ReactNode } from "react";

export type PanelHeader = {
  /** 눈표 앞쪽 글씨. `TERRITORY` 처럼 대문자로 낸다 */
  kindLabel: string;
  /** 눈표 앞쪽 글씨 색 토큰. 섬 색이거나 null(회색) */
  kindToken: string | null;
  /** 눈표 앞쪽 글씨를 강조색으로 칠한다. 관계 탭의 `RELATION · 선택됨` 이 그렇다 */
  kindAccent?: boolean;
  stateLabel: string;
  title: string;
  subtitle: string;
};

export default function PanelShell({
  open,
  onToggle,
  header,
  children,
}: {
  open: boolean;
  onToggle: (open: boolean) => void;
  header: PanelHeader;
  children: ReactNode;
}) {
  if (!open) {
    return (
      <aside
        className="flex shrink-0 flex-col items-center gap-s4 border-l border-divider bg-panel py-s5"
        style={{ width: "var(--w-panel-rail)" }}
      >
        <button
          type="button"
          aria-label="상세패널 펼치기"
          onClick={() => onToggle(true)}
          className="grid size-[24px] place-items-center rounded-full border border-edge text-[11px] text-body"
        >
          ›
        </button>
        <span
          className="text-[11px] tracking-[0.1em] text-label"
          style={{ writingMode: "vertical-rl" }}
        >
          상세패널
        </span>
      </aside>
    );
  }

  const kindColor = header.kindAccent
    ? "var(--t-accent)"
    : header.kindToken
      ? `var(--t-island-${header.kindToken})`
      : "var(--t-text-label)";

  return (
    // 핸들을 패널 왼쪽 밖으로 내밀어야 해서 바깥을 한 겹 더 쌌다.
    // 패널 자체는 세로로 넘칠 수 있어 `overflow-y-auto` 인데, 그러면
    // 안에 둔 핸들이 잘린다.
    //
    // **본문은 바깥 틀 안에 절대 위치로 띄운다.** `body` 가 `min-h-full` 이라
    // 높이가 묶여 있지 않아서, 본문이 흐름 안에 있으면 [연결] 목록처럼 긴
    // 내용이 화면 전체를 세로로 늘인다. 띄워 두면 틀 높이는 가운데 화면이
    // 정하고 본문은 그 안에서만 굴러간다
    <div className="relative shrink-0" style={{ width: "var(--w-panel)" }}>
      <button
        type="button"
        aria-label="상세패널 접기"
        onClick={() => onToggle(false)}
        className="absolute left-[-12px] top-[92px] z-10 grid size-[24px] place-items-center rounded-full border border-edge bg-panel text-[11px] text-body"
      >
        ‹
      </button>

      <aside className="absolute inset-0 flex flex-col gap-s5 overflow-y-auto border-l border-divider bg-panel px-s5 py-s5">
        <header className="flex flex-col gap-s2">
          <p className="text-[10px] tracking-[0.16em]">
            <span style={{ color: kindColor }}>{header.kindLabel}</span>
            <span style={{ color: header.kindAccent ? kindColor : "var(--t-text-label)" }}>
              {" "}
              · {header.stateLabel}
            </span>
          </p>
          <h2 className="text-[20px] font-semibold leading-tight text-title">{header.title}</h2>
          <p className="text-[12px] text-label">{header.subtitle}</p>
        </header>

        {children}
      </aside>
    </div>
  );
}
