// 사람 확인 (Cloudflare Turnstile). 설계서 「질문 한 건」 순서 1: 봇에게는 어떤 일도 하지 않는다.
// 서버가 사람 확인을 켰을 때(/api/status 의 turnstile: true)만 쓴다. 토큰은 한 번 쓰면 끝이라 질문마다 새로 받는다.
// 사이트 열쇠는 공개 값이다 (VITE_TURNSTILE_SITEKEY). 비밀 열쇠는 서버 .env 에만 있다.

const SITEKEY = import.meta.env.VITE_TURNSTILE_SITEKEY as string | undefined
const SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'

interface TurnstileApi {
  render(el: HTMLElement, opts: Record<string, unknown>): string
  remove(id: string): void
}
declare global {
  interface Window { turnstile?: TurnstileApi }
}

let loading: Promise<TurnstileApi> | null = null

function load(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile)
  loading ??= new Promise<TurnstileApi>((resolve, reject) => {
    const s = document.createElement('script')
    s.src = SRC
    s.async = true
    s.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new Error('turnstile')))
    s.onerror = () => { loading = null; reject(new Error('turnstile')) }
    document.head.appendChild(s)
  })
  return loading
}

export const turnstileConfigured = () => !!SITEKEY

/**
 * 토큰 하나를 받는다. 대부분은 화면에 아무것도 보이지 않고 끝나고, 드물게 확인 상자가 el 안에 보인다.
 * 사이트 열쇠가 없거나 스크립트를 못 불러오면 null (서버가 401 로 돌려보낸다).
 */
export async function turnstileToken(el: HTMLElement, timeoutMs = 60000): Promise<string | null> {
  if (!SITEKEY) return null
  let api: TurnstileApi
  try { api = await load() } catch { return null }
  return new Promise<string | null>((resolve) => {
    let id = ''
    const finish = (token: string | null) => {
      clearTimeout(timer)
      try { if (id) api.remove(id) } catch { /* 이미 지워짐 */ }
      resolve(token)
    }
    const timer = setTimeout(() => finish(null), timeoutMs)
    id = api.render(el, {
      sitekey: SITEKEY,
      theme: 'dark',
      language: 'ko',
      appearance: 'interaction-only',      // 확인이 필요할 때만 상자가 보임
      callback: (token: string) => finish(token),
      'error-callback': () => finish(null),
      'expired-callback': () => finish(null),
    })
  })
}
