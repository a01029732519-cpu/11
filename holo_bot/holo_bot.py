#!/usr/bin/env python3
"""holo_bot — 홀로라이브 멤버 정보 · 방송 · X 텔레그램 봇.

멤버 데이터는 홀로라이브 공식 사이트(hololive.hololivepro.com)에서 직접 가져와
members.json 에 캐시하고 24시간마다 갱신한다. 최근 영상은 YouTube 공개 RSS 피드를 쓴다.
방송 상태는 Holodex API(holodex_key.txt 필요)로 1분마다 확인하고, Holodex 가 안 되면
알림 켠 멤버만 유튜브 채널 페이지로 직접 확인한다.
X 새 글은 폰의 X 앱 알림을 termux-notification-list(Termux:API)로 읽어서 전달한다.
외부 패키지 없이 파이썬 표준 라이브러리만 사용하므로 Termux 에서 바로 실행된다.

사용법:
    python holo_bot.py            봇 실행 (토큰: 환경변수 HOLO_BOT_TOKEN 또는 token.txt)
    python holo_bot.py --scrape   공식 사이트에서 멤버 데이터만 새로 받아 요약 출력
    python holo_bot.py --check    Holodex·유튜브·폰 알림 연결만 점검해서 출력
"""

import html
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, "members.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.txt")
HOLODEX_KEY_PATH = os.path.join(BASE_DIR, "holodex_key.txt")
SUBS_PATH = os.path.join(BASE_DIR, "subs.json")
LIVE_STATE_PATH = os.path.join(BASE_DIR, "live_state.json")

SITE = "https://hololive.hololivepro.com"
LIST_URL = SITE + "/en/talents/"
GROUP_URL = SITE + "/en/talents?gp={}"
TALENT_URL = SITE + "/en/talents/{}/"
YT_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
YT_WATCH_URL = "https://www.youtube.com/watch?v={}"
YT_CHANNEL_LIVE_URL = "https://www.youtube.com/channel/{}/live"
HOLODEX_USERS_LIVE_URL = "https://holodex.net/api/v2/users/live?channels={}"
UA = ("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36")
# 유튜브 채널 페이지는 데스크톱 페이지로 받아야 채널 ID 가 온전히 들어있다
YT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept-Language": "en",
    "Cookie": "CONSENT=YES+1",
}

REFRESH_INTERVAL = 24 * 3600      # 공식 사이트 자동 갱신 주기
MANUAL_REFRESH_COOLDOWN = 600     # /refresh 최소 간격
VIDEO_CACHE_TTL = 600             # 최근 영상 캐시
VIDEO_COUNT = 5
MIN_MEMBERS = 20                  # 이보다 적게 받아지면 사이트 구조가 바뀐 것으로 보고 캐시 유지
LIVE_POLL_SEC = 60                # 방송 상태 확인 간격
FALLBACK_MAX_CHANNELS = 30        # Holodex 가 안 될 때 유튜브로 직접 확인할 최대 채널 수
LATE_ALERT_SEC = 30 * 60          # 시작한 지 이보다 오래된 방송은 (봇이 꺼져 있었던 경우) 알림 생략
UPCOMING_HOURS = 24               # 예정 방송 목록 범위
NOTIF_POLL_SEC = 15               # 폰 알림(X) 확인 간격
X_PACKAGE = "com.twitter.android"
ALUM_GROUP = "alum"
GROUP_LABELS = {ALUM_GROUP: "🎓 졸업 멤버"}  # 공식 사이트 그룹 이름 대신 보여줄 이름
# 공식 사이트 이름 앞에 붙는 상태 표시 ([Alum] Minato Aqua 등)
STATUS = {
    "alum": ("🎓", "졸업"),
    "affiliate": ("🤝", "어필리에이트"),
    "retirement": ("💤", "활동 종료"),
}
LIVE_TRACK_STATUS = {"", "affiliate"}  # 방송 감시 대상 (현역 + 어필리에이트)
NOT_TALENT_SLUGS = {"feed", "page"}

PROFILE_LABELS = {
    "Birthday": "🎂 생일",
    "Debut Stream": "📅 데뷔",
    "Height": "📏 키",
    "Unit": "👥 유닛",
    "Illustrator": "🎨 일러스트",
    "Fan Name": "💗 팬네임",
    "Hashtags": "#️⃣ 해시태그",
    "Catchphrases": "💬 캐치프레이즈",
    "Dream": "🌟 꿈",
    "Regular/Specialty Streams": "🎮 주요 방송",
    "Regular Streams": "🎮 주요 방송",
    "Age": "🎈 나이",
    "Referred to as": "🏷️ 애칭",
    "Hobbies": "🎯 취미",
    "Likes": "❤️ 좋아하는 것",
    "Special Skills": "✨ 특기",
}

COMMANDS = [
    ("start", "시작 / 메뉴"),
    ("menu", "메뉴 보기"),
    ("live", "지금 방송 중인 멤버"),
    ("schedule", "예정 방송 (24시간)"),
    ("alerts", "내 알림 설정 보기"),
    ("search", "멤버 검색 (예: /search pekora)"),
    ("x", "멤버 X 링크 (예: /x marine)"),
    ("yt", "멤버 유튜브 채널 (예: /yt suisei)"),
    ("refresh", "공식 사이트에서 멤버 정보 새로고침"),
    ("help", "도움말"),
]

HELP_TEXT = (
    "<b>holo_bot</b> — 홀로라이브 멤버 정보 · 방송 · X 봇\n\n"
    "• /menu — 메뉴 (그룹별 멤버 목록)\n"
    "• /live — 지금 방송 중인 멤버\n"
    "• /schedule — 예정 방송 (24시간)\n"
    "• /alerts — 내 알림 설정\n"
    "• /search 이름 — 멤버 검색 (영어/일본어 이름, 일부만 입력해도 됨)\n"
    "• /x 이름, /yt 이름 — X · 유튜브 링크\n"
    "• /refresh — 공식 사이트에서 정보 새로고침\n\n"
    "🔔 알림: 멤버 카드의 <b>🔔 알림 켜기</b> 를 누르면 그 멤버가 방송을 켜거나 X 에 글을 올릴 때 알려드려요. "
    "그룹 화면에서 한 번에 켤 수도 있어요.\n"
    "(X 알림은 봇이 돌아가는 폰의 X 앱에서 그 멤버 알림 🔔 이 켜져 있어야 와요)\n\n"
    "개인 채팅에서는 명령어 없이 이름만 보내도 검색돼요. 예: <code>pekora</code>, <code>ぺこら</code>\n"
    "🔴 방송 중 · 🎓 졸업 · 🤝 어필리에이트 · 💤 활동 종료\n"
    "정보 출처: hololive 공식 사이트 · 방송 정보: Holodex"
)


def log(msg):
    print(time.strftime("[%Y-%m-%d %H:%M:%S]"), msg, flush=True)


