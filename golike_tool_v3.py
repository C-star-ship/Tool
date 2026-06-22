#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║      GOLIKE AUTO TOOL — ShopVietX v2.0              ║
║   Tự động làm nhiệm vụ kiếm tiền trên Golike        ║
╚══════════════════════════════════════════════════════╝
Cài đặt: pip install requests colorama --break-system-packages
Chạy:    python3 golike_tool.py
"""

import os, sys, json, time, random, hashlib, platform as _platform
import subprocess, base64
from datetime import datetime

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    R=Fore.RED; G=Fore.GREEN; Y=Fore.YELLOW
    B=Fore.CYAN; DIM=Style.DIM; BOLD=Style.BRIGHT; RESET=Style.RESET_ALL
except:
    R=G=Y=B=DIM=BOLD=RESET=""

import requests
import threading
try:
    from curl_cffi import requests as _cffi_requests
    _IG_SCRAPER = _cffi_requests.Session(impersonate="chrome124")
except ImportError:
    try:
        import cloudscraper as _cloudscraper
        _IG_SCRAPER = _cloudscraper.create_scraper(browser={"browser":"chrome","platform":"windows","mobile":False})
    except ImportError:
        _IG_SCRAPER = None
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════
# LICENSE KEY — Dán key của bạn vào đây
# ═══════════════════════════════════════════════════════════════
LICENSE_KEY = ""
# ═══════════════════════════════════════════════════════════════

# ── Cấu hình ──────────────────────────────────────────────────────────────────
GATEWAY    = "https://gateway.golike.net/api"
CFG_FILE   = os.path.join(os.path.expanduser("~"), ".golike_cfg.json")
KEY_FILE   = os.path.join(os.path.expanduser("~"), ".golike_key")
DEBUG_MODE   = [False]
SESSION_FILE = os.path.join(os.path.expanduser("~"), ".golike_session.json")
STATS_FILE    = os.path.join(os.path.expanduser("~"), ".golike_stats.json")
FAIL_LOG_FILE = os.path.join(os.path.expanduser("~"), ".golike_fail_log.json")

# ══════════════════════════════════════════════════════════════════════════════
# MODULE THỐNG KÊ JOB — theo dõi tỷ lệ thành công/thất bại theo loại job
# ══════════════════════════════════════════════════════════════════════════════

# Bộ đếm phiên hiện tại (reset khi khởi động lại)
JOB_STATS = {
    "success":           0,   # hoàn thành thành công
    "failed":            0,   # thất bại chung
    "uid_not_performed": 0,   # 400 "chưa thực hiện thao tác"
    "rate_limit":        0,   # 429 "báo cáo quá nhanh"
    "system_check":      0,   # 400 "hệ thống check lỗi"
    "by_type":           {},  # {job_type: {"success":0,"failed":0}}
}
_jstats_lock = threading.Lock()

def _jstats_add(result_type: str, job_type: str = ""):
    """Tăng bộ đếm thống kê thread-safe."""
    with _jstats_lock:
        JOB_STATS[result_type] = JOB_STATS.get(result_type, 0) + 1
        if job_type:
            if job_type not in JOB_STATS["by_type"]:
                JOB_STATS["by_type"][job_type] = {"success": 0, "failed": 0}
            key = "success" if result_type == "success" else "failed"
            JOB_STATS["by_type"][job_type][key] += 1

def _jstats_log_fail(job_id, job_type: str, platform: str, reason: str, msg: str):
    """Ghi lỗi vào file fail log riêng."""
    try:
        with _jstats_lock:
            data = []
            if os.path.exists(FAIL_LOG_FILE):
                try: data = json.load(open(FAIL_LOG_FILE, encoding="utf-8"))
                except: data = []
            data.append({
                "time":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "platform": platform,
                "job_id":   str(job_id),
                "type":     job_type,
                "reason":   reason,
                "message":  msg[:120],
            })
            if len(data) > 500: data = data[-500:]
            json.dump(data, open(FAIL_LOG_FILE, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
    except: pass

def print_jstats():
    """In bảng thống kê phiên hiện tại."""
    with _jstats_lock:
        s  = JOB_STATS["success"]
        f  = JOB_STATS["failed"]
        u  = JOB_STATS["uid_not_performed"]
        rl = JOB_STATS["rate_limit"]
        sc = JOB_STATS["system_check"]
        total = s + f
        rate  = (s / total * 100) if total > 0 else 0.0
        print(f"\n{B}{'━'*44}{RESET}")
        print(f"{B}📊 THỐNG KÊ PHIÊN{RESET}")
        print(f"  {G}Success:           {s}{RESET}")
        print(f"  {R}Failed:            {f}{RESET}")
        print(f"  {Y}UID not performed: {u}{RESET}")
        print(f"  {Y}429 rate limit:    {rl}{RESET}")
        print(f"  {Y}System check err:  {sc}{RESET}")
        print(f"  {G}Success rate:      {rate:.1f}%{RESET}")
        by_type = JOB_STATS.get("by_type", {})
        if by_type:
            print(f"\n  {B}Theo loại job:{RESET}")
            for jt, v in sorted(by_type.items(),
                                key=lambda x: -(x[1]["success"]+x[1]["failed"])):
                tot = v["success"] + v["failed"]
                r2  = (v["success"]/tot*100) if tot > 0 else 0.0
                print(f"    {jt:<32} ✅{v['success']}  ❌{v['failed']}  ({r2:.0f}%)")
        print(f"{B}{'━'*44}{RESET}\n")

# ── Stats toàn cục ────────────────────────────────────────────────────────────
_stats_lock = threading.Lock()

def load_stats() -> dict:
    try:
        if os.path.exists(STATS_FILE):
            return json.load(open(STATS_FILE, encoding="utf-8"))
    except: pass
    return {}

def save_stats(stats: dict):
    try:
        json.dump(stats, open(STATS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except: pass

def add_stat(acc: str, platform: str, earned: float, done: int):
    with _stats_lock:
        stats = load_stats()
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in stats: stats[today] = {}
        key = f"{acc}|{platform}"
        if key not in stats[today]: stats[today][key] = {"earned": 0, "done": 0}
        stats[today][key]["earned"] += earned
        stats[today][key]["done"]   += done
        save_stats(stats)

def show_stats():
    stats = load_stats()
    if not stats:
        print(f"  {Y}Chưa có dữ liệu thống kê{RESET}"); return
    for day in sorted(stats.keys(), reverse=True)[:7]:
        total_e = sum(v["earned"] for v in stats[day].values())
        total_d = sum(v["done"]   for v in stats[day].values())
        print(f"\n  {B}{day}{RESET} — {G}+{total_e:.0f}đ{RESET} | {total_d} job")
        for key, v in sorted(stats[day].items(), key=lambda x: -x[1]["earned"]):
            acc_p, plat = (key.split("|") + ["?"])[:2]
            print(f"    {plat:<12} {acc_p:<20} +{v['earned']:.0f}đ ({v['done']} job)")

# ── Session lưu config chạy ──────────────────────────────────────────────────
def load_session() -> dict:
    try:
        if os.path.exists(SESSION_FILE):
            s = json.load(open(SESSION_FILE, encoding="utf-8"))
            # Session chỉ valid trong 24h
            if time.time() - s.get("_saved_at", 0) < 86400:
                return s
    except: pass
    return {}

def save_session(data: dict):
    data["_saved_at"] = time.time()
    try:
        json.dump(data, open(SESSION_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except: pass

# ── Telegram notify ──────────────────────────────────────────────────────────
def tg_notify(bot_token: str, chat_id: str, msg: str):
    if not bot_token or not chat_id: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except: pass


# ── License system ─────────────────────────────────────────────────────────────
def _get_hwid() -> str:
    """Lấy Hardware ID của máy"""
    try:
        raw = ""
        if _platform.system() == "Android" or os.path.exists("/data/data/com.termux"):
            # Termux/Android: dùng kết hợp thông tin thiết bị
            try:
                r = subprocess.check_output(
                    ["getprop","ro.serialno"], stderr=subprocess.DEVNULL
                ).decode().strip()
                raw = r
            except: pass
            if not raw:
                try:
                    r = subprocess.check_output(
                        ["getprop","ro.boot.serialno"], stderr=subprocess.DEVNULL
                    ).decode().strip()
                    raw = r
                except: pass
        if not raw:
            import uuid
            raw = str(uuid.getnode())  # MAC address
        return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    except:
        return "UNKNOWN"

def _make_valid_key(key: str) -> str:
    """Chuẩn hóa key: uppercase, bỏ dấu gạch"""
    return key.strip().upper().replace("-","").replace(" ","")

def _verify_key(key: str) -> tuple:
    """
    Xác minh key offline.
    Format key: XXXX-XXXX-XXXX-XXXX-XXXX (25 ký tự + 4 gạch)
    Key được tạo từ: SHA256(SECRET + HWID + EXPIRE_DATE)[:20]
    Trả về: (valid: bool, message: str, days_left: int)
    """
    SECRET   = "ShopVietX_GolikeTool_2025"
    raw      = _make_valid_key(key)

    if len(raw) != 24:
        return False, "Key không đúng định dạng (cần 24 ký tự)", 0

    # Phần cuối 8 ký tự = ngày hết hạn encode
    payload  = raw[:16]
    expire_s = raw[16:]

    # Decode ngày hết hạn từ hex
    try:
        expire_ts = int(expire_s, 16)
    except:
        return False, "Key không hợp lệ", 0

    now_ts = int(time.time())
    if now_ts > expire_ts:
        import datetime as dt
        exp_date = dt.datetime.fromtimestamp(expire_ts).strftime("%d/%m/%Y")
        return False, f"Key đã hết hạn từ {exp_date}", 0

    # Xác minh payload = SHA256(SECRET + expire_s)[:16]
    expected = hashlib.sha256(f"{SECRET}{expire_s}".encode()).hexdigest()[:16].upper()
    if payload != expected:
        return False, "Key không hợp lệ hoặc đã bị chỉnh sửa", 0

    days_left = max(0, (expire_ts - now_ts) // 86400)
    return True, f"Key hợp lệ — còn {days_left} ngày", days_left

def _load_saved_key() -> str:
    """Đọc key đã lưu từ file"""
    try:
        if os.path.exists(KEY_FILE):
            return open(KEY_FILE).read().strip()
    except: pass
    return ""

def _save_key(key: str):
    """Lưu key vào file"""
    try:
        open(KEY_FILE, "w").write(key.strip())
    except: pass

def check_license() -> bool:
    """
    Kiểm tra license. Thứ tự ưu tiên:
    1. LICENSE_KEY hardcode ở đầu file
    2. Key đã lưu trong ~/.golike_key
    3. Yêu cầu nhập key
    """
    clear()
    print(f"""{G}{BOLD}
