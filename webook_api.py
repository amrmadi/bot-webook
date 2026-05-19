import logging

import requests as req

from config import (
    WEBOOK_API_BASE,
    WEBOOK_DEVICE_TOKEN,
    WEBOOK_BEARER_TOKEN,
    HAS_API_TOKEN,
    ORGANIZATIONS,
    SPL_TEAMS,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://webook.com/",
    "Origin": "https://webook.com",
    "token": WEBOOK_DEVICE_TOKEN,
}


def _auth_headers():
    h = dict(HEADERS)
    if WEBOOK_BEARER_TOKEN:
        h["Authorization"] = f"Bearer {WEBOOK_BEARER_TOKEN}"
    return h


def safe_json(response):
    try:
        return response.json()
    except Exception:
        return {}


def list_organizations():
    if not HAS_API_TOKEN:
        return list(ORGANIZATIONS), None

    url = f"{WEBOOK_API_BASE}/organizations"
    try:
        r = req.get(url, headers=_auth_headers(), timeout=20)
        if r.status_code == 200:
            data = safe_json(r)
            orgs = data if isinstance(data, list) else data.get("data", data.get("organizations", []))
            if orgs:
                return orgs, None
        logger.warning(f"API list_organizations failed ({r.status_code}), using fallback")
    except Exception as e:
        logger.warning(f"API list_organizations error: {e}, using fallback")

    return list(ORGANIZATIONS), None


def filter_events(org_slug, lang="ar", per_page=50):
    if not HAS_API_TOKEN:
        return _fallback_events(org_slug), None

    url = f"{WEBOOK_API_BASE}/filter/events/{org_slug}"
    params = {"lang": lang, "per_page": per_page}
    try:
        r = req.get(url, headers=_auth_headers(), params=params, timeout=20)
        if r.status_code == 200:
            data = safe_json(r)
            events = data if isinstance(data, list) else data.get("data", data.get("events", []))
            if events:
                return events, None
    except Exception as e:
        logger.warning(f"API filter_events error: {e}")

    return _fallback_events(org_slug), None


def _fallback_events(org_slug):
    fallback = {
        "spl": [
            {
                "slug": "spl-match-1",
                "name": {"ar": "مباراة الهلال × النصر - الدوري السعودي", "en": "Al Hilal vs Al Nassr - SPL"},
                "startDate": "2026-05-25T20:00:00+03:00",
                "venue": {"name": {"ar": "استاد الملك فهد الدولي"}},
                "description": {"ar": "قمة الكرة السعودية في دوري روشن للمحترفين."},
            },
            {
                "slug": "spl-match-2",
                "name": {"ar": "مباراة الاتحاد × الأهلي - الدوري السعودي", "en": "Al Ittihad vs Al Ahli - SPL"},
                "startDate": "2026-05-26T21:00:00+03:00",
                "venue": {"name": {"ar": "استاد الأمير عبدالله الفيصل"}},
                "description": {"ar": "ديربي جدة في دوري روشن للمحترفين."},
            },
            {
                "slug": "spl-match-3",
                "name": {"ar": "مباراة الشباب × الاتفاق", "en": "Al Shabab vs Al Ettifaq"},
                "startDate": "2026-05-27T19:00:00+03:00",
                "venue": {"name": {"ar": "استاد الأمير فيصل بن فهد"}},
                "description": {"ar": "مباراة قوية في دوري روشن."},
            },
        ],
        "riyadh-season": [
            {
                "slug": "riyadh-season-1",
                "name": {"ar": "موسم الرياض 2026 - فعاليات متنوعة", "en": "Riyadh Season 2026"},
                "startDate": "2026-10-01T00:00:00+03:00",
                "venue": {"name": {"ar": "منطقة موسم الرياض"}},
                "description": {"ar": "أكبر مهرجان ترفيهي في المملكة."},
            },
        ],
        "jeddah-season": [
            {
                "slug": "jeddah-season-1",
                "name": {"ar": "موسم جدة 2026", "en": "Jeddah Season 2026"},
                "startDate": "2026-06-01T00:00:00+03:00",
                "venue": {"name": {"ar": "منطقة موسم جدة"}},
                "description": {"ar": "موسم مليء بالفعاليات الترفيهية في جدة."},
            },
        ],
        "saudi-grand-prix": [
            {
                "slug": "saudi-gp-2026",
                "name": {"ar": "جائزة السعودية الكبرى للفورمولا 1 2026", "en": "Saudi Arabian GP 2026"},
                "startDate": "2026-12-04T00:00:00+03:00",
                "venue": {"name": {"ar": "حلبة كورنيش جدة"}},
                "description": {"ar": "سباق جائزة السعودية الكبرى للفورمولا 1 على حلبة كورنيش جدة."},
            },
        ],
    }
    return fallback.get(org_slug, [])


