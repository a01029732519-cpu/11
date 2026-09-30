# 칸나 펫이 오류·대기·질문 상태를 받게 폰 조종 서버(~/phone-mcp/server.mjs)를 고침
#   - 폰 조작 도구가 실패하면 펫에 '오류' 신호
#   - 새 도구 phone_pet: 질문(ask)·대기(wait)·완료(done) 등을 직접 표시
# 원본은 ~/.mcp-backup/phone-mcp/server.mjs.before-pet 에 백업. 두 번 실행해도 안전.
# 'kanna-server v3' 표시는 그대로 둬서 MCP Controller 앱이 시작할 때 덮어쓰지 않음.
import os, shutil, subprocess, sys

SRV = os.path.expanduser('~/phone-mcp/server.mjs')
BAK = os.path.expanduser('~/.mcp-backup/phone-mcp/server.mjs.before-pet')
MARK = '// pet-patch v1'

HELPER = r"""
// pet-patch v1: 칸나 펫 상태 신호 (실패하면 '오류', phone_pet 도구로 질문·대기 등 표시)
const PET_RECV = 'com.pastel.aipet.kanna/com.pastel.aipet.PetReceiver';
function petSignal(type, text = '') {
  if (fs.existsSync(HOME + '/.config/phone-mcp/pet.off')) return;
  const args = ['-s', addr(), 'shell', 'am', 'broadcast', '-n', PET_RECV, '-a', 'com.pastel.aipet.EVENT', '--es', 'type', type];
  const t = String(text || '').replace(/\s+/g, ' ').trim().slice(0, 60);
  if (t) args.push('--es', 'text', "'" + t.replace(/'/g, "'\\''") + "'");
  execFile('adb', args, { timeout: 5000 }, () => {});
}
"""

WRAP = r"""
  // pet-patch v1: 도구가 실패하면 펫에 '오류' 표시
  const addTool = s.tool.bind(s);
  s.tool = (name, desc, schema, handler) => addTool(name, desc, schema, async (...a) => {
    try { return await handler(...a); } catch (e) { petSignal('error', e && e.message); throw e; }
  });
"""

PET_TOOL = r"""
  s.tool('phone_pet', '칸나 펫 상태 표시. 사용자에게 질문하거나 허락을 구할 때 ask, 오래 기다릴 때(생성·로딩·한도) wait, 작업이 끝나면 done, 실패하면 error, 생각 중 think, 설명 중 talk. text는 말풍선(선택, 60자)',
    { state: z.enum(['ask', 'wait', 'done', 'error', 'think', 'talk', 'idle', 'sleep']), text: z.string().max(60).optional() },
    async ({ state, text }) => { petSignal(state, text); return ok(); });
"""

# (찾을 줄, 바꿀 줄) - 하나라도 없으면 아무것도 안 바꾸고 멈춤
EDITS = [
    ("const ok = (t = 'ok') => ({ content: [{ type: 'text', text: t }] });\n",
     "const ok = (t = 'ok') => ({ content: [{ type: 'text', text: t }] });\n" + HELPER),
    ("  const s = new McpServer({ name: 'phone', version: '3.0.0' });\n",
     "  const s = new McpServer({ name: 'phone', version: '3.0.0' });\n" + WRAP),
    ("      if (/[^\\x20-\\x7E]/.test(text)) return ok('한글 등 비ASCII 문자는 ADB 기본 입력으로 불가');\n",
     "      if (/[^\\x20-\\x7E]/.test(text)) { petSignal('error', '한글은 입력 못 함'); return ok('한글 등 비ASCII 문자는 ADB 기본 입력으로 불가'); }\n"),
    ("  return s;\n}\n",
     PET_TOOL.lstrip('\n') + "  return s;\n}\n"),
]


def main():
    src = open(SRV, encoding='utf-8').read()
    if MARK in src:
        print('PET_PATCH_ALREADY')
        return
    if 'kanna-server v3' not in src:
        sys.exit('server.mjs 가 v3 가 아님 - 중단')
    out = src
    for old, new in EDITS:
        if out.count(old) != 1:
            sys.exit('고칠 위치를 못 찾음 - 중단: ' + old.strip()[:60])
        out = out.replace(old, new)
    tmp = SRV[:-4] + '.pet.mjs'
    open(tmp, 'w', encoding='utf-8').write(out)
    if subprocess.run(['node', '--check', tmp]).returncode != 0:
        os.remove(tmp)
        sys.exit('문법 검사 실패 - 중단 (원본 그대로)')
    os.makedirs(os.path.dirname(BAK), exist_ok=True)
    shutil.copy2(SRV, BAK)
    os.replace(tmp, SRV)
    print('PET_PATCH_OK')


if __name__ == '__main__':
    main()
