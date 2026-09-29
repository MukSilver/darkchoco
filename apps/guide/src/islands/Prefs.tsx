// 헤더의 보기 설정: 온라인 신청이 어려워요, 글자 크게, 밝기
import { useEffect, useState } from "preact/hooks";
import { Ico } from "../lib/icons";
import { prefs, announcePrefs, type Theme } from "../lib/store";
import { toast } from "../lib/ui";

export default function Prefs() {
  const [open, setOpen] = useState(false);
  const [easy, setEasy] = useState(false);
  const [big, setBig] = useState(false);
  const [theme, setTheme] = useState<Theme>("auto");

  useEffect(() => {
    setEasy(prefs.easy); setBig(prefs.big); setTheme(prefs.theme);
    const close = (e: Event) => { const t = e.target as Element; if (!t.closest("#prefs") && !t.closest("#prefsBtn")) setOpen(false); };
    const esc = () => { setOpen((o) => { if (o) document.getElementById("prefsBtn")?.focus(); return false; }); };
    document.addEventListener("click", close); document.addEventListener("guide:escape", esc);
    return () => { document.removeEventListener("click", close); document.removeEventListener("guide:escape", esc); };
  }, []);

  const themes: [Theme, string, string, string][] = [["auto", "auto", "자동", "기기 설정을 따라요"], ["light", "sun", "밝게", "밝은 화면"], ["dark", "moon", "어둡게", "어두운 화면"]];
  return (
    <>
      <button class="prefs-btn" id="prefsBtn" type="button" aria-expanded={open} aria-controls="prefs" onClick={() => setOpen(!open)}>
        <Ico id="sliders" />보기 설정
      </button>
      <div class={"prefs" + (open ? " open" : "")} id="prefs">
        <span class="prefs-head">보기 설정</span>
        <button class="sw" type="button" aria-pressed={easy} data-tip="전화나 방문으로 하는 방법을 먼저 보여드려요"
          onClick={() => { const v = !easy; prefs.easy = v; setEasy(v); announcePrefs(); toast(v ? "전화나 방문으로 하는 방법을 먼저 보여드려요." : "온라인 신청 방법을 먼저 보여드려요."); }}>
          <span class="knob"></span>온라인 신청이 어려워요
        </button>
        <button class="sw" type="button" aria-pressed={big} onClick={() => { const v = !big; prefs.big = v; setBig(v); announcePrefs(); }}>
          <span class="knob"></span>글자 크게
        </button>
        <div class="seg" role="group" aria-label="화면 밝기">
          {themes.map(([id, icon, label, tip]) => (
            <button type="button" aria-pressed={theme === id} aria-label={"화면 밝기 " + label} data-tip={tip}
              onClick={() => { prefs.theme = id; setTheme(id); announcePrefs(); toast(id === "auto" ? "기기 설정에 맞춰 화면 밝기를 바꿔요." : id === "dark" ? "어두운 화면으로 바꿨어요." : "밝은 화면으로 바꿨어요."); }}>
              <Ico id={icon} /><span>{label}</span>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}
