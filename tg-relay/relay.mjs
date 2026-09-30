// Claude Alert 봇 ↔ 폰의 Claude / ChatGPT 앱 중계
// 텔레그램에서 메시지를 보내면 폰에서 앱을 열어 대신 입력하고, 답을 텔레그램으로 돌려준다.
import { execFile } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { promisify } from "node:util";

const run = promisify(execFile);
const HOME = process.env.HOME;
const ENV_FILE = `${HOME}/tg-relay/.env`;
const STATE_FILE = `${HOME}/tg-relay/state.json`;
const ADB = ["-s", "127.0.0.1:5555"];

const APPS = {
  claude: { name: "Claude", pkg: "com.anthropic.claude", icon: "🟠" },
  gpt: { name: "ChatGPT", pkg: "com.openai.chatgpt", icon: "🟢" },
};
const SEND_RE = /^(메시지 보내기|보내기|전송|Send|Send message)$/i;
const STOP_RE = /(중지|중단|Stop|생성 멈추기)/i;
const COPY_RE = /^(복사|Copy|메시지 복사|응답 복사)$/i;
const NEW_RE = /^(새 채팅|새 대화|New chat)$/i;
const MENU_RE = /^(메뉴 열기|메뉴|Open menu|사이드바 열기)$/i;
const MAX_WAIT_MS = 240_000;

const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- 설정 ----------
async function loadEnv() {
  const env = {};
  for (const line of (await readFile(ENV_FILE, "utf8")).split("\n")) {
    const m = line.match(/^\s*([A-Z_]+)\s*=\s*(.*)\s*$/);
    if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
  if (!/^\d+:[\w-]{30,}$/.test(env.BOT_TOKEN ?? "")) throw new Error("BOT_TOKEN 형식 이상");
  if (!/^-?\d+$/.test(env.CHAT_ID ?? "")) throw new Error("CHAT_ID 없음");
  return env;
}
let state = { target: "claude" };
const loadState = async () => { try { state = { ...state, ...JSON.parse(await readFile(STATE_FILE, "utf8")) }; } catch {} };
const saveState = () => writeFile(STATE_FILE, JSON.stringify(state)).catch(() => {});

// ---------- 텔레그램 ----------
let TOKEN, CHAT_ID;
async function tg(method, params = {}) {
  const res = await fetch(`https://api.telegram.org/bot${TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(params),
  });
  const data = await res.json().catch(() => ({}));
  if (!data.ok) {
    const err = new Error(`${method}: ${data.description ?? res.status}`);
    err.code = data.error_code ?? res.status;
    throw err;
  }
  return data.result;
}
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
function chunks(text, limit = 3500) {
  const out = [];
  let rest = String(text);
  while (rest.length > limit) {
    let cut = rest.lastIndexOf("\n", limit);
    if (cut < limit / 2) cut = limit;
    out.push(rest.slice(0, cut));
    rest = rest.slice(cut).replace(/^\n/, "");
  }
  if (rest) out.push(rest);
  return out;
}
const send = (text, extra = {}) => tg("sendMessage", { chat_id: CHAT_ID, text, parse_mode: "HTML", disable_web_page_preview: true, ...extra });

function menuKeyboard() {
  const mark = (k) => (state.target === k ? "✅ " : "") + APPS[k].icon + " " + APPS[k].name;
  return {
    inline_keyboard: [
      [{ text: mark("claude"), callback_data: "t:claude" }, { text: mark("gpt"), callback_data: "t:gpt" }],
      [{ text: "🆕 새 대화 시작", callback_data: "new" }, { text: "ℹ️ 상태", callback_data: "status" }],
    ],
  };
}
const menuText = () =>
  `<b>AI 중계 메뉴</b>\n지금 대상: ${APPS[state.target].icon} <b>${APPS[state.target].name}</b>\n` +
  `메시지를 보내면 폰의 ${APPS[state.target].name} 앱에 대신 입력하고 답을 가져와요.\n` +
  `(폰 화면이 켜져 있고 잠금이 풀려 있어야 해요)`;

// ---------- 폰 조작 ----------
const adb = (...args) => run("adb", [...ADB, ...args], { maxBuffer: 16 << 20, timeout: 60_000 });
const shell = (cmd) => adb("shell", cmd);

async function dump() {
  await shell("uiautomator dump /sdcard/relay_ui.xml >/dev/null 2>&1");
  const { stdout } = await shell("cat /sdcard/relay_ui.xml");
  const nodes = [];
  for (const m of stdout.matchAll(/<node [^>]*?>/g)) {
    const a = (k) => (m[0].match(new RegExp(` ${k}="([^"]*)"`)) ?? [])[1] ?? "";
    const b = a("bounds").match(/\[(\d+),(\d+)\]\[(\d+),(\d+)\]/);
    if (!b) continue;
    const dec = (s) => s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#10;/g, "\n").replace(/&#39;/g, "'");
    nodes.push({
      text: dec(a("text")),
      desc: dec(a("content-desc")),
      cls: a("class"),
      pkg: a("package"),
      click: a("clickable") === "true",
      x1: +b[1], y1: +b[2], x2: +b[3], y2: +b[4],
      cx: (+b[1] + +b[3]) >> 1, cy: (+b[2] + +b[4]) >> 1,
    });
  }
  return nodes;
}
const label = (n) => n.desc || n.text;
const find = (nodes, re) => nodes.filter((n) => re.test(label(n).trim()));
const tap = (x, y) => shell(`input tap ${x} ${y}`);

