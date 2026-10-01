import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// 글꼴은 직접 싣는다. 바깥 글꼴 서버를 부르지 않는다 (방문자 접속 정보가 밖으로 나가지 않게)
import '@fontsource-variable/noto-sans-kr'
import '@fontsource-variable/jetbrains-mono'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
