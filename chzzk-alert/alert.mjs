// 치지직 스텔라이브 멤버 방송/채팅 알림 → 텔레그램
// - 방송 켜짐/꺼짐: 치지직 live-status 를 주기적으로 확인
// - 채팅: 방송 중인 멤버 채팅방에 읽기 전용으로 접속해서, 다른 멤버가 채팅하면 알림
// - 텔레그램은 보내기만 한다 (getUpdates/webhook 안 씀 → 같은 봇을 쓰는 다른 프로그램과 충돌 없음)
// 실행: node alert.mjs          테스트: node alert.mjs --test
import { readFileSync } from "node:fs";

const dir = new URL(".", import.meta.url);
const fileEnv = (() => {
  try {
    return Object.fromEntries(
      readFileSync(new URL(".env", dir), "utf8")
        .split("\n")
        .filter((l) => l.includes("=") && !l.startsWith("#"))
        .map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()]),
    );
  } catch {
    return {};
  }
})();
const cfg = (k, d) => process.env[k] ?? fileEnv[k] ?? d;

const BOT_TOKEN = cfg("BOT_TOKEN");
const CHAT_ID = cfg("CHAT_ID");
const POLL_SEC = Number(cfg("POLL_SEC", 30));
const WATCH_CHAT = cfg("WATCH_CHAT", "1") === "1";
const ALERT_OWN_CHAT = cfg("ALERT_OWN_CHAT", "0") === "1"; // 자기 방송에서 치는 채팅도 알릴지
if (!BOT_TOKEN || !CHAT_ID) {
  console.error(".env 에 BOT_TOKEN, CHAT_ID 가 필요합니다");
  process.exit(1);
}

const members = JSON.parse(readFileSync(new URL("members.json", dir), "utf8"));
const memberById = new Map(members.map((m) => [m.id, m]));

const UA = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(new Date().toISOString(), ...a);
const esc = (s) => String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);
const liveUrl = (id) => `https://chzzk.naver.com/live/${id}`;
const channelUrl = (id) => `https://chzzk.naver.com/${id}`;