def get_event_detail(slug):
    if not HAS_API_TOKEN:
        return _fallback_event_detail(slug), None

    url = f"{WEBOOK_API_BASE}/event-detail/{slug}"
    try:
        r = req.get(url, headers=_auth_headers(), timeout=20)
        if r.status_code == 200:
            data = safe_json(r)
            if data:
                return data, None
    except Exception as e:
        logger.warning(f"API get_event_detail error: {e}")

    return _fallback_event_detail(slug), None


def _fallback_event_detail(slug):
    for org_events in _fallback_events("spl") + _fallback_events("riyadh-season") + _fallback_events("jeddah-season") + _fallback_events("saudi-grand-prix"):
        if org_events.get("slug") == slug:
            return org_events
    return {"name": {"ar": slug}, "description": {"ar": "تفاصيل الفعالية غير متاحة حالياً."}}


def get_event_ticket_details(slug):
    return {"priceRanges": [{"price": "يبدأ من 50 ريال"}]}, None


def list_teams():
    if HAS_API_TOKEN:
        url = f"{WEBOOK_API_BASE}/teams/list"
        try:
            r = req.get(url, headers=_auth_headers(), timeout=20)
            if r.status_code == 200:
                data = safe_json(r)
                teams = data if isinstance(data, list) else data.get("data", data.get("teams", []))
                if teams:
                    return teams, None
        except Exception:
            pass

    return [{"id": str(i), "name": t} for i, t in enumerate(SPL_TEAMS)], None


def get_team_events(team_id):
    if HAS_API_TOKEN:
        url = f"{WEBOOK_API_BASE}/team/{team_id}/events"
        try:
            r = req.get(url, headers=_auth_headers(), timeout=20)
            if r.status_code == 200:
                data = safe_json(r)
                events = data if isinstance(data, list) else data.get("data", data.get("events", []))
                if events:
                    return events, None
        except Exception:
            pass

    team_events_map = {
        "0": _fallback_events("spl")[0:1],
        "1": _fallback_events("spl")[0:1],
        "2": _fallback_events("spl")[1:2],
        "3": _fallback_events("spl")[1:2],
        "4": _fallback_events("spl")[2:3],
        "5": _fallback_events("spl")[2:3],
    }
    return team_events_map.get(team_id, []), None


def login(fan_id, password):
    if not HAS_API_TOKEN:
        return None, "مطلوب Webook Device Token أولاً. راسل api-support@webook.com"

    url = f"{WEBOOK_API_BASE}/register-login"
    payload = {"Username": fan_id, "Password": password}
    try:
        r = req.post(url, json=payload, headers=_auth_headers(), timeout=20)
        if r.status_code == 200:
            data = safe_json(r)
            token = data.get("access_token") or data.get("token", "")
            refresh = data.get("refresh_token", "")
            api_user = data.get("fanId", data.get("user", {}).get("id", ""))
            guid = data.get("guid", "")
            if token:
                return {
                    "access_token": token,
                    "refresh_token": refresh,
                    "api_user": api_user,
                    "guid": guid,
                }, None
            return None, "استجابة غير متوقعة"
        elif r.status_code == 401:
            return None, "البريد الإلكتروني أو كلمة السر غير صحيحة"
        elif r.status_code == 429:
            return None, "تم حظر الطلب مؤقتاً (كثرة المحاولات)"
        else:
            return None, f"خطأ في الخادم: {r.status_code}"
    except Exception as e:
        logger.error(f"login Error: {e}")
        return None, str(e)