def http_get(url, timeout=20, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_text(url, timeout=20, headers=None):
    return http_get(url, timeout, headers).decode("utf-8", "replace")


# ---------------------------------------------------------------- 공식 사이트 스크래핑

SLUG_RE = re.compile(r"/en/talents/([a-z0-9-]+)/")
GROUP_RE = re.compile(r'/en/talents\?gp=([^"&]+)"[^>]*>(.*?)</a>', re.S)
NAME_RE = re.compile(r"<h1>\s*([^<]+?)\s*(?:<span>(.*?)</span>)?\s*</h1>", re.S)
STATUS_PREFIX_RE = re.compile(r"^\[([^\]]+)\]\s*(.+)$")
CATCH_RE = re.compile(r'<p class="catch">(.*?)</p>', re.S)
DESC_RE = re.compile(r'<p class="txt">(.*?)</p>', re.S)
SNS_RE = re.compile(r'<ul class="t_sns[^"]*">(.*?)</ul>', re.S)
LINK_RE = re.compile(r'<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
PROFILE_RE = re.compile(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", re.S)
OG_IMAGE_RE = re.compile(r'<meta property="og:image" content="([^"]+)"')
CHANNEL_RE = re.compile(r"youtube\.com/channel/(UC[\w-]{22})")
# 채널 페이지(youtube.com/@아이디)에서 그 채널 자신의 ID 를 찾는 패턴 (앞에 있을수록 확실)
CHANNEL_PAGE_RES = [
    re.compile(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"'),
    re.compile(r'"externalId":"(UC[\w-]{22})"'),
    re.compile(r'<meta itemprop="identifier" content="(UC[\w-]{22})"'),
]


def clean(text):
    """HTML 조각을 줄바꿈이 살아있는 평문으로."""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<video.*?</video>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [re.sub(r"[ \t　]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def page_slugs(page):
    return [s for s in dict.fromkeys(SLUG_RE.findall(page)) if s not in NOT_TALENT_SLUGS]


def normalize_link(url, label):
    url = html.unescape(url).strip()
    if "twitter.com/" in url:
        url = url.replace("://twitter.com/", "://x.com/").replace("://www.twitter.com/", "://x.com/")
    if "youtube.com/" in url:
        url = url.split("?", 1)[0]
    if label.lower() == "x" or "x.com/" in url:
        label = "X"
    return url, label


def parse_talent(slug, page):
    m = NAME_RE.search(page)
    if not m:
        raise ValueError("이름(h1)을 찾지 못함")
    name, status = clean(m.group(1)), ""
    if (p := STATUS_PREFIX_RE.match(name)):
        status, name = p.group(1).strip(), p.group(2).strip()
    talent = {
        "slug": slug,
        "name": name,
        "name_jp": clean(m.group(2) or ""),
        "status": status,
        "catch": "",
        "description": "",
        "profile": [],
        "links": [],
        "youtube": "",
        "channel_id": "",
        "x": "",
        "image": "",
        "url": TALENT_URL.format(slug),
    }
    if (c := CATCH_RE.search(page)):
        talent["catch"] = clean(c.group(1))
    if (d := DESC_RE.search(page)):
        talent["description"] = clean(d.group(1))
    if (s := SNS_RE.search(page)):
        for href, label in LINK_RE.findall(s.group(1)):
            url, label = normalize_link(href, clean(label) or "Link")
            if not url.startswith(("http://", "https://")):
                continue
            talent["links"].append({"label": label, "url": url})
            if "youtube.com/" in url and not talent["youtube"]:
                talent["youtube"] = url
                if (ch := CHANNEL_RE.search(url)):
                    talent["channel_id"] = ch.group(1)
            elif "x.com/" in url and not talent["x"]:
                talent["x"] = url
    for key, value in PROFILE_RE.findall(page):
        key, value = clean(key).rstrip(":：").strip(), clean(value)
        if key and value:
            talent["profile"].append([key, value])
    if (img := OG_IMAGE_RE.search(page)):
        talent["image"] = html.unescape(img.group(1))
    return talent


def resolve_channel_id(url):
    """youtube.com/@아이디 같은 링크의 실제 채널 ID(UC...)를 채널 페이지에서 찾는다. 실패하면 ""."""
    try:
        page = http_text(url, headers=YT_HEADERS)
    except Exception as e:
        log(f"유튜브 채널 페이지 실패 ({url}): {e}")
        return ""
    for pattern in CHANNEL_PAGE_RES:
        if (m := pattern.search(page)):
            return m.group(1)
    log(f"유튜브 채널 ID 를 못 찾음: {url}")
    return ""


def fill_channel_ids(members, old_members, delay):
    """링크에 채널 ID 가 없는 멤버(@아이디 링크)는 채널 페이지에서 찾아 채운다 (최근 영상용)."""
    resolved = {}
    for slug, t in members.items():
        if not t.get("youtube") or t.get("channel_id"):
            continue
        prev = old_members.get(slug) or {}
        if prev.get("youtube") == t["youtube"] and prev.get("channel_id"):
            t["channel_id"] = prev["channel_id"]
            continue
        if t["youtube"] not in resolved:
            resolved[t["youtube"]] = resolve_channel_id(t["youtube"])
            time.sleep(delay)
        t["channel_id"] = resolved[t["youtube"]]


def scrape(old=None, delay=0.3):
    """공식 사이트 전체를 긁어 {"updated", "groups", "members"} 를 만든다."""
    old_members = (old or {}).get("members", {})
    top = http_text(LIST_URL)

    groups, seen = [], set()
    for gp, label in GROUP_RE.findall(top):
        gp = html.unescape(gp)
        if gp in seen:
            continue
        seen.add(gp)
        groups.append({"id": gp, "label": clean(label) or gp, "members": []})

    slugs = page_slugs(top)
    for g in groups:
        try:
            g["members"] = page_slugs(http_text(GROUP_URL.format(urllib.parse.quote(g["id"], safe=""))))
        except Exception as e:  # 그룹 하나 실패해도 나머지는 계속
            log(f"그룹 {g['id']} 가져오기 실패: {e}")
        for s in g["members"]:
            if s not in slugs:
                slugs.append(s)
        time.sleep(delay)

    members, failed = {}, []
    for slug in slugs:
        try:
            members[slug] = parse_talent(slug, http_text(TALENT_URL.format(slug)))
        except Exception as e:
            failed.append(slug)
            log(f"{slug} 가져오기 실패: {e}")
            if slug in old_members:
                members[slug] = old_members[slug]
        time.sleep(delay)

    if len(members) < MIN_MEMBERS:
        raise RuntimeError(f"멤버가 {len(members)}명밖에 안 받아짐 — 사이트 구조 변경 의심")
    fill_channel_ids(members, old_members, delay)

    for g in groups:
        g["members"] = [s for s in g["members"] if s in members]
    groups = [g for g in groups if g["members"]]
    for slug, t in members.items():
        t["groups"] = [g["id"] for g in groups if slug in g["members"]]
        if ALUM_GROUP in t["groups"] and not t.get("status"):
            t["status"] = "Alum"
    if failed:
        log(f"실패 {len(failed)}명: {', '.join(failed)}")
    return {"updated": time.time(), "groups": groups, "members": members}


def load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("members") and data.get("groups"):
            return data
    except FileNotFoundError:
        pass
    except Exception as e:
        log(f"캐시 읽기 실패: {e}")
    return None


def save_cache(data):
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CACHE_PATH)


class Store:
    """멤버 데이터 보관 + 백그라운드 갱신."""

    def __init__(self):
        self.data = load_cache()
        self.lock = threading.Lock()
        self.last_manual = 0.0

    def refresh(self):
        if not self.lock.acquire(blocking=False):
            return False
        try:
            log("공식 사이트에서 멤버 정보 갱신 시작")
            data = scrape(self.data)
            save_cache(data)
            self.data = data
            log(f"갱신 완료: 멤버 {len(data['members'])}명, 그룹 {len(data['groups'])}개")
            return True
        except Exception as e:
            log(f"갱신 실패 (기존 데이터 유지): {e}")
            return False
        finally:
            self.lock.release()

    def stale(self):
        return not self.data or time.time() - self.data.get("updated", 0) > REFRESH_INTERVAL

    def refresh_async(self):
        threading.Thread(target=self.refresh, daemon=True).start()

    def auto_refresh_loop(self):
        while True:
            time.sleep(600)
            if self.stale():
                self.refresh()




def norm(s):
    return re.sub(r"[\s\-_・·'’.,!★☆]", "", s.lower())


def search(data, query):
    q = norm(query)
    if not q:
        return []
    exact, partial = [], []
    for t in data["members"].values():
        keys = [norm(t["name"]), norm(t["name_jp"]), norm(t["slug"])]
        if q in keys:
            exact.append(t)
        elif any(q in k for k in keys):
            partial.append(t)
    return exact or partial


# ---------------------------------------------------------------- YouTube 최근 영상

_video_cache = {}


def latest_videos(channel_id):
    hit = _video_cache.get(channel_id)
    if hit and time.time() - hit[0] < VIDEO_CACHE_TTL:
        return hit[1]
    root = ET.fromstring(http_get(YT_FEED_URL.format(channel_id)))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    videos = []
    for entry in root.findall("a:entry", ns)[:VIDEO_COUNT]:
        link = entry.find("a:link", ns)
        videos.append({
            "title": entry.findtext("a:title", "", ns),
            "url": link.get("href") if link is not None else "",
            "date": entry.findtext("a:published", "", ns)[:10],
        })
    _video_cache[channel_id] = (time.time(), videos)
    return videos


# ---------------------------------------------------------------- 방송 상태 (Holodex, 안 되면 유튜브 직접)

YT_CANONICAL_WATCH_RE = re.compile(r'<link rel="canonical" href="https://www\.youtube\.com/watch\?v=([\w-]{11})"')
YT_TITLE_RE = re.compile(r'"title":"((?:[^"\\]|\\.)*)"')


def parse_time(s):
    """ISO 시각 문자열 → epoch 초. 없거나 형식이 틀리면 None."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def fmt_time(ts):
    return time.strftime("%m/%d %H:%M", time.localtime(ts)) if ts else "시간 미정"


def load_holodex_key():
    key = os.environ.get("HOLODEX_KEY", "").strip()
    if not key and os.path.exists(HOLODEX_KEY_PATH):
        with open(HOLODEX_KEY_PATH, encoding="utf-8") as f:
            key = f.read().strip()
    return key if re.fullmatch(r"[0-9A-Za-z-]{20,64}", key) else ""


def tracked_channels(data):
    """방송을 감시할 채널 ID → 그 채널을 쓰는 멤버 slug 목록 (현역·어필리에이트만).
    FUWAMOCO 처럼 여러 멤버가 같이 쓰는 채널은 그 멤버 모두의 방송으로 본다."""
    owners = {}
    for t in data["members"].values():
        if t.get("channel_id") and t.get("status", "").lower() in LIVE_TRACK_STATUS:
            owners.setdefault(t["channel_id"], []).append(t["slug"])
    return owners


def holodex_videos(key, channel_ids):
    """Holodex /users/live — 채널들의 방송 중·예정 영상."""
    ids = sorted(channel_ids)
    videos = []
    for i in range(0, len(ids), 40):
        raw = json.loads(http_text(HOLODEX_USERS_LIVE_URL.format(",".join(ids[i:i + 40])),
                                   headers={"X-APIKEY": key, "User-Agent": UA, "Accept": "application/json"}))
        if not isinstance(raw, list):
            raise ValueError("Holodex 응답 형식이 예상과 달라요")
        videos.extend(raw)
    return videos


def video_info(v, owners):
    """Holodex 영상 → 봇에서 쓰는 형태. 우리 멤버의 유튜브 방송이 아니면 None."""
    if not isinstance(v, dict):
        return None
    ch = v.get("channel") if isinstance(v.get("channel"), dict) else {}
    slugs = owners.get(ch.get("id") or v.get("channel_id"))
    vid = v.get("id") or ""
    status = v.get("status")
    if not slugs or not re.fullmatch(r"[\w-]{11}", vid) or v.get("type", "stream") != "stream" \
            or status not in ("live", "upcoming"):
        return None
    start = parse_time(v.get("start_actual") if status == "live" else v.get("start_scheduled"))
    viewers = v.get("live_viewers")
    return {
        "id": vid,
        "slugs": list(slugs),
        "title": v.get("title") or "",
        "status": status,
        "start": start or parse_time(v.get("available_at")),
        "viewers": viewers if isinstance(viewers, int) and viewers > 0 else None,
        "topic": v.get("topic_id") or "",
        "url": YT_WATCH_URL.format(vid),
    }


def youtube_live_video(channel_id):
    """유튜브 채널의 /live 페이지로 지금 방송 중인지 확인 (Holodex 가 안 될 때만 씀).
    /live 가 가리키는 영상의 videoDetails 에 "isLive":true 가 있고 이 채널 영상이면 방송 중."""
    page = http_text(YT_CHANNEL_LIVE_URL.format(channel_id), headers=YT_HEADERS)
    m = YT_CANONICAL_WATCH_RE.search(page)
    if not m:
        return None  # 방송이 없으면 /live 가 채널 홈으로 감
    vid = m.group(1)
    i = page.find('"videoDetails":{"videoId":"%s"' % vid)
    if i < 0:
        return None
    j = page.find('"shortDescription"', i)
    block = page[i:j if 0 < j - i < 20000 else i + 5000]
    if '"isLive":true' not in block or '"channelId":"%s"' % channel_id not in block:
        return None
    title = ""
    if (t := YT_TITLE_RE.search(block)):
        try:
            title = json.loads('"%s"' % t.group(1))
        except ValueError:
            title = t.group(1)
    return {"id": vid, "slugs": [], "title": title, "status": "live", "start": None,
            "viewers": None, "topic": "", "url": YT_WATCH_URL.format(vid)}


class LiveTracker:
    """방송 상태 보관. poll() 은 새로 시작해서 알려야 할 방송 목록을 돌려준다."""

    def __init__(self, store, key, state_path=LIVE_STATE_PATH):
        self.store = store
        self.key = key
        self.state_path = state_path
        self.live = {}        # slug -> 방송 중 영상 (같이 쓰는 채널이면 여러 slug 가 같은 영상)
        self.upcoming = []    # 예정 영상 (시간순)
        self.updated = 0.0
        self.source = ""      # "holodex" | "youtube" | ""
        self.error = ""
        self.has_state = os.path.exists(state_path)
        self.alerted = {}     # 알린 영상 id -> 시각 (재시작해도 같은 방송을 두 번 알리지 않게)
        if self.has_state:
            try:
                with open(state_path, encoding="utf-8") as f:
                    self.alerted = {k: float(v) for k, v in json.load(f).items()}
            except Exception as e:
                log(f"방송 알림 기록 읽기 실패: {e}")

    def _save(self):
        cutoff = time.time() - 3 * 24 * 3600
        self.alerted = {k: v for k, v in self.alerted.items() if v > cutoff}
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.alerted, f)
        os.replace(tmp, self.state_path)
        self.has_state = True

    def _fetch(self, owners, watch_slugs):
        if self.key:
            try:
                videos = [v for v in (video_info(r, owners) for r in holodex_videos(self.key, owners)) if v]
                if self.source != "holodex":
                    log("방송 정보: Holodex 연결됨")
                self.source, self.error = "holodex", ""
                return videos
            except Exception as e:
                if not self.error:  # 실패가 시작될 때 한 번만 기록
                    log(f"Holodex 실패 — 알림 켠 멤버만 유튜브로 직접 확인: {e}")
                self.error = f"Holodex: {e}"
        # Holodex 가 없거나 안 되면: 알림 켠 멤버의 채널만 유튜브 /live 페이지로 확인
        watched = [(cid, slugs) for cid, slugs in sorted(owners.items()) if set(slugs) & watch_slugs]
        videos = []
        for cid, slugs in watched[:FALLBACK_MAX_CHANNELS]:
            try:
                v = youtube_live_video(cid)
            except Exception:
                continue
            if v:
                v["slugs"] = list(slugs)
                videos.append(v)
            time.sleep(0.5)
        self.source = "youtube"
        return videos

    def poll(self, watch_slugs=()):
        owners = tracked_channels(self.store.data)
        videos = self._fetch(owners, set(watch_slugs))
        now = time.time()
        live = {}
        for v in videos:
            if v["status"] != "live":
                continue
            for slug in v["slugs"]:
                cur = live.get(slug)  # 한 멤버가 동시에 두 방송이면 먼저 시작한 것
                if not cur or (v["start"] or now) < (cur["start"] or now):
                    live[slug] = v
        upcoming = sorted((v for v in videos if v["status"] == "upcoming" and v["start"]
                           and -1800 < v["start"] - now < UPCOMING_HOURS * 3600), key=lambda v: v["start"])
        first_run = not self.has_state  # 처음 설치한 뒤 첫 확인: 이미 하고 있던 방송은 알리지 않음
        new = []
        for v in {v["id"]: v for v in live.values()}.values():
            if v["id"] in self.alerted:
                continue
            self.alerted[v["id"]] = now
            late = v["start"] is not None and now - v["start"] > LATE_ALERT_SEC
            if not first_run and not late:
                new.append(v)
        self.live, self.upcoming, self.updated = live, upcoming, now
        if new or first_run or live:
            self._save()
        return new

    def live_videos(self):
        """지금 방송 중인 영상 (같은 영상은 한 번만, 시작 순)."""
        return sorted({v["id"]: v for v in self.live.values()}.values(), key=lambda v: v["start"] or 0)

    def upcoming_of(self, slug):
        return next((v for v in self.upcoming if slug in v["slugs"]), None)


# ---------------------------------------------------------------- 알림 설정 / X 알림

class Subs:
    """채팅별로 알림 받을 멤버 목록 (subs.json)."""

    def __init__(self, path=SUBS_PATH):
        self.path = path
        self.lock = threading.Lock()
        self.data = {}
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            self.data = {str(k): list(dict.fromkeys(v)) for k, v in raw.items() if isinstance(v, list) and v}
        except FileNotFoundError:
            pass
        except Exception as e:
            log(f"알림 설정 읽기 실패: {e}")

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def get(self, chat_id):
        return list(self.data.get(str(chat_id), []))

    def is_on(self, chat_id, slug):
        return slug in self.data.get(str(chat_id), [])

    def set_many(self, chat_id, slugs, on):
        with self.lock:
            cur = self.data.get(str(chat_id), [])
            if on:
                cur = cur + [s for s in slugs if s not in cur]
            else:
                drop = set(slugs)
                cur = [s for s in cur if s not in drop]
            if cur:
                self.data[str(chat_id)] = cur
            else:
                self.data.pop(str(chat_id), None)
            self._save()

    def toggle(self, chat_id, slug):
        on = not self.is_on(chat_id, slug)
        self.set_many(chat_id, [slug], on)
        return on

    def clear(self, chat_id):
        with self.lock:
            if self.data.pop(str(chat_id), None) is not None:
                self._save()

    def chats_for(self, slug):
        return [int(c) for c, v in list(self.data.items()) if slug in v]

    def all_slugs(self):
        return {s for v in list(self.data.values()) for s in v}


def x_handle(t):
    return t["x"].rstrip("/").rsplit("/", 1)[-1] if t.get("x") else ""


def match_x_member(data, title, content):
    """X 앱 알림이 어느 멤버 것인지. 제목(보낸 계정 이름)을 먼저 보고, 없으면 본문까지. 가장 긴 이름이 이김."""
    for text in (title, f"{title} {content}"):
        nt = norm(text)
        best = None
        for t in data["members"].values():
            keys = [norm(x_handle(t))] + [norm(n) for n in (t.get("name_jp"), t.get("name")) if n]
            for k in keys:
                if len(k) >= 3 and k in nt and (best is None or len(k) > best[0]):
                    best = (len(k), t)
        if best:
            return best[1]
    return None


class XWatcher:
    """폰의 X 앱 알림 중 홀로라이브 멤버 것을 골라낸다 (termux-notification-list 필요)."""

    def __init__(self):
        self.seen = {}      # 알림 키 → None (넣은 순서 유지)
        self.first = True   # 처음 읽을 때 이미 떠 있던 알림은 보내지 않음
        self.warned = False

    @staticmethod
    def list_notifications():
        try:
            out = subprocess.run(["termux-notification-list"], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if out.returncode != 0:
            return None
        try:
            items = json.loads(out.stdout)
        except ValueError:
            return None
        return items if isinstance(items, list) else None

    def poll(self, data):
        items = self.list_notifications()
        if items is None:
            if not self.warned:
                log("폰 알림을 읽을 수 없어요 (Termux:API 앱·알림 접근 권한 확인) — X 알림 쉬는 중")
                self.warned = True
            return []
        self.warned = False
        found = []
        for n in items:
            if not isinstance(n, dict) or n.get("packageName") != X_PACKAGE:
                continue
            title, content = n.get("title") or "", n.get("content") or ""
            if not content:
                continue
            key = f"{n.get('when')}|{title}|{content}"
            if key in self.seen:
                continue
            self.seen[key] = None
            if self.first:
                continue
            t = match_x_member(data, title, content)
            if t:
                found.append((t, content))
        self.first = False
        if len(self.seen) > 3000:
            for k in list(self.seen)[:2000]:
                del self.seen[k]
        return found


# ---------------------------------------------------------------- Telegram API

class TelegramError(Exception):
    pass


class Telegram:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}/"

    def call(self, method, params=None, http_timeout=30):
        req = urllib.request.Request(
            self.base + method,
            data=json.dumps(params or {}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
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


# ---------------------------------------------------------------- 화면 (메시지 + 버튼)

def esc(s):
    return html.escape(s, quote=False)


def button(text, data):
    return {"text": text, "callback_data": data[:64]}


def url_button(text, url):
    return {"text": text, "url": url}


def rows_of(buttons, n):
    return [buttons[i:i + n] for i in range(0, len(buttons), n)]


def no_preview():
    return {"is_disabled": True}


class Ctx:
    """화면을 그릴 때 필요한 것들: 멤버 데이터, 방송 상태, 이 채팅의 알림 설정."""

    def __init__(self, data, chat_id=None, live=None, subs=None):
        self.data = data
        self.chat_id = chat_id
        self.live = live
        self.subs = subs

    def live_of(self, slug):
        return self.live.live.get(slug) if self.live else None

    def subscribed(self, slug):
        return bool(self.subs and self.chat_id is not None and self.subs.is_on(self.chat_id, slug))

    def my_subs(self):
        return self.subs.get(self.chat_id) if self.subs and self.chat_id is not None else []


def status_of(t):
    """(아이콘, 한국어 이름) 또는 None."""
    s = t.get("status", "")
    if not s:
        return None
    return STATUS.get(s.lower(), ("📌", s))


def group_label(g):
    return GROUP_LABELS.get(g["id"], g["label"])


def member_label(t, gp=None):
    st = status_of(t)
    if not st or (gp == ALUM_GROUP and t["status"].lower() == "alum"):
        return t["name"]
    return f"{st[0]} {t['name']}"


def member_button_label(ctx, t, gp=None):
    label = member_label(t, gp)
    if ctx.live_of(t["slug"]):
        label = "🔴 " + label
    if ctx.subscribed(t["slug"]):
        label += " 🔔"
    return label


def link_icon(link):
    if "youtube.com/" in link["url"]:
        return "▶️ "
    return "𝕏 " if link["label"] == "X" else "🔗 "


def cb_member(slug, gp):
    data = f"m:{slug}:{gp}" if gp else f"m:{slug}"
    return data if len(data) <= 64 else f"m:{slug}"


def with_gp(prefix, slug, gp):
    data = f"{prefix}:{slug}:{gp}" if gp else f"{prefix}:{slug}"
    return data if len(data) <= 64 else f"{prefix}:{slug}"


def menu_view(ctx):
    data = ctx.data
    updated = time.strftime("%Y-%m-%d %H:%M", time.localtime(data.get("updated", 0)))
    text = (
        "🌟 <b>holo_bot</b> — 홀로라이브 멤버 정보 · 방송 · X\n\n"
        f"그룹을 고르세요. (멤버 {len(data['members'])}명 · {updated} 기준)\n"
        "이름을 바로 보내면 검색돼요. 예: <code>pekora</code>"
    )
    n_live = len(ctx.live.live) if ctx.live else 0  # 방송 중인 멤버 수
    rows = [[button(f"🔴 방송 중 ({n_live})", "lv"), button("📅 예정 방송", "up")],
            [button(f"🔔 내 알림 ({len(ctx.my_subs())})", "my")]]
    buttons = [button(f"{group_label(g)} ({len(g['members'])})", f"g:{g['id']}") for g in data["groups"]]
    return text, {"inline_keyboard": rows + rows_of(buttons, 2)}, no_preview()


def group_view(ctx, gp):
    data = ctx.data
    group = next((g for g in data["groups"] if g["id"] == gp), None)
    if not group:
        return menu_view(ctx)
    members = [data["members"][s] for s in group["members"] if s in data["members"]]
    text = f"👥 <b>{esc(group_label(group))}</b> — {len(members)}명\n멤버를 고르세요."
    legend = {status_of(t) for t in members if status_of(t) and member_label(t, gp) != t["name"]}
    if any(ctx.live_of(t["slug"]) for t in members):
        legend.add(("🔴", "방송 중"))
    if any(ctx.subscribed(t["slug"]) for t in members):
        legend.add(("🔔", "알림 켬"))
    if legend:
        text += "\n" + " · ".join(f"{icon} = {ko}" for icon, ko in sorted(legend, key=lambda x: x[1]))
    buttons = [button(member_button_label(ctx, t, gp), cb_member(t["slug"], gp)) for t in members]
    rows = rows_of(buttons, 2)
    rows.append([button("🔔 전체 알림 켜기", f"sg:{gp}:1"), button("🔕 전체 끄기", f"sg:{gp}:0")])
    rows.append([button("⬅️ 메뉴", "menu")])
    return text, {"inline_keyboard": rows}, no_preview()


def member_view(ctx, slug, gp=None):
    data = ctx.data
    t = data["members"].get(slug)
    if not t:
        return menu_view(ctx)
    head = f"<b>{esc(t['name'])}</b>"
    if t["name_jp"]:
        head += f" ({esc(t['name_jp'])})"
    if (st := status_of(t)):
        head += f"\n{st[0]} {esc(st[1])} ({esc(t['status'])})"
    live = ctx.live_of(slug)
    upcoming = ctx.live.upcoming_of(slug) if ctx.live and not live else None
    if live:
        head += f"\n🔴 <b>방송 중</b>: <a href=\"{html.escape(live['url'])}\">{esc(live['title'] or '제목 없음')}</a>"
    elif upcoming:
        head += (f"\n📅 예정 {fmt_time(upcoming['start'])}: "
                 f"<a href=\"{html.escape(upcoming['url'])}\">{esc(upcoming['title'] or '제목 없음')}</a>")
    parts = [head]
    if t["catch"]:
        parts.append(f"<i>{esc(t['catch'][:300])}</i>")
    profile = [f"{PROFILE_LABELS.get(key, '• ' + key)}: {esc(value[:300])}" for key, value in t["profile"]]
    if profile:
        parts.append("\n".join(profile))
    links = []
    if t["x"]:
        links.append(f"𝕏 X: @{esc(x_handle(t))}")
    if t["youtube"]:
        links.append(f"▶️ YouTube: {esc(t['youtube'])}")
    if links:
        parts.append("\n".join(links))
    if t["description"]:
        desc = t["description"]
        parts.append(esc(desc if len(desc) <= 600 else desc[:600].rstrip() + "…"))
    while len("\n\n".join(parts)) > 4000 and len(parts) > 1:
        parts.pop()
    text = "\n\n".join(parts)

    rows = [[url_button("🔴 방송 보러가기", live["url"])]] if live else []
    rows += rows_of([url_button(link_icon(l) + l["label"], l["url"]) for l in t["links"]], 2)
    sub = ctx.subscribed(slug)
    rows.append([button("🔕 알림 끄기" if sub else "🔔 알림 켜기", with_gp("s", slug, gp))])
    extra = []
    if t["channel_id"]:
        extra.append(button("📺 최근 영상", with_gp("v", slug, gp)))
    extra.append(url_button("🌐 공식 프로필", t["url"]))
    rows.append(extra)
    group = next((g for g in data["groups"] if g["id"] == gp), None) if gp else None
    rows.append([button(f"⬅️ {group_label(group)}", f"g:{gp}") if group else button("⬅️ 메뉴", "menu")])
    preview = ({"url": t["image"], "prefer_large_media": True, "show_above_text": True}
               if t["image"] else no_preview())
    return text, {"inline_keyboard": rows}, preview


def live_status_note(lt):
    if lt.source == "youtube":
        return "\n\n⚠️ Holodex 연결이 안 돼서 알림 켠 멤버만 유튜브로 직접 확인했어요."
    return ""


def names_of(data, slugs):
    return " · ".join(data["members"][s]["name"] for s in slugs if s in data["members"])


def live_view(ctx):
    data, lt = ctx.data, ctx.live
    back = [button("🔄 새로고침", "lv"), button("⬅️ 메뉴", "menu")]
    if not lt or not lt.updated:
        return ("🔴 방송 정보를 불러오는 중이에요. 잠시 뒤 새로고침을 눌러주세요.",
                {"inline_keyboard": [back]}, no_preview())
    items = lt.live_videos()
    text = f"🔴 <b>지금 방송 중</b> — {len(lt.live)}명 · {time.strftime('%H:%M', time.localtime(lt.updated))} 기준"
    if not items:
        text += "\n\n지금 방송 중인 멤버가 없어요."
    for v in items:
        line = f"\n\n<b>{esc(names_of(data, v['slugs']))}</b>"
        if v["viewers"]:
            line += f" · 👀 {v['viewers']:,}"
        line += f"\n<a href=\"{html.escape(v['url'])}\">{esc(v['title'] or '제목 없음')}</a>"
        if len(text) + len(line) > 3800:
            text += "\n\n…"
            break
        text += line
    text += live_status_note(lt)
    buttons = [button(f"🔴 {data['members'][s]['name']}", cb_member(s, None))
               for v in items for s in v["slugs"] if s in data["members"]]
    return text, {"inline_keyboard": rows_of(buttons[:40], 2) + [back]}, no_preview()


def upcoming_view(ctx):
    data, lt = ctx.data, ctx.live
    back = [button("🔄 새로고침", "up"), button("⬅️ 메뉴", "menu")]
    if not lt or not lt.updated:
        return ("📅 방송 정보를 불러오는 중이에요. 잠시 뒤 새로고침을 눌러주세요.",
                {"inline_keyboard": [back]}, no_preview())
    text = f"📅 <b>예정 방송</b> — 앞으로 {UPCOMING_HOURS}시간"
    if lt.source != "holodex":
        text += "\n\n예정 방송은 Holodex 가 연결돼야 볼 수 있어요." + live_status_note(lt)
        return text, {"inline_keyboard": [back]}, no_preview()
    if not lt.upcoming:
        text += "\n\n예정된 방송이 없어요."
    for v in lt.upcoming:
        names = names_of(data, v["slugs"])
        if not names:
            continue
        line = (f"\n• {fmt_time(v['start'])} <b>{esc(names)}</b>\n"
                f"  <a href=\"{html.escape(v['url'])}\">{esc(v['title'] or '제목 없음')}</a>")
        if len(text) + len(line) > 3800:
            text += "\n…"
            break
        text += line
    return text, {"inline_keyboard": [back]}, no_preview()


def subs_view(ctx):
    data = ctx.data
    mine = [data["members"][s] for s in ctx.my_subs() if s in data["members"]]
    text = f"🔔 <b>내 알림</b> — {len(mine)}명\n"
    if mine:
        text += "아래 멤버가 방송을 켜거나 X 에 글을 올리면 알려드려요."
    else:
        text += "아직 알림 켠 멤버가 없어요.\n멤버 카드의 <b>🔔 알림 켜기</b>, 또는 그룹 화면의 <b>🔔 전체 알림 켜기</b> 로 켤 수 있어요."
    text += "\n\n(X 알림은 봇이 돌아가는 폰의 X 앱에서 그 멤버 알림 🔔 이 켜져 있어야 와요)"
    buttons = [button(member_button_label(ctx, t), cb_member(t["slug"], None)) for t in mine[:60]]
    rows = rows_of(buttons, 2)
    if mine:
        rows.append([button("🔕 알림 전부 끄기", "sc")])
    rows.append([button("⬅️ 메뉴", "menu")])
    return text, {"inline_keyboard": rows}, no_preview()


def videos_view(ctx, slug, gp=None):
    t = ctx.data["members"].get(slug)
    if not t or not t["channel_id"]:
        return member_view(ctx, slug, gp)
    back = [button("⬅️ 프로필", cb_member(slug, gp)), url_button("▶️ 채널 열기", t["youtube"])]
    try:
        videos = latest_videos(t["channel_id"])
    except Exception as e:
        log(f"YouTube 피드 실패 ({slug}): {e}")
        text = f"📺 <b>{esc(t['name'])}</b>\n\n최근 영상을 불러오지 못했어요. 잠시 뒤 다시 시도하거나 채널을 직접 열어보세요."
        return text, {"inline_keyboard": [back]}, no_preview()
    if not videos:
        text = f"📺 <b>{esc(t['name'])}</b>\n\n공개된 영상이 없어요."
        return text, {"inline_keyboard": [back]}, no_preview()
    lines = [f"📺 <b>{esc(t['name'])}</b> 최근 영상\n"]
    for i, v in enumerate(videos, 1):
        lines.append(f"{i}. <a href=\"{html.escape(v['url'])}\">{esc(v['title'])}</a> ({v['date']})")
    preview = {"url": videos[0]["url"], "prefer_large_media": True, "show_above_text": True}
    return "\n".join(lines), {"inline_keyboard": [back]}, preview


def results_view(ctx, query, results):
    if not results:
        text = (f"🔍 <b>{esc(query)}</b> — 찾는 멤버가 없어요.\n"
                "영어/일본어 이름으로 검색해 보세요. 예: <code>marine</code>, <code>マリン</code>")
        return text, {"inline_keyboard": [[button("📋 메뉴", "menu")]]}, no_preview()
    if len(results) == 1:
        return member_view(ctx, results[0]["slug"])
    text = f"🔍 <b>{esc(query)}</b> 검색 결과 {len(results)}명"
    buttons = [button(member_button_label(ctx, t), cb_member(t["slug"], None)) for t in results[:40]]
    return text, {"inline_keyboard": rows_of(buttons, 2) + [[button("📋 메뉴", "menu")]]}, no_preview()


def links_text(query, results, kind):
    if not results:
        return f"🔍 <b>{esc(query)}</b> — 찾는 멤버가 없어요."
    lines = []
    for t in results[:10]:
        url = t["x"] if kind == "x" else t["youtube"]
        name = esc(member_label(t))
        lines.append(f"{name}: {esc(url)}" if url else f"{name}: (링크 없음)")
    return "\n".join(lines)


def live_alert_view(data, v):
    slugs = [s for s in v["slugs"] if s in data["members"]]
    t = data["members"][slugs[0]]
    if len(slugs) == 1:
        text = f"🔴 <b>LIVE</b> · <b>{esc(t['name'])}</b>" + (f" ({esc(t['name_jp'])})" if t["name_jp"] else "")
    else:
        text = f"🔴 <b>LIVE</b> · <b>{esc(names_of(data, slugs))}</b>"
    text += f"\n<blockquote>{esc(v['title'] or '제목 없음')}</blockquote>"
    if v.get("topic"):
        text += f"\n🎮 {esc(v['topic'])}"
    kb = [[url_button("▶ 방송 보러가기", v["url"])], [button("👤 프로필", cb_member(t["slug"], None))]]
    return text, {"inline_keyboard": kb}, {"url": v["url"], "prefer_large_media": True, "show_above_text": True}


def x_alert_view(t, content):
    handle = x_handle(t)
    text = f"𝕏 <b>{esc(t['name'])}</b>" + (f" <i>@{esc(handle)}</i>" if handle else "")
    text += f"\n<blockquote>{esc(content[:1500])}</blockquote>"
    kb = [[url_button("𝕏 게시물 보러가기", t["x"] or "https://x.com/notifications")]]
    return text, {"inline_keyboard": kb}, no_preview()


# ---------------------------------------------------------------- 봇

class Bot:
    def __init__(self, tg, store, live=None, subs=None, xwatch=None):
        self.tg = tg
        self.store = store
        self.live = live
        self.subs = subs if subs is not None else Subs()
        self.xwatch = xwatch

    def ctx(self, chat_id=None):
        return Ctx(self.store.data, chat_id, self.live, self.subs)

    def send(self, chat_id, view):
        text, markup, preview = view
        self.tg.call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                     "reply_markup": markup, "link_preview_options": preview})

    def edit(self, chat_id, message_id, view):
        text, markup, preview = view
        try:
            self.tg.call("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text,
                                             "parse_mode": "HTML", "reply_markup": markup,
                                             "link_preview_options": preview})
        except TelegramError as e:
            if "message is not modified" in str(e):
                return
            self.send(chat_id, view)  # 오래된 메시지 등 수정 불가 → 새로 보냄

    def reply_text(self, chat_id, text):
        self.tg.call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                     "link_preview_options": no_preview()})

    def handle(self, update):
        if "callback_query" in update:
            self.on_callback(update["callback_query"])
        elif "message" in update:
            self.on_message(update["message"])

    def on_message(self, msg):
        text = (msg.get("text") or "").strip()
        chat = msg["chat"]
        if not text:
            return
        ctx = self.ctx(chat["id"])
        data = ctx.data
        if text.startswith("/"):
            cmd, _, arg = text.partition(" ")
            cmd = cmd[1:].split("@", 1)[0].lower()
            arg = arg.strip()
            if cmd in ("start", "menu"):
                self.send(chat["id"], menu_view(ctx))
            elif cmd == "live":
                self.send(chat["id"], live_view(ctx))
            elif cmd == "schedule":
                self.send(chat["id"], upcoming_view(ctx))
            elif cmd == "alerts":
                self.send(chat["id"], subs_view(ctx))
            elif cmd == "help":
                self.reply_text(chat["id"], HELP_TEXT)
            elif cmd == "search":
                if not arg:
                    self.reply_text(chat["id"], "검색할 이름을 같이 보내주세요. 예: <code>/search pekora</code>")
                else:
                    self.send(chat["id"], results_view(ctx, arg, search(data, arg)))
            elif cmd in ("x", "yt"):
                if not arg:
                    self.reply_text(chat["id"], f"이름을 같이 보내주세요. 예: <code>/{cmd} marine</code>")
                else:
                    self.reply_text(chat["id"], links_text(arg, search(data, arg), cmd))
            elif cmd == "refresh":
                self.on_refresh(chat["id"])
            elif chat.get("type") == "private":
                self.reply_text(chat["id"], "모르는 명령어예요. /help 를 확인해 주세요.")
        elif chat.get("type") == "private":
            self.send(chat["id"], results_view(ctx, text, search(data, text)))

    def on_refresh(self, chat_id):
        now = time.time()
        if self.store.lock.locked():
            self.reply_text(chat_id, "이미 새로고침 중이에요. 1~2분 뒤 확인해 주세요.")
            return
        wait = int(MANUAL_REFRESH_COOLDOWN - (now - self.store.last_manual))
        if wait > 0:
            self.reply_text(chat_id, f"방금 새로고침했어요. {wait // 60 + 1}분 뒤 다시 시도해 주세요.")
            return
        self.store.last_manual = now
        self.store.refresh_async()
        self.reply_text(chat_id, "🔄 공식 사이트에서 멤버 정보를 새로 가져오는 중이에요. (1~2분 소요)")

    def on_callback(self, cq):
        msg = cq.get("message")
        if not msg or "chat" not in msg:
            self.answer(cq)
            return
        chat_id = msg["chat"]["id"]
        ctx = self.ctx(chat_id)
        data = ctx.data
        kind, _, rest = (cq.get("data") or "").partition(":")
        slug, _, gp = rest.partition(":")
        toast = ""
        if kind == "g":
            view = group_view(ctx, rest)
        elif kind == "m":
            view = member_view(ctx, slug, gp or None)
        elif kind == "v":
            view = videos_view(ctx, slug, gp or None)
        elif kind == "s" and slug in data["members"]:
            on = self.subs.toggle(chat_id, slug)
            toast = f"🔔 {data['members'][slug]['name']} 알림을 켰어요" if on else "🔕 알림을 껐어요"
            view = member_view(ctx, slug, gp or None)
        elif kind == "sg":
            group = next((g for g in data["groups"] if g["id"] == slug), None)
            if group:
                on = gp == "1"
                self.subs.set_many(chat_id, group["members"], on)
                toast = f"🔔 {group_label(group)} 전체 알림을 켰어요" if on else "🔕 전체 알림을 껐어요"
            view = group_view(ctx, slug)
        elif kind == "sc":
            self.subs.clear(chat_id)
            toast = "🔕 알림을 전부 껐어요"
            view = subs_view(ctx)
        elif kind == "lv":
            view = live_view(ctx)
        elif kind == "up":
            view = upcoming_view(ctx)
        elif kind == "my":
            view = subs_view(ctx)
        else:
            view = menu_view(ctx)
        self.answer(cq, toast)
        self.edit(chat_id, msg["message_id"], view)

    def answer(self, cq, text=""):
        try:
            self.tg.call("answerCallbackQuery", {"callback_query_id": cq["id"], **({"text": text} if text else {})})
        except TelegramError:
            pass

    # ---- 알림 보내기 (백그라운드)

    def broadcast(self, slugs, view):
        chats = sorted({c for s in slugs for c in self.subs.chats_for(s)})
        for chat_id in chats:
            try:
                self.send(chat_id, view)
            except TelegramError as e:
                if any(s in str(e).lower() for s in ("blocked", "chat not found", "deactivated", "kicked")):
                    log(f"채팅 {chat_id} 에 보낼 수 없어 알림 설정을 지워요: {e}")
                    self.subs.clear(chat_id)
                else:
                    log(f"알림 전송 실패 ({chat_id}): {e}")
            except Exception as e:
                log(f"알림 전송 실패 ({chat_id}): {e}")
            time.sleep(0.05)

    def alert_step(self, now, last_live):
        """한 번 돌기. 방송 확인 시각을 돌려준다."""
        if self.live and now - last_live >= LIVE_POLL_SEC:
            last_live = now
            try:
                for v in self.live.poll(self.subs.all_slugs()):
                    if not any(s in self.store.data["members"] for s in v["slugs"]):
                        continue
                    log(f"방송 시작: {names_of(self.store.data, v['slugs'])} — {v['title']}")
                    self.broadcast(v["slugs"], live_alert_view(self.store.data, v))
            except Exception as e:
                log(f"방송 확인 오류: {type(e).__name__}: {e}")
        if self.xwatch and self.subs.all_slugs():
            try:
                for t, content in self.xwatch.poll(self.store.data):
                    if self.subs.chats_for(t["slug"]):
                        log(f"X 알림: {t['name']}")
                        self.broadcast([t["slug"]], x_alert_view(t, content))
            except Exception as e:
                log(f"X 알림 오류: {type(e).__name__}: {e}")
        return last_live

    def alert_loop(self):
        last_live = 0.0
        while True:
            last_live = self.alert_step(time.time(), last_live)
            time.sleep(NOTIF_POLL_SEC)

    def run(self):
        offset = None
        backoff = 1
        while True:
            try:
                params = {"timeout": 50, "allowed_updates": ["message", "callback_query"]}
                if offset is not None:
                    params["offset"] = offset
                updates = self.tg.call("getUpdates", params, http_timeout=60)
                backoff = 1
            except Exception as e:
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


def load_token():
    token = os.environ.get("HOLO_BOT_TOKEN", "").strip()
    if not token and os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, encoding="utf-8") as f:
            token = f.read().strip()
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{30,}", token):
        sys.exit(f"봇 토큰이 없거나 형식이 잘못됐어요. {TOKEN_PATH} 에 BotFather 토큰을 넣어주세요.")
    return token


def print_summary(data):
    print(f"멤버 {len(data['members'])}명 / 그룹 {len(data['groups'])}개")
    for g in data["groups"]:
        names = ", ".join(member_label(data["members"][s], g["id"]) for s in g["members"])
        print(f"- {g['label']} [{g['id']}]: {names}")
    missing = [t["name"] for t in data["members"].values()
               if not t["x"] or not t["youtube"]]
    print(f"X/YouTube 링크 없는 멤버: {', '.join(missing) or '없음'}")
    no_videos = [t["name"] for t in data["members"].values() if t["youtube"] and not t["channel_id"]]
    print(f"최근 영상 안 되는 멤버: {', '.join(no_videos) or '없음'}")
    owners = tracked_channels(data)
    print(f"방송 감시 채널: {len(owners)}개 (멤버 {sum(len(v) for v in owners.values())}명)")


def check(store):
    """설치 점검: Holodex · 유튜브 직접 확인 · 폰 알림 읽기."""
    data = store.data
    owners = tracked_channels(data)
    print(f"방송 감시 채널 {len(owners)}개 (멤버 {sum(len(v) for v in owners.values())}명)")
    live_cids = []
    key = load_holodex_key()
    if not key:
        print("❌ Holodex 키 없음 (holodex_key.txt)")
    else:
        try:
            videos = [v for v in (video_info(r, owners) for r in holodex_videos(key, owners)) if v]
            live = [v for v in videos if v["status"] == "live"]
            up = [v for v in videos if v["status"] == "upcoming"]
            print(f"✅ Holodex: 방송 중 {len(live)}개 {[names_of(data, v['slugs']) for v in live]}, 예정 {len(up)}개")
            live_cids = [c for c, sl in owners.items() if any(set(sl) & set(v["slugs"]) for v in live)]
        except Exception as e:
            print(f"❌ Holodex 실패: {e}")
    # 유튜브 직접 확인(Holodex 대체용): 방송 중인 채널로 시험해서 실제로 잡히는지 본다
    for cid in (live_cids[:2] + sorted(owners)[:1])[:3]:
        name = names_of(data, owners[cid])
        try:
            v = youtube_live_video(cid)
            print(f"{'✅' if (v is not None) == (cid in live_cids) else '❌'} 유튜브 직접 확인 {name}: "
                  + (f"방송 중 — {v['title']}" if v else "방송 안 함")
                  + (" (Holodex 는 방송 중)" if cid in live_cids else ""))
        except Exception as e:
            print(f"❌ 유튜브 직접 확인 {name}: {e}")
    items = XWatcher.list_notifications()
    if items is None:
        print("❌ 폰 알림 읽기 실패 (Termux:API 앱 + 알림 접근 권한 필요)")
    else:
        xs = [n for n in items if isinstance(n, dict) and n.get("packageName") == X_PACKAGE]
        matched = [match_x_member(data, n.get("title") or "", n.get("content") or "") for n in xs]
        print(f"✅ 폰 알림 {len(items)}개 중 X {len(xs)}개, 홀로 멤버 것 {sum(1 for m in matched if m)}개")


def main():
    if "--scrape" in sys.argv:
        data = scrape(load_cache())
        save_cache(data)
        print_summary(data)
        return
    if "--check" in sys.argv:
        store = Store()
        if not store.data:
            sys.exit("members.json 이 없어요. 먼저 --scrape 를 실행하세요.")
        check(store)
        return

    tg = Telegram(load_token())
    me = tg.call("getMe")
    log(f"@{me['username']} 로그인 완료")

    store = Store()
    if not store.data:
        log("캐시가 없어 처음으로 공식 사이트에서 멤버 정보를 받아요 (1~2분)")
        while not store.refresh():
            time.sleep(60)
    elif store.stale():
        store.refresh_async()
    threading.Thread(target=store.auto_refresh_loop, daemon=True).start()

    key = load_holodex_key()
    if not key:
        log(f"Holodex 키가 없어요 ({HOLODEX_KEY_PATH}) — 알림 켠 멤버만 유튜브로 직접 확인해요")
    bot = Bot(tg, store, live=LiveTracker(store, key), subs=Subs(), xwatch=XWatcher())
    threading.Thread(target=bot.alert_loop, daemon=True).start()

    try:
        tg.call("deleteWebhook")
        tg.call("setMyCommands", {"commands": [{"command": c, "description": d} for c, d in COMMANDS]})
        tg.call("setMyShortDescription", {"short_description": "홀로라이브 멤버 정보 · 방송 · X 알림 봇"})
    except TelegramError as e:
        log(f"초기 설정 경고: {e}")

    log("업데이트 대기 중")
    bot.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
