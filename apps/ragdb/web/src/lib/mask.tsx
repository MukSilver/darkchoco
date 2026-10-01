// 가림 표시. 서버는 「(조직명 가림)」 같은 글자를 준다. 화면은 그 자리를 피그마 「가림 표시」 알약으로 그린다.
// 글자를 지우는 것이 아니라 모양만 바꾼다. 원래 글자는 읽어 주는 이름(aria-label)과 복사할 때 그대로 남는다.
import type { ReactNode } from 'react'

const MARKS = ['(조직명 가림)', '(주소 가림)', '(다른 이름 가림)', '(개인정보 가림)']
const SPLIT = new RegExp(`(${MARKS.map((m) => m.replace(/[()]/g, '\\$&')).join('|')})`, 'g')

export function Mask({ label }: { label: string }) {
  return (
    <span
      aria-label={label.replace(/[()]/g, '')}
      title={label.replace(/[()]/g, '')}
      className="mx-[1px] inline-flex items-center rounded-[5px] border border-mask-line bg-mask-bg px-[7px] align-[0.08em] text-[11px] leading-[1.6] font-medium tracking-[0.66px] whitespace-nowrap text-mask-text"
    >
      가림
    </span>
  )
}

/** 글 속의 가림 표시를 알약으로 바꿔 그린다. */
export function masked(text: string | null | undefined): ReactNode {
  if (!text) return null
  const parts = text.split(SPLIT)
  if (parts.length === 1) return text
  return parts.map((p, i) => (MARKS.includes(p) ? <Mask key={i} label={p} /> : p))
}