async function ensureUnlocked() {
  await shell("input keyevent KEYCODE_WAKEUP");
  const { stdout } = await shell("dumpsys window | grep -E 'mDreamingLockscreen|isKeyguardShowing|mShowingLockscreen' | head -3");
  if (/(mDreamingLockscreen|isKeyguardShowing|mShowingLockscreen)=true/.test(stdout)) throw new Error("폰이 잠겨 있어요. 잠금을 풀어 주세요.");
}

async function openApp(app) {
  await shell(`monkey -p ${app.pkg} -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1`);
  for (let i = 0; i < 10; i++) {
    await sleep(800);
    const nodes = await dump();
    if (nodes.some((n) => n.pkg === app.pkg)) return nodes;
  }
  throw new Error(`${app.name} 앱이 안 열려요`);
}

async function newChat(app) {
  let nodes = await openApp(app);
  for (let step = 0; step < 4; step++) {
    const nb = find(nodes, NEW_RE)[0];
    if (nb) { await tap(nb.cx, nb.cy); await sleep(1500); return true; }
    const mb = find(nodes, MENU_RE)[0];
    if (mb && step === 0) { await tap(mb.cx, mb.cy); await sleep(1200); nodes = await dump(); continue; }
    await shell("input keyevent KEYCODE_BACK"); await sleep(900);
    nodes = await openApp(app);
  }
  return false;
}

async function relay(key, text) {
  const app = APPS[key];
  await ensureUnlocked();
  let nodes = await openApp(app);
  let edit = nodes.filter((n) => n.pkg === app.pkg && /EditText/.test(n.cls)).at(-1);
  if (!edit) {
    await shell("input keyevent KEYCODE_BACK"); await sleep(900);
    nodes = await openApp(app);
    edit = nodes.filter((n) => n.pkg === app.pkg && /EditText/.test(n.cls)).at(-1);
  }
  if (!edit) throw new Error(`${app.name} 입력창을 못 찾았어요`);

  const beforeCopies = find(nodes, COPY_RE).length;
  await tap(edit.cx, edit.cy);
  await sleep(500);
  await run("termux-clipboard-set", [text], { timeout: 15_000 });
  await shell("input keyevent 279"); // 붙여넣기
  await sleep(900);

  nodes = await dump();
  const sendBtn = find(nodes, SEND_RE).filter((n) => n.pkg === app.pkg).at(-1);
  if (!sendBtn) throw new Error(`${app.name} 보내기 버튼을 못 찾았어요 (붙여넣기 실패?)`);
  await tap(sendBtn.cx, sendBtn.cy);
  log("sent to", app.name);

  // 답변 끝날 때까지 기다리기: 중지 버튼이 사라지고 화면이 두 번 연속 같으면 끝
  const start = Date.now();
  let prev = "", same = 0;
  await sleep(4000);
  while (Date.now() - start < MAX_WAIT_MS) {
    nodes = await dump();
    const busy = find(nodes, STOP_RE).some((n) => n.pkg === app.pkg);
    const snap = nodes.filter((n) => n.pkg === app.pkg).map(label).join("\u0001");
    same = !busy && snap === prev ? same + 1 : 0;
    prev = snap;
    if (same >= 2) break;
    await sleep(3000);
  }

  // 1순위: 마지막 답변의 복사 버튼 → 클립보드
  const copies = find(nodes, COPY_RE).filter((n) => n.pkg === app.pkg);
  if (copies.length) {
    const last = copies.reduce((a, b) => (b.cy > a.cy ? b : a));
    await run("termux-clipboard-set", [""]).catch(() => {});
    await tap(last.cx, last.cy);
    for (let i = 0; i < 5; i++) {
      await sleep(800);
      const { stdout } = await run("termux-clipboard-get", [], { timeout: 15_000 });
      const got = stdout.trim();
      if (got && got !== text.trim()) return got;
    }
  }

  // 2순위: 화면 글자에서 내가 보낸 말 아래쪽 글만 모으기
  const editTop = (nodes.filter((n) => /EditText/.test(n.cls)).at(-1) ?? { y1: 99999 }).y1;
  const texts = nodes.filter((n) => n.pkg === app.pkg && n.text && !/EditText|Button/.test(n.cls) && n.y2 <= editTop);
  const head = text.trim().slice(0, 20);
  const idx = texts.map((n) => n.text).findLastIndex((t) => t.includes(head));
  const UI = /^(이미지|사진|복사|공유|좋아요|별로예요|다시 생성|편집|더 보기|음성|받아쓰기|Copy|Share|Edit|Retry|Image)$/i;
  const body = texts.slice(idx + 1).map((n) => n.text.trim()).filter((t) => t && !UI.test(t)).join("\n").trim();
  return body || "(답변을 읽지 못했어요. 앱에서 확인해 주세요.)";
}

