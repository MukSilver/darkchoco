/**
 * 오른쪽 패널의 틀 — 폭 312, 접힘 48 (설계서 4.2.4).
 *
 * 지도 · 엔티티 · 타임라인 탭은 `DetailPanel` 이, 관계 탭은 `RelationPanel`
 * 이 이 틀을 쓴다. 두 패널은 머리글 모양과 접는 법이 같고 본문만 다르다
 * (설계서 4.3.6 「우측 패널 (중심 영토 기준)」).
 *
 * 양식은 설계서 4.2.4 「폭 312, 왼쪽 1px 테두리, 헤더와 탭 바 아래 구분선, 동그라미
 * ‹ 핸들」이다. 치수는 피그마 ⑦-1(펼침) · ⑦-7 · ⑦-9b(접힘 레일) 픽셀에서 읽었다.
 *
 *   머리글       위아래 12 · 줄 사이 4. 아래 구분선을 패널 폭 전체로 긋는다
 *   탭 바        본문 맨 위 `nav`. 구분선을 패널 폭 전체로 편다 (아래 BODY 주석)
 *   핸들         지름 24, 왼쪽 테두리에 반쯤 걸친다. 가운데가 머리글 구분선 11px 아래
 *   접힘 레일     같은 자리에 같은 핸들, 그 아래 세로 글씨 「상세패널」
 *
 * **핸들은 펼침과 접힘 모두 ‹ 다.** 설계서 4.2.4 표가 두 상태 모두 「‹ 클릭」으로
 * 적었고 피그마 ⑦-1 · ⑦-7 도 같다. 전에는 접힘 레일만 › 였다.
 */

"use client";

import type { ReactNode } from "react";

export type PanelHeader = {
  /** 눈표 앞쪽 글씨. `TERRITORY` 처럼 대문자로 낸다 */
  kindLabel: string;
  /** 눈표 글씨 색 토큰. 섬 색이거나 null(회색). 눈표 앞뒤가 이 한 색이다 */
  kindToken: string | null;
  /** 눈표를 강조색으로 칠한다. 관계 탭의 `RELATION · 선택됨` 이 그렇다 */
  kindAccent?: boolean;
  stateLabel: string;
  title: string;
  subtitle: string;
};

/**
 * 핸들. 펼침과 접힘이 같은 자리 같은 모양이다.
 *
 * `top` 89px 은 머리글 한 줄씩(눈표 15 · 제목 25 · 부제 18 + 여백 12 · 12 · 4 · 4 + 구분선 1
 * = 91)일 때 핸들 가운데가 구분선 11px 아래에 오는 값이다 (⑦-1). 제목이 두 줄로
 * 늘면 핸들이 머리글 옆에 걸리지만, 핸들은 왼쪽 여백(24) 안쪽 12px 까지만 들어와서
 * 글씨를 가리지 않는다
 */
const HANDLE =
  "absolute left-[-12px] top-[89px] z-10 grid size-[24px] place-items-center rounded-full border border-edge bg-panel text-[11px] text-body hover:text-title";

/**
 * 본문. 여백 24, 조각 사이 24.
 *
 * **맨 위 `nav` 는 여백을 거슬러 패널 폭 전체로 편다.** `DetailPanel` 의 개요 / 사건 /
 * 연결 탭 바다. 설계서 4.2.4 「탭 바 아래 구분선」이 피그마 ⑦-1 에서 패널 끝에서
 * 끝까지 이어진다. 탭 바는 머리글 구분선에 붙고 글씨 위 여백은 8 이다 (탭 바 높이 40).
 * 관계 탭 패널처럼 탭 바가 없으면 본문이 구분선 24px 아래에서 시작한다
 */
const BODY =
  "flex flex-col gap-s5 p-s5 [&>nav:first-child]:-mx-s5 [&>nav:first-child]:-mt-s5 [&>nav:first-child]:px-s5 [&>nav:first-child]:pt-s2";

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
        className="relative flex shrink-0 flex-col items-center border-l border-divider bg-panel pt-[132px]"
        style={{ width: "var(--w-panel-rail)" }}
      >
        <button
          type="button"
          aria-label="상세패널 펼치기"
          aria-expanded={false}
          onClick={() => onToggle(true)}
          className={HANDLE}
        >
          ‹
        </button>
        {/* 한글은 세로쓰기에서 글자가 선다 (⑦-7 「상 세 패 널」) */}
        <span
          className="text-[12px] tracking-[0.35em] text-label"
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
    // **본문은 바깥 틀 안에 절대 위치로 띄운다.** 틀 높이는 가운데 화면이 정하고
    // 본문은 그 안에서만 굴러간다. 전에는 `body` 가 `min-h-full` 이라 이렇게 피해야
    // 긴 [연결] 목록이 화면 전체를 늘이지 않았다. 2026-09-28 에 `body` 를 창 높이로
    // 묶었지만(`layout.tsx`) 핸들을 밖으로 내미는 구조라 그대로 둔다
    <div className="relative shrink-0" style={{ width: "var(--w-panel)" }}>
      <button
        type="button"
        aria-label="상세패널 접기"
        aria-expanded
        onClick={() => onToggle(false)}
        className={HANDLE}
      >
        ‹
      </button>

      <aside className="absolute inset-0 flex flex-col overflow-y-auto border-l border-divider bg-panel">
        <header className="flex shrink-0 flex-col gap-s1 border-b border-divider px-s5 py-s3">
          {/*
            눈표는 앞뒤가 한 색이다. 피그마 ⑦-2 「ISLAND · 선택됨」 · ⑦-11b 「TERRITORY ·
            선택됨」 이 통째로 칠해져 있다 — 전에는 뒤쪽(「· 선택됨」)만 회색이었다.
            아무것도 안 고른 「ECOSYSTEM · 선택 없음」(⑦-1)은 `kindColor` 가 회색이라 그대로다
          */}
          <p className="font-mono text-[10px] tracking-[0.16em]" style={{ color: kindColor }}>
            {header.kindLabel} · {header.stateLabel}
          </p>
          <h2 className="text-[20px] font-semibold leading-tight text-title">{header.title}</h2>
          <p className="text-[12px] text-label">{header.subtitle}</p>
        </header>

        <div className={BODY}>{children}</div>
      </aside>
    </div>
  );
}
