/**
 * 판 위 휠을 모아 줌 단계로 넘기고, 둘레 칸 · 페이지 스크롤은 막는다 — 지도 캔버스와 관계도가 같이 쓴다.
 *
 * React 의 `onWheel` 은 passive 듣개라 `preventDefault` 가 안 먹는다. 그래서 타임라인 왼쪽 칸처럼
 * 세로로 굴러가는 칸 안에 지도를 두면 휠 한 번에 줌과 칸 스크롤이 같이 일어났다 (2026-09-29 묶음 5
 * 검토). 창이 화면 최소 높이보다 낮아 페이지가 굴러갈 때도 같다. passive 를 끈 듣개를 직접 단다.
 *
 * 줌이 그쪽 끝(`atEnd`)이면 휠을 막지 않고 칸 스크롤에 넘긴다 — 50% 에서도 휠을 먹으면 타임라인 왼쪽
 * 칸이 지도 위에서 안 굴러갔다 (2026-09-29 묶음 7 검토). `dir` 는 +1 이 확대(휠 위로), −1 이 축소다
 */

import { useEffect, useEffectEvent, useRef, type RefObject } from "react";

import { wheelSteps } from "@/lib/zoom";

export function useWheelSteps(
  ref: RefObject<HTMLElement | null>,
  onSteps: (steps: number) => void,
  atEnd?: (dir: 1 | -1) => boolean,
) {
  // 문턱을 못 넘은 휠 양. 모아서 넘을 때 한 단계씩 (`wheelSteps`)
  const acc = useRef(0);
  const fire = useEffectEvent((e: WheelEvent) => {
    if (e.deltaY !== 0 && atEnd?.(e.deltaY < 0 ? 1 : -1)) {
      acc.current = 0;
      return;
    }
    e.preventDefault();
    const r = wheelSteps(acc.current, e.deltaY, e.deltaMode);
    acc.current = r.acc;
    if (r.steps) onSteps(r.steps);
  });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const h = (e: WheelEvent) => fire(e);
    el.addEventListener("wheel", h, { passive: false });
    return () => el.removeEventListener("wheel", h);
  }, [ref]);
}