╔══════════════════════════════════════════════════════╗
║      💰 GOLIKE AUTO TOOL — ShopVietX v2.0           ║
╚══════════════════════════════════════════════════════╝{RESET}""")

    # Thử theo thứ tự ưu tiên
    candidates = []
    if LICENSE_KEY.strip():
        candidates.append(("hardcode", LICENSE_KEY.strip()))
    saved = _load_saved_key()
    if saved:
        candidates.append(("saved", saved))

    for source, key in candidates:
        valid, msg, days = _verify_key(key)
        if valid:
            if days <= 7:
                print(f"\n  {Y}⚠️  {msg}{RESET}")
            else:
                print(f"\n  {G}✅ {msg}{RESET}")
            if days <= 3 and days > 0:
                print(f"  {R}⚠️  Key sắp hết hạn! Liên hệ ShopVietX để gia hạn{RESET}")
            time.sleep(1)
            return True

    # Chưa có key hoặc key không hợp lệ — yêu cầu nhập
    hwid = _get_hwid()
    print(f"\n  {Y}🔑 XÁC THỰC BẢN QUYỀN{RESET}\n")
    print(f"  {DIM}HWID của máy bạn:{RESET} {B}{hwid}{RESET}")
    print(f"  {DIM}Gửi HWID này cho ShopVietX để nhận key kích hoạt{RESET}\n")
    print(f"  {B}Liên hệ: t.me/ShopVietX{RESET}\n")

    for attempt in range(3):
        key_input = input(f"  {G}Nhập key kích hoạt: {RESET}").strip()
        if not key_input:
            print(f"  {R}Vui lòng nhập key!{RESET}")
            continue

        valid, msg, days = _verify_key(key_input)
        if valid:
            _save_key(key_input)
            print(f"\n  {G}✅ {msg}{RESET}")
            time.sleep(1)
            return True
        else:
            print(f"  {R}❌ {msg}{RESET}")
            if attempt < 2:
                print(f"  {Y}Còn {2-attempt} lần thử{RESET}\n")

    print(f"\n  {R}Xác thực thất bại! Liên hệ ShopVietX để được hỗ trợ.{RESET}\n")
    return False

# ── Platform map ───────────────────────────────────────────────────────────────
PLATFORMS = {
    "facebook":  {"prefix": "fb",        "acct_ep": "fb-account",
                  "acct_id": "account_id",
                  "ads_id":  "ads_id",
                  "name_fields": ["fb_name","display_name","nickname","full_name","name"],
                  "need_cookie": False, "action": "server",
                  "job_endpoint":      "advertising/publishers/get-jobs-2026",
                  "complete_endpoint": "advertising/publishers/complete-jobs-2026"},
    "instagram": {"prefix": "instagram", "acct_ep": "instagram-account",
                  "acct_id": "instagram_account_id",
                  "private_param": "instagram_username", "private_name_field": "instagram_username",
                  "ads_id":  "instagram_users_advertising_id",
                  "name_fields": ["instagram_username","display_name","full_name","name","username"],
                  "need_cookie": True,  "action": "api"},
    "youtube":   {"prefix": "youtube",   "acct_ep": "youtube-account",
                  "acct_id": "account_id",
                  "ads_id":  "ads_id",
                  "name_fields": ["name","channel_name","display_name","full_name","username"],
                  "need_cookie": True,  "action": "api"},
    "twitter":   {"prefix": "twitter",   "acct_ep": "twitter-account",
                  "acct_id": "account_id",
                  "ads_id":  "ads_id",
                  "name_fields": ["screen_name","display_name","name","username"],
                  "need_cookie": False, "action": "server"},
    "threads":   {"prefix": "threads",   "acct_ep": "threads-account",
                  "acct_id": "account_id", "private_param": "threads_username",
                  "private_name_field": "threads_username",
                  "ads_id":  "ads_id",
                  "name_fields": ["threads_username","display_name","name","username"],
                  "need_cookie": False, "action": "server"},
    "linkedin":  {"prefix": "linkedin",  "acct_ep": "linkedin-account",
                  "acct_id": "account_id", "private_param": "linkedin_username",
                  "private_name_field": "name",
                  "ads_id":  "ads_id",
                  "name_fields": ["full_name","display_name","name","username"],
                  "need_cookie": False, "action": "server"},
    "pinterest": {"prefix": "pinterest", "acct_ep": "pinterest-account",
                  "acct_id": "account_id", "private_param": "pinterest_username", "private_name_field": "pinterest_username",
                  "ads_id":  "ads_id",
                  "name_fields": ["display_name","full_name","name","username"],
                  "need_cookie": False, "action": "server"},
    "snapchat":  {"prefix": "snapchat", "acct_ep": "snapchat-account",
                  "acct_id": "account_id", "private_param": "snap_username",
                  "private_name_field": "snap_username",
                  "ads_id": "ads_id",
                  "name_fields": ["snap_username","name","username"],
                  "need_cookie": False, "action": "server"},
    "tiktok":    {"prefix": "tiktok",   "acct_ep": "tiktok-account",
                  "acct_id": "account_id", "private_param": "unique_username",
                  "private_name_field": "unique_username",
                  "ads_id": "ads_id",
                  "name_fields": ["unique_username","nickname","name","username"],
                  "need_cookie": False, "action": "server"},
    "lazada":    {"prefix": "lazada",    "acct_ep": "lazada-account",
                  "acct_id": "account_id", "private_param": "account_id", "private_name_field": "",
                  "ads_id":  "ads_id",
                  "name_fields": ["seller_name","shop_name","display_name","name","username"],
                  "need_cookie": False, "action": "server"},
}
PLAT_LIST = list(PLATFORMS.keys())

# ── Helpers ────────────────────────────────────────────────────────────────────
def clear(): os.system("cls" if os.name=="nt" else "clear")

def banner():
    print(f"""{G}{BOLD}
