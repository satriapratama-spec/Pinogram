import os
import re
import sqlite3
import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(
    __name__, static_folder="public", static_url_path=""
)

# Konfigurasi Pinogram
BOT_TOKEN = "8177708983:AAFb_47Nv0qakggXC6ZXoyaGjn54fNXkA5U"
OWNER_ID = 8338766322
TARGET_GROUP_ID = -1004418845797
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

DB_NAME = "pinogram.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT,
                    sender_name TEXT,
                    text TEXT,
                    direction TEXT,
                    is_otp INTEGER DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )""")
    conn.commit()
    conn.close()


init_db()


def check_is_otp(text):
    # Deteksi otomatis jika teks mengandung kata OTP atau pola 4-6 digit angka
    if not text:
        return 0
    match = re.search(r"\b\d{4,6}\b", text)
    if "otp" in text.lower() or match:
        return 1
    return 0


def save_message(chat_id, sender_name, text, direction):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    is_otp = check_is_otp(text)
    c.execute(
        "INSERT INTO messages (chat_id, sender_name, text, direction, is_otp) VALUES (?, ?, ?, ?, ?)",
        (str(chat_id), sender_name, text, direction, is_otp),
    )
    conn.commit()
    conn.close()


# Serve Frontend
@app.route("/")
def index():
    return send_from_directory("public", "index.html")


# Webhook Telegram
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if "message" in data:
        msg = data["message"]
        chat = msg["chat"]
        chat_id = chat["id"]
        sender = msg.get("from", {})
        sender_name = sender.get("first_name", "Unknown")
        text = msg.get("text", "[Media / Non-Text]")

        # Filter keamanan: Hanya izinkan Owner atau Grup OTP yang ditentukan
        if chat_id == TARGET_GROUP_ID or sender.get("id") == OWNER_ID:
            save_message(
                chat_id,
                f"{sender_name} ({'Grup' if chat_id < 0 else 'Private'})",
                text,
                "in",
            )

    return jsonify({"status": "ok"}), 200


# API Chat List
@app.route("/api/chats", methods=["GET"])
def get_chats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT DISTINCT chat_id, sender_name FROM messages ORDER BY id DESC"
    )
    rows = c.fetchall()
    conn.close()

    chats = [{"chat_id": r[0], "name": r[1]} for r in rows]
    return jsonify(chats)


# API Message History
@app.route("/api/messages/<chat_id>", methods=["GET"])
def get_messages(chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT text, direction, timestamp, sender_name, is_otp FROM messages WHERE chat_id = ? ORDER BY id ASC",
        (chat_id,),
    )
    rows = c.fetchall()
    conn.close()

    msgs = [
        {
            "text": r[0],
            "direction": r[1],
            "time": r[2],
            "sender": r[3],
            "is_otp": r[4],
        }
        for r in rows
    ]
    return jsonify(msgs)


# API Send Message
@app.route("/api/send", methods=["POST"])
def send_message():
    data = request.get_json()
    chat_id = data.get("chat_id")
    text = data.get("text")

    payload = {"chat_id": chat_id, "text": text}
    resp = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

    if resp.status_code == 200:
        save_message(chat_id, "Pinogram Admin", text, "out")
        return jsonify({"status": "success"})
    return jsonify({"status": "failed", "error": resp.text}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
