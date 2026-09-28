// Telegram <-> Roblox 중계 서버 (Cloudflare Worker)
// 환경 변수: BOT_TOKEN, SECRET, CHAT_ID
// 저장소 없이 동작: Roblox가 offset을 들고 있고, Worker는 getUpdates를 대신 호출만 한다.

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });

async function tg(env, method, body) {
  const res = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.headers.get("X-Secret") !== env.SECRET) {
      return json({ ok: false, error: "unauthorized" }, 401);
    }

    // Roblox -> Worker: 새 텔레그램 명령 가져오기
    if (url.pathname === "/poll" && request.method === "GET") {
      const offset = Number(url.searchParams.get("offset") || 0);
      const data = await tg(env, "getUpdates", {
        offset,
        timeout: 0,
        allowed_updates: ["message"],
      });
      if (!data.ok) return json({ ok: false, error: data.description }, 502);

      let nextOffset = offset;
      const commands = [];
      for (const u of data.result) {
        nextOffset = Math.max(nextOffset, u.update_id + 1);
        const m = u.message;
        if (!m || typeof m.text !== "string") continue;
        if (String(m.chat.id) !== String(env.CHAT_ID)) continue; // 내 채팅만 허용
        commands.push({ text: m.text, from: m.from?.username || m.from?.first_name || "" });
      }
      return json({ ok: true, next_offset: nextOffset, commands });
    }

    // Roblox -> Worker -> Telegram: 메시지 보내기
    if (url.pathname === "/send" && request.method === "POST") {
      const { text } = await request.json();
      if (typeof text !== "string" || text.length === 0) {
        return json({ ok: false, error: "text required" }, 400);
      }
      const data = await tg(env, "sendMessage", {
        chat_id: env.CHAT_ID,
        text: text.slice(0, 4096),
      });
      return json({ ok: data.ok, error: data.description }, data.ok ? 200 : 502);
    }

    // 설정 확인용: 봇에게 온 최근 메시지의 chat id 보기 (CHAT_ID 찾을 때 사용)
    if (url.pathname === "/whoami") {
      const data = await tg(env, "getUpdates", { timeout: 0 });
      const chats = (data.result || [])
        .filter((u) => u.message)
        .map((u) => ({ chat_id: u.message.chat.id, name: u.message.chat.username || u.message.chat.title }));
      return json({ ok: data.ok, chats });
    }

    return json({ ok: false, error: "not found" }, 404);
  },
};
