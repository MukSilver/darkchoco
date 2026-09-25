/**
 * 영토 호버 툴팁 — 설계서 4.2.3 의 여섯 줄, 피그마 `13_⑦-1 하단` 툴팁 ·
 * 컴포넌트 시트 `11 / 02 Map Tooltip`. 폭 255, 높이 141.
 *
 *     줄 1   섬 색 육각 · 영토 이름 · 상태 알약      ⬢ Qilin (ACTIVE)
 *     줄 2   섬 이름, 섬 안 비중 (3.6)              랜섬웨어 섬 · 섬 안 비중 23%
 *     줄 3~5 활동도 · 사건 · 최근 관측 세 칸         활동도 / 93 ▲12%   사건 / 38건   최근 관측 / 09-14
 *     줄 6   안내                                   클릭: 선택 (떠오름 · 관계선)
 *
 * 설계서 표는 줄 3 · 4 · 5 를 따로 적었지만 피그마는 세 값을 이름 위 · 값 아래의
 * 세 칸으로 한 줄에 둔다. 모양은 피그마를 따르고 내용은 설계서를 따른다.
 *
 * **설계서가 「칸 수 표기와 더블클릭 안내는 수정 예정」이라고 적어 두었다**
 * (5.3). 그래서 피그마의 「칸 22 / 61」 자리에 섬 안 비중을 적고 더블클릭 안내는
 * 안 넣었다. 영토 더블클릭은 동작이 없다고 4.2.3 이 명시했다.
 *
 * 캔버스 오른쪽 · 아래 끝에서는 커서 반대쪽으로 뒤집는다 (`tipPlace`). 전에는
 * 커서 오른쪽 아래에만 띄워서 가장자리 영토의 툴팁이 캔버스 밖으로 잘렸다.
 */

import { hexPoints } from "@/lib/hex";
import type { TerritoryShape } from "@/lib/layout";
import { tipPlace, type Pt, type Size } from "@/lib/mapui";
import type { Status } from "@/lib/score";

/** 툴팁 크기 — `tokens.css` 의 `--w-tooltip` · `--h-tooltip` 과 같은 값이다 */
const TIP: Size = { w: 255, h: 141 };

/** 머리 줄의 섬 색 육각. 지도 칸과 같은 뾰족 위 육각이다 */
const HEX_ICON = `M${hexPoints(0, 0, 8)
  .map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`)
  .join("L")}Z`;

/**
 * 상태 알약. 글씨는 **`ACTIVE` · `QUIET` 영문이다** (2026-09-26 다시 바꿈).
 *
 * 피그마를 따랐다. 컴포넌트 시트 `02 · Map Tooltip` 의 알약 글씨가 「ACTIVE」 이고,
 * 설계서 4.2.3 표 1번 줄 예시도 「Qilin · ACTIVE」 다. 화면 시안 `13_⑦-1 하단` 의
 * 알약은 글씨가 채움색과 같아 안 읽혀 근거로 쓰지 않았다. 관측 중 쪽은 어느 시안에도
 * 없어 처음 판(aa88112)이 쓰던 「QUIET」 을 짝으로 둔다.
 *
 * 한동안 엔티티 탭 칩(⑦-7)에 맞춰 한글(`활성` · `관측 중`)로 적었다. 엔티티 탭은
 * 설계서 4.3.5 가 「활성 / 관측 중 (3.7)」 으로 적어 한글 그대로 두고, 툴팁만 피그마
 * 글씨를 쓴다. 데이터 값(`Status`)은 3.7 대로 한글이다. 색은 엔티티 탭 칩과 같다.
 */
const STATUS_PILL: Record<Status, { text: string; className: string }> = {
  활성: { text: "ACTIVE", className: "bg-success-bg text-success border-success-edge" },
  "관측 중": { text: "QUIET", className: "bg-neutral-bg text-neutral border-neutral-edge" },
};

export type HoverTipProps = {
  territory: TerritoryShape;
  islandName: string;
  /** 최근 관측일. `MM-DD` 로 낸다. 없으면 「—」 */
  lastSeen: string | null;
  /** 캔버스 안에서의 마우스 자리 (px) */
  at: Pt;
  /** 캔버스 크기 (px). 넘치면 뒤집는다 */
  box: Size;
};

export default function HoverTip({
  territory: t,
  islandName,
  lastSeen,
  at,
  box,
}: HoverTipProps) {
  const m = t.metrics;
  /**
   * **활동도 옆 ▲▼ 는 사건 수 30일 변화율이다** (설계서 3.7, 판 1.2).
   *
   * 판 1.1 은 활동도끼리 뺀 값이었는데, 판 1.2 에서 활동도가 사건과 무관한
   * 규모 원자료로 갈리면서 그 차가 뜻을 잃었다. 직전 30일이 0건이면 나눌 수
   * 없어 아예 표시하지 않는다. 자리는 설계서 표 3번 줄 · 피그마대로 활동도 칸이다.
   */
  const rate = m.countChangeRate30d;
  const { left, top } = tipPlace(at, TIP, box);

  return (
    <div
      className="pointer-events-none absolute z-20 flex flex-col rounded-[12px] border border-edge bg-panel px-s4 py-s3 shadow-xl"
      style={{ width: "var(--w-tooltip)", left, top }}
    >
      <div className="flex items-center gap-s2">
        <svg aria-hidden viewBox="-9 -9 18 18" className="size-[14px] shrink-0">
          <path d={HEX_ICON} fill={`var(--t-island-${t.token})`} />
        </svg>
        <span className="min-w-0 truncate text-[14px] font-semibold text-title">{t.name}</span>
        <span
          className={
            "shrink-0 rounded-full border px-s2 py-[1px] text-[10px] font-semibold tracking-[0.04em] " +
            STATUS_PILL[m.status].className
          }
        >
          {STATUS_PILL[m.status].text}
        </span>
      </div>

      <p className="mt-s1 text-[12px] text-label">
        {islandName} 섬 · 섬 안 비중 {Math.round(m.shareInIsland)}%
      </p>

      <dl className="mt-s3 flex gap-s4">
        <div>
          <dt className="text-[11px] text-label">활동도</dt>
          <dd className="flex items-baseline gap-s1 text-[13px] font-semibold tabular-nums text-strong">
            {m.activity}
            {rate !== null && Math.round(rate) !== 0 && (
              <span
                className="text-[11px]"
                style={{
                  color: rate > 0 ? "var(--t-trend-up)" : "var(--t-trend-down)",
                }}
              >
                {rate > 0 ? "▲" : "▼"}
                {Math.abs(Math.round(rate))}%
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] text-label">사건</dt>
          <dd className="text-[13px] font-semibold tabular-nums text-strong">
            {m.eventCount}건
          </dd>
        </div>
        <div>
          <dt className="text-[11px] text-label">최근 관측</dt>
          <dd className="text-[13px] font-semibold tabular-nums text-strong">
            {lastSeen ?? "—"}
          </dd>
        </div>
      </dl>

      <p className="mt-s3 border-t border-divider pt-s2 text-[11px] text-label">
        클릭: 선택 (떠오름 · 관계선)
      </p>
    </div>
  );
}
