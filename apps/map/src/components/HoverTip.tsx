/**
 * 영토 호버 툴팁 — 설계서 4.2.3 의 여섯 줄. 폭 255, 높이 141.
 *
 *     줄 1   영토 이름, 상태 칩          Qilin · ACTIVE
 *     줄 2   섬 이름, 섬 안 비중 (3.5)   랜섬웨어 섬 · 섬 안 비중 23%
 *     줄 3   활동도, 30일 변화           93 ▲12
 *     줄 4   사건 수                     38건
 *     줄 5   최근 관측                   09-14
 *     줄 6   안내                        클릭: 선택 (떠오름 · 관계선)
 *
 * **설계서가 「칸 수 표기와 더블클릭 안내는 수정 예정」이라고 적어 두었다**
 * (5.3). 그래서 칸 수는 안 넣고 더블클릭 안내도 안 넣었다. 영토 더블클릭은
 * 동작이 없다고 4.2.3 이 명시했다.
 */

import type { TerritoryShape } from "@/lib/layout";
import type { Status } from "@/lib/score";

/**
 * 상태 칩 표기와 색.
 *
 * **설계서가 상태를 두 군데에서 서로 다르게 적었다.** 3.7 은 값을 한글로
 * (`활성`, `관측 중`) 정했는데, 화면을 정한 4.2.3 의 툴팁 예시는
 * `Qilin · ACTIVE` 로 영문이다. 피그마도 영문 칩이다. 화면에 무엇을 낼지는
 * 화면 절이 정하는 것이 맞고 피그마와도 같으므로 영문으로 낸다.
 * 데이터 쪽 값은 3.7 대로 한글 그대로 둔다.
 *
 * 설계서에 상태는 둘뿐이다. 세 번째 값은 없다.
 */
const STATUS_CHIP: Record<Status, { text: string; tone: string }> = {
  활성: { text: "ACTIVE", tone: "var(--t-trend-up)" },
  "관측 중": { text: "QUIET", tone: "var(--t-text-label)" },
};

export type HoverTipProps = {
  territory: TerritoryShape;
  islandName: string;
  /** 최근 관측일. `MM-DD` 로 낸다. 없으면 줄을 비운다 */
  lastSeen: string | null;
  /** 캔버스 안에서의 자리 (px) */
  at: { x: number; y: number };
};

export default function HoverTip({
  territory: t,
  islandName,
  lastSeen,
  at,
}: HoverTipProps) {
  const m = t.metrics;
  /**
   * **활동도 옆 ▲▼ 는 사건 수 30일 변화율이다** (설계서 3.7, 판 1.2).
   *
   * 판 1.1 은 활동도끼리 뺀 값이었는데, 판 1.2 에서 활동도가 사건과 무관한
   * 규모 원자료로 갈리면서 그 차가 뜻을 잃었다. 직전 30일이 0건이면 나눌 수
   * 없어 아예 표시하지 않는다.
   */
  const rate = m.countChangeRate30d;

  return (
    <div
      className="pointer-events-none absolute z-20 flex flex-col gap-s2 rounded-[10px] border border-edge bg-panel px-s4 py-s3 shadow-lg"
      style={{ width: "var(--w-tooltip)", left: at.x + 14, top: at.y + 14 }}
    >
      <div className="flex items-baseline gap-s2">
        <span className="text-[13px] font-semibold text-title">{t.name}</span>
        <span
          className="text-[10px] font-semibold tracking-[0.06em]"
          style={{ color: STATUS_CHIP[m.status].tone }}
        >
          {STATUS_CHIP[m.status].text}
        </span>
      </div>

      <p className="text-[11px] text-label">
        {islandName} 섬 · 섬 안 비중 {Math.round(m.shareInIsland)}%
      </p>

      <p className="flex items-baseline gap-s2 text-[11px]">
        <span className="text-label">활동도</span>
        <span className="text-[15px] font-semibold tabular-nums text-strong">
          {m.activity}
        </span>
        {rate !== null && Math.round(rate) !== 0 && (
          <span
            className="tabular-nums"
            style={{
              color: rate > 0 ? "var(--t-trend-up)" : "var(--t-trend-down)",
            }}
          >
            {rate > 0 ? "▲" : "▼"}
            {Math.abs(Math.round(rate))}%
          </span>
        )}
      </p>

      <p className="text-[11px] tabular-nums text-body">{m.eventCount}건</p>

      <p className="text-[11px] tabular-nums text-label">
        최근 관측 {lastSeen ?? "—"}
      </p>

      <p className="border-t border-divider pt-s2 text-[10px] text-label">
        클릭: 선택 (떠오름 · 관계선)
      </p>
    </div>
  );
}
