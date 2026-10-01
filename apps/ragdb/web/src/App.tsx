// 공개 화면은 둘이다 (설계서 「화면 목록」): 묻고 답하기 ( / ) 와 출처 원문 ( /doc/{문서}/{조각 순번} ).
// 라우터 라이브러리는 스택에 없으므로 주소는 직접 읽는다. 스냅샷은 서버 없이 뜨고, 질의 서버 상태는 따로 본다.
import { useCallback, useEffect, useRef, useState } from 'react'
import { serverStatus, snapshot } from './api'
import { turnstileToken } from './turnstile'
import { Answer, Progress } from './components/Answer'
import { AskBoxAnswer, AskBoxHome } from './components/AskBox'
import { Banner, Header } from './components/Header'
import type { ServerState } from './components/Header'
import { DocView, SourcePanel, useDoc } from './components/SourcePanel'
import type { Answers, Current, PreparedAnswer } from './types'
import { useAsk } from './useAsk'

type Route = { page: 'ask' } | { page: 'doc'; id: string; index: number } | { page: 'missing' }

function parse(pathname: string): Route {
  if (pathname === '/' || pathname === '') return { page: 'ask' }
  const m = /^\/doc\/([^/]+)(?:\/(\d+))?\/?$/.exec(pathname)
  if (m) return { page: 'doc', id: decodeURIComponent(m[1]), index: Number(m[2] ?? 0) }
  return { page: 'missing' }
}

const CONTACT = import.meta.env.VITE_CONTACT_EMAIL as string | undefined

export default function App() {
  const [route, setRoute] = useState<Route>(() => parse(location.pathname))
  const [current, setCurrent] = useState<Current | null>(null)
  const [answers, setAnswers] = useState<Answers | null>(null)
  const [server, setServer] = useState<ServerState>('loading')
  const { turn, start, showPrepared, reset } = useAsk()
  const [open, setOpen] = useState<{ n: number; documentId: string; chunkId: string | null } | null>(null)
  const [human, setHuman] = useState(false)          // 서버가 사람 확인을 켰는가
  const [checking, setChecking] = useState(false)    // 사람 확인을 기다리는 중
  const humanEl = useRef<HTMLDivElement>(null)

  const go = useCallback((path: string) => {
    history.pushState(null, '', path)
    setRoute(parse(path))
  }, [])

  useEffect(() => {
    const onPop = () => setRoute(parse(location.pathname))
    addEventListener('popstate', onPop)
    return () => removeEventListener('popstate', onPop)
  }, [])

  const checkServer = useCallback(() => {
    serverStatus().then((s) => {
      setServer(!s || !s.ok ? 'off' : s.accepting ? 'ok' : s.reason === 'budget' ? 'budget' : 'off')
      setHuman(!!s?.turnstile)
    })
  }, [])

  useEffect(() => {
    snapshot.current().then(async (c) => {
      setCurrent(c)
      setAnswers(await snapshot.answers(c.version).catch(() => null))
    }).catch(() => setCurrent(null))
    checkServer()
  }, [checkServer])

  // 하루 차단기에 걸리면 헤더와 입력창도 그 상태로
  useEffect(() => {
    if (turn?.phase === 'error' && turn.error?.code === 'budget') setServer('budget')
  }, [turn])

  const home = () => { reset(); setOpen(null); go('/') }
  const ask = async (q: string) => {
    if (checking) return
    setOpen(null)
    if (route.page !== 'ask') go('/')
    let token: string | null = null
    if (human && humanEl.current) {
      // 사람 확인. 대부분 아무것도 안 보이고 지나간다. 토큰을 못 받으면 그대로 보내고 서버가 401 로 돌려보낸다
      setChecking(true)
      token = await turnstileToken(humanEl.current)
      setChecking(false)
    }
    start(q, token)
  }
  const example = (a: PreparedAnswer) => { setOpen(null); showPrepared(a) }
  const cite = (n: number) => {
    const s = turn?.sources.find((x) => x.n === n)
    if (!s) return
    setOpen(open?.n === n ? null : { n, documentId: s.document_id, chunkId: s.chunk_id })
  }

  return (
    <div className="flex h-full flex-col">
      <Header version={current?.version ?? null} server={server} onHome={home} />
      <Banner server={server} />
      <div className="flex min-h-0 flex-1">
        <main className="flex min-w-0 flex-1 flex-col items-center overflow-y-auto">
          {/* 사람 확인 상자가 필요할 때만 여기에 보인다 (Cloudflare Turnstile) */}
          <div className={`flex w-full max-w-[720px] flex-col gap-2 px-6 ${checking ? 'pt-6' : ''}`}>
            {checking && <p className="text-[13px] leading-normal text-muted" role="status">사람인지 확인하고 있어요…</p>}
            <div ref={humanEl} />
          </div>
          {route.page === 'missing' && <Missing text="이런 주소는 없어요" onHome={home} />}
          {route.page === 'doc' && <DocPage version={current?.version ?? null} id={route.id} index={route.index} onHome={home} go={go} />}
          {route.page === 'ask' && !turn && (
            <Home server={server} answers={answers} onAsk={ask} onExample={example} />
          )}
          {route.page === 'ask' && turn && (
            <div className="flex w-full max-w-[720px] flex-1 flex-col gap-4 px-6 pt-7 pb-5">
              <div className="flex flex-col gap-2">
                <span className="text-[12px] leading-none font-medium tracking-[1.2px] text-accent">질문</span>
                <h1 className="text-[21px] leading-[1.35] font-semibold tracking-[-0.315px] text-strong">{turn.question}</h1>
              </div>
              <Progress turn={turn} />
              <Answer turn={turn} selected={open?.n ?? null} onCite={cite} />
              <div className="min-h-4 flex-1" />
              <div className="sticky bottom-0 -mx-6 bg-page/90 px-6 pt-2 pb-1 backdrop-blur-[6px]">
                <AskBoxAnswer
                  server={server}
                  busy={turn.phase !== 'done' && turn.phase !== 'error'}
                  onSubmit={ask}
                  onExamples={home}
                />
              </div>
              <Footer />
            </div>
          )}
        </main>
        {route.page === 'ask' && open && current && (
          <SourcePanel
            version={current.version}
            documentId={open.documentId}
            chunkId={open.chunkId}
            onChunk={(id) => setOpen({ ...open, chunkId: id })}
            onClose={() => setOpen(null)}
          />
        )}
      </div>
    </div>
  )
}

