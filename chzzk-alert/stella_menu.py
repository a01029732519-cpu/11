#!/usr/bin/env python3
"""스텔라이브 멤버 메뉴 (Stellar Agent 봇에 holo_bot 같은 메뉴 붙이기).

alert.mjs(방송·채팅·카페·X 알림)는 텔레그램에 보내기만 해서, 같은 봇으로 이 프로그램이
명령어·버튼을 받아 메뉴를 보여줘도 충돌하지 않는다.
- 멤버 목록: members.json (alert.mjs 와 같은 파일, 같은 폴더)
- 봇 토큰: .env 의 BOT_TOKEN (alert.mjs 와 같은 파일)
- 채널 정보·방송 상태: 치지직 공개 엔드포인트 (API 키 불필요)
외부 패키지 없이 파이썬 표준 라이브러리만 사용한다.

실행: python stella_menu.py          점검: python stella_menu.py --check
"""

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(DIR, ".env")
MEMBERS_PATH = os.path.join(DIR, "members.json")

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36")}
LIVE_STATUS_URL = "https://api.chzzk.naver.com/polling/v3/channels/{}/live-status"   # alert.mjs 와 같은 곳
LIVE_DETAIL_URL = "https://api.chzzk.naver.com/service/v3/channels/{}/live-detail"
CHANNEL_URL = "https://api.chzzk.naver.com/service/v1/channels/{}"
STATUS_TTL = 30          # 방송 상태 캐시(초)
CHANNEL_TTL = 3600       # 채널 정보 캐시(초)

COMMANDS = [
    ("start", "시작 / 멤버 메뉴"),
    ("menu", "멤버 메뉴"),
    ("live", "지금 방송 중인 멤버"),
    ("help", "도움말"),
]

HELP_TEXT = (
    "<b>Stellar</b> — 스텔라이브 멤버 메뉴\n\n"
    "• /menu — 멤버 목록 (🔴 = 방송 중)\n"
    "• /live — 지금 방송 중인 멤버\n\n"
    "멤버를 누르면 방송 상태 · 채널 소개 · 팔로워 · 치지직 / X 버튼이 나와요.\n"
    "개인 채팅에서는 이름만 보내도 찾아줘요. 예: <code>마시로</code>\n\n"
    "방송 켜짐 · 멤버 채팅 · 카페 · X 알림은 지금처럼 자동으로 와요."
)


def log(msg):
    print(time.strftime("[%Y-%m-%d %H:%M:%S]"), msg, flush=True)


def load_env(path=ENV_PATH):
    env = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def load_members(path=MEMBERS_PATH):
    with open(path, encoding="utf-8") as f:
        members = json.load(f)
    return [m for m in members if re.fullmatch(r"[0-9a-f]{32}", m.get("id", ""))]


# ---------------------------------------------------------------- 치지직

