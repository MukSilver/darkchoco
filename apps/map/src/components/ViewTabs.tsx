/**
 * 가운데 화면 탭 넷 — 지도 · 엔티티 · 관계 · 타임라인.
 *
 * 설계서 4.3.5 · 4.3.6 · 4.3.7 이 나머지 셋을 정의한다.
 *
 * 관계 탭은 2026-09-22 에 노션 관계선 DB 가 생긴 뒤 굽기가 관계선을 싣게 되어
 * 열었다 (2026-09-25). 전에는 「관계선 DB 없음」으로 막아 두었다.
 */

export type ViewTabKey = "map" | "entity" | "relation" | "timeline";

const TABS: { key: ViewTabKey; name: string; why?: string }[] = [
  { key: "map", name: "지도" },
  { key: "entity", name: "엔티티" },
  { key: "relation", name: "관계" },
  { key: "timeline", name: "타임라인" },
];

/** 아직 못 만든 탭. 눌러도 안 열린다. 지금은 없다 */
const LOCKED = new Set<ViewTabKey>();

export default function ViewTabs({
  current,
  onChange,
}: {
  current: ViewTabKey;
  onChange: (k: ViewTabKey) => void;
}) {
  /*
    피그마 ⑦-1 보기 탭 · 컴포넌트 시트 `07 / 01 Segmented`: 테두리 있는 통(235 × 39)에
    고른 탭만 테두리 있는 패널색 칸이다. 머리띠 웹 전환(`AppHeader`)과 같은 얼개라
    통 · 칸 모서리와 안쪽 3px 도 같게 둔다. 칸 폭은 ⑦-1 「지도」 칸 49px 에서 좌우
    10px 을 읽었다 — 전에는 좌우 24px 이라 통이 피그마보다 훨씬 넓었다
  */
  return (
    <nav
      aria-label="화면 전환"
      className="flex shrink-0 items-center rounded-[8px] border border-edge bg-track p-[3px]"
    >
      {TABS.map((t) => {
        const on = t.key === current;
        const locked = LOCKED.has(t.key);
        return (
          <button
            key={t.key}
            type="button"
            disabled={locked}
            aria-current={on ? "page" : undefined}
            onClick={() => onChange(t.key)}
            title={t.why}
            className={[
              // 좁은 창에서 「타임라인」 이 글자마다 쪼개지지 않게 (2026-09-28 최현서 4번)
              "whitespace-nowrap rounded-[6px] border px-[10px] py-[5px] text-[13px]",
              on
                ? "border-edge bg-panel font-semibold text-strong"
                : "border-transparent text-label disabled:cursor-not-allowed",
              !on && !locked ? "hover:text-body" : "",
            ].join(" ")}
          >
            {t.name}
          </button>
        );
      })}
    </nav>
  );
}
