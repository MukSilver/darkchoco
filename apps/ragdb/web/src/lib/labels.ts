// 서버가 주는 값을 화면 말로 바꾸는 곳. 서버 값은 바꾸지 않고 여기서만 바꿔 부른다.
import type { Kind } from '../types'

/** 종류 이름. 피그마 「답 · 끝」 의 출처 카드 표기를 따른다. 팀이 대응표를 주면 여기만 고친다. */
export const KIND_LABEL: Record<Kind, string> = {
  포럼: '포럼',
  텔레그램: '텔레그램',
  랜섬웨어: '랜섬웨어',
  행위자: '활동 계정',
  사고: '유출 사고',
  판정: '검증 결과',
}

export type Tone = 'online' | 'offline' | 'unknown' | 'plain'

/** 상태 값의 색. online 초록, offline 회색, 미확인 노랑 (피그마 「상태 표시」). 그 밖의 값은 글자만. */
export function statusTone(status: string | null): Tone {
  if (!status) return 'plain'
  const s = status.toLowerCase()
  if (s === 'online' || status === '확인됨' || status === '검증 완료') return 'online'
  if (s === 'offline' || status === '압수됨' || status === '인계됨') return 'offline'
  if (status === '미확인' || status === '검증 중' || status === '보류') return 'unknown'
  return 'plain'
}

export const TONE_TEXT: Record<Tone, string> = {
  online: 'text-online',
  offline: 'text-offline',
  unknown: 'text-unknown',
  plain: 'text-muted',
}

/** 2026-09-14 → 09-14. 출처 카드의 짧은 날짜 */
export function shortDate(d: string | null): string {
  if (!d) return ''
  const m = /^\d{4}-(\d{2}-\d{2})/.exec(d)
  return m ? m[1] : d
}

export const QUESTION_MAX = 300

/** 오류 코드 → 화면 문구. 질문이나 자료 문자열은 보이지 않는다. */
export function errorMessage(code: string): { title: string; body: string } {
  switch (code) {
    case 'budget':
      return { title: '오늘은 새 답변이 쉬어요', body: '예시 질문과 출처 원문은 그대로 볼 수 있어요.' }
    case 'turnstile':
      return { title: '사람 확인을 통과하지 못했어요', body: '다시 확인한 뒤 물어 주세요.' }
    case 'too_long':
      return { title: '질문이 너무 길어요', body: '300자 안으로 줄여 주세요.' }
    case 'rate':
      return { title: '잠시 뒤 다시 물어 주세요', body: '질문이 너무 잦아요.' }
    default:
      return { title: '답을 만들지 못했어요', body: '잠시 뒤 다시 물어 주세요. 예시 질문과 출처 원문은 그대로 볼 수 있어요.' }
  }
}
