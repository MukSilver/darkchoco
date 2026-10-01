// 감시 (설계서 「개발 스택」: Cloudflare Workers 예약 실행 5분마다, 디스코드 웹훅).
// 질의 서버의 /api/status 를 불러 보고, 멈췄거나 새 질문을 못 받는 상태가 되면 디스코드로 알린다. 돌아오면 한 번 더 알린다.
//
// 알림에는 자료 내용을 싣지 않는다. 상태 한 낱말과 시각뿐이다.
// 설정: STATUS_URL (wrangler.jsonc 의 vars), DISCORD_WEBHOOK (비밀값: npx wrangler secret put DISCORD_WEBHOOK)
// 상태 기억: KV 묶음 STATE 가 있으면 상태가 바뀔 때만 알린다. 없으면 멈춰 있는 동안 30분마다 알린다.

const TIMEOUT_MS = 10000

/** 지금 상태 한 낱말. ok, budget(하루 차단기), upstream, no_version, down(응답 없음), bad(이상한 응답) */
export async function check(statusUrl, fetcher = fetch) {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), TIMEOUT_MS)
  try {
    const r = await fetcher(statusUrl, { signal: ctl.signal, headers: { 'User-Agent': 'ragdb-monitor' } })
    let j = null
    try { j = await r.json() } catch { return 'bad' }
    if (j && j.ok && j.accepting) return 'ok'
    return (j && j.reason) || 'bad'
  } catch {
    return 'down'
  } finally {
    clearTimeout(timer)
  }
}

const TEXT = {
  ok: 'RAG DB 질의 서버가 다시 새 질문을 받습니다.',
  budget: 'RAG DB: 오늘 하루 한도에 닿아 새 답변을 쉽니다. 예시 질문과 출처 원문은 그대로 뜹니다.',
  upstream: 'RAG DB: 질의 서버가 Supabase 에 닿지 못해 새 질문을 받지 않습니다.',
  no_version: 'RAG DB: 질의 서버에 판이 없습니다. refresh.py 를 확인하십시오.',
  down: 'RAG DB: 질의 서버가 응답하지 않습니다. 서버와 터널을 확인하십시오.',
  bad: 'RAG DB: 질의 서버의 상태 응답이 이상합니다.',
}

/** 알릴지. prev 는 지난번 상태(모르면 null), minute 는 지금 분 */
export function shouldNotify(prev, now, minute, hasState) {
  if (hasState) {
    if (prev === null) return now !== 'ok'        // 처음 돌 때는 문제가 있을 때만
    return prev !== now
  }
  return now !== 'ok' && minute % 30 < 5          // 기억이 없으면 멈춰 있는 동안 30분마다
}

async function notify(webhook, text) {
  if (!webhook) return
  await fetch(webhook, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: text.slice(0, 1900) }) })
}

export default {
  async scheduled(event, env) {
    if (!env.STATUS_URL) return
    const now = await check(env.STATUS_URL)
    const hasState = !!env.STATE
    const prev = hasState ? await env.STATE.get('status') : null
    const minute = new Date(event.scheduledTime).getUTCMinutes()
    if (shouldNotify(prev, now, minute, hasState)) await notify(env.DISCORD_WEBHOOK, TEXT[now] || TEXT.bad)
    if (hasState && prev !== now) await env.STATE.put('status', now)
  },
}
