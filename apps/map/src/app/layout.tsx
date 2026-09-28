import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "생태계 지도",
  description: "유출 생태계를 섬 지도로 보여 줍니다",
  // 색인 거부 세 겹 가운데 둘째 (public/robots.txt · public/_headers 와 같이 푼다)
  robots: { index: false, follow: false, noarchive: true },
};

/**
 * **`data-mode` 를 여기서 건다.** 값은 색 판 이름이지 밝기가 아니다.
 *
 *     white   ⑦ 화이트 (참고용)
 *     black   ⑦ 라이트 블랙  ← 다크웹 화면이 쓰는 판
 *     neon    ⑦ 다크 네온 (참고용)
 *     open    ④ 오픈웹
 *
 * 다크웹은 「항상 다크(라이트 블랙, 차콜)」이고 사용자가 바꾸는 단추가
 * 없다 (설계서 4.2.6). 그래서 여기에 박아 둔다.
 *
 * 피그마 보드가 「프레임의 변수 모드만 바꾸면 같은 컴포넌트가 해당 화면
 * 색으로 바뀐다」고 적어 둔 것을 그대로 옮긴 구조다.
 *
 * **`body` 높이를 창에 묶는다.** 전에는 `min-h-full` 이라 긴 목록(엔티티 표 · 타임라인 ·
 * 검색 결과)이 페이지째 늘어나 스냅샷 바와 머리띠가 스크롤로 밀려났다 (2026-09-28 최현서
 * 10번). 이제 각 영역의 `overflow-y-auto` 가 제 안에서만 굴린다. 창이 화면 최소 크기
 * (`page.tsx` 바깥 틀)보다 작으면 **스크롤바는 `body` 한 곳에만** 뜬다 (4번 「화면은 최대로
 * 고정해 두고, 줄였을 때 스크롤바를 띄운다」).
 *
 * **`html` 은 넘침을 막고 `body` 가 제 높이 안에서 굴린다.** `html` 이 넘침을 두면 `body` 의
 * 스크롤이 문서로 넘어가서, 폭만 좁은 창에서도 가로 스크롤바 두께만큼 세로 스크롤이 더
 * 생겼다(`h-dvh` 를 쓴 첫 판, 2026-09-28 검토)
 */
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" data-mode="black" className="h-full overflow-hidden antialiased">
      <body className="h-full overflow-auto">{children}</body>
    </html>
  );
}
