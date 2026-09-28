// 치지직 채팅 중계 (Cloudflare Worker)
// 폰 와이파이가 *.game.naver.com / *.chat.naver.com 을 막을 때 대신 접속해 준다.
// - GET /token?cid=..&key=..   채팅 접속 토큰 받아오기
// - WS  /chat?n=1..9&key=..    채팅 서버 WebSocket 을 그대로 연결 (패스스루라 Worker CPU 거의 안 씀)
// - GET /open/cafe?u=카페주소    텔레그램 버튼용: 브라우저 대신 네이버 카페 앱으로 바로 이동 (키 불필요)
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 텔레그램 버튼은 http(s) 주소만 되므로, 이 페이지가 navercafe:// 앱 링크로 넘겨준다
    if (url.pathname === "/open/cafe") {
      const u = url.searchParams.get("u") || "";
      if (!/^[A-Za-z0-9_]{1,40}$/.test(u)) return new Response("bad cafe", { status: 400 });
      const web = `https://m.cafe.naver.com/${u}`;
      const app = `intent://cafe?cafeUrl=${u}#Intent;scheme=navercafe;package=com.nhn.android.navercafe;S.browser_fallback_url=${encodeURIComponent(web)};end`;
      return new Response(
        `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>카페 앱으로 이동</title>
<body style="font-family:sans-serif;text-align:center;padding:48px 16px;background:#fff;color:#222">
<p>네이버 카페 앱으로 이동 중…</p>
<p><a id="go" href="${app}" style="display:inline-block;padding:14px 22px;background:#03c75a;color:#fff;border-radius:10px;text-decoration:none;font-weight:bold">카페 앱으로 열기</a></p>
<p><a href="${web}" style="color:#666">웹으로 보기</a></p>
<script>location.replace(document.getElementById("go").href)</script>`,
        { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } },
      );
    }

    if (url.searchParams.get("key") !== env.SECRET) return new Response("unauthorized", { status: 401 });

    if (url.pathname === "/token") {
      const cid = url.searchParams.get("cid") || "";
      if (!/^[A-Za-z0-9_-]{1,32}$/.test(cid)) return new Response("bad cid", { status: 400 });
      const res = await fetch(
        `https://comm-api.game.naver.com/nng_main/v1/chats/access-token?channelId=${cid}&chatType=STREAMING`,
        { headers: { "User-Agent": UA } },
      );
      return new Response(res.body, { status: res.status, headers: { "content-type": "application/json" } });
    }

    if (url.pathname === "/chat") {
      if (request.headers.get("Upgrade") !== "websocket") return new Response("websocket only", { status: 426 });
      const n = url.searchParams.get("n") || "1";
      if (!/^[1-9]$/.test(n)) return new Response("bad n", { status: 400 });
      return fetch(`https://kr-ss${n}.chat.naver.com/chat`, {
        headers: { Upgrade: "websocket", Origin: "https://chzzk.naver.com", "User-Agent": UA },
      });
    }

    return new Response("not found", { status: 404 });
  },
};