def get_content(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    content = data.get("content") if isinstance(data, dict) else None
    if not isinstance(content, dict):
        raise ValueError(f"응답에 content 없음 (code {data.get('code') if isinstance(data, dict) else '?'})")
    return content


def live_url(cid):
    return f"https://chzzk.naver.com/live/{cid}"


def channel_page(cid):
    return f"https://chzzk.naver.com/{cid}"


class Chzzk:
    """방송 상태·채널 정보 조회 + 짧은 캐시."""

    def __init__(self, fetch=get_content):
        self.fetch = fetch
        self.cache = {}  # (종류, id) -> (시각, 값)

    def _cached(self, kind, cid, ttl, url):
        hit = self.cache.get((kind, cid))
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        value = self.fetch(url.format(cid))
        self.cache[(kind, cid)] = (time.time(), value)
        return value

    def status(self, cid):
        """{"live": bool, "title", "category", "viewers"} — 실패하면 None."""
        try:
            c = self._cached("status", cid, STATUS_TTL, LIVE_STATUS_URL)
        except Exception as e:
            log(f"방송 상태 확인 실패 ({cid[:8]}): {e}")
            return None
        viewers = c.get("concurrentUserCount")
        return {
            "live": c.get("status") == "OPEN",
            "title": c.get("liveTitle") or "",
            "category": c.get("liveCategoryValue") or "",
            "viewers": viewers if isinstance(viewers, int) and viewers > 0 else None,
        }

    def statuses(self, members):
        with ThreadPoolExecutor(max_workers=6) as pool:
            return dict(zip([m["id"] for m in members], pool.map(lambda m: self.status(m["id"]), members)))

    def detail(self, cid):
        """방송 중일 때 썸네일·시청자 수 (없으면 빈 dict)."""
        try:
            c = self._cached("detail", cid, STATUS_TTL, LIVE_DETAIL_URL)
        except Exception:
            return {}
        image = c.get("liveImageUrl") or ""
        viewers = c.get("concurrentUserCount")
        return {
            "image": image.replace("{type}", "720") if image.startswith("https://") else "",
            "viewers": viewers if isinstance(viewers, int) and viewers > 0 else None,
        }

    def channel(self, cid):
        try:
            c = self._cached("channel", cid, CHANNEL_TTL, CHANNEL_URL)
        except Exception as e:
            log(f"채널 정보 확인 실패 ({cid[:8]}): {e}")
            return {}
        followers = c.get("followerCount")
        image = c.get("channelImageUrl") or ""
        return {
            "name": c.get("channelName") or "",
            "image": image if image.startswith("https://") else "",
            "description": c.get("channelDescription") or "",
            "followers": followers if isinstance(followers, int) else None,
        }


# ---------------------------------------------------------------- Telegram

class TelegramError(Exception):
    pass


class Telegram:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}/"

    def call(self, method, params=None, http_timeout=30):
        req = urllib.request.Request(self.base + method, data=json.dumps(params or {}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=http_timeout) as resp:
                res = json.load(resp)
        except urllib.error.HTTPError as e:
            try:
                res = json.loads(e.read().decode("utf-8"))
            except Exception:
                raise TelegramError(f"HTTP {e.code}") from None
        if not res.get("ok"):
            raise TelegramError(res.get("description", "unknown error"))
        return res.get("result")


# ---------------------------------------------------------------- 화면

def esc(s):
    return html.escape(str(s), quote=False)


def button(text, data):
    return {"text": text, "callback_data": data[:64]}


def url_button(text, url):
    return {"text": text, "url": url}


def rows_of(buttons, n):
    return [buttons[i:i + n] for i in range(0, len(buttons), n)]


NO_PREVIEW = {"is_disabled": True}


def norm(s):
    return re.sub(r"[\s_\-.·]", "", s.lower())


def search(members, query):
    q = norm(query)
    if not q:
        return []
    return [m for m in members if q in norm(m["name"]) or (m.get("x") and q in norm(m["x"]))]


def menu_view(members, chzzk):
    st = chzzk.statuses(members)
    live = [m for m in members if (st.get(m["id"]) or {}).get("live")]
    text = (f"🌟 <b>Stellar</b> — 스텔라이브 멤버 {len(members)}명\n"
            f"지금 방송 중 {len(live)}명 · {time.strftime('%H:%M')} 기준\n\n"
            "멤버를 고르세요. 🔴 = 방송 중")
    buttons = [button(("🔴 " if m in live else "") + m["name"], f"m:{m['id']}") for m in members]
    rows = [[button(f"🔴 방송 중 ({len(live)})", "lv")]] + rows_of(buttons, 2)
    return text, {"inline_keyboard": rows}, NO_PREVIEW


def member_view(members, chzzk, cid):
    m = next((m for m in members if m["id"] == cid), None)
    if not m:
        return menu_view(members, chzzk)
    st = chzzk.status(cid)
    ch = chzzk.channel(cid)
    parts = [f"<b>{esc(m['name'])}</b>" + (f"  <i>{esc(ch['name'])}</i>" if ch.get("name") and ch["name"] != m["name"] else "")]
    preview_image = ch.get("image")
    if st is None:
        parts.append("❔ 방송 상태를 불러오지 못했어요")
    elif st["live"]:
        d = chzzk.detail(cid)
        viewers = st["viewers"] or d.get("viewers")
        line = f"🔴 <b>방송 중</b>: {esc(st['title'] or '제목 없음')}"
        extra = " · ".join(x for x in (f"🎮 {esc(st['category'])}" if st["category"] else "",
                                       f"👀 {viewers:,}" if viewers else "") if x)
        parts.append(line + (f"\n{extra}" if extra else ""))
        preview_image = d.get("image") or preview_image
    else:
        parts.append("⚫ 오프라인")
    info = []
    if ch.get("followers") is not None:
        info.append(f"💗 팔로워 {ch['followers']:,}명")
    info.append(f"📺 치지직: {esc(channel_page(cid))}")
    if m.get("x"):
        info.append(f"𝕏 X: @{esc(m['x'])}")
    parts.append("\n".join(info))
    if ch.get("description"):
        desc = ch["description"].strip()
        parts.append(esc(desc if len(desc) <= 500 else desc[:500].rstrip() + "…"))
    text = "\n\n".join(parts)[:4000]

    rows = []
    if st and st["live"]:
        rows.append([url_button("▶ 방송 보러가기", live_url(cid))])
    links = [url_button("📺 치지직 채널", channel_page(cid))]
    if m.get("x"):
        links.append(url_button("𝕏 X", f"https://x.com/{m['x']}"))
    rows.append(links)
    rows.append([button("🔄 새로고침", f"m:{cid}"), button("⬅️ 멤버 목록", "menu")])
    preview = ({"url": preview_image, "prefer_large_media": True, "show_above_text": True}
               if preview_image else NO_PREVIEW)
    return text, {"inline_keyboard": rows}, preview


def live_view(members, chzzk):
    st = chzzk.statuses(members)
    live = [m for m in members if (st.get(m["id"]) or {}).get("live")]
    failed = sum(1 for m in members if st.get(m["id"]) is None)
    text = f"🔴 <b>지금 방송 중</b> — {len(live)}명 · {time.strftime('%H:%M')} 기준"
    if not live:
        text += "\n\n지금 방송 중인 멤버가 없어요."
    for m in live:
        s = st[m["id"]]
        text += f"\n\n<b>{esc(m['name'])}</b>" + (f" · 👀 {s['viewers']:,}" if s["viewers"] else "")
        text += f"\n{esc(s['title'] or '제목 없음')}" + (f" · 🎮 {esc(s['category'])}" if s["category"] else "")
    if failed:
        text += f"\n\n⚠️ {failed}명은 상태를 불러오지 못했어요."
    rows = [[url_button(f"▶ {m['name']}", live_url(m["id"])), button("정보", f"m:{m['id']}")] for m in live]
    rows.append([button("🔄 새로고침", "lv"), button("⬅️ 멤버 목록", "menu")])
    return text[:4000], {"inline_keyboard": rows}, NO_PREVIEW


def results_view(members, chzzk, query, results):
    if len(results) == 1:
        return member_view(members, chzzk, results[0]["id"])
    if not results:
        return (f"🔍 <b>{esc(query)}</b> — 찾는 멤버가 없어요.", {"inline_keyboard": [[button("⬅️ 멤버 목록", "menu")]]},
                NO_PREVIEW)
    buttons = [button(m["name"], f"m:{m['id']}") for m in results]
    return (f"🔍 <b>{esc(query)}</b> 검색 결과 {len(results)}명",
            {"inline_keyboard": rows_of(buttons, 2) + [[button("⬅️ 멤버 목록", "menu")]]}, NO_PREVIEW)


# ---------------------------------------------------------------- 봇

class Bot:
    def __init__(self, tg, members, chzzk):
        self.tg = tg
        self.members = members
        self.chzzk = chzzk

    def send(self, chat_id, view):
        text, markup, preview = view
        params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "link_preview_options": preview}
        if markup:
            params["reply_markup"] = markup
        self.tg.call("sendMessage", params)

    def edit(self, chat_id, message_id, view):
        text, markup, preview = view
        try:
            self.tg.call("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text,
                                             "parse_mode": "HTML", "reply_markup": markup,
                                             "link_preview_options": preview})
        except TelegramError as e:
            if "message is not modified" not in str(e):
                self.send(chat_id, view)  # 알림 메시지 등 수정할 수 없는 메시지면 새로 보냄

    def handle(self, update):
        if "callback_query" in update:
            cq = update["callback_query"]
            try:
                self.tg.call("answerCallbackQuery", {"callback_query_id": cq["id"]})
            except TelegramError:
                pass
            msg = cq.get("message")
            if not msg or "chat" not in msg:
                return
            kind, _, arg = (cq.get("data") or "").partition(":")
            if kind == "m":
                view = member_view(self.members, self.chzzk, arg)
            elif kind == "lv":
                view = live_view(self.members, self.chzzk)
            else:
                view = menu_view(self.members, self.chzzk)
            self.edit(msg["chat"]["id"], msg["message_id"], view)
        elif "message" in update:
            msg = update["message"]
            text = (msg.get("text") or "").strip()
            chat = msg["chat"]
            if not text:
                return
            if text.startswith("/"):
                cmd = text.split()[0][1:].split("@", 1)[0].lower()
                if cmd in ("start", "menu"):
                    self.send(chat["id"], menu_view(self.members, self.chzzk))
                elif cmd == "live":
                    self.send(chat["id"], live_view(self.members, self.chzzk))
                elif cmd == "help":
                    self.send(chat["id"], (HELP_TEXT, None, NO_PREVIEW))
            elif chat.get("type") == "private":
                self.send(chat["id"], results_view(self.members, self.chzzk, text, search(self.members, text)))

    def run(self):
        offset = None
        backoff = 1
        conflict_logged = False
        while True:
            try:
                params = {"timeout": 50, "allowed_updates": ["message", "callback_query"]}
                if offset is not None:
                    params["offset"] = offset
                updates = self.tg.call("getUpdates", params, http_timeout=60)
                backoff = 1
                conflict_logged = False
            except Exception as e:
                if "conflict" in str(e).lower():
                    # 다른 프로그램이 같은 봇으로 getUpdates 중 — 그쪽을 방해하지 않게 천천히 재시도
                    if not conflict_logged:
                        log(f"다른 프로그램이 이 봇의 업데이트를 받고 있어요: {e} — 30초마다 재시도")
                        conflict_logged = True
                    time.sleep(30)
                    continue
                log(f"getUpdates 오류: {e} — {backoff}초 뒤 재시도")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    self.handle(update)
                except Exception as e:
                    log(f"업데이트 처리 오류: {type(e).__name__}: {e}")


