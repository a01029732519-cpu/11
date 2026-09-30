// 메시지 포맷 (Telegram HTML)
export const MAX_BODY = 3500;

export const LEVELS = {
  info: { icon: "ℹ️", silent: false },
  progress: { icon: "⏳", silent: true },
  done: { icon: "✅", silent: false },
  warn: { icon: "⚠️", silent: false },
  error: { icon: "❌", silent: false },
};

const SOURCE_NAMES = { claude: "Claude", gpt: "ChatGPT", chatgpt: "ChatGPT", grok: "Grok" };

// 텔레그램으로 나가기 전에 흔한 비밀값 모양을 가린다.
const SECRET_PATTERNS = [
  /\b\d{8,12}:[A-Za-z0-9_-]{30,}\b/g, // 텔레그램 봇 토큰
  /\b(?:sk|pk)-[A-Za-z0-9_-]{16,}\b/g, // sk-... 류
  /\b(?:ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{20,}\b/g, // 깃허브 토큰
  /\bBearer\s+[A-Za-z0-9._~+/=-]{16,}/gi,
  /\b((?:token|secret|password|passwd|api[_-]?key|key|비번|비밀번호|pin|핀)\s*[:=]\s*)[^\s"',;]{4,}/gi,
];

export function redact(text) {
  let out = String(text);
  for (const re of SECRET_PATTERNS) out = out.replace(re, (m, g1) => (typeof g1 === "string" ? `${g1}***` : "***"));
  return out;
}

// 긴 글을 텔레그램 한도에 맞게 줄바꿈 기준으로 나눈다.
export function chunk(text, limit = MAX_BODY) {
  const s = String(text);
  if (s.length <= limit) return [s];
  const parts = [];
  let rest = s;
  while (rest.length > limit) {
    let cut = rest.lastIndexOf("\n", limit);
    if (cut < limit * 0.5) cut = rest.lastIndexOf(" ", limit);
    if (cut < limit * 0.5) cut = limit;
    parts.push(rest.slice(0, cut));
    rest = rest.slice(cut).replace(/^\s+/, "");
  }
  if (rest) parts.push(rest);
  return parts;
}

export function esc(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function truncate(text, limit = MAX_BODY) {
  const s = String(text);
  return s.length <= limit ? s : s.slice(0, limit - 1) + "…";
}

export function sourceName(source) {
  return SOURCE_NAMES[source] ?? source;
}

export function formatNotify(source, level, message, part = "") {
  return `${LEVELS[level].icon} <b>${esc(sourceName(source))}</b>${part}\n${esc(truncate(redact(message)))}`;
}

export function formatQuestion(source, question) {
  return `❓ <b>${esc(sourceName(source))}</b>\n${esc(truncate(redact(question)))}`;
}

export function formatAnswer(answer) {
  if (!answer) return "<b>→ ⏱ 응답 없음</b>";
  return `<b>→ ${esc(truncate(answer.value, 300))}</b>`;
}
