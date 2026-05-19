import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "webook_bot.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            joined_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_slug TEXT NOT NULL,
            event_title TEXT,
            UNIQUE(user_id, event_slug),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS booking_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_slug TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS user_prefs (
            user_id INTEGER PRIMARY KEY,
            phone TEXT,
            email TEXT,
            webook_email TEXT,
            webook_password TEXT,
            notifications INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS webook_auth_tokens (
            user_id INTEGER PRIMARY KEY,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            api_user TEXT,
            guid TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS seen_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_slug TEXT NOT NULL UNIQUE,
            first_seen TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()

def add_user(user_id, first_name, username):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
        (user_id, first_name, username),
    )
    conn.commit()
    conn.close()

def subscribe(user_id, event_slug, event_title=""):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO subscriptions (user_id, event_slug, event_title) VALUES (?, ?, ?)",
            (user_id, event_slug, event_title),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def unsubscribe(user_id, event_slug=None):
    conn = get_connection()
    if event_slug:
        conn.execute(
            "DELETE FROM subscriptions WHERE user_id = ? AND event_slug = ?",
            (user_id, event_slug),
        )
    else:
        conn.execute(
            "DELETE FROM subscriptions WHERE user_id = ?", (user_id,)
        )
    conn.commit()
    conn.close()

def is_subscribed(user_id, event_slug):
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM subscriptions WHERE user_id = ? AND event_slug = ?",
        (user_id, event_slug),
    ).fetchone()
    conn.close()
    return row is not None

def get_user_subscriptions(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT event_slug, event_title FROM subscriptions WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return [{"slug": r["event_slug"], "title": r["event_title"]} for r in rows]

def get_event_subscribers(event_slug):
    conn = get_connection()
    rows = conn.execute(
        """SELECT DISTINCT u.user_id, u.first_name, u.username
           FROM subscriptions s
           JOIN users u ON u.user_id = s.user_id
           WHERE s.event_slug = ?""",
        (event_slug,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_booking_request(user_id, event_slug, email="", phone=""):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO booking_requests (user_id, event_slug, email, phone) VALUES (?, ?, ?, ?)",
        (user_id, event_slug, email, phone),
    )
    conn.commit()
    request_id = cursor.lastrowid
    conn.close()
    return request_id

def get_prefs(user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM user_prefs WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        "user_id": user_id,
        "phone": None,
        "email": None,
        "webook_email": None,
        "webook_password": None,
        "notifications": 1,
    }


def set_pref(user_id, key, value):
    prefs = get_prefs(user_id)
    keys = {"phone", "email", "webook_email", "webook_password", "notifications"}
    if key in keys:
        prefs[key] = value
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO user_prefs
           (user_id, phone, email, webook_email, webook_password, notifications, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            user_id,
            prefs.get("phone"),
            prefs.get("email"),
            prefs.get("webook_email"),
            prefs.get("webook_password"),
            prefs.get("notifications", 1),
        ),
    )
    conn.commit()
    conn.close()


def save_webook_token(user_id, access_token, refresh_token="", api_user="", guid=""):
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO webook_auth_tokens
           (user_id, access_token, refresh_token, api_user, guid, updated_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))""",
        (user_id, access_token, refresh_token, api_user, guid),
    )
    conn.commit()
    conn.close()


def get_webook_token(user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM webook_auth_tokens WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def mark_event_seen(event_slug):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO seen_events (event_slug) VALUES (?)",
        (event_slug,),
    )
    conn.commit()
    conn.close()

def is_event_seen(event_slug):
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM seen_events WHERE event_slug = ?", (event_slug,)
    ).fetchone()
    conn.close()
    return row is not None