async function getJSON(url) {
  const res = await fetch(url, { headers: UA, signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${url}`);
  return res.json();
}

async function tg(method, body) {
  for (let i = 0; i < 3; i++) {
    try {
      const res = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/${method}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(15000),
      });
      const data = await res.json();
      if (data.ok) return data;
      if (data.parameters?.retry_after) {
        await sleep(data.parameters.retry_after * 1000);
        continue;
      }
      log("텔레그램 오류:", data.description);
      return data;
    } catch (e) {
      log("텔레그램 전송 실패:", e.message);
      await sleep(3000);
    }
  }
}

function send(text, buttons, silent = false) {
  return tg("sendMessage", {
    chat_id: CHAT_ID,
    text,
    parse_mode: "HTML",
    disable_web_page_preview: true,
    disable_notification: silent,
    ...(buttons && { reply_markup: { inline_keyboard: buttons } }),
  });
}

const liveButtons = (m) => [
  [
    { text: "📺 방송 보러가기", url: liveUrl(m.id) },
    { text: "📢 채널", url: channelUrl(m.id) },
  ],
];

// ───── 방송 켜짐/꺼짐 ─────
const state = new Map(); // id -> { status, chatChannelId, title, category, offCount }

async function fetchLive(m) {
  const d = await getJSON(`https://api.chzzk.naver.com/polling/v3/channels/${m.id}/live-status`);
  const c = d.content;
  if (!c) throw new Error(`live-status 응답 없음 (code ${d.code})`);
  return { status: c.status, chatChannelId: c.chatChannelId, title: c.liveTitle, category: c.liveCategoryValue };
}

async function checkMember(m, first) {
  let cur;
  try {
    cur = await fetchLive(m);
  } catch (e) {
    log("상태 확인 실패", m.name, e.message);
    return;
  }
  const prev = state.get(m.id);
  const isOpen = cur.status === "OPEN";

  if (first || !prev) {
    state.set(m.id, { ...cur, offCount: 0 });
    if (isOpen) startChat(m, cur.chatChannelId);
    return;
  }

  if (isOpen) {
    if (prev.status !== "OPEN") {
      log("방송 시작", m.name, cur.title);
      await send(
        `🔴 <b>${esc(m.name)}</b> 방송 시작!\n${esc(cur.title)}` + (cur.category ? `\n🎮 ${esc(cur.category)}` : ""),
        liveButtons(m),
      );
    } else if (prev.chatChannelId !== cur.chatChannelId) {
      stopChat(m.id);
    }
    state.set(m.id, { ...cur, offCount: 0 });
    startChat(m, cur.chatChannelId);
    return;
  }

  // 잠깐 CLOSE 로 보이는 경우가 있어 2번 연속일 때만 종료로 처리
  if (prev.status === "OPEN") {
    const offCount = prev.offCount + 1;
    if (offCount < 2) {
      state.set(m.id, { ...prev, offCount });
      return;
    }
    log("방송 종료", m.name);
    stopChat(m.id);
    await send(`⚫ ${esc(m.name)} 방송 종료`, [[{ text: "📢 채널", url: channelUrl(m.id) }]], true);
  }
  state.set(m.id, { ...cur, offCount: 0 });
}

async function pollAll(first = false) {
  for (const m of members) {
    await checkMember(m, first);
    await sleep(300);
  }
}

// ───── 채팅 ─────
const chats = new Map(); // 방송 중인 멤버 id -> { ws, ping, closed }
const pending = new Map(); // "채팅친멤버>방송멤버" -> { lines, donation }

function chatServer(chatChannelId) {
  const sum = [...chatChannelId].reduce((a, c) => a + c.charCodeAt(0), 0);
  return `wss://kr-ss${(sum % 9) + 1}.chat.naver.com/chat`;
}

function startChat(streamer, chatChannelId, onReady) {
  if (!WATCH_CHAT || !chatChannelId || chats.has(streamer.id)) return;
  const entry = { closed: false, fails: 0 };
  chats.set(streamer.id, entry);

  const connect = async () => {
    if (entry.closed) return;
    try {
      const t = await getJSON(
        `https://comm-api.game.naver.com/nng_main/v1/chats/access-token?channelId=${chatChannelId}&chatType=STREAMING`,
      );
      const accTkn = t.content?.accessToken;
      if (!accTkn) throw new Error("채팅 토큰 없음");
      const ws = new WebSocket(chatServer(chatChannelId));
      entry.ws = ws;
      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            ver: "3",
            cmd: 100,
            svcid: "game",
            cid: chatChannelId,
            tid: 1,
            bdy: {
              uid: null,
              devType: 2001,
              accTkn,
              auth: "READ",
              libVer: "4.9.3",
              osVer: "Windows/10",
              devName: "Google Chrome/127.0.0.0",
              locale: "ko",
              timezone: "Asia/Seoul",
            },
          }),
        );
        entry.ping = setInterval(() => ws.readyState === 1 && ws.send(JSON.stringify({ ver: "3", cmd: 0 })), 20000);
      };
      ws.onmessage = (ev) => {
        let p;
        try {
          p = JSON.parse(ev.data);
        } catch {
          return;
        }
        if (p.cmd === 0) return ws.send(JSON.stringify({ ver: "3", cmd: 10000 }));
        if (p.cmd === 10100) {
          entry.fails = 0;
          log("채팅 접속", streamer.name, "retCode", p.retCode);
          onReady?.(p.retCode);
          return;
        }
        if (p.cmd === 93101 || p.cmd === 93102) {
          for (const msg of Array.isArray(p.bdy) ? p.bdy : []) onChat(streamer, msg, p.cmd === 93102);
        }
      };
      ws.onclose = () => {
        clearInterval(entry.ping);
        if (!entry.closed) setTimeout(connect, 5000);
      };
      ws.onerror = () => {}; // 곧 onclose 가 와서 재접속
    } catch (e) {
      // 채팅 서버가 막힌 네트워크(일부 와이파이)면 계속 실패함 → 15초부터 최대 5분까지 간격을 늘려 재시도
      entry.fails++;
      const wait = Math.min(15000 * 2 ** (entry.fails - 1), 300000);
      if (entry.fails <= 3 || entry.fails % 10 === 0) log("채팅 접속 실패", streamer.name, e.message, `(${wait / 1000}초 후 재시도)`);
      if (!entry.closed) setTimeout(connect, wait);
    }
  };
  connect();
}

