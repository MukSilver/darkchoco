/**
 * 가운데 화면 탭 넷 — 지도 · 엔티티 · 관계 · 타임라인.
 *
 * 설계서 4.3.5 · 4.3.6 · 4.3.7 이 나머지 셋을 정의한다. 지도와 엔티티는 열린다.
 *
 * **관계 탭만 못 만든다.** 관계선 DB 가 노션에 아직 없다 (설계서 5.1-4).
 * 눌리지 않게 두고 까닭을 `title` 로 적었다.
 */

export type ViewTabKey = "map" | "entity" | "relation" | "timeline";

const TABS: { key: ViewTabKey; name: string; why?: string }[] = [
  { key: "map", name: "지도" },
  { key: "entity", name: "엔티티" },
  {
    key: "relation",
    name: "관계",
    why: "관계선 DB 가 노션에 아직 없습니다 (설계서 5.1-4)",
  },
  { key: "timeline", name: "타임라인" },
];

/** 아직 못 만든 탭. 눌러도 안 열린다 */
const LOCKED = new Set<ViewTabKey>(["relation"]);

export default function ViewTabs({
  current,
  onChange,
}: {
  current: ViewTabKey;
  onChange: (k: ViewTabKey) => void;
}) {
  return (
    <nav
      aria-label="화면 전환"
      className="flex items-center gap-s1 rounded-[10px] bg-track p-[3px]"
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
              "rounded-[8px] px-s5 py-s2 text-[13px]",
              on
                ? "bg-selected font-semibold text-strong"
                : "text-label disabled:cursor-not-allowed",
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
