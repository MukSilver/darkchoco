// 화면 공통 동작: 도움말 풍선, 연결 강조, 알림과 되돌리기, 따라오는 진행 막대, 목차, 밝기.
// 섬 바깥의 문서 전체에 한 번만 붙습니다. 원본 프로토타입의 동작을 그대로 옮겼습니다.
import { prefs, announcePrefs, markFlowReset } from "./store";

let toastTimer: ReturnType<typeof setTimeout> | null = null;
let undoFn: (() => void) | null = null;

export function toast(msg: string, undo?: () => void) {
  const el = document.getElementById("toast");
  if (!el) return;
  undoFn = undo || null;
  el.innerHTML = `<span></span>${undo ? '<button type="button" data-undo="1">되돌리기</button>' : ""}`;
  (el.firstChild as HTMLElement).textContent = msg;
  el.classList.add("on");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("on"), undo ? 5000 : 2600);
}

export function applyTheme() {
  const root = document.documentElement;
  const t = prefs.theme;
  if (t === "auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", t);
  root.classList.toggle("big", prefs.big);
  const tc = t === "dark" ? "#26282B" : t === "light" ? "#FFFFFF" : null;
  document.querySelectorAll('meta[name="theme-color"]').forEach((m, k) => m.setAttribute("content", tc || (k ? "#26282B" : "#FFFFFF")));
}

function measure() {
  const top = document.getElementById("top");
  if (top) document.documentElement.style.setProperty("--hh", top.offsetHeight + "px");
}

/* 도움말 풍선 */
let tipFor: Element | null = null;
function showTip(el: Element) {
  const tip = document.getElementById("tip");
  const txt = el.getAttribute("data-tip");
  if (!tip || !txt) return;
  tipFor = el; tip.textContent = txt; tip.classList.add("on");
  const r = el.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight;
  let x = r.left + r.width / 2 - tw / 2; x = Math.max(8, Math.min(x, window.innerWidth - tw - 8));
  let y = r.top - th - 10, below = false;
  if (y < 8) { y = r.bottom + 10; below = true; }
  tip.classList.toggle("below", below); tip.style.left = x + "px"; tip.style.top = y + "px";
  tip.style.setProperty("--ax", (r.left + r.width / 2 - x) + "px");
}
export function hideTip() { tipFor = null; document.getElementById("tip")?.classList.remove("on"); }

/* 연결 강조: 위험에 올리면 관련 항목과 할 일만 밝게 */
let linking = false;
function linkOn(src: string) {
  const scope = document.getElementById("app"); if (!scope) return;
  linking = true; scope.classList.add("linking");
  scope.querySelectorAll<HTMLElement>("[data-keys]").forEach((el) => {
    const hit = (el.dataset.keys || "").split(" ").includes(src);
    el.classList.toggle("lit", hit); el.classList.toggle("dim", !hit);
  });
}
function linkOff() {
  if (!linking) return; linking = false;
  const scope = document.getElementById("app"); if (!scope) return;
  scope.classList.remove("linking");
  scope.querySelectorAll(".lit,.dim").forEach((el) => el.classList.remove("lit", "dim"));
}

/* 따라오는 진행 막대와 목차 */
let io: IntersectionObserver | null = null, io2: IntersectionObserver | null = null;
export function watchSheet() {
  const m = document.getElementById("mini"), t = document.getElementById("toc");
  if (io) { io.disconnect(); io = null; }
  if (io2) { io2.disconnect(); io2 = null; }
  if (!m || !t) return;
  const tgt = document.getElementById("sec-next");
  m.classList.remove("on");
  if (tgt && m.childElementCount && "IntersectionObserver" in window) {
    io = new IntersectionObserver((es) => es.forEach((e) => {
      const past = !e.isIntersecting && e.boundingClientRect.top < 0;
      m.classList.toggle("on", past); m.setAttribute("aria-hidden", String(!past));
    }), { rootMargin: "-60px 0px 0px 0px" });
    io.observe(tgt);
  }
  const secs = [["sec-next", "다음 할 일"], ["sec-stage", "퍼진 단계"], ["sec-board", "항목과 위험"], ["sec-rest", "남은 할 일"], ["sec-harm", "피해가 생겼다면"], ["sec-claim", "보상 요구"], ["sec-help", "도움 받기"]].filter(([id]) => document.getElementById(id));
  if (secs.length < 3) { t.innerHTML = ""; return; }
  t.innerHTML = "<b>이 화면의 순서</b>" + secs.map(([id, n]) => `<a href="#${id}" data-jump="${id}">${n}</a>`).join("");
  if (!("IntersectionObserver" in window)) return;
  io2 = new IntersectionObserver((es) => es.forEach((e) => {
    if (e.isIntersecting) t.querySelectorAll("a").forEach((a) => a.classList.toggle("on", a.dataset.jump === e.target.id));
  }), { rootMargin: "-45% 0px -50% 0px" });
  secs.forEach(([id]) => io2!.observe(document.getElementById(id)!));
}

