/**
 * 재생 단추 그림 (피그마 ⑦-9b · ⑦-9c). 타임라인 탭과 스냅샷 바가 같이 쓴다.
 *
 * **글자(◀ ▶ ⏸)를 쓰지 않는다.** ⏸ · ▶ 는 윈도에서 컬러 이모지로 바뀌어 피그마의
 * 흰 도형과 달라진다. 크기는 ⑦-9b 에서 읽었다 — 삼각형 폭 6px(▶▶ 는 둘을 3px 띄움),
 * 일시정지 막대 약 4px 둘을 1.5px 띄움.
 *
 * 전에는 타임라인 탭 안에만 있어서 스냅샷 바 재생 단추는 글자였다 — 같은 단추가 탭마다
 * 다르게 보였다 (2026-09-28 코드 분석)
 */
export default function PlayGlyph({ kind }: { kind: "prev" | "play" | "pause" | "next" }) {
  const w = kind === "next" ? 16 : 12;
  return (
    <svg aria-hidden width={w} height="12" viewBox={`0 0 ${w} 12`} fill="currentColor">
      {kind === "prev" && <path d="M9 2.5v7L3 6z" />}
      {kind === "play" && <path d="M3.5 2v8L10 6z" />}
      {kind === "pause" && (
        <>
          <rect x="1.5" y="2" width="3.75" height="8" rx="0.5" />
          <rect x="6.75" y="2" width="3.75" height="8" rx="0.5" />
        </>
      )}
      {kind === "next" && (
        <>
          <path d="M0.5 2.5v7L6.5 6z" />
          <path d="M9.5 2.5v7L15.5 6z" />
        </>
      )}
    </svg>
  );
}
