/**
 * 앱 머리띠 — 설계서 4.2.1.
 *
 * 왼쪽부터 로고 · 웹 전환 탭 · (빈칸) · 기준 시각 · 검색창이다.
 * 높이는 `--h-header`(54px) 다. 모양은 피그마 ⑦-1 머리띠와 컴포넌트 시트
 * `11 / 02 App Header` 를 따랐다.
 *
 * **로고는 팀 로고 마크(섬 색 점 넷)와 두 줄 글씨다.** 누르면 첫 화면으로 간다
 * (설계서 4.2.1 「로고 — 클릭 시 첫 화면」). 정본의 첫 화면은 연결 3D(③-0)인데
 * 3D 가 보류라 다크웹을 처음 연 상태로 돌린다. 무엇을 되돌리는지는 부르는 쪽
 * (`page.tsx` `goHome`)이 정한다. `onHome` 을 안 주면 로고는 눌리지 않는다.
 *
 * **웹 전환은 눌러도 아직 아무 일이 없다.** 오픈웹과 연결 3D 화면이
 * 우리 몫이 아니거나 보류라서 갈 곳이 없다 (설계서 1.2, DEV.md 3-1).
 * 눌리지 않는다는 것이 보이게 글씨를 흐리게 두고 `title` 로 까닭을 적었다.
 * 점은 고르지 않은 탭도 제 색으로 칠한다 — 피그마 ⑦-1 이 그렇다. 색은 설계서 6.5
 * 「탭 강조」 값이다 (`tokens.css`).
 *
 * 검색창을 누르면 검색이 열린다 (설계서 4.2.2). 열린 검색 창은 `children` 으로
 * 받아 검색창 자리에 겹쳐 놓는다 — 피그마 ⑦-10 처럼 그 자리에서 입력하고 아래로
 * 목록이 펼쳐진다. 무엇을 찾을 수 있는지는 `SearchOverlay` 머리에 적어 두었다.
 */

import type { ReactNode } from "react";

import { TeamMark } from "./RelBits";
import type { Web } from "@/lib/types";

/** 웹 전환 탭 셋. 순서는 설계서 4.2.1 의 「오픈웹 / 연결 / 다크웹」이다 */
const WEBS: { key: Web | "link"; name: string; dot: string }[] = [
  { key: "open", name: "오픈웹", dot: "var(--t-web-open)" },
  { key: "link", name: "연결", dot: "var(--t-web-connection)" },
  { key: "dark", name: "다크웹", dot: "var(--t-web-dark)" },
];

export type AppHeaderProps = {
  /** 지금 보고 있는 웹. 이 탭만 진하게 보인다 */
  current: Web | "link";
  /** 검색창을 눌렀을 때 */
  onSearch: () => void;
  /** 로고를 눌렀을 때 — 첫 화면으로 (설계서 4.2.1). 없으면 로고가 눌리지 않는다 */
  onHome?: () => void;
  /**
   * 데이터 기준 시각. 굽기가 낸 `generatedAt` 을 그대로 받는다.
   * 화면에는 `UTC 2026-09-16 09:30` 꼴로 낸다 (설계서 4.2.1 예시)
   */
  generatedAt: string;
  /** 검색창에 남겨 둘 글. 검색 결과로 이동했을 때 그 검색어다 (피그마 ⑦-10b) */
  query?: string;
  /** 열린 검색 창. 검색창 자리에 겹친다 */
  children?: ReactNode;
};

/** ISO 문자열을 `UTC 2026-09-16 09:30` 으로. 설계서 4.2.1 의 예시 형식이다 */
function utcLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "기준 시각 모름";
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    `UTC ${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}` +
    ` ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`
  );
}

/**
 * 로고 속. 마크 18px 에 글씨 두 줄이다 (⑦-1 에서 마크 16~18px, 글씨와 12px 띄움).
 * 마크는 행위자 노드 상징과 같은 `TeamMark` 다 — 설계서 4.3.6 이 행위자 노드의 기본
 * 상징을 「팀 로고 마크」로 정해 둘이 같은 그림이어야 한다. 피그마 머리띠는 점
 * 크기가 조금씩 다른데(8 · 7 · 7 · 5px) 행위자 노드와 어긋나지 않게 고른 크기로 둔다
 */
function Logo() {
  return (
    <>
      <svg aria-hidden width="18" height="18" viewBox="0 0 18 18" className="shrink-0">
        <TeamMark cx={9} cy={9} size={18} />
      </svg>
      <span className="flex flex-col gap-[5px] text-left">
        <span className="text-[14px] font-bold leading-none tracking-[0.08em] text-title">
          WEB SCOPE
        </span>
        <span className="font-mono text-[9px] leading-none tracking-[0.1em] text-label">
          ECOSYSTEM MAP
        </span>
      </span>
    </>
  );
}

export default function AppHeader({
  current,
  generatedAt,
  onSearch,
  onHome,
  query,
  children,
}: AppHeaderProps) {
  return (
    <header
      className="flex shrink-0 items-center gap-s5 border-b border-divider bg-panel px-s5"
      style={{ height: "var(--h-header)" }}
    >
      {onHome ? (
        <button
          type="button"
          onClick={onHome}
          aria-label="WEB SCOPE — 첫 화면으로"
          title="첫 화면으로"
          className="flex items-center gap-s3 rounded-[8px]"
        >
          <Logo />
        </button>
      ) : (
        <div className="flex items-center gap-s3">
          <Logo />
        </div>
      )}

      {/*
        웹 전환 통 (⑦-1): 테두리 있는 둥근 네모 통에 고른 탭만 테두리 있는 패널색
        칸이다. 화면 탭(`ViewTabs`)과 같은 얼개다
      */}
      <nav
        aria-label="웹 전환"
        className="flex items-center gap-s1 rounded-[8px] border border-edge bg-track p-[3px]"
      >
        {WEBS.map((w) => {
          const on = w.key === current;
          return (
            <button
              key={w.key}
              type="button"
              disabled={!on}
              aria-current={on ? "page" : undefined}
              title={
                on
                  ? undefined
                  : "이 화면은 아직 없습니다 — 오픈웹은 다른 팀 몫이고 연결 3D 는 보류입니다"
              }
              className={[
                "flex items-center gap-s2 rounded-[6px] border px-s4 py-[5px] text-[13px]",
                on
                  ? "border-edge bg-panel font-semibold text-strong"
                  : "border-transparent text-label disabled:cursor-not-allowed",
              ].join(" ")}
            >
              <span
                aria-hidden
                className="size-[7px] rounded-full"
                style={{ background: w.dot }}
              />
              {w.name}
            </button>
          );
        })}
      </nav>

      <div className="flex-1" />

      <time
        dateTime={generatedAt}
        className="font-mono text-[12px] tabular-nums tracking-[0.04em] text-label"
      >
        {utcLabel(generatedAt)}
      </time>

      <div className="relative h-[34px] w-[320px]">
        <button
          type="button"
          onClick={onSearch}
          className="flex size-full items-center gap-s2 rounded-full border border-edge-input bg-input px-s4 text-left"
        >
          <span aria-hidden className="text-[12px] text-disabled">
            ⌕
          </span>
          <span className={"flex-1 truncate text-[12px] " + (query ? "text-body" : "text-disabled")}>
            {query || "노드 · 키워드 · 엔티티 검색"}
          </span>
          <kbd className="rounded bg-kbd px-s2 py-[2px] text-[10px] text-label">
            ⌘K
          </kbd>
        </button>
        {children}
      </div>
    </header>
  );
}
