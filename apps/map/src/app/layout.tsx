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
 */
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" data-mode="black" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