def load_token(env):
    token = os.environ.get("BOT_TOKEN") or env.get("BOT_TOKEN", "")
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{30,}", token):
        sys.exit(f"{ENV_PATH} 에 BOT_TOKEN 이 없거나 형식이 잘못됐어요 (alert.mjs 와 같은 .env)")
    return token


def check(tg, members, chzzk):
    me = tg.call("getMe")
    print(f"✅ 봇: @{me['username']} ({me.get('first_name', '')})")
    hook = tg.call("getWebhookInfo").get("url")
    print("❌ 웹훅이 설정돼 있어요 (다른 프로그램이 쓰는 중): " + hook if hook else "✅ 웹훅 없음 → 메뉴 사용 가능")
    st = chzzk.statuses(members)
    for m in members:
        s = st.get(m["id"])
        state = "❔ 실패" if s is None else (f"🔴 {s['title']} ({s['category']}, 👀 {s['viewers']})" if s["live"] else "⚫")
        print(f"  {m['name']}: {state}")
    ch = chzzk.channel(members[0]["id"])
    print(f"✅ 채널 정보 ({members[0]['name']}): 이름={ch.get('name')!r} 팔로워={ch.get('followers')} "
          f"사진={'있음' if ch.get('image') else '없음'} 소개={len(ch.get('description', ''))}자")


def main():
    env = load_env()
    tg = Telegram(load_token(env))
    members = load_members()
    chzzk = Chzzk()
    if "--check" in sys.argv:
        check(tg, members, chzzk)
        return
    me = tg.call("getMe")
    hook = tg.call("getWebhookInfo").get("url")
    if hook:
        # 웹훅을 쓰는 다른 프로그램이 있으면 그걸 끊지 않고 멈춘다
        sys.exit(f"@{me['username']} 에 웹훅이 설정돼 있어서 메뉴를 켜지 않아요: {hook}")
    try:
        tg.call("setMyCommands", {"commands": [{"command": c, "description": d} for c, d in COMMANDS]})
    except TelegramError as e:
        log(f"명령어 등록 경고: {e}")
    log(f"@{me['username']} 메뉴 시작 (멤버 {len(members)}명)")
    Bot(tg, members, chzzk).run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