╔══════════════════════════════════════════════════════╗
║      💰 GOLIKE AUTO TOOL — ShopVietX v3.0           ║
║      Tự động kiếm xu tối đa — Mọi nền tảng Golike   ║
╚══════════════════════════════════════════════════════╝{RESET}""")

def log(msg, level="ok"):
    t = datetime.now().strftime("%H:%M:%S")
    icons = {"ok":"✅","err":"❌","warn":"⚠️ ","wait":"⏳","info":"🔵","money":"💰","job":"📦"}
    icon  = icons.get(level,"•")
    color = {"ok":G,"err":R,"warn":Y,"wait":Y,"info":B,"money":G,"job":B}.get(level,RESET)
    print(f"[{t}] {icon}  {color}{msg}{RESET}")

def save_cfg(cfg):
    try: json.dump(cfg, open(CFG_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e: log(f"Lưu config lỗi: {e}", "warn")

def load_cfg():
    try:
        if os.path.exists(CFG_FILE):
            return json.load(open(CFG_FILE, encoding="utf-8"))
    except: pass
    return {"accounts": [], "mxh_cookies": {}}

def get_acc_name(acc: dict, platform: str) -> str:
    if DEBUG_MODE[0]:
        print(f"{Y}[DEBUG acc fields/{platform}]: {list(acc.keys())}{RESET}")
        for k, v in acc.items():
            if isinstance(v, str) and v and k not in (
                "description","profile_image_url","avatar","avatar_url",
                "latest_time_complete_jobs","created_at","updated_at",
                "invite_code","service_token","device_token","roll_call_code"
            ):
                print(f"  {k} = {v[:60]}")

    fields = PLATFORMS[platform]["name_fields"]
    golike_username = acc.get("username","")  # tên Golike account - bỏ qua

    for f in fields:
        if f == "username": continue  # bỏ qua username Golike ở vòng đầu
        v = acc.get(f)
        if v and str(v).strip() and str(v).strip() not in ("null","None",""):
            return str(v).strip()

    # Fallback: dùng username chỉ khi không có field nào khác
    if golike_username:
        return golike_username
    return str(acc.get("id","?"))

def parse_uid_from_cookie(cookie: str, platform: str) -> str:
    """Parse UID từ cookie string theo platform"""
    fields = {
        "facebook":  ["c_user", "i_user"],          # FB UID
        "instagram": ["ds_user_id", "sessionid"],   # IG user id
        "youtube":   ["SID", "HSID"],               # YT (không có UID rõ)
        "twitter":   ["twid"],                      # Twitter uid=xxx
        "threads":   ["ds_user_id"],
    }
    uid_fields = fields.get(platform, [])
    cookie_map = {}
    for part in cookie.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookie_map[k.strip()] = v.strip()

    for f in uid_fields:
        v = cookie_map.get(f, "")
        if v:
            # Twitter: twid = u%3D123456 → 123456
            if f == "twid" and "=" in v:
                v = v.split("=")[-1]
            return v.strip('"').strip()
    return ""


def gen_t() -> str:
    """Tạo t token động: base64(base64(base64(unix_timestamp)))"""
    ts = str(int(time.time()))
    d1 = base64.b64encode(ts.encode()).decode()
    d2 = base64.b64encode(d1.encode()).decode()
    d3 = base64.b64encode(d2.encode()).decode()
    return d3

class GolikeSession(requests.Session):
    """Session tự động cập nhật t token và g-auth trước mỗi request"""
    def __init__(self, auth: str, g_auth: str, device_id: str):
        super().__init__()
        self.g_auth    = g_auth
        self.device_id = device_id
        self.headers.update({
            "accept":             "application/json, text/plain, */*",
            "accept-language":    "vi-VN",
            "authorization":      auth,
            "content-type":       "application/json;charset=utf-8",
            "g-device-id":        device_id,
            "origin":             "https://app.golike.net",
            "priority":           "u=1, i",
            "referer":            "https://app.golike.net/",
            "sec-ch-ua":          '"Chromium";v="127", "Not)A;Brand";v="99", '
                                  '"Microsoft Edge Simulate";v="127", "Lemur";v="127"',
            "sec-ch-ua-mobile":   "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest":     "empty",
            "sec-fetch-mode":     "cors",
            "sec-fetch-site":     "same-site",
            "user-agent":         "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
        })

    def request(self, method, url, **kwargs):
        self.headers.update({
            "t":      gen_t(),
            "g-auth": self.g_auth,
        })
        resp = super().request(method, url, **kwargs)
        # Auto retry 1 lần nếu 403 — g-auth có thể cũ
        if resp.status_code == 403 and self._refresh_count < 1:
            self._refresh_count += 1
            time.sleep(2)
            self.headers.update({"t": gen_t()})
            resp = super().request(method, url, **kwargs)
        else:
            self._refresh_count = 0
        return resp

    _refresh_count = 0

def make_session(auth: str, g_auth: str = "", device_id: str = ""):
    import uuid as _uuid
    did = device_id or str(_uuid.uuid4())
    s   = GolikeSession(auth, g_auth, did)
    return s, did

# ── Golike API ─────────────────────────────────────────────────────────────────
class GolikeAPI:
    def __init__(self, auth: str, g_auth: str = "", device_id: str = ""):
        self.auth = auth
        self.s, self.device_id = make_session(auth, g_auth, device_id)
        self._job_blacklist: set = set()  # job_id đã lỗi nhiều lần

    def blacklist_job(self, job_id):
        self._job_blacklist.add(str(job_id))

    def is_blacklisted(self, job_id) -> bool:
        return str(job_id) in self._job_blacklist

    def _is_cloudflare(self, r) -> bool:
        return r.status_code in (403,503) and "just a moment" in r.text.lower()

    def get_user(self) -> dict:
        try:
            r = self.s.get(f"{GATEWAY}/users/me", timeout=10)

            if DEBUG_MODE[0]:
                print(f"\n{Y}[DEBUG get_user] status={r.status_code}{RESET}")
                try: print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:1000])
                except: print(r.text[:300])

            if self._is_cloudflare(r):
                log("Cloudflare block! Token hết hạn — vào Setup [U] cập nhật lại", "err")
                return {}

            if r.status_code == 401:
                log("Token hết hạn (401) — vào Setup [U] cập nhật lại", "err")
                return {}

            if r.status_code == 200:
                body = r.json()
                # Golike trả data trong body.data hoặc thẳng body
                data = body.get("data") or body.get("user") or body
                if not isinstance(data, dict):
                    data = body
                data["_pending"] = (data.get("pending_coin") or
                                    data.get("hold_coin") or
                                    data.get("temp_coin") or 0)
                return data

            log(f"get_user lỗi HTTP {r.status_code}: {r.text[:100]}", "err")
        except requests.exceptions.ConnectionError:
            log("Không kết nối được mạng!", "err")
        except requests.exceptions.Timeout:
            log("get_user timeout!", "err")
        except Exception as e:
            log(f"get_user lỗi: {e}", "err")
        return {}

    def get_accounts(self, platform: str) -> list:
        ep = PLATFORMS[platform]["acct_ep"]
        try:
            r = self.s.get(f"{GATEWAY}/{ep}", params={"limit":200}, timeout=10)
            if DEBUG_MODE[0]:
                print(f"\n{Y}[DEBUG get_accounts/{platform}] {r.status_code}{RESET}")
                try: print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:2000])
                except: print(r.text[:300])
            if self._is_cloudflare(r):
                log("Token hết hạn — vào Setup cập nhật lại", "err"); return []
            if r.status_code == 200:
                body = r.json()
                data = body.get("data", [])
                if isinstance(data, dict): data = data.get("data", [])
                return data if isinstance(data, list) else []
        except Exception as e:
            log(f"get_accounts lỗi: {e}", "err")
        return []

    def get_fb_server(self) -> str:
        """Lấy server FB trước khi get_job — mặc định sv2"""
        try:
            r = self.s.get(f"{GATEWAY}/advertising/publishers/server", timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", {})
                sv = (data.get("server") or data.get("name") or
                      (data[0].get("name") if isinstance(data, list) and data else None) or "sv2")
                if DEBUG_MODE[0]:
                    print(f"{Y}[DEBUG get_fb_server] {sv}{RESET}")
                return str(sv)
        except: pass
        return "sv2"

    def get_jobs_fb(self, plat_acc: dict, server: str = "sv2") -> list:
        """FB trả về list job — thử endpoint mới trước, fallback endpoint cũ"""
        fb_id = plat_acc.get("fb_id","")

        # Danh sách endpoint thử theo thứ tự
        endpoints = [
            f"{GATEWAY}/advertising/publishers/_private/get-jobs?fb_id={fb_id}",
            f"{GATEWAY}/advertising/publishers/get-jobs-2026?fb_id={fb_id}&server={server}&low_job=1",
            f"{GATEWAY}/advertising/publishers/facebook/jobs?fb_id={fb_id}&server={server}&low_job=1",
        ]

        for url in endpoints:
            try:
                r = self.s.get(url, timeout=15)
                if DEBUG_MODE[0]:
                    print(f"\n{Y}[DEBUG get_jobs_fb] {url}{RESET}")
                    print(f"  Status: {r.status_code}")
                    try: print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:2000])
                    except: print(r.text[:300])
                if r.status_code == 200:
                    resp = r.json()
                    if resp.get("status") == 200 and resp.get("success"):
                        data = resp.get("data", [])
                        def _mfb(j):
                            j["_from_private"] = True
                            if "job_id" in j and "id" not in j: j["id"] = j["job_id"]
                            if "fix_coin" in j and "fix_coin_job" not in j: j["fix_coin_job"] = j["fix_coin"]
                            return j
                        if isinstance(data, list) and data: return [_mfb(j) for j in data]
                        if isinstance(data, dict) and data: return [_mfb(data)]
                elif r.status_code == 403:
                    log(f"  Endpoint bị chặn, thử tiếp...", "warn")
                    continue
            except Exception as e:
                log(f"get_jobs_fb lỗi [{url[:50]}]: {e}", "err")
        return []

    def get_job(self, platform: str, acc_id: int, plat_acc: dict = None) -> dict:
        """Lấy 1 job — thử _private endpoint trước, fallback endpoint cũ"""
        pinfo  = PLATFORMS[platform]
        p      = pinfo["prefix"]
        af     = pinfo["acct_id"]
        pp     = pinfo.get("private_param", af)

        # Lấy giá trị param đúng cho _private
        pnf = pinfo.get("private_name_field", "")
        if plat_acc and pp != af:
            param_val = (plat_acc.get(pnf) if pnf else None) or                         plat_acc.get("linkedin_username") or                         plat_acc.get("threads_username") or                         plat_acc.get("instagram_username") or                         plat_acc.get("pinterest_username") or                         plat_acc.get("unique_username") or                         plat_acc.get("username") or str(acc_id)
        else:
            param_val = str(acc_id)

        # Thử _private endpoint trước
        private_url = f"{GATEWAY}/advertising/publishers/{p}/_private/get-jobs"
        try:
            r0 = self.s.get(private_url, params={pp: param_val}, timeout=15)
            if r0.status_code == 200:
                resp0 = r0.json()
                if resp0.get("success") and resp0.get("data"):
                    data = resp0["data"]
                    if DEBUG_MODE[0]:
                        print(f"\n{Y}[DEBUG get_job/{platform}] _private 200{RESET}")
                        print(json.dumps(resp0, ensure_ascii=False, indent=2)[:1000])
                    def normalize_job(j):
                        """Chuẩn hóa format job từ _private về format thống nhất"""
                        if isinstance(j, dict):
                            # _private dùng job_id, fix_coin thay vì id, fix_coin_job
                            if "job_id" in j and "id" not in j:
                                j["id"] = j["job_id"]
                            if "fix_coin" in j and "fix_coin_job" not in j:
                                j["fix_coin_job"] = j["fix_coin"]
                        return j
                    def mark_private(j):
                        j = normalize_job(j)
                        j["_from_private"] = True
                        return j
                    # data=[false] nghĩa là không có job
                    if isinstance(data, list) and data and data[0] is not False:
                        return mark_private(data[0])
                    if isinstance(data, dict) and (data.get("id") or data.get("job_id")):
                        return mark_private(data)
                    if isinstance(data, list) and (not data or data[0] is False):
                        return None  # không có job, không fallback
        except: pass

        # Chỉ fallback nếu không có _private endpoint
        if pinfo.get("private_param"):
            return None  # platform có _private nhưng không có job

        url    = f"{GATEWAY}/advertising/publishers/{p}/jobs"
        params = {af: acc_id}

        for attempt in range(2):
            try:
                r = self.s.get(url, params=params, timeout=15)
                if DEBUG_MODE[0]:
                    print(f"\n{Y}[DEBUG get_job/{platform}]{RESET}")
                    print(f"  URL: {r.url}")
                    print(f"  Status: {r.status_code}")
                    try: print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:1500])
                    except: print(r.text[:300])
                if r.status_code == 403:
                    log(f"  403 endpoint bị chặn — bỏ qua", "warn")
                    return None
                if r.status_code == 429:
                    log("  Rate limit — chờ 30s...", "warn")
                    time.sleep(30); continue
                if r.status_code == 200:
                    resp = r.json()
                    if resp.get("status") == 200:
                        data = resp.get("data")
                        if isinstance(data, dict) and data: return data
                        if isinstance(data, list) and data: return data[0]
                    if DEBUG_MODE[0]:
                        print(f"  → status={resp.get('status')} msg={resp.get('message','')}")
                break
            except requests.exceptions.Timeout:
                log(f"  get_job timeout (lần {attempt+1})", "warn")
            except Exception as e:
                log(f"get_job lỗi: {e}", "err"); break
        return {}

    def do_login(self, email: str, password: str) -> dict:
        """Đăng nhập lấy token mới"""
        try:
            r = self.s.post(
                f"{GATEWAY}/login",
                json={"email": email, "password": password},
                timeout=15
            )
            if DEBUG_MODE[0]:
                print(f"\n{Y}[DEBUG login] status={r.status_code}{RESET}")
                try: print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:500])
                except: print(r.text[:200])
            if r.status_code == 200:
                body  = r.json()
                token = (body.get("data",{}).get("access_token") or
                         body.get("data",{}).get("token") or
                         body.get("access_token") or
                         body.get("token") or "")
                return {"token": token, "body": body}
        except Exception as e:
            log(f"login lỗi: {e}", "err")
        return {}

    def complete_job(self, platform: str, ads_id: int, acc_id: int,
                     plat_acc: dict = None, job: dict = None) -> dict:
        pinfo    = PLATFORMS[platform]
        p        = pinfo["prefix"]
        j        = job or {}
        j_type   = j.get("type", "unknown")
        j_id     = j.get("id", ads_id)
        obj_id   = str(j.get("object_id", ""))
        j_link   = j.get("link", "")
        t_start  = time.time()

        # ── Log chi tiết trước khi gửi ────────────────────────────────────────
        log(f"  │  🔵 COMPLETE START | job#{j_id} | type={j_type} | obj={obj_id[:40]}", "info")
        if j_link:
            log(f"  │     link={j_link[:80]}", "info")

        # ══════════════════════════════════════════════════════════════════════
        # DELAY TOÀN CỤC — áp dụng cho TẤT CẢ platform, TẤT CẢ loại job
        # ══════════════════════════════════════════════════════════════════════
        delay = random.uniform(6, 13)
        print(f"⏳ Delay {delay:.1f}s trước khi gửi complete")
        time.sleep(delay)

        # ── Build URL + payload ────────────────────────────────────────────────
        # Nhánh _private (không phải facebook)
        if (j.get("_from_private") or ("job_id" in j and "id" not in j)) and platform != "facebook":
            pp        = pinfo.get("private_param", pinfo["acct_id"])
            pnf       = pinfo.get("private_name_field", "")
            pa        = plat_acc or {}
            param_val = pa.get(pnf) or str(acc_id) if pnf else str(acc_id)
            url = f"{GATEWAY}/advertising/publishers/{p}/_private/complete-jobs"
            payload = {
                "job_id":  j.get("job_id", ads_id),
                pp:        param_val,
                "success": True,
            }
            if "comment" in j_type.lower():
                cr  = j.get("comment_run", {}) or {}
                msg = (cr.get("message") or cr.get("content") or
                       j.get("description") or j.get("message") or
                       j.get("content") or "")
                if not msg: msg = "Nội dung hay! 👍"
                payload["message"]    = msg
                payload["content"]    = msg
                payload["comment_id"] = cr.get("id", "")

        # Nhánh Facebook
        elif platform == "facebook":
            url    = f"{GATEWAY}/{pinfo.get('complete_endpoint','advertising/publishers/complete-jobs-2026')}"
            fb_id  = plat_acc.get("fb_id","") if plat_acc else ""
            payload = {
                "object_id":            obj_id,
                "job_id":               j_id,
                "type":                 j_type,
                "uid":                  fb_id,
                "users_fb_account_id":  acc_id,
                "users_advertising_id": j_id,
                "message":              None,
            }
            if "like" in j_type.lower():
                payload["reaction"] = j.get("reaction", "like")

        # Nhánh các platform còn lại
        else:
            af          = pinfo["acct_id"]
            ads_field   = pinfo["ads_id"]
            url         = f"{GATEWAY}/advertising/publishers/{p}/complete-jobs"
            real_ads_id = j.get(ads_field) or j.get("id") or ads_id
            payload = {
                ads_field: real_ads_id,
                af:        acc_id,
                "async":   True,
                "data":    None,
            }
            if "comment" in j_type.lower():
                cr  = j.get("comment_run", {}) or {}
                msg = (cr.get("message") or cr.get("content") or
                       j.get("description") or j.get("message") or
                       j.get("content") or "")
                if not msg: msg = "Nội dung hay! 👍"
                payload["message"]    = msg
                payload["content"]    = msg
                payload["comment_id"] = cr.get("id", "")

        print(f"COMPLETE URL: {url}")
        print(f"COMPLETE PAYLOAD: {json.dumps(payload, ensure_ascii=False)}")

        # ── Gửi request — retry tối đa 1 lần ────────────────────────────────
        def _parse_429_wait(msg_text: str) -> int:
            """Đọc số giây từ message '...chờ X giây...' của Golike."""
            import re as _re
            m = _re.search(r'(\d+)\s*gi[aâ]y', msg_text, _re.IGNORECASE)
            if m: return max(int(m.group(1)), 2)
            m2 = _re.search(r'(\d+)\s*s', msg_text, _re.IGNORECASE)
            if m2: return max(int(m2.group(1)), 2)
            return 5  # default nếu không parse được

        def _classify_error(resp_dict: dict, http_status: int):
            """
            Phân loại lỗi thành 4 nhóm:
            - 'uid_not_performed' : "chưa thực hiện thao tác"
            - 'rate_limit'        : 429 hoặc "báo cáo quá nhanh"
            - 'system_check'      : "hệ thống check lỗi"
            - 'generic'           : lỗi khác
            Trả về (error_class, wait_seconds)
            """
            msg = str(resp_dict.get("message", resp_dict.get("error", ""))).lower()
            st  = resp_dict.get("status", http_status)
            if "chưa thực hiện" in msg or "chua thuc hien" in msg:
                return "uid_not_performed", 0
            if st == 429 or "quá nhanh" in msg or "qua nhanh" in msg or "báo cáo" in msg:
                return "rate_limit", _parse_429_wait(msg)
            if "hệ thống check" in msg or "he thong check" in msg or "báo admin" in msg:
                return "system_check", 0
            return "generic", 0

        for _attempt in range(2):
            try:
                if "fb" in p or platform == "facebook":
                    self.s.headers.update({"t": gen_t()})
                r = self.s.post(url, json=payload, timeout=30)
                print(f"COMPLETE RESPONSE: {r.text[:500]}")
                if DEBUG_MODE[0]:
                    print(f"\n{Y}[DEBUG complete_job/{platform}] {r.status_code}{RESET}")
                    try: print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:1500])
                    except: print(r.text[:300])

                resp = r.json()
                elapsed = time.time() - t_start
                log(f"  │     ⏱ {elapsed:.1f}s | HTTP {r.status_code} | attempt={_attempt+1}", "info")

                # ── Thành công ───────────────────────────────────────────────
                if r.status_code in (200, 201) and (resp.get("success") or resp.get("status") == 200):
                    if isinstance(resp, dict) and "status" not in resp:
                        resp["status"] = 200
                    log(f"  │     ✅ COMPLETE OK | job#{j_id} | type={j_type}", "ok")
                    _jstats_add("success", j_type)
                    return resp

                # ── Phân loại lỗi ────────────────────────────────────────────
                err_class, wait_s = _classify_error(resp, r.status_code)
                err_msg = resp.get("message", resp.get("error", str(r.status_code)))

                if err_class == "uid_not_performed":
                    # Server xác nhận chưa thực hiện → không retry, bỏ job
                    log(f"  │     ⚠️  UID chưa thực hiện thao tác — bỏ job#{j_id}", "warn")
                    _jstats_add("uid_not_performed", j_type)
                    _jstats_add("failed", j_type)
                    _jstats_log_fail(j_id, j_type, platform, "uid_not_performed", err_msg)
                    resp["_error_class"] = "uid_not_performed"
                    return resp

                elif err_class == "rate_limit":
                    _jstats_add("rate_limit")
                    if _attempt == 0:
                        actual_wait = wait_s if wait_s > 0 else random.randint(3, 8)
                        log(f"  │     ⚠️  429 báo cáo quá nhanh — chờ {actual_wait}s rồi retry...", "warn")
                        time.sleep(actual_wait)
                        print("🔄 Retry complete lần 2...")
                        continue
                    # Attempt 1 vẫn 429 → ghi fail
                    log(f"  │     ❌ 429 sau 2 lần — bỏ job#{j_id}", "err")
                    _jstats_add("failed", j_type)
                    _jstats_log_fail(j_id, j_type, platform, "rate_limit", err_msg)
                    resp["_error_class"] = "rate_limit"
                    return resp

                elif err_class == "system_check":
                    # Bỏ qua ngay, không retry
                    log(f"  │     ⚠️  Hệ thống check lỗi — bỏ qua job#{j_id}", "warn")
                    _jstats_add("system_check")
                    _jstats_add("failed", j_type)
                    _jstats_log_fail(j_id, j_type, platform, "system_check", err_msg)
                    resp["_error_class"] = "system_check"
                    return resp

                else:
                    # Lỗi generic — retry 1 lần
                    if _attempt == 0:
                        wait = random.randint(3, 8)
                        log(f"  │     ⚠️  Lỗi {r.status_code}: {err_msg[:80]} — chờ {wait}s retry...", "warn")
                        time.sleep(wait)
                        print("🔄 Retry complete lần 2...")
                        continue
                    log(f"  │     ❌ Thất bại sau 2 lần | job#{j_id}: {err_msg[:80]}", "err")
                    _jstats_add("failed", j_type)
                    _jstats_log_fail(j_id, j_type, platform, "generic", err_msg)
                    return resp

            except requests.exceptions.Timeout:
                if _attempt == 0:
                    wait = random.randint(3, 8)
                    log(f"  ⚡ complete_job timeout — chờ {wait}s rồi retry...", "warn")
                    time.sleep(wait)
                    print("🔄 Retry complete lần 2...")
                    continue
                log(f"  complete_job timeout sau 2 lần — bỏ job!", "err")
                _jstats_add("failed", j_type)
                _jstats_log_fail(j_id, j_type, platform, "timeout", "Connection timed out")
                return {"status": 0, "error": "timeout", "message": "Connection timed out"}
            except requests.exceptions.ConnectionError:
                if _attempt == 0:
                    wait = random.randint(3, 8)
                    log(f"  ⚡ complete_job mất kết nối — chờ {wait}s rồi retry...", "warn")
                    time.sleep(wait)
                    print("🔄 Retry complete lần 2...")
                    continue
                log(f"  complete_job mất kết nối sau 2 lần!", "err")
                _jstats_add("failed", j_type)
                _jstats_log_fail(j_id, j_type, platform, "conn_error", "Connection error")
                return {"status": 0, "error": "connection_error", "message": "Connection error"}
            except Exception as e:
                _jstats_add("failed", j_type)
                _jstats_log_fail(j_id, j_type, platform, "exception", str(e))
                return {"error": str(e), "status": 0}

        _jstats_add("failed", j_type)
        return {"status": 0, "error": "max_retry"}

    def skip_job(self, platform: str, ads_id: int, acc_id: int,
                 object_id: str, job_type: str, plat_acc: dict = None):
        pinfo = PLATFORMS[platform]
        p     = pinfo["prefix"]

        if platform == "facebook":
            fb_id = plat_acc.get("fb_id","") if plat_acc else ""
            try:
                self.s.post(
                    f"{GATEWAY}/report/send",
                    json={
                        "description":          "Job đủ số lượng",
                        "users_advertising_id": ads_id,
                        "type":                 "ads",
                        "fb_id":                fb_id,
                        "error_type":           1,
                        "provider":             "facebook",
                        "comment":              None,
                    },
                    timeout=10
                )
            except: pass
        else:
            af = pinfo["acct_id"]
            try:
                self.s.post(
                    f"{GATEWAY}/advertising/publishers/{p}/skip-jobs",
                    json={"ads_id": ads_id, af: acc_id,
                          "object_id": object_id, "type": job_type},
                    timeout=10
                )
            except: pass

# ── TikTok follow qua cookie ───────────────────────────────────────────────────
def do_tiktok_follow(cookie_str: str, job: dict) -> bool:
    """Thực hiện follow TikTok bằng cookie của tài khoản."""
    import re as _re
    obj_id = str(job.get("object_id", ""))
    link   = job.get("link", "https://www.tiktok.com/")

    if not cookie_str or not obj_id:
        log("  TikTok follow: thiếu cookie hoặc object_id → bỏ qua action", "warn")
        return True  # Fallback: để complete_job thử

    # ── Parse cookie string → dict ──────────────────────────────────────────
    ck_dict: dict = {}
    for part in cookie_str.replace("; ", ";").split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            ck_dict[k.strip()] = v.strip()

    session_id = ck_dict.get("sessionid") or ck_dict.get("session_id", "")
    if not session_id:
        log("  TikTok follow: không tìm thấy sessionid trong cookie", "warn")
        return True

    UA_TK = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
             "AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/124.0.0.0 Safari/537.36")

    # ── Lấy CSRF token từ cookie hoặc trang chủ ────────────────────────────
    csrf = ck_dict.get("tt_csrf_token", "")
    msToken = ck_dict.get("msToken", "")

    if not csrf:
        try:
            r0 = requests.get(
                "https://www.tiktok.com/",
                cookies=ck_dict,
                headers={"User-Agent": UA_TK},
                timeout=12,
            )
            m = _re.search(r'"csrf_token"\s*:\s*"([^"]+)"', r0.text)
            if m:
                csrf = m.group(1)
            if not msToken:
                m2 = _re.search(r'"msToken"\s*:\s*"([^"]+)"', r0.text)
                if m2:
                    msToken = m2.group(1)
        except Exception as _e:
            log(f"  TikTok: không lấy được csrf ({_e})", "warn")

    # ── Gọi follow API ──────────────────────────────────────────────────────
    follow_url = "https://www.tiktok.com/api/commit/follow/user/"
    params = {
        "aid":             "1988",
        "app_language":    "en",
        "app_name":        "tiktok_web",
        "device_platform": "web_pc",
    }
    if msToken:
        params["msToken"] = msToken

    headers = {
        "User-Agent":   UA_TK,
        "Accept":       "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin":       "https://www.tiktok.com",
        "Referer":      link,
    }
    if csrf:
        headers["X-CSRFToken"] = csrf

    data = {
        "user_id":    obj_id,
        "type":       "1",   # 1=follow, 0=unfollow
        "from":       "0",
        "from_pre":   "0",
        "channel_id": "0",
    }

    try:
        s = requests.Session()
        s.cookies.update(ck_dict)
        r = s.post(follow_url, params=params, data=data,
                   headers=headers, timeout=15)
        resp = r.json()
        sc   = resp.get("status_code", -1)
        # 0 = thành công, 2069 = đã follow rồi, 2105 = không thể follow chính mình
        if sc in (0, 2069, 2105):
            log(f"  TikTok follow OK (status_code={sc})", "info")
            return True
        elif sc == 3102:
            log("  TikTok cookie hết hạn hoặc không hợp lệ (3102)", "warn")
            return False
        elif sc == 2683:
            log("  TikTok: tài khoản bị giới hạn follow (2683)", "warn")
            return False
        else:
            log(f"  TikTok follow status_code={sc}: {resp.get('message','?')}", "warn")
            return True  # Không rõ → vẫn thử complete_job
    except requests.exceptions.Timeout:
        log("  TikTok follow timeout — vẫn thử complete_job", "warn")
        return True
    except Exception as ex:
        log(f"  TikTok follow lỗi: {ex}", "warn")
        return True  # Fallback an toàn


# ── Action thật qua cookie MXH ────────────────────────────────────────────────
def do_action(platform: str, job: dict, cookie: str) -> bool:
    """Thực hiện action thật. Trả True = tiếp tục complete_job."""
    job_type = job.get("type","")
    # facebook_like_v1 cần cookie thật dù platform action = "server"
    # Các job cần cookie thật dù platform action = "server"
    need_cookie_action = (
        (platform == "facebook" and "like_v1" in job_type) or
        (platform == "tiktok"   and "follow"  in job_type.lower())
    )
    if not cookie or (PLATFORMS[platform]["action"] == "server" and not need_cookie_action):
        return True

    job_type  = job.get("type","")
    object_id = str(job.get("object_id",""))
    desc      = job.get("description","")

    try:
        if platform == "facebook" and ("like_v1" in job_type or "corona" in job_type or "like_page" in job_type):
            import re as _re
            dtsg = ""; lsd = ""
            try:
                r0 = requests.get("https://www.facebook.com/",
                    headers={
                        "cookie":     cookie,
                        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "accept":     "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    }, timeout=10)
                m = _re.search(r'"dtsg":{"token":"([^"]+)"', r0.text)
                if not m: m = _re.search(r'name="fb_dtsg" value="([^"]+)"', r0.text)
                if m: dtsg = m.group(1)
                m2 = _re.search(r'"LSD"[^"]*"token":"([^"]+)"', r0.text)
                if m2: lsd = m2.group(1)
            except: pass

            object_id2 = str(job.get("object_id",""))
            c_user = ""
            try: c_user = [p.split("=",1)[1] for p in cookie.split(";") if "c_user=" in p][0].strip()
            except: pass

            fb_h = {
                "cookie":       cookie,
                "user-agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "content-type": "application/x-www-form-urlencoded",
                "origin":       "https://www.facebook.com",
                "referer":      "https://www.facebook.com/",
                "accept":       "*/*",
                "x-fb-lsd":     lsd,
            }
            reaction = job.get("reaction","like").upper()
            data = {
                "fb_api_caller_class":      "RelayModern",
                "fb_api_req_friendly_name": "CometUFIFeedbackReactMutation",
                "variables": '{"input":{"feedback_id":"' + object_id2 + '","feedback_reaction_id":"1635855486666999","feedback_source":"OBJECT","reaction_style":"' + reaction + '","actor_id":"' + c_user + '","client_mutation_id":"1"}}',
                "doc_id":   "9740159112729312",
                "fb_dtsg":  dtsg,
                "lsd":      lsd,
            }
            try:
                r = requests.post("https://www.facebook.com/api/graphql/",
                    headers=fb_h, data=data, timeout=15)
                resp_t = r.text
                if any(x in resp_t for x in ["feedback","likers","reaction","viewer"]):
                    return True
                log(f"  FB action response: {resp_t[:200]}", "warn")
                return False
            except Exception as ex:
                log(f"  FB action lỗi: {ex}", "warn")
                return False

        if platform == "instagram":
            csrf = ""
            try: csrf = cookie.split("csrftoken=")[1].split(";")[0]
            except: pass

            # Extract thêm fields từ cookie
            mid = ""
            ds_user_id = ""
            try:
                for part in cookie.split(";"):
                    part = part.strip()
                    if part.startswith("mid="): mid = part.split("=",1)[1]
                    if part.startswith("ds_user_id="): ds_user_id = part.split("=",1)[1]
            except: pass

            ig_h = {
                "cookie":              cookie,
                "accept":              "*/*",
                "accept-language":     "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                "content-type":        "application/x-www-form-urlencoded",
                "origin":              "https://www.instagram.com",
                "referer":             "https://www.instagram.com/",
                "user-agent":          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                                       "Chrome/124.0.0.0 Safari/537.36",
                "x-csrftoken":         csrf,
                "x-ig-app-id":         "936619743392459",
                "x-ig-www-claim":      "0",
                "x-instagram-ajax":    "1019434984",
                "x-requested-with":    "XMLHttpRequest",
                "x-asbd-id":           "129477",
                "x-mid":               mid,
                "sec-ch-ua":           '"Google Chrome";v="124","Chromium";v="124","Not-A.Brand";v="99"',
                "sec-ch-ua-mobile":    "?0",
                "sec-ch-ua-platform":  '"Windows"',
                "sec-fetch-dest":      "empty",
                "sec-fetch-mode":      "cors",
                "sec-fetch-site":      "same-origin",
                "dpr":                 "2",
                "viewport-width":      "1280",
            }

            if job_type == "follow":
                # Dùng GraphQL mutation giống tool chuyên nghiệp
                variables = '{"target_user_id":"' + str(object_id) + '","container_module":"profile","nav_chain":"PolarisProfilePostsTabRoot%3AprofilePage%3A1%3Avia_cold_start%3A0"}'
                ig_gql_data = {
                    "fb_api_caller_class": "RelayModern",
                    "fb_api_req_friendly_name": "usePolarisFollowMutation",
                    "variables": variables,
                    "server_timestamps": "true",
                    "doc_id": "9740401592729312",
                }
                ig_gql_h = dict(ig_h)
                ig_gql_h["content-type"] = "application/x-www-form-urlencoded"
                ig_gql_h["x-ig-app-id"] = "936619743392459"
                try:
                    _s = _IG_SCRAPER if _IG_SCRAPER else requests
                    # Dùng requests thường với allow_redirects=False
                    r2 = requests.post(
                        f"https://www.instagram.com/api/v1/friendships/create/{object_id}/",
                        headers=ig_h,
                        data={"container_module":"profile","user_id":object_id},
                        timeout=15,
                        allow_redirects=False
                    )
                    resp = r2.text
                    if '"status":"ok"' in resp: return True
                    if '"spam":true' in resp: log("  IG bị chặn follow (spam)", "warn")
                    if '"require_login"' in resp: log("  IG cookie die!", "err")
                    log(f"  IG follow response: {resp[:200]}", "warn")
                    return False
                except Exception as e:
                    log(f"  IG follow lỗi: {e}", "warn")
                    return False

            elif job_type == "like":
                _s = _IG_SCRAPER if _IG_SCRAPER else requests
                resp = _s.post(
                    f"https://www.instagram.com/api/v1/web/likes/{desc}/like/",
                    headers=ig_h, timeout=15
                ).text
                if '"status":"ok"' in resp: return True
                if '"spam":true'   in resp: log("  IG bị chặn like (spam)", "warn")
                if '"require_login"' in resp: log("  IG cookie die!", "err")
                return False

            return True  # job type khác IG

        elif platform == "youtube":
            sapisid = ""
            for part in cookie.split(";"):
                p2 = part.strip()
                if "SAPISID=" in p2 or "__Secure-3PAPISID=" in p2:
                    sapisid = p2.split("=",1)[1]; break

            ts       = int(time.time())
            sapihash = f"SAPISIDHASH {ts}_{hashlib.sha1(f'{ts} {sapisid} https://www.youtube.com'.encode()).hexdigest()}"

            yt_h = {
                "cookie":        cookie,
                "authorization": sapihash,
                "content-type":  "application/json",
                "origin":        "https://www.youtube.com",
                "referer":       "https://www.youtube.com/",
                "user-agent":    "Mozilla/5.0 (Linux; Android 10) Chrome/121.0.0.0",
                "x-origin":      "https://www.youtube.com",
            }
            ctx = {"client": {"clientName":"WEB","clientVersion":"2.20240101"}}

            if job_type == "subscribe":
                r = requests.post(
                    "https://www.youtube.com/youtubei/v1/subscription/subscribe",
                    headers=yt_h,
                    json={"channelIds":[object_id], "context":ctx},
                    timeout=15
                )
                return r.status_code in (200,204)

            elif job_type == "like":
                r = requests.post(
                    "https://www.youtube.com/youtubei/v1/like/like",
                    headers=yt_h,
                    json={"target":{"videoId":object_id}, "context":ctx},
                    timeout=15
                )
                return r.status_code in (200,204)

            return True

        # ── TikTok follow (cookie-based) ──────────────────────────────────
        if platform == "tiktok" and "follow" in job_type.lower():
            return do_tiktok_follow(cookie, job)

    except Exception as e:
        log(f"do_action lỗi: {e}", "err")
        return False

    return True

# ── Setup ──────────────────────────────────────────────────────────────────────
def setup(cfg: dict) -> dict:
    accounts    = cfg.get("accounts", [])
    mxh_cookies = cfg.get("mxh_cookies", {})

    while True:
        clear(); banner()
        print(f"{G}⚙️  QUẢN LÝ TÀI KHOẢN{RESET}\n")

        # Hiện danh sách
        if accounts:
            print(f"{'STT':<4} {'Tên':<20} {'Username':<20} {'Coin'}")
            print("─" * 55)
            for i, a in enumerate(accounts):
                status = f"{G}✅{RESET}" if a.get("active") else f"{R}❌{RESET}"
                print(f"{status} {i+1:<3} {a['name']:<20} "
                      f"{a.get('username','?'):<20} {a.get('coin','?')}đ")
        else:
            print(f"  {Y}Chưa có tài khoản nào{RESET}")

        print(f"\n  {B}[A]{RESET} ➕ Thêm tài khoản Golike")
        print(f"  {B}[M]{RESET} 📱 Thêm tài khoản MXH vào Golike (username)")
        print(f"  {B}[C]{RESET} 🍪 Quản lý Cookie MXH")
        print(f"  {B}[U]{RESET} 🔄 Cập nhật token")
        print(f"  {B}[D]{RESET} 🗑️  Xóa tài khoản Golike")
        print(f"  {B}[0]{RESET} ↩️  Quay lại\n")

        ch = input(f"{B}Chọn: {RESET}").strip().upper()

        if ch == "0": break

        elif ch == "A":
            clear(); banner()
            print(f"{G}➕ THÊM TÀI KHOẢN GOLIKE{RESET}\n")
            print(f"  {B}[1]{RESET} 📧 Đăng nhập Email + Password (khuyến nghị)")
            print(f"  {B}[2]{RESET} 🔑 Nhập Authorization token thủ công")
            print(f"  {B}[0]{RESET} ↩️  Quay lại\n")
            method = input(f"{B}Chọn: {RESET}").strip()

            if method == "0": continue

            name = input(f"{B}Tên gợi nhớ (Enter = tự đặt): {RESET}").strip() \
                   or f"acc{len(accounts)+1}"

            if method == "1":
                # Đăng nhập email/password
                email = input(f"{B}Email Golike: {RESET}").strip()
                pw    = input(f"{B}Password: {RESET}").strip()
                if not email or not pw:
                    log("Email/Password không được để trống!", "err")
                    time.sleep(1); continue

                log("Đang đăng nhập...", "wait")
                tmp_api = GolikeAPI("")
                result  = tmp_api.do_login(email, pw)
                token   = result.get("token","")

                if token:
                    auth = f"Bearer {token}"
                    api  = GolikeAPI(auth)
                    user = api.get_user()
                    uname = (user.get("username") or user.get("email") or email)
                    coin  = user.get("coin", 0)
                    accounts.append({
                        "name":     name,
                        "auth":     auth,
                        "email":    email,
                        "password": pw,  # lưu để auto-refresh sau này
                        "username": uname,
                        "coin":     coin,
                        "active":   True,
                    })
                    cfg["accounts"] = accounts; save_cfg(cfg)
                    log(f"✅ Đăng nhập thành công: {uname} | {coin}đ", "ok")
                else:
                    body = result.get("body", {})
                    msg  = body.get("message") or body.get("error") or "Sai email/password"
                    log(f"❌ Đăng nhập thất bại: {msg}", "err")

            elif method == "2":
                # Token thủ công
                print(f"\n{Y}Cách lấy header từ DevTools:{RESET}")
                print(f"  1. Mở Chrome → {B}app.golike.net{RESET} → đăng nhập")
                print(f"  2. F12 → tab {B}Network{RESET} → tải lại trang")
                print(f"  3. Click request bất kỳ → {B}Request Headers{RESET}")
                print(f"  4. Copy các header bên dưới\n")

                auth = input(f"{B}authorization (Bearer eyJ...): {RESET}").strip()
                if not auth:
                    log("Bỏ qua!", "warn"); time.sleep(1); continue
                if not auth.startswith("Bearer "):
                    auth = f"Bearer {auth}"

                g_auth = input(f"{B}g-auth (bắt buộc): {RESET}").strip()
                did    = input(f"{B}g-device-id (Enter = tự tạo): {RESET}").strip()

                old_dbg = DEBUG_MODE[0]; DEBUG_MODE[0] = True
                log("Đang kiểm tra token...", "wait")
                api  = GolikeAPI(auth, g_auth, did)
                user = api.get_user()
                DEBUG_MODE[0] = old_dbg

                if user and (user.get("username") or user.get("email") or user.get("id")):
                    uname = user.get("username") or user.get("email") or str(user.get("id",""))
                    coin  = user.get("coin", 0)
                    accounts.append({
                        "name": name, "auth": auth,
                        "g_auth": g_auth,
                        "device_id": api.device_id,
                        "username": uname, "coin": coin, "active": True,
                    })
                    cfg["accounts"] = accounts; save_cfg(cfg)
                    log(f"✅ Thêm thành công: {uname} | {coin}đ", "ok")
                else:
                    log("Token 401 — kiểm tra lại authorization và g-auth", "err")
                    if input(f"{B}Vẫn lưu? (y/n): {RESET}").lower() == "y":
                        accounts.append({
                            "name": name, "auth": auth,
                            "g_auth": g_auth, "device_id": api.device_id,
                            "active": True, "username": "", "coin": 0,
                        })
                        cfg["accounts"] = accounts; save_cfg(cfg)
                        log("Đã lưu (chưa xác minh)", "warn")
            time.sleep(1)

        elif ch == "U":
            if not accounts:
                log("Chưa có tài khoản!", "err"); time.sleep(1); continue
            for i, a in enumerate(accounts):
                print(f"  {B}[{i+1}]{RESET} {a['name']} ({a.get('username','')})")
            sel = input(f"{B}Chọn acc cần cập nhật: {RESET}").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(accounts):
                idx    = int(sel)-1
                auth   = input(f"{B}authorization mới: {RESET}").strip()
                g_auth = input(f"{B}g-auth mới (Enter giữ nguyên): {RESET}").strip()
                if not auth.startswith("Bearer "): auth = f"Bearer {auth}"
                if not g_auth: g_auth = accounts[idx].get("g_auth","")

                api  = GolikeAPI(auth, g_auth, accounts[idx].get("device_id",""))
                user = api.get_user()
                if user and (user.get("username") or user.get("id")):
                    accounts[idx]["auth"]     = auth
                    accounts[idx]["g_auth"]   = g_auth
                    accounts[idx]["username"] = user.get("username", accounts[idx].get("username",""))
                    accounts[idx]["coin"]     = user.get("coin", 0)
                    cfg["accounts"] = accounts; save_cfg(cfg)
                    log(f"✅ Cập nhật thành công: {user.get('username','')}", "ok")
                else:
                    log("Vẫn lỗi — kiểm tra lại authorization và g-auth", "err")
            time.sleep(1)

        elif ch == "M":
            # Thêm tài khoản MXH vào Golike bằng username
            if not accounts:
                log("Cần thêm tài khoản Golike trước!", "err"); time.sleep(1); continue

            clear(); banner()
            print(f"{G}📱 THÊM TÀI KHOẢN MXH VÀO GOLIKE{RESET}\n")
            print(f"{DIM}Nhập username MXH để Golike xác minh và thêm vào danh sách{RESET}\n")

            # Chọn Golike acc
            gl_acc = accounts[0]
            if len(accounts) > 1:
                for i, a in enumerate(accounts):
                    print(f"  {B}[{i+1}]{RESET} {a.get('username', a['name'])}")
                sel = input(f"{B}Chọn tài khoản Golike: {RESET}").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(accounts):
                    gl_acc = accounts[int(sel)-1]

            # Chọn platform
            print(f"\n{B}Chọn nền tảng:{RESET}")
            for i, p in enumerate(PLAT_LIST):
                print(f"  {B}[{i+1}]{RESET} {p.capitalize()}")
            sp = input(f"{B}Chọn: {RESET}").strip()
            if not sp.isdigit() or not (1 <= int(sp) <= len(PLAT_LIST)):
                time.sleep(1); continue
            plat = PLAT_LIST[int(sp)-1]

            # Nhập danh sách username (hỗ trợ nhiều acc cùng lúc)
            print(f"\n{Y}Nhập username {plat} (mỗi dòng 1 username, Enter trống để xong):{RESET}")
            usernames = []
            while True:
                u = input(f"  {B}Username: {RESET}").strip().lstrip("@")
                if not u: break
                usernames.append(u)

            if not usernames:
                log("Không có username nào!", "warn"); time.sleep(1); continue

            api = GolikeAPI(gl_acc["auth"], gl_acc.get("g_auth",""), gl_acc.get("device_id",""))
            ep  = PLATFORMS[plat]["acct_ep"]

            print()
            ok_count = 0
            for u in usernames:
                try:
                    r = api.s.post(
                        f"{GATEWAY}/{ep}/verify-account",
                        json={"object_id": u},
                        timeout=15
                    )
                    resp = r.json()
                    if r.status_code == 200 and resp.get("status") == 200:
                        log(f"✅ {u} — Thêm thành công!", "ok")
                        ok_count += 1
                    else:
                        msg = resp.get("message") or resp.get("error") or f"HTTP {r.status_code}"
                        log(f"❌ {u} — {msg}", "err")
                except Exception as e:
                    log(f"❌ {u} — Lỗi: {e}", "err")
                time.sleep(1)

            print(f"\n  {G}Xong: {ok_count}/{len(usernames)} tài khoản thêm thành công{RESET}")
            input(f"\n{DIM}Enter để tiếp tục...{RESET}")
            if not accounts:
                log("Chưa có tài khoản!", "err"); time.sleep(1); continue
            for i, a in enumerate(accounts):
                print(f"  {B}[{i+1}]{RESET} {a['name']}")
            sel = input(f"{B}Chọn acc xóa (hoặc * để xóa tất cả): {RESET}").strip()
            if sel == "*":
                accounts.clear()
            elif sel.isdigit() and 1 <= int(sel) <= len(accounts):
                accounts.pop(int(sel)-1)
            cfg["accounts"] = accounts; save_cfg(cfg)
            log("Đã xóa", "ok"); time.sleep(1)

        elif ch == "C":
            # Quản lý cookie MXH
            while True:
                clear(); banner()
                print(f"{G}🍪 COOKIE TÀI KHOẢN MXH{RESET}")
                print(f"{DIM}Cookie gắn với từng tài khoản MXH cụ thể{RESET}\n")

                for i, p in enumerate(PLAT_LIST):
                    ck_list = mxh_cookies.get(p, [])
                    count   = len(ck_list)
                    mark    = f"{G}✅ {count} cookie{RESET}" if count else f"{Y}Chưa có{RESET}"
                    need    = f"{R}[BẮT BUỘC]{RESET}" if PLATFORMS[p]["need_cookie"] else ""
                    print(f"  {B}[{i+1}]{RESET} {p.capitalize():<12} {mark} {need}")

                print(f"\n  {B}[A]{RESET} ➕ Thêm/gán cookie cho acc")
                print(f"  {B}[V]{RESET} 👁️  Xem cookie từng acc")
                print(f"  {B}[X]{RESET} 🗑️  Xóa cookie")
                print(f"  {B}[0]{RESET} ↩️  Quay lại\n")

                sc = input(f"{B}Chọn: {RESET}").strip().upper()
                if sc == "0": break

                elif sc == "A":
                    # Chọn Golike acc để lấy danh sách MXH acc
                    if not accounts:
                        log("Cần thêm tài khoản Golike trước!", "err"); time.sleep(1); continue

                    gl_acc = accounts[0]
                    if len(accounts) > 1:
                        for i, a in enumerate(accounts):
                            print(f"  {B}[{i+1}]{RESET} {a.get('username', a['name'])}")
                        sel = input(f"{B}Chọn Golike acc: {RESET}").strip()
                        if sel.isdigit() and 1 <= int(sel) <= len(accounts):
                            gl_acc = accounts[int(sel)-1]

                    # Chọn platform
                    for i, p in enumerate(PLAT_LIST):
                        print(f"  {B}[{i+1}]{RESET} {p.capitalize()}")
                    sp = input(f"{B}Chọn platform: {RESET}").strip()
                    if not sp.isdigit() or not (1 <= int(sp) <= len(PLAT_LIST)):
                        time.sleep(1); continue
                    plat = PLAT_LIST[int(sp)-1]

                    # Lấy danh sách acc MXH từ Golike
                    log("Đang lấy danh sách tài khoản...", "wait")
                    api_tmp  = GolikeAPI(gl_acc["auth"], gl_acc.get("g_auth",""), gl_acc.get("device_id",""))
                    plat_accs = api_tmp.get_accounts(plat)

                    if not plat_accs:
                        log(f"Không có tài khoản {plat}", "err"); time.sleep(1); continue

                    if plat not in mxh_cookies: mxh_cookies[plat] = []
                    ck_list = mxh_cookies[plat]

                    # Hiện danh sách acc + cookie hiện tại
                    print(f"\n{Y}Tài khoản {plat.upper()}:{RESET}")
                    print(f"  {'#':<4} {'Tên':<25} {'Cookie hiện tại'}")
                    print(f"  {'─'*55}")
                    for i, pa in enumerate(plat_accs):
                        pname  = get_acc_name(pa, plat)[:24]
                        pa_id  = pa.get("id","")
                        ck_ent = next((c for c in ck_list if str(c.get("acc_id","")) == str(pa_id)), None)
                        ck_s   = f"{G}✅ {ck_ent.get('name','?')}{RESET}" if ck_ent else f"{R}❌ Chưa có{RESET}"
                        print(f"  {i+1:<4} {pname:<25} {ck_s}")

                    print(f"\n{DIM}Chọn số acc để gán cookie (VD: 1,2 hoặc * cho tất cả){RESET}")
                    sel_acc = input(f"{B}Chọn acc: {RESET}").strip()

                    if sel_acc == "*":
                        chosen_idxs = list(range(len(plat_accs)))
                    else:
                        chosen_idxs = [int(x.strip())-1 for x in sel_acc.split(",")
                                       if x.strip().isdigit() and 1 <= int(x.strip()) <= len(plat_accs)]

                    for cidx in chosen_idxs:
                        pa    = plat_accs[cidx]
                        pa_id = pa.get("id","")
                        pname = get_acc_name(pa, plat)[:20]
                        print(f"\n{Y}Gán cookie cho: {pname} (id={pa_id}){RESET}")
                        print(f"{DIM}Lấy cookie từ DevTools → Application → Cookies → {plat}.com{RESET}")
                        ck = input(f"{B}Cookie (Enter bỏ qua): {RESET}").strip()
                        if not ck: continue

                        # Tự động parse UID từ cookie để xác nhận đúng acc
                        uid_from_ck = parse_uid_from_cookie(ck, plat)
                        uid_from_acc = (pa.get("fb_id") or pa.get("instagram_id") or
                                        str(pa.get("user_id","")) or "")

                        if uid_from_ck:
                            log(f"  UID trong cookie: {uid_from_ck}", "info")
                            if uid_from_acc and uid_from_ck != uid_from_acc.lstrip("0"):
                                print(f"  {Y}⚠️  UID cookie ({uid_from_ck}) ≠ UID acc ({uid_from_acc}){RESET}")
                                print(f"  {Y}Cookie có thể không đúng với acc này!{RESET}")
                                if input(f"  {B}Vẫn lưu? (y/n): {RESET}").lower() != "y":
                                    continue

                        nick = uid_from_ck or pname  # dùng UID làm tên mặc định

                        # Xóa cookie cũ của acc này nếu có
                        mxh_cookies[plat] = [c for c in ck_list if str(c.get("acc_id","")) != str(pa_id)]
                        mxh_cookies[plat].append({
                            "acc_id": pa_id,
                            "name":   nick,
                            "cookie": ck,
                        })
                        ck_list = mxh_cookies[plat]
                        cfg["mxh_cookies"] = mxh_cookies
                        save_cfg(cfg)
                        log(f"✅ Đã gán cookie cho {pname}", "ok")
                    time.sleep(1)

                elif sc == "V":
                    # Xem cookie từng acc
                    for i, p in enumerate(PLAT_LIST):
                        if mxh_cookies.get(p):
                            print(f"\n{Y}{p.capitalize()}:{RESET}")
                            for ck in mxh_cookies[p]:
                                aid   = ck.get("acc_id","?")
                                name  = ck.get("name","?")
                                short = ck.get("cookie","")[:30] + "..."
                                print(f"  acc_id={aid} | {name} | {short}")
                    input(f"\n{DIM}Enter để tiếp tục...{RESET}")

                elif sc == "X":
                    for i, p in enumerate(PLAT_LIST):
                        if mxh_cookies.get(p):
                            print(f"  {B}[{i+1}]{RESET} {p.capitalize()} ({len(mxh_cookies[p])} cookie)")
                    sp = input(f"{B}Chọn platform: {RESET}").strip()
                    if sp.isdigit() and 1 <= int(sp) <= len(PLAT_LIST):
                        plat    = PLAT_LIST[int(sp)-1]
                        ck_list = mxh_cookies.get(plat, [])
                        if not ck_list:
                            log("Không có cookie nào", "warn"); time.sleep(1); continue
                        for i, ck in enumerate(ck_list):
                            print(f"  {B}[{i+1}]{RESET} acc_id={ck.get('acc_id','?')} | {ck.get('name','?')}")
                        print(f"  {B}[*]{RESET} Xóa tất cả")
                        sx = input(f"{B}Chọn: {RESET}").strip()
                        if sx == "*":
                            mxh_cookies[plat] = []
                        elif sx.isdigit() and 1 <= int(sx) <= len(ck_list):
                            ck_list.pop(int(sx)-1)
                            mxh_cookies[plat] = ck_list
                        cfg["mxh_cookies"] = mxh_cookies; save_cfg(cfg)
                        log("Đã xóa", "ok")
                    time.sleep(1)

    return cfg

# ── Auto Mission ───────────────────────────────────────────────────────────────
def _run_platform_acc(api, platform, pinfo, acc_id, acc_name, mxh_ck,
                      max_job, max_fail, max_wait_no_job,
                      delay_min, delay_max, smart_delay,
                      total_ref, lock,
                      tg_token="", tg_chat="", tg_milestone=0,
                      fb_server="sv2", priority_high=False):
    """Chạy 1 acc trên 1 platform — dùng cho cả serial và parallel."""
    job_done   = 0
    fail_count = 0
    no_job_start = None
    acc_earned = 0.0

    log(f"  ┌─ {acc_name} [{platform}]", "info")

    # ── Facebook ──────────────────────────────────────────────────────────────
    if platform == "facebook":
        log(f"  │  Server: {fb_server}", "info")
        while job_done < max_job:
            if fail_count >= max_fail:
                log(f"  └─ ⚠️  Lỗi {fail_count}/{max_fail} → đổi acc", "warn"); break
            if no_job_start is not None:
                waited = (time.time() - no_job_start) / 60
                if waited >= max_wait_no_job:
                    log(f"  └─ Chờ {waited:.1f}/{max_wait_no_job} phút → đổi acc", "warn"); break

            jobs_batch = api.get_jobs_fb({"fb_id": acc_id}, fb_server)
            if not jobs_batch:
                if priority_high:
                    # Không có job cao → thử lấy job thường
                    jobs_batch = api.get_jobs_fb({"fb_id": acc_id}, fb_server)
                if not jobs_batch:
                    if no_job_start is None:
                        no_job_start = time.time()
                        log(f"  │  Chưa có job — chờ (tối đa {max_wait_no_job} phút)...", "wait")
                    else:
                        waited = (time.time() - no_job_start) / 60
                        log(f"  │  Vẫn chưa có job — đã chờ {waited:.1f}/{max_wait_no_job} phút", "wait")
                    time.sleep(15); continue

            no_job_start = None
            # [FIX #3] Loại bỏ "facebook_like_v1" khỏi SKIP_TYPES — job này được hỗ trợ
            SKIP_TYPES = {"facebook_like_corona_0", "like_page_corona_0"}
            jobs_batch = [j for j in jobs_batch if j.get("type","") not in SKIP_TYPES]
            if not jobs_batch:
                if no_job_start is None: no_job_start = time.time()
                log("  │  Chỉ có job type không hỗ trợ — chờ...", "wait")
                time.sleep(15)
                continue
            jobs_batch.sort(key=lambda j: float(j.get("fix_coin_job", j.get("prices", 0)) or 0), reverse=True)
            log(f"  │  Lấy được {len(jobs_batch)} job (facebook_like_v1 đã được kích hoạt)", "info")

            for job in jobs_batch:
                if job_done >= max_job or fail_count >= max_fail: break
                j_id   = job.get("id")
                if api.is_blacklisted(j_id):
                    log(f"  │  Bỏ qua job #{j_id} (blacklist)", "warn"); continue
                j_type = job.get("type","?")
                react  = job.get("reaction","like")
                reward = float(job.get("fix_coin", job.get("fix_coin_job", job.get("prices", 0))) or 0)
                log(f"  │  📦 #{j_id} | {j_type} | {react} | +{reward:.0f}đ", "job")

                # _private job: server tự xử lý, không cần do_action
                if job.get("_from_private"):
                    ok = True  # server tự xử lý
                else:
                    ok = do_action(platform, job, mxh_ck)
                if not ok:
                    fail_count += 1
                    log(f"  │  Action thất bại ({fail_count}/{max_fail})", "warn")
                    api.skip_job(platform, j_id, acc_id, str(job.get("object_id","")), j_type, {"fb_id": acc_id})
                    time.sleep(random.randint(3,6)); continue

                # Delay 10-25s đã được xử lý bên trong complete_job — không delay thêm ở đây

                result = api.complete_job(platform, j_id, acc_id, {"fb_id": acc_id}, job)
                if result.get("status") == 200 or result.get("success"):
                    data   = result.get("data") or {}
                    earned = float(data.get("fix_coin", data.get("fix_coin_job", data.get("prices", reward))) or reward)
                    job_done += 1; fail_count = 0; acc_earned += earned
                    with lock:
                        total_ref[0] += earned; total_ref[1] += 1
                    log(f"  │  ✅ +{earned:.0f}đ | Phiên: {total_ref[0]:.0f}đ | {total_ref[1]} job", "money")
                    add_stat(acc_id, platform, earned, 1)
                    # In thống kê mỗi 50 job
                    if total_ref[1] % 50 == 0:
                        print_jstats()
                    # Telegram milestone
                    if tg_token and tg_chat and tg_milestone > 0:
                        if int(total_ref[0]) % tg_milestone < int(earned) + 1:
                            tg_notify(tg_token, tg_chat,
                                f"💰 Golike Tool\nĐạt <b>{total_ref[0]:.0f}đ</b> | {total_ref[1]} job\nAcc: {acc_id}")
                else:
                    err_cls  = result.get("_error_class", "")
                    err      = result.get("message", result.get("error","?"))
                    cooldown = result.get("cooldown", 0)
                    status   = result.get("status", 0)

                    if err_cls == "uid_not_performed" or (status == 400 and "chưa thực hiện" in str(err)):
                        # Server xác nhận chưa làm — đổi acc, không tính fail_count
                        log(f"  │  ⚠️  UID chưa thực hiện — đổi acc", "warn")
                        api.skip_job(platform, j_id, acc_id, str(job.get("object_id","")), j_type, {"fb_id": acc_id})
                        break
                    elif err_cls == "system_check":
                        # Bỏ qua job, chuyển job khác, không tăng fail
                        log(f"  │  ⚠️  Hệ thống check lỗi — bỏ job, tiếp tục", "warn")
                        api.blacklist_job(j_id)
                        time.sleep(random.randint(2, 5)); continue
                    elif err_cls == "rate_limit":
                        # Đã retry trong complete_job, vẫn fail → đổi acc
                        log(f"  │  ⚠️  429 liên tục — đổi acc", "warn")
                        break
                    elif cooldown and int(cooldown) > 0:
                        log(f"  │  ⏳ Cooldown {cooldown} phút — đổi acc", "warn")
                        break
                    else:
                        fail_count += 1
                        log(f"  │  ❌ Thất bại ({fail_count}/{max_fail}): {err}", "err")
                        api.blacklist_job(j_id)
                        api.skip_job(platform, j_id, acc_id, str(job.get("object_id","")), j_type, {"fb_id": acc_id})
                time.sleep(random.randint(2,5))

        log(f"  └─ {acc_name}: xong {job_done} job (+{acc_earned:.0f}đ)", "ok")
        return job_done, acc_earned

    # ── Các platform khác ─────────────────────────────────────────────────────
    # Cache plat_acc để truyền vào get_job
    _plat_acc_cache = {}
    try:
        _accs = api.get_accounts(platform)
        for _pa in _accs:
            _plat_acc_cache[str(_pa.get("id",""))] = _pa
            # Thêm key theo username để dễ tìm
            pnf = PLATFORMS[platform].get("private_name_field","")
            if pnf and _pa.get(pnf):
                _plat_acc_cache[str(_pa.get(pnf))] = _pa
    except: pass

    while job_done < max_job:
        if fail_count >= max_fail:
            log(f"  └─ ⚠️  Lỗi {fail_count}/{max_fail} → đổi acc", "warn"); break
        if no_job_start is not None:
            waited = (time.time() - no_job_start) / 60
            if waited >= max_wait_no_job:
                log(f"  └─ Chờ {waited:.1f}/{max_wait_no_job} phút → đổi acc", "warn"); break

        _pa_debug = _plat_acc_cache.get(str(acc_id))
        job = api.get_job(platform, acc_id, _pa_debug)
        if not job:
            if no_job_start is None:
                no_job_start = time.time()
                log(f"  │  Chưa có job — chờ (tối đa {max_wait_no_job} phút)...", "wait")
            else:
                waited = (time.time() - no_job_start) / 60
                log(f"  │  Vẫn chưa có job — đã chờ {waited:.1f}/{max_wait_no_job} phút", "wait")
            time.sleep(15); continue

        no_job_start = None
        ads_id    = job.get("id")
        if api.is_blacklisted(ads_id):
            log(f"  │  Bỏ qua job #{ads_id} (blacklist)", "warn"); continue
        j_type    = job.get("type","?")
        object_id = str(job.get("object_id", job.get("link","")))
        reward    = float(job.get("prices", job.get("price", job.get("coin", 0))) or 0)

        log(f"  │  📦 #{ads_id} | {j_type} | +{reward:.0f}đ", "job")

        # [FIX #5] TikTok _from_private: KHÔNG bỏ qua do_action — cần cookie follow thật
        # Với các platform server-side khác: vẫn bypass an toàn
        bypass_action = (
            job.get("_from_private") and
            not (platform == "tiktok" and "follow" in j_type.lower())
        )
        if bypass_action:
            ok = True
        else:
            ok = do_action(platform, job, mxh_ck)
        if not ok:
            fail_count += 1
            log(f"  │  Action thất bại ({fail_count}/{max_fail})", "warn")
            api.skip_job(platform, ads_id, acc_id, object_id, j_type)
            time.sleep(random.randint(3,6)); continue

        # [FIX #2] TikTok follow — chờ 10-15s để Golike đồng bộ trạng thái follow
        if platform == "tiktok" and "follow" in j_type.lower():
            tiktok_delay = random.randint(10, 15)
            log(f"  │  ⏳ TikTok follow — chờ {tiktok_delay}s đồng bộ hệ thống...", "wait")
            time.sleep(tiktok_delay)

        # Delay 10-25s đã được xử lý bên trong complete_job — không delay thêm ở đây
        result = api.complete_job(platform, ads_id, acc_id, _plat_acc_cache.get(str(acc_id)), job)
        if result.get("status") == 200 or result.get("success"):
            data   = result.get("data") or {}
            earned = float(data.get("fix_coin", data.get("prices", data.get("price", data.get("coin", reward)))) or reward)
            job_done += 1; fail_count = 0; acc_earned += earned
            with lock:
                total_ref[0] += earned; total_ref[1] += 1
            log(f"  │  ✅ +{earned:.0f}đ | Phiên: {total_ref[0]:.0f}đ | {total_ref[1]} job", "money")
            add_stat(acc_id, platform, earned, 1)
            if total_ref[1] % 50 == 0:
                print_jstats()
            if tg_token and tg_chat and tg_milestone > 0:
                if int(total_ref[0]) % tg_milestone < int(earned) + 1:
                    tg_notify(tg_token, tg_chat,
                        f"💰 Golike Tool\nĐạt <b>{total_ref[0]:.0f}đ</b> | {total_ref[1]} job")
        else:
            err_cls  = result.get("_error_class", "")
            err      = result.get("message", result.get("error","?"))
            cooldown = result.get("cooldown", 0)
            status   = result.get("status", 0)

            if err_cls == "uid_not_performed" or (status == 400 and "chưa thực hiện" in str(err)):
                log(f"  │  ⚠️  UID chưa thực hiện — đổi acc", "warn")
                if ads_id and object_id:
                    api.skip_job(platform, ads_id, acc_id, object_id, j_type)
                break
            elif err_cls == "system_check":
                log(f"  │  ⚠️  Hệ thống check lỗi — bỏ job, tiếp tục", "warn")
                api.blacklist_job(ads_id)
                time.sleep(random.randint(2, 5)); continue
            elif err_cls == "rate_limit":
                log(f"  │  ⚠️  429 liên tục — đổi acc", "warn")
                break
            elif cooldown and int(cooldown) > 0:
                log(f"  │  ⏳ Cooldown {cooldown} phút — đổi acc", "warn")
                break
            else:
                fail_count += 1
                log(f"  │  ❌ Thất bại ({fail_count}/{max_fail}): {err}", "err")
                api.blacklist_job(ads_id)
                if ads_id and object_id:
                    api.skip_job(platform, ads_id, acc_id, object_id, j_type)
        time.sleep(random.randint(2,5))

    log(f"  └─ {acc_name}: xong {job_done} job (+{acc_earned:.0f}đ)", "ok")
    return job_done, acc_earned


def auto_mission(cfg: dict):
    clear(); banner()
    print(f"{G}⚡ TỰ ĐỘNG LÀM NHIỆM VỤ — v3.0{RESET}\n")

    accounts = [a for a in cfg.get("accounts",[]) if a.get("active")]
    if not accounts:
        log("Chưa có tài khoản Golike! Vào [9] Setup thêm trước.", "err")
        input(); return

    run_accounts = accounts
    mxh_cookies  = cfg.get("mxh_cookies", {})
    tg_cfg       = cfg.get("telegram", {})
    tg_token     = tg_cfg.get("bot_token","")
    tg_chat      = tg_cfg.get("chat_id","")
    tg_ms        = tg_cfg.get("milestone", 0)

    # Load session cũ làm default
    sess = load_session()

    # Chỉ hỏi 3 thứ quan trọng nhất
    print(f"{B}Platform (Enter=tất cả, fb/ig/yt/tw/th/li/pi/la/tất cả):{RESET} ", end="")
    sel = input().strip().lower()
    alias = {"fb":"facebook","ig":"instagram","yt":"youtube","tw":"twitter",
             "th":"threads","li":"linkedin","pi":"pinterest","la":"lazada"}
    if sel in alias:           selected = [alias[sel]]
    elif sel in PLAT_LIST:     selected = [sel]
    elif sel in ("","0","tất cả","all"): selected = PLAT_LIST[:]
    else:
        parts = [alias.get(x.strip(), x.strip()) for x in sel.split(",")]
        selected = [p for p in parts if p in PLAT_LIST] or PLAT_LIST[:]

    def _q(prompt, default):
        v = input(f"{B}{prompt}{RESET} [{G}{default}{RESET}]: ").strip()
        try: return int(v) if v else default
        except: return default

    max_job         = _q("Job/acc", sess.get("max_job", 50))
    max_rounds      = _q("Vòng lặp (0=∞)", sess.get("max_rounds", 0))

    # Các thông số khác lấy từ session hoặc default cứng
    max_fail        = sess.get("max_fail", 5)
    max_wait_no_job = sess.get("max_wait_no_job", 5)
    delay_min       = sess.get("delay_min", 3)
    delay_max       = sess.get("delay_max", 8)
    parallel        = sess.get("parallel", False)
    smart_delay_on  = True
    priority_high   = True

    # Tự quét acc có cookie cho từng platform
    total_valid = 0
    preview = []
    for golike in run_accounts:
        api = GolikeAPI(golike["auth"], golike.get("g_auth",""), golike.get("device_id",""))
        for platform in selected:
            pinfo     = PLATFORMS[platform]
            plat_accs = api.get_accounts(platform)
            ck_list   = mxh_cookies.get(platform, [])
            valid_cnt = 0
            for pa in plat_accs:
                pa_id  = pa.get("id")
                has_ck = any(str(c.get("acc_id","")) == str(pa_id) for c in ck_list)
                if not pinfo["need_cookie"] or has_ck:
                    valid_cnt += 1
            if valid_cnt:
                preview.append(f"  {G}✅{RESET} {platform:<12} {valid_cnt} acc")
                total_valid += valid_cnt
            else:
                preview.append(f"  {Y}⚠️ {RESET} {platform:<12} 0 acc có cookie — bỏ qua")

    print(f"\n{Y}━━━ SẼ CHẠY ━━━{RESET}")
    for p in preview: print(p)
    print(f"  Job/acc: {G}{max_job}{RESET}  |  Vòng: {G}{'∞' if not max_rounds else max_rounds}{RESET}")
    print(f"{Y}━━━━━━━━━━━━━━━{RESET}")

    if total_valid == 0:
        log("Không có acc hợp lệ nào — thêm cookie trước!", "err")
        input(); return

    print(f"\n{B}Bắt đầu? (Enter=yes, n=no): {RESET}", end="")
    if input().strip().lower() == "n": return

    save_session({
        "_desc": f"{', '.join(selected)} | {max_job} job/acc",
        "max_job": max_job, "max_fail": max_fail,
        "max_wait_no_job": max_wait_no_job, "max_rounds": max_rounds,
        "delay_min": delay_min, "delay_max": delay_max,
        "selected": selected, "parallel": parallel,
    })

    total_ref  = [0.0, 0]
    lock       = threading.Lock()
    start_time = time.time()
    print(f"\n{DIM}Ctrl+C để dừng{RESET}\n")

    try:
        round_num = 0
        while True:
            round_num += 1
            if max_rounds > 0 and round_num > max_rounds:
                log(f"Đã đủ {max_rounds} vòng — dừng.", "ok"); break

            log(f"{'━'*42}", "info")
            log(f"🔄 Vòng #{round_num}{' / '+str(max_rounds) if max_rounds else ''}", "info")

            for golike in run_accounts:
                api     = GolikeAPI(golike["auth"], golike.get("g_auth",""), golike.get("device_id",""))
                api._job_blacklist = set()  # reset blacklist mỗi vòng
                gl_name = golike.get("username", golike["name"])
                log(f"Golike: {gl_name}", "info")

                fb_server = api.get_fb_server() if "facebook" in selected else "sv2"

                for platform in selected:
                    pinfo     = PLATFORMS[platform]
                    plat_accs = api.get_accounts(platform)
                    if not plat_accs:
                        log(f"Không có acc {platform}", "warn"); continue

                    ck_list = mxh_cookies.get(platform, [])

                    def get_ck(pa_id, _ck=ck_list):
                        for ck in _ck:
                            if str(ck.get("acc_id","")) == str(pa_id):
                                return ck
                        return None

                    # Tự động chọn tất cả acc hợp lệ — không hỏi
                    valid = []
                    for pa in plat_accs:
                        pa_id  = pa.get("id")
                        pname  = get_acc_name(pa, platform)
                        ck_ent = get_ck(pa_id)
                        ck     = ck_ent.get("cookie","") if ck_ent else ""
                        if pinfo["need_cookie"] and not ck:
                            continue  # bỏ qua silently
                        valid.append((pa_id, pname, ck))

                    if not valid:
                        log(f"  {platform}: không có acc có cookie", "warn"); continue

                    log(f"  {platform}: {len(valid)} acc", "ok")

                    if parallel and len(valid) > 1:
                        threads = []
                        for acc_id, acc_name, mxh_ck in valid:
                            t = threading.Thread(
                                target=_run_platform_acc,
                                args=(api, platform, pinfo, acc_id, acc_name, mxh_ck,
                                      max_job, max_fail, max_wait_no_job,
                                      delay_min, delay_max, smart_delay_on,
                                      total_ref, lock,
                                      tg_token, tg_chat, tg_ms,
                                      fb_server, priority_high),
                                daemon=True
                            )
                            threads.append(t); t.start()
                            time.sleep(1)
                        for t in threads: t.join()
                    else:
                        for acc_id, acc_name, mxh_ck in valid:
                            _run_platform_acc(
                                api, platform, pinfo, acc_id, acc_name, mxh_ck,
                                max_job, max_fail, max_wait_no_job,
                                delay_min, delay_max, smart_delay_on,
                                total_ref, lock,
                                tg_token, tg_chat, tg_ms,
                                fb_server, priority_high
                            )

            log(f"🔄 Xong vòng #{round_num} — nghỉ 10s...", "info")
            if max_rounds > 0 and round_num >= max_rounds: break
            time.sleep(10)

    except KeyboardInterrupt:
        print(f"\n{Y}Đã dừng!{RESET}")

    elapsed = time.time() - start_time
    print(f"\n{G}━━━ KẾT THÚC ━━━{RESET}")
    print(f"  Tổng kiếm được:      {G}{total_ref[0]:.0f}đ{RESET}")
    print(f"  Tổng job hoàn thành: {G}{total_ref[1]}{RESET}")
    print(f"  Thời gian chạy:      {G}{elapsed/3600:.1f}h{RESET}")
    print_jstats()
    if tg_token and tg_chat:
        tg_notify(tg_token, tg_chat,
            f"✅ Golike Tool kết thúc\n💰 <b>{total_ref[0]:.0f}đ</b> | {total_ref[1]} job\n⏱ {elapsed/3600:.1f}h")
    input(f"\n{DIM}Enter để tiếp tục...{RESET}")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    cfg = load_cfg()

    while True:
        try:
            clear(); banner()
            accounts = [a for a in cfg.get("accounts",[]) if a.get("active")]
            mxh_ck   = cfg.get("mxh_cookies", {})

            # Header info — refresh coin từ API
            if accounts:
                for a in accounts:
                    try:
                        _api = GolikeAPI(a["auth"], a.get("g_auth",""), a.get("device_id",""))
                        _u   = _api.get_user()
                        if _u and _u.get("coin") is not None:
                            a["coin"] = _u.get("coin", a.get("coin", 0))
                    except: pass
                save_cfg(cfg)
                total = sum(float(a.get("coin",0) or 0) for a in accounts)
                print(f"  {G}✅ {len(accounts)} tài khoản Golike | Tổng: {total:.0f}đ{RESET}")
                for a in accounts[:3]:
                    print(f"     • {a.get('username',a['name'])} — {G}{a.get('coin','?')}đ{RESET}")
                if len(accounts) > 3:
                    print(f"     ... và {len(accounts)-3} tài khoản khác")
            else:
                print(f"  {Y}⚠️  Chưa có tài khoản — vào [9] Setup để thêm{RESET}")

            # Hiện cookie status
            has_ck = [p for p in PLAT_LIST if mxh_ck.get(p)]
            if has_ck:
                print(f"  {B}🍪 Cookie MXH: {', '.join(has_ck)}{RESET}")
            print()

            print(f"  {G}[1]{RESET} ⚡ Tự động làm nhiệm vụ kiếm tiền")
            print(f"  {G}[2]{RESET} 📊 Thống kê xu theo ngày/acc/platform")
            print(f"  {G}[3]{RESET} 🔔 Cài đặt Telegram notify")
            print(f"  {G}[4]{RESET} 💰 Kiểm tra số dư")
            print(f"  {G}[5]{RESET} 📱 Xem tài khoản MXH đã thêm")
            print(f"  {G}[9]{RESET} ⚙️  Quản lý tài khoản & Cookie")
            dbg = f"{G}BẬT{RESET}" if DEBUG_MODE[0] else f"{R}TẮT{RESET}"
            print(f"  {G}[8]{RESET} 🔍 Debug Mode [{dbg}]")
            print(f"  {G}[0]{RESET} 🚪 Thoát\n")

            choice = input(f"{G}Chọn chức năng: {RESET}").strip()

            if   choice == "1": auto_mission(cfg)
            elif choice == "2":
                clear(); banner()
                print(f"{G}📊 THỐNG KÊ XU{RESET}\n")
                show_stats()
                input(f"\n{DIM}Enter để tiếp tục...{RESET}")
            elif choice == "3":
                clear(); banner()
                print(f"{G}🔔 TELEGRAM NOTIFY{RESET}\n")
                tg_token = input(f"{B}Bot token (Enter bỏ qua): {RESET}").strip()
                if tg_token:
                    tg_chat = input(f"{B}Chat ID: {RESET}").strip()
                    try: tg_ms = int(input(f"{B}Thông báo mỗi N đồng (0=tắt): {RESET}").strip() or "0")
                    except: tg_ms = 0
                    cfg["telegram"] = {"bot_token": tg_token, "chat_id": tg_chat, "milestone": tg_ms}
                    save_cfg(cfg)
                    tg_notify(tg_token, tg_chat, "✅ Golike Tool — Kết nối Telegram thành công!")
                    log("Đã lưu cài đặt Telegram", "ok")
                time.sleep(1)
            elif choice == "4":
                clear(); banner()
                print(f"{G}💰 KIỂM TRA SỐ DƯ{RESET}\n")
                accounts = cfg.get("accounts", [])
                for a in accounts:
                    api = GolikeAPI(a["auth"], a.get("g_auth",""), a.get("device_id",""))
                    user = api.get_user()
                    if user:
                        coin    = user.get("coin", 0)
                        pending = user.get("_pending", 0)
                        uname   = user.get("username", a.get("username","?"))
                        a["coin"] = coin
                        print(f"  {G}✅{RESET} {uname:<20} {G}{coin:.0f}đ{RESET} (chờ duyệt: {Y}{pending:.0f}đ{RESET})")
                    else:
                        print(f"  {R}❌{RESET} {a.get('username', a['name'])}: lỗi kết nối")
                save_cfg(cfg)
                input(f"\n{DIM}Enter để tiếp tục...{RESET}")
            elif choice == "5":
                clear(); banner()
                print(f"{G}📱 TÀI KHOẢN MXH ĐÃ THÊM{RESET}\n")
                accounts = cfg.get("accounts", [])
                if not accounts:
                    print(f"  {Y}Chưa có tài khoản Golike{RESET}")
                else:
                    api = GolikeAPI(accounts[0]["auth"], accounts[0].get("g_auth",""), accounts[0].get("device_id",""))
                    for p in PLAT_LIST:
                        accs = api.get_accounts(p)
                        if accs:
                            print(f"\n  {B}{p.upper()}{RESET} ({len(accs)} acc):")
                            for pa in accs:
                                name = get_acc_name(pa, p)
                                jobs = pa.get("counter_jobs_today", 0)
                                print(f"    • {name:<25} {jobs} job hôm nay")
                input(f"\n{DIM}Enter để tiếp tục...{RESET}")
            elif choice == "9": cfg = setup(cfg)
            elif choice == "8":
                DEBUG_MODE[0] = not DEBUG_MODE[0]
                log(f"Debug Mode: {'BẬT' if DEBUG_MODE[0] else 'TẮT'}", "info")
                time.sleep(1)
            elif choice == "0":
                print(f"\n{G}Tạm biệt! 👋{RESET}\n"); break
            else:
                log("Lựa chọn không hợp lệ!", "warn"); time.sleep(1)

        except KeyboardInterrupt:
            print(f"\n{Y}Nhấn 0 để thoát hoặc Enter để tiếp tục{RESET}\n")
            time.sleep(1)

if __name__ == "__main__":
    main()
