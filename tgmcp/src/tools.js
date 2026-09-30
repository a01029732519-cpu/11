// MCP 도구 정의 + 실행
import { ask } from "./ask.js";
import { LEVELS, chunk, formatNotify, formatQuestion } from "./format.js";

export class ToolInputError extends Error {}

const ASK_DEFAULT_TIMEOUT = 50;
const ASK_MAX_TIMEOUT = 55;

function requireString(args, key, maxLen) {
  const v = args[key];
  if (typeof v !== "string" || !v.trim()) throw new ToolInputError(`${key}는 비어 있지 않은 문자열이어야 해`);
  if (maxLen && v.length > maxLen) throw new ToolInputError(`${key}는 ${maxLen}자 이하`);
  return v.trim();
}

const TOOLS = [
  {
    name: "tg_notify",
    description:
      "사용자의 텔레그램으로 Claude의 활동을 전부 미러링한다. 요청 접수(info), 단계별 진행(progress, 무음), " +
      "최종 답변 전문(done), 주의(warn), 오류(error)를 보낼 때 사용. 긴 글은 자동으로 여러 메시지로 나뉜다. 비밀값은 ***로 가려서 보낼 것.",
    inputSchema: {
      type: "object",
      properties: {
        message: { type: "string", description: "보낼 내용 (최대 12000자, 길면 자동 분할)" },
        level: { type: "string", enum: Object.keys(LEVELS), default: "info" },
      },
      required: ["message"],
    },
    async run(args, ctx) {
      const message = requireString(args, "message", 12000);
      const level = args.level ?? "info";
      if (!LEVELS[level]) throw new ToolInputError(`level은 ${Object.keys(LEVELS).join(", ")} 중 하나`);
      const parts = chunk(message);
      for (let i = 0; i < parts.length; i++) {
        const tag = parts.length > 1 ? ` (${i + 1}/${parts.length})` : "";
        await ctx.tg.sendMessage(ctx.chatId, formatNotify(ctx.source, level, parts[i], tag), { silent: LEVELS[level].silent });
      }
      return parts.length > 1 ? `알림 보냄 (${parts.length}개로 나눔)` : "알림 보냄";
    },
  },
  {
    name: "tg_ask",
    description:
      "사용자의 텔레그램으로 선택지 버튼이 달린 질문을 보내고 응답을 기다린다. 작업 중 사용자 결정이 필요할 때 사용. " +
      "사용자가 버튼 대신 직접 답장하면 그 텍스트를 돌려준다. 응답이 없으면 timeout을 돌려주니 임의로 진행하지 말 것.",
    inputSchema: {
      type: "object",
      properties: {
        question: { type: "string", description: "질문 내용" },
        options: {
          type: "array",
          items: { type: "string" },
          minItems: 2,
          maxItems: 6,
          description: "버튼 선택지 (각 40자 이하)",
        },
        timeout_sec: {
          type: "integer",
          minimum: 10,
          maximum: ASK_MAX_TIMEOUT,
          default: ASK_DEFAULT_TIMEOUT,
        },
      },
      required: ["question", "options"],
    },
    async run(args, ctx) {
      const question = requireString(args, "question", 3000);
      const options = args.options;
      if (!Array.isArray(options) || options.length < 2 || options.length > 6) {
        throw new ToolInputError("options는 2~6개");
      }
      if (options.some((o) => typeof o !== "string" || !o.trim() || o.length > 40)) {
        throw new ToolInputError("options 각 항목은 1~40자 문자열");
      }
      const timeoutSec = Math.min(
        ASK_MAX_TIMEOUT,
        Math.max(10, Number.isInteger(args.timeout_sec) ? args.timeout_sec : ASK_DEFAULT_TIMEOUT),
      );

      const answer = await ask(ctx.tg, ctx.chatId, {
        text: formatQuestion(ctx.source, question),
        options: options.map((o) => o.trim()),
        timeoutSec,
      });
      if (!answer) return JSON.stringify({ status: "timeout" });
      return JSON.stringify({ status: "answered", type: answer.kind, answer: answer.value });
    },
  },
];

export function listTools() {
  return TOOLS.map(({ name, description, inputSchema }) => ({ name, description, inputSchema }));
}

export function findTool(name) {
  return TOOLS.find((t) => t.name === name);
}
