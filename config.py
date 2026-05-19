import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
admin_val = os.getenv("ADMIN_CHAT_ID", "0")
ADMIN_CHAT_ID = int(admin_val) if admin_val and admin_val.strip() else None
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))

WEBOOK_API_BASE = "https://api.webook.com/api/v1"
WEBOOK_DEVICE_TOKEN = os.getenv("WEBOOK_DEVICE_TOKEN", "")
WEBOOK_BEARER_TOKEN = os.getenv("WEBOOK_BEARER_TOKEN", "")

HAS_API_TOKEN = bool(WEBOOK_DEVICE_TOKEN and len(WEBOOK_DEVICE_TOKEN) > 10)

# Hardcoded fallback data (works without API token)
ORGANIZATIONS = [
    {"slug": "spl", "name": {"ar": "الدوري السعودي للمحترفين", "en": "SPL"}},
    {"slug": "riyadh-season", "name": {"ar": "موسم الرياض", "en": "Riyadh Season"}},
    {"slug": "jeddah-season", "name": {"ar": "موسم جدة", "en": "Jeddah Season"}},
    {"slug": "saudi-grand-prix", "name": {"ar": "جائزة السعودية الكبرى", "en": "Saudi GP"}},
]

SPL_TEAMS = [
    "الهلال", "النصر", "الاتحاد", "الأهلي", "الشباب",
    "الاتفاق", "الفيحاء", "الخليج", "التعاون", "الرائد",
    "الطائي", "أبها", "ضمك", "الوحدة", "الباطن",
]

EVENT_CATEGORIES = [
    "⚽ مباريات كرة قدم",
    "🎵 حفلات ومهرجانات",
    "🎪 فعاليات ترفيهية",
    "🏎️ سباقات وفعاليات رياضية",
    "🎭 مسرح وعروض",
]
