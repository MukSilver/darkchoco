/**
 * 줌 규칙 — 지도(`MapCanvas`)와 관계도(`RelationTab`)가 같이 쓴다.
 *
 * 범위와 단위는 설계서 4.2.3 「50%~200%, 25% 단위」다. 관계도에는 설계서가 줌을 정하지
 * 않았는데 지도와 같은 규칙을 쓴다 (2026-09-28 최현서 5번 — 「관계도도 확대/축소」).
 *
 * **휠은 한 칸씩 모아서 옮긴다.** 전에는 휠 이벤트 하나마다 25% 라 트랙패드를 한 번 쓸면
 * 50% ↔ 200% 끝까지 튀었다 (2026-09-28 코드 분석). `deltaY` 를 모아 문턱(`WHEEL_STEP`)을
 * 넘을 때 한 단계 옮긴다. 마우스 휠 한 칸은 보통 `deltaY` 100 이라 한 칸이 한 단계다
 */

export const ZOOM_MIN = 50;
export const ZOOM_MAX = 200;
export const ZOOM_STEP = 25;

/** 휠 누적 문턱 */
export const WHEEL_STEP = 100;

export function clampZoom(z: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
}

/**
 * 휠 한 번. 모아 둔 값 `acc` 에 `deltaY` 를 더해, 문턱을 넘은 만큼 줌 단계를 돌려준다.
 * 돌려준 `steps` 는 양수면 확대, 음수면 축소다 (휠을 위로 = `deltaY` 음수 = 확대).
 * 줄 단위(`deltaMode` 1)로 오는 휠은 한 줄을 40 으로 본다
 */
export function wheelSteps(acc: number, deltaY: number, deltaMode = 0): { acc: number; steps: number } {
  const next = acc + (deltaMode === 1 ? deltaY * 40 : deltaY);
  const steps = Math.trunc(next / WHEEL_STEP);
  return { acc: next - steps * WHEEL_STEP, steps: -steps };
}
