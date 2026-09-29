/**
 * 배포 직후 옛 HTML 을 붙잡은 방문자를 새 HTML 로 한 번 다시 부르는 인라인 스크립트 (`layout.tsx` 머리에 넣는다).
 *
 * 배포하면 청크 파일 이름이 바뀌고 옛 청크는 없어진다. 그런데 배포 뒤 1분 안팎은 Cloudflare 가 옛 HTML 을
 * 「바뀌지 않음(304)」으로 답해서, 그 사이 다시 부른 사람은 옛 HTML 이 가리키는 없는 청크(404)를 받아
 * 오류 화면(`__next_error__`)을 봤다 (2026-09-29 밤 두 번 겪음, 최현서가 넣기로 함).
 *
 * `/_next/static/` 파일을 못 받았거나 ChunkLoadError 가 나면 주소에 `v=시각` 을 붙여 다시 부른다 — 주소가
 * 달라 브라우저 · 가장자리 캐시를 안 거치고 새 HTML 을 받는다. 1분 안에는 되풀이하지 않는다(저장소가 막혀
 * 있으면 주소에 `v` 가 이미 있을 때 멈춘다). 다시 부른 뒤에는 주소의 `v` 를 지운다.
 * CSP 가 인라인 스크립트를 허용한다(`public/_headers` script-src 'unsafe-inline').
 */
export const STALE_RELOAD = `(function () {
  var KEY = "dcMapStaleReload";
  var done = false;
  function again() {
    if (done) return;
    try {
      var last = Number(sessionStorage.getItem(KEY) || 0);
      if (Date.now() - last < 60000) return;
      sessionStorage.setItem(KEY, String(Date.now()));
    } catch (e) {
      if (/[?&]v=\\d+/.test(location.search)) return;
    }
    done = true;
    var u = new URL(location.href);
    u.searchParams.set("v", String(Date.now()));
    location.replace(u.toString());
  }
  var CHUNK = /ChunkLoadError|Loading chunk|Failed to load chunk/;
  window.addEventListener("error", function (e) {
    var t = e.target;
    var src = t && (t.src || t.href);
    if (typeof src === "string" && src.indexOf("/_next/static/") !== -1) again();
    else if (e.message && CHUNK.test(e.message)) again();
  }, true);
  window.addEventListener("unhandledrejection", function (e) {
    var r = e.reason;
    if (r && (r.name === "ChunkLoadError" || CHUNK.test(String(r.message || r)))) again();
  });
  if (/[?&]v=\\d+/.test(location.search)) {
    var c = new URL(location.href);
    c.searchParams.delete("v");
    history.replaceState(history.state, "", c.pathname + c.search + c.hash);
  }
})();`;