function stopChat(id) {
  const e = chats.get(id);
  if (!e) return;
  e.closed = true;
  clearInterval(e.ping);
  try {
    e.ws?.close();
  } catch {}
  chats.delete(id);
}

function onChat(streamer, msg, donation) {
  const uid = msg.uid ?? msg.userId;
  const who = memberById.get(uid);
  if (!who) return;
  if (uid === streamer.id && !ALERT_OWN_CHAT) return;
  const text = msg.msg ?? msg.content ?? "";
  if (!text) return;

  // 여러 줄을 연달아 치면 5초 동안 모아서 한 번에 보냄
  const key = `${uid}>${streamer.id}`;
  let b = pending.get(key);
  if (!b) {
    b = { lines: [], donation: false };
    pending.set(key, b);
    setTimeout(() => flushChat(key, who, streamer), 5000);
  }
  b.lines.push(text);
  b.donation ||= donation;
}

async function flushChat(key, who, streamer) {
  const b = pending.get(key);
  pending.delete(key);
  if (!b) return;
  const where = who.id === streamer.id ? "자기 방송" : `${esc(streamer.name)} 방송`;
  const lines = b.lines.slice(-10).map((l) => `• ${esc(l)}`).join("\n");
  log("멤버 채팅", who.name, "→", streamer.name, b.lines.length + "줄");
  await send(`${b.donation ? "💰" : "💬"} <b>${esc(who.name)}</b> → ${where} 채팅\n${lines}`, [
    [{ text: `📺 ${streamer.name} 방송 보기`, url: liveUrl(streamer.id) }],
  ]);
}

// ───── 실행 ─────
async function main() {
  await pollAll(true);
  const live = members.filter((m) => state.get(m.id)?.status === "OPEN");
  log("시작. 방송 중:", live.map((m) => m.name).join(", ") || "없음");
  await send(
    `🔔 스텔라이브 알림 시작 (${members.length}명 감시)\n` +
      (live.length ? `지금 방송 중: ${live.map((m) => esc(m.name)).join(", ")}` : "지금 방송 중인 멤버 없음"),
    live.length ? live.map((m) => [{ text: `📺 ${m.name}`, url: liveUrl(m.id) }]) : undefined,
    true,
  );
  for (;;) {
    await sleep(POLL_SEC * 1000);
    await pollAll();
  }
}

async function test() {
  const m = members[0];
  const cur = await fetchLive(m);
  log("live-status OK:", m.name, cur.status, cur.chatChannelId);
  const r = await send(
    `🧪 테스트 알림\n🔴 <b>${esc(m.name)}</b> 방송 시작! (예시)\n${esc(cur.title)}`,
    liveButtons(m),
  );
  log("텔레그램 전송:", r?.ok ? "OK" : "실패");
  const ok = await new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), 15000);
    startChat(m, cur.chatChannelId, (ret) => {
      clearTimeout(timer);
      resolve(ret === 0);
    });
  });
  log("채팅 서버 접속:", ok ? "OK" : "실패");
  stopChat(m.id);
  process.exit(ok && r?.ok ? 0 : 1);
}

(process.argv.includes("--test") ? test() : main()).catch((e) => {
  log("치명적 오류:", e);
  process.exit(1);
});
