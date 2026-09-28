/**
 * 검색 단축키 표시 — 맥은 「⌘K」, 그 밖은 「Ctrl K」 (설계서 4.2.2 「Ctrl+K(맥 ⌘K)」). 전에는 윈도에서도
 * ⌘K 라 적혔다 (2026-09-28 코드 분석). 누르는 키는 둘 다 받는다(`page.tsx`).
 *
 * 미리 굽는 첫 그림은 플랫폼을 몰라 「Ctrl K」 로 두고, 브라우저에서 맥이면 바꾼다
 * (`useSyncExternalStore` 의 서버 값 → 브라우저 값이라 하이드레이션이 어긋나지 않는다).
 */

import { useSyncExternalStore } from "react";

const noSubscribe = () => () => {};
const onMac = () => /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

export function useShortcutLabel(): string {
  return useSyncExternalStore(
    noSubscribe,
    () => (onMac() ? "⌘K" : "Ctrl K"),
    () => "Ctrl K",
  );
}