export function jumpTo(id: string) {
  const el = document.getElementById(id); if (!el) return;
  el.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  const f = el.querySelector<HTMLElement>("button,a"); if (f) setTimeout(() => f.focus({ preventScroll: true }), 400);
}

export function initUi() {
  applyTheme(); measure();
  document.addEventListener("mouseover", (e) => {
    const tgt = e.target as Element;
    const t = tgt.closest("[data-tip]");
    if (t && t !== tipFor) showTip(t); else if (!t && tipFor) hideTip();
    const s = tgt.closest<HTMLElement>("[data-src]");
    if (s && isSheet()) linkOn(s.dataset.src!); else if (!s) linkOff();
  });
  document.addEventListener("focusin", (e) => {
    const tgt = e.target as Element;
    const t = tgt.closest("[data-tip]"); if (t && tgt.matches(":focus-visible")) showTip(t);
    const s = tgt.closest<HTMLElement>("[data-src]"); if (s && isSheet()) linkOn(s.dataset.src!);
  });
  document.addEventListener("focusout", () => { hideTip(); linkOff(); });
  window.addEventListener("scroll", hideTip, { passive: true });
  window.addEventListener("resize", () => { measure(); hideTip(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { hideTip(); linkOff(); document.dispatchEvent(new CustomEvent("guide:escape")); } });
  document.addEventListener("click", (e) => {
    const a = (e.target as Element).closest<HTMLAnchorElement>("a[href]");
    if (a && /^\/notice\//.test(a.getAttribute("href") || "") && !inFlow()) markFlowReset();
    const t = (e.target as Element).closest<HTMLElement>("[data-undo],[data-jump]"); if (!t) return;
    if (t.dataset.undo) { if (undoFn) { const f = undoFn; undoFn = null; f(); toast("되돌렸어요."); } return; }
    if (t.dataset.jump) { e.preventDefault(); jumpTo(t.dataset.jump); }
  });
  document.addEventListener("guide:prefs", applyTheme);
  document.addEventListener("guide:rendered", () => { measure(); watchSheet(); });
  announcePrefs();
  enterPage();
}

/** 대응 한 장인지. 항목판이 있는 안내문 3단계에서는 연결 강조를 하지 않습니다 */
const isSheet = () => !!document.getElementById("sec-board");
/** 안내문 경로(안내문 세 단계와 안내문 기준 대응 한 장) 안에 있는지 */
const inFlow = () => /^\/(notice|plan)\//.test(location.pathname);

/** 화면에 들어올 때: 조각들이 차례로 나타나고, 사이트 안에서 옮겨 왔으면 제목에 초점을 둡니다 (프로토타입의 route 끝부분) */
function enterPage() {
  const app = document.getElementById("app"); if (!app) return;
  app.classList.add("enter");
  setTimeout(() => app.classList.remove("enter"), 700);
  let from = "";
  try { from = sessionStorage.getItem("guide-visited") || ""; sessionStorage.setItem("guide-visited", "1"); } catch { /* 무시 */ }
  const nav = (performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined)?.type;
  if (from && nav !== "reload") { const h1 = app.querySelector<HTMLElement>("h1"); if (h1) h1.focus({ preventScroll: true }); }
}
