"""대시보드를 브라우저에 띄웁니다.

    python apps/dash/serve.py            굽고 띄운다
    python apps/dash/serve.py --no-build 굽지 않고 있는 것만 띄운다

**127.0.0.1 에만 붙습니다.** 밖에서 안 보입니다. 화면에 수집 표 현황과 노션 사건이
들어 있어 네트워크에 열어 두면 안 됩니다.

**명령을 실행하지 않습니다.** 이 서버는 파일만 내줍니다. 화면의 명령 단추는 눌러서
복사만 되고, 실행은 터미널이나 제어판에서 사람이 합니다. 웹이 명령을 돌리게 하면
그 포트에 닿는 것이 곧 명령 실행이 되기 때문입니다.
"""
from __future__ import annotations

import argparse
import http.server
import sys
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent


class _조용히(http.server.SimpleHTTPRequestHandler):
    """줄마다 찍는 로그를 끕니다. 오류만 봅니다."""

    def log_message(self, fmt, *args):  # noqa: A003
        pass

    def end_headers(self):
        # 화면이 밖으로 아무것도 못 보내게 합니다. 데이터가 표와 노션에서 온 것이라
        # 실수로 나가는 길을 아예 막습니다.
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; connect-src 'none'; "
                         "img-src 'self' data:")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        super().end_headers()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="대시보드를 띄웁니다")
    ap.add_argument("--no-build", action="store_true", help="굽지 않는다")
    ap.add_argument("--no-notion", action="store_true", help="구울 때 노션을 안 읽는다")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--no-open", action="store_true", help="브라우저를 안 연다")
    a = ap.parse_args(argv)

    if not a.no_build:
        sys.path.insert(0, str(HERE))
        import build

        build.main(["--no-notion"] if a.no_notion else [])

    if not (HERE / "data" / "dash.js").is_file():
        print("  구운 것이 없다. python apps/dash/build.py 를 먼저 돌린다.")
        return 1

    handler = lambda *x, **k: _조용히(*x, directory=str(HERE), **k)  # noqa: E731
    for 포트 in range(a.port, a.port + 20):
        try:
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 포트), handler)
            break
        except OSError:
            continue
    else:
        print("  빈 포트를 못 찾았다 (%d~%d)" % (a.port, a.port + 19))
        return 1

    주소 = "http://127.0.0.1:%d/index.html" % 포트
    print()
    print("  %s" % 주소)
    print("  멈추려면 Ctrl+C")
    print()
    if not a.no_open:
        webbrowser.open(주소)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  멈췄다")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
