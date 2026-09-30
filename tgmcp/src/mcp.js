// MCP (JSON-RPC 2.0, Streamable HTTP, stateless) 처리
import { ConfigError } from "./config.js";
import { TelegramError } from "./telegram.js";
import { ToolInputError, findTool, listTools } from "./tools.js";

const SERVER_INFO = { name: "tg-notify", version: "1.0.0" };
const DEFAULT_PROTOCOL = "2025-06-18";
const INSTRUCTIONS =
  "사용자 텔레그램 미러링 도구. 사용자가 텔레그램으로 Claude의 활동을 전부 받아본다. 다음 규칙을 항상 지켜라. " +
  "(1) 사용자 요청을 받으면 먼저 tg_notify(level=info)로 요청을 1~2줄로 요약해 보낸다. " +
  "(2) 도구를 쓰거나 단계를 마칠 때마다 무엇을 했고 결과가 어땠는지 tg_notify(level=progress, 무음)로 보낸다. " +
  "(3) 사용자에게 보여줄 최종 답변은 전문 그대로 tg_notify(level=done)로 보낸다. 길면 서버가 알아서 나눠 보낸다. " +
  "(4) 실패나 오류는 level=error, 주의할 점은 level=warn으로 보낸다. " +
  "(5) 사용자 결정이 필요하면 tg_ask를 쓴다. " +
  "(6) 비밀번호, PIN, API 키, 토큰, 개인정보는 그대로 보내지 말고 ***로 가린다. " +
  "(7) 전송이 실패해도 원래 작업은 계속한다.";

class RpcError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

const rpcError = (id, code, message) => ({ jsonrpc: "2.0", id, error: { code, message } });

async function callTool(params, ctx) {
  const tool = findTool(params?.name);
  if (!tool) throw new RpcError(-32602, `알 수 없는 도구: ${params?.name}`);
  try {
    const client = ctx.getClient();
    const text = await tool.run(params.arguments ?? {}, { ...ctx, ...client });
    return { content: [{ type: "text", text }] };
  } catch (e) {
    if (e instanceof ToolInputError || e instanceof TelegramError || e instanceof ConfigError) {
      return { content: [{ type: "text", text: `오류: ${e.message}` }], isError: true };
    }
    throw e;
  }
}

async function dispatch(method, params, ctx) {
  switch (method) {
    case "initialize":
      return {
        protocolVersion: typeof params?.protocolVersion === "string" ? params.protocolVersion : DEFAULT_PROTOCOL,
        capabilities: { tools: { listChanged: false } },
        serverInfo: SERVER_INFO,
        instructions: INSTRUCTIONS,
      };
    case "ping":
      return {};
    case "tools/list":
      return { tools: listTools() };
    case "tools/call":
      return callTool(params, ctx);
    default:
      throw new RpcError(-32601, `지원하지 않는 메서드: ${method}`);
  }
}

// 응답이 필요 없으면 null
export async function handleMessage(msg, ctx) {
  if (!msg || typeof msg !== "object" || msg.jsonrpc !== "2.0") {
    return rpcError(msg?.id ?? null, -32600, "Invalid Request");
  }
  if (typeof msg.method !== "string" || !("id" in msg)) return null; // 알림 or 클라이언트 응답

  try {
    return { jsonrpc: "2.0", id: msg.id, result: await dispatch(msg.method, msg.params ?? {}, ctx) };
  } catch (e) {
    if (e instanceof RpcError) return rpcError(msg.id, e.code, e.message);
    return rpcError(msg.id, -32603, "Internal error");
  }
}