// ---------- 메인 루프 ----------
let busy = false;
const queue = [];

async function worker() {
  if (busy) return;
  busy = true;
  while (queue.length) {
    const { key, text } = queue.shift();
    const app = APPS[key];
    let status;
    try {
      status = await send(`${app.icon} <b>${app.name}</b>에 보내는 중…`, { disable_notification: true });
      const answer = await relay(key, text);
      const parts = chunks(answer);
      for (let i = 0; i < parts.length; i++) {
        const tag = parts.length > 1 ? ` (${i + 1}/${parts.length})` : "";
        await send(`${app.icon} <b>${app.name}</b>${tag}\n${esc(parts[i])}`);
      }
      await tg("deleteMessage", { chat_id: CHAT_ID, message_id: status.message_id }).catch(() => {});
    } catch (e) {
      log("relay error", e.message);
      await send(`❌ <b>${app.name}</b> 중계 실패\n${esc(e.message)}`).catch(() => {});
    }
    await shell("input keyevent KEYCODE_HOME").catch(() => {});
  }
  busy = false;
}

async function doNew() {
  if (busy) return send("⏳ 지금 처리 중인 메시지가 끝나면 다시 눌러 주세요.");
  busy = true;
  try {
    await ensureUnlocked();
    const ok = await newChat(APPS[state.target]);
    await send(ok ? `🆕 ${APPS[state.target].name} 새 대화를 열었어요.` : `⚠️ ${APPS[state.target].name} 새 대화 버튼을 못 찾았어요.`);
  } catch (e) {
    await send(`❌ ${esc(e.message)}`).catch(() => {});
  } finally {
    await shell("input keyevent KEYCODE_HOME").catch(() => {});
    busy = false;
    worker();
  }
}

const answerCb = (id, text) => tg("answerCallbackQuery", { callback_query_id: id, text }).catch(() => {});

async function handle(u) {
  const cq = u.callback_query;
  if (cq) {
    if (String(cq.from?.id) !== CHAT_ID) return answerCb(cq.id, "권한 없음");
    const d = cq.data ?? "";
    if (d.startsWith("t:") && APPS[d.slice(2)]) {
      state.target = d.slice(2); await saveState();
      await answerCb(cq.id, `${APPS[state.target].name}로 바꿨어요`);
      await tg("editMessageText", { chat_id: CHAT_ID, message_id: cq.message.message_id, text: menuText(), parse_mode: "HTML", reply_markup: menuKeyboard() }).catch(() => {});
    } else if (d === "new") {
      await answerCb(cq.id, "새 대화를 여는 중…");
      await doNew();
    } else if (d === "status") {
      await answerCb(cq.id, `대상: ${APPS[state.target].name} · 대기 ${queue.length}건${busy ? " · 처리 중" : ""}`);
    } else {
      // tg_ask(알림 도구)의 버튼일 수 있으니 건드리지 않음
    }
    return;
  }
  const msg = u.message;
  if (!msg || String(msg.chat?.id) !== CHAT_ID || !msg.text) return;
  const t = msg.text.trim();
  const cmd = t.match(/^\/(\w+)(?:@\w+)?\s*([\s\S]*)$/);
  if (cmd) {
    const [, c, rest] = cmd;
    if (c === "start" || c === "menu") return send(menuText(), { reply_markup: menuKeyboard() });
    if (c === "claude" || c === "gpt") {
      state.target = c; await saveState();
      if (rest.trim()) { queue.push({ key: c, text: rest.trim() }); worker(); return; }
      return send(`${APPS[c].icon} 이제 <b>${APPS[c].name}</b>로 보내요.`, { reply_markup: menuKeyboard() });
    }
    if (c === "new") return doNew();
    return;
  }
  queue.push({ key: state.target, text: t });
  worker();
}

async function main() {
  const env = await loadEnv();
  TOKEN = env.BOT_TOKEN; CHAT_ID = env.CHAT_ID;
  await loadState();
  await tg("setMyCommands", {
    commands: [
      { command: "menu", description: "AI 중계 메뉴" },
      { command: "claude", description: "Claude 앱으로 보내기 (/claude 질문)" },
      { command: "gpt", description: "ChatGPT 앱으로 보내기 (/gpt 질문)" },
      { command: "new", description: "지금 대상 앱에서 새 대화 열기" },
    ],
  });
  await tg("setChatMenuButton", { menu_button: { type: "commands" } }).catch(() => {});
  log("relay started, target", state.target);

  let offset;
  for (;;) {
    try {
      const updates = await tg("getUpdates", { offset, timeout: 25, allowed_updates: ["message", "callback_query"] });
      for (const u of updates) {
        offset = u.update_id + 1;
        handle(u).catch((e) => log("handle error", e.message));
      }
    } catch (e) {
      // 409 = 알림 도구(tg_ask)가 잠깐 응답을 기다리는 중 → 양보
      if (e.code === 409) { log("yield to tg_ask"); await sleep(60_000); }
      else { log("poll error", e.message); await sleep(5000); }
    }
  }
}
main().catch((e) => { console.error("fatal:", e.message); process.exit(1); });