function Home({ server, answers, onAsk, onExample }: {
  server: ServerState; answers: Answers | null; onAsk: (q: string) => void; onExample: (a: PreparedAnswer) => void
}) {
  const examples = answers?.answers ?? []
  return (
    <div className="flex w-full max-w-[720px] flex-1 flex-col gap-10 px-6 pt-[88px] pb-6 max-sm:pt-12">
      <div className="flex flex-col gap-[14px]">
        <h1 className="text-[36px] leading-[1.2] font-semibold tracking-[-0.72px] text-strong max-sm:text-[28px]">조사 기록에 물어보세요</h1>
        <p className="max-w-[520px] text-[16px] leading-[1.65] text-muted">조사 기록 안에서만 답하고, 문장마다 출처를 붙입니다. 근거가 없으면 없다고 답합니다.</p>
      </div>
      <div className="flex w-full flex-col gap-[10px]">
        <AskBoxHome server={server} onSubmit={onAsk} />
        <p className="px-[6px] text-[13px] leading-[1.6] text-faint">
          <span className="font-medium text-muted">물을 수 있는 것</span> 분야 · 시기 · 장소(포럼, 텔레그램, 랜섬웨어) · 행위자. 피해 조직의 이름으로는 찾을 수 없어요.
        </p>
      </div>
      {examples.length > 0 && (
        <section className="flex w-full flex-col gap-3" aria-label="예시 질문">
          <h2 className="text-[12px] leading-none font-medium tracking-[1.2px] text-muted">예시 질문</h2>
          <div className="grid grid-cols-3 gap-[10px] max-sm:grid-cols-1">
            {examples.map((a) => (
              <button
                key={a.question}
                type="button"
                onClick={() => onExample(a)}
                className="cursor-pointer rounded-[14px] border border-line-card bg-card px-4 py-[14px] text-left text-[14.5px] leading-[1.45] text-body transition-colors hover:border-line"
              >
                {a.question}
              </button>
            ))}
          </div>
        </section>
      )}
      <div className="flex-1" />
      <Footer />
    </div>
  )
}

/** 주소로 바로 연 출처 원문. */
function DocPage({ version, id, index, onHome, go }: { version: string | null; id: string; index: number; onHome: () => void; go: (p: string) => void }) {
  const load = useDoc(version, id)
  if (!version || load.state === 'loading') return null
  if (load.state === 'missing') return <Missing text="찾을 수 없는 문서예요" onHome={onHome} />
  const chunk = load.doc.chunks[index] ?? load.doc.chunks[0]
  return (
    <div className="flex w-full max-w-[720px] flex-col gap-[18px] px-6 pt-10 pb-8">
      <span className="text-[12px] leading-none font-medium tracking-[1.2px] text-muted">출처 원문</span>
      <DocView
        doc={load.doc}
        chunkId={chunk?.chunk_id ?? null}
        onChunk={(cid) => go(`/doc/${encodeURIComponent(id)}/${load.doc.chunks.findIndex((c) => c.chunk_id === cid)}`)}
      />
      <Footer />
    </div>
  )
}

function Missing({ text, onHome }: { text: string; onHome: () => void }) {
  return (
    <div className="flex w-full max-w-[720px] flex-col items-start gap-4 px-6 pt-[88px]">
      <h1 className="text-[28px] leading-[1.2] font-semibold text-strong">{text}</h1>
      <button type="button" onClick={onHome} className="cursor-pointer rounded-[9px] bg-accent px-4 py-[9px] text-[14px] font-medium text-white">첫 화면으로</button>
    </div>
  )
}

/** 바닥글 (설계서 「묻고 답하기」): AI가 만든 글임을 숨기지 않고, 잘못된 답과 가려지지 않은 이름을 알릴 창구를 둔다. */
function Footer() {
  return (
    <footer className="pt-2 pb-1 text-[12px] leading-[1.6] text-faint">
      AI가 만든 답이에요. 출처로 확인해 주세요.
      {CONTACT && <> 잘못된 답이나 가려지지 않은 이름은 <a className="text-accent-text hover:text-accent-strong" href={`mailto:${CONTACT}`}>{CONTACT}</a> 로 알려 주세요.</>}
    </footer>
  )
}
