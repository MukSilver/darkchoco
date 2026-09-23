/**
 * 앱 머리띠 — 설계서 4.2.1.
 *
 * 왼쪽부터 로고 · 웹 전환 탭 · (빈칸) · 기준 시각 · 검색창이다.
 * 높이는 `--h-header`(54px) 다.
 *
 * **웹 전환은 눌러도 아직 아무 일이 없다.** 오픈웹과 연결 3D 화면이
 * 우리 몫이 아니거나 보류라서 갈 곳이 없다 (설계서 1.2, DEV.md 3-1).
 * 눌리지 않는다는 것이 보이게 흐리게 두고 `title` 로 까닭을 적었다.
 *
 * 검색창을 누르면 검색이 열린다 (설계서 4.2.2). 무엇을 찾을 수 있는지는
 * `SearchOverlay` 머리에 적어 두었다 — 지금은 엔티티 하나뿐이다.
 */

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
  /**
   * 데이터 기준 시각. 굽기가 낸 `generatedAt` 을 그대로 받는다.
   * 화면에는 `UTC 2026-09-16 09:30` 꼴로 낸다 (설계서 4.2.1 예시)
   */
  generatedAt: string;
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

export default function AppHeader({
  current,
  generatedAt,
  onSearch,
}: AppHeaderProps) {
  return (
    <header
      className="flex shrink-0 items-center gap-s5 border-b border-divider bg-panel px-s5"
      style={{ height: "var(--h-header)" }}
    >
      <div className="flex items-baseline gap-s2">
        <span className="text-[15px] font-bold tracking-[0.14em] text-title">
          WEB SCOPE
        </span>
        <span className="text-[9px] tracking-[0.22em] text-label">
          ECOSYSTEM MAP
        </span>
      </div>

      <nav
        aria-label="웹 전환"
        className="flex items-center gap-s1 rounded-full bg-track p-[3px]"
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
                "flex items-center gap-s2 rounded-full px-s4 py-[5px] text-[12px]",
                on
                  ? "bg-selected font-semibold text-strong"
                  : "text-label disabled:cursor-not-allowed",
              ].join(" ")}
            >
              <span
                aria-hidden
                className="size-[6px] rounded-full"
                style={{
                  background: on ? w.dot : "var(--t-web-inactive)",
                }}
              />
              {w.name}
            </button>
          );
        })}
      </nav>

      <div className="flex-1" />

      <time
        dateTime={generatedAt}
        className="text-[12px] tabular-nums tracking-[0.04em] text-label"
      >
        {utcLabel(generatedAt)}
      </time>

      <button
        type="button"
        onClick={onSearch}
        className="flex h-[34px] w-[320px] items-center gap-s2 rounded-full border border-edge-input bg-input px-s4 text-left"
      >
        <span aria-hidden className="text-[12px] text-disabled">
          ⌕
        </span>
        <span className="flex-1 text-[12px] text-disabled">
          노드 · 키워드 · 엔티티 검색
        </span>
        <kbd className="rounded bg-kbd px-s2 py-[2px] text-[10px] text-label">
          ⌘K
        </kbd>
      </button>
    </header>
  );
}
