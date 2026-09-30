// 화면 골격. 공개 화면은 둘이다 (설계서 「화면 목록」): 묻고 답하기 ( / ) 와 출처 원문 ( /doc/{id}/{s} ).
// 디자인(v1/v2)이 확정되면 컴포넌트를 채운다. 라우터 라이브러리는 스택에 없으므로 주소는 직접 읽는다.
import { useEffect, useState } from 'react'
import { serverStatus, snapshot } from './api'
import type { Answers, Current, SnapshotStatus, Status } from './types'

type Route = { page: 'ask' } | { page: 'doc'; id: string; section: number } | { page: 'missing' }

function route(pathname: string): Route {
  if (pathname === '/' || pathname === '') return { page: 'ask' }
  const m = /^\/doc\/([^/]+)(?:\/(\d+))?$/.exec(pathname)
  if (m) return { page: 'doc', id: decodeURIComponent(m[1]), section: Number(m[2] ?? 0) }
  return { page: 'missing' }
}

export default function App() {
  const [r, setRoute] = useState<Route>(() => route(location.pathname))
  const [current, setCurrent] = useState<Current | null>(null)
  const [snap, setSnap] = useState<SnapshotStatus | null>(null)
  const [answers, setAnswers] = useState<Answers | null>(null)
  const [server, setServer] = useState<Status | null | 'loading'>('loading')

  useEffect(() => {
    const onPop = () => setRoute(route(location.pathname))
    addEventListener('popstate', onPop)
    return () => removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => {
    // 스냅샷은 서버 없이 뜬다. 질의 서버 상태는 따로 본다 (설계서 「묻고 답하기」: 서버가 꺼져도 예시와 원문은 그대로)
    snapshot.current().then(async (c) => {
      setCurrent(c)
      const [s, a] = await Promise.all([snapshot.status(c.version), snapshot.answers(c.version)])
      setSnap(s)
      setAnswers(a)
    }).catch(() => setCurrent(null))
    serverStatus().then(setServer)
  }, [])

  const header = (
    <header className="flex h-14 items-center justify-between border-b border-line bg-frame px-6">
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold">다크웹 RAG DB</span>
        {snap && <span className="font-mono text-xs text-muted">판 {snap.version} · 문서 {snap.documents}</span>}
      </div>
      <ServerBadge server={server} />
    </header>
  )

  return (
    <div className="flex min-h-full flex-col">
      {header}
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">
        {r.page === 'ask' && <AskPlaceholder answers={answers} server={server} />}
        {r.page === 'doc' && current && <DocPlaceholder version={current.version} id={r.id} section={r.section} />}
        {r.page === 'missing' && <p className="text-muted">이런 주소는 없어요.</p>}
      </main>
      <footer className="border-t border-line px-6 py-4 text-xs text-muted">
        AI가 만든 답이에요. 출처로 확인해 주세요. 잘못된 답이나 가려지지 않은 이름은 (팀 연락 메일: 미정) 으로 알려 주세요.
      </footer>
    </div>
  )
}

function ServerBadge({ server }: { server: Status | null | 'loading' }) {
  if (server === 'loading') return null
  const [color, text] = server === null ? ['bg-coral', '지금은 새 질문을 받지 않아요']
    : server.accepting ? ['bg-ok', '새 질문 받는 중']
    : server.reason === 'budget' ? ['bg-unk', '오늘 새 답변은 쉬어요']
    : ['bg-coral', '지금은 새 질문을 받지 않아요']
  return <span className="flex items-center gap-2 text-xs text-text-2"><i className={`inline-block h-2 w-2 rounded-full ${color}`} />{text}</span>
}

function AskPlaceholder({ answers, server }: { answers: Answers | null; server: Status | null | 'loading' }) {
  const locked = server === null || (server !== 'loading' && !server.accepting)
  return (
    <section>
      <h1 className="text-3xl font-bold tracking-tight">팀이 쌓은 조사 기록에 물어보세요</h1>
      <p className="mt-3 text-text-2">기록 안에서만 답하고, 문장마다 어느 기록에서 나왔는지 번호를 붙입니다. 근거가 없으면 없다고 답합니다.</p>
      <div className="mt-6 rounded-xl border border-line bg-panel p-4 text-muted">
        {locked ? '지금은 새 질문을 받지 않아요. 예시 질문과 출처 원문은 볼 수 있어요.' : '(입력창 자리. 300자, 질문은 저장하지 않아요)'}
      </div>
      <p className="mt-3 text-sm text-muted">피해 조직 이름과 주소는 가려져 있어 이름으로는 찾을 수 없어요. 분야 · 시기 · 장소 · 행위자로 물어 보세요. 질문과 가까운 자료 다섯 개로 답해요.</p>
      <h2 className="mt-8 font-mono text-xs tracking-widest text-coral-ink">EXAMPLES · 사람이 검토한 답</h2>
      {!answers || answers.answers.length === 0
        ? <p className="mt-2 text-sm text-muted">검토를 통과한 사전 답변이 아직 없어요.</p>
        : <ol className="mt-2 space-y-2">{answers.answers.map((a, i) => (
            <li key={i} className="rounded-lg border border-line bg-panel px-4 py-3 text-sm">{a.question}</li>))}</ol>}
    </section>
  )
}

function DocPlaceholder({ version, id, section }: { version: string; id: string; section: number }) {
  const [state, setState] = useState<'loading' | 'missing' | 'ok'>('loading')
  const [title, setTitle] = useState('')
  useEffect(() => {
    snapshot.doc(version, id).then((d) => { setTitle(d.title); setState('ok') }).catch(() => setState('missing'))
  }, [version, id])
  if (state === 'loading') return null
  if (state === 'missing') return <p className="text-muted">찾을 수 없는 문서예요.</p>
  return <section><h1 className="text-2xl font-bold">{title}</h1><p className="mt-2 text-sm text-muted">(출처 원문 자리. 조각 {section})</p></section>
}
