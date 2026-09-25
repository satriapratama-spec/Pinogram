import os
import re
import sqlite3
import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="public", static_url_path="")

DEFAULT_BOT_TOKEN = "8973070744:AAG1Xgxt9rnkR2wHMOuRUGcYWrlSIVrCIxc"
OWNER_ID = 8338766322
TARGET_GROUP_ID = -1004418845797

DB_NAME = "pinogram.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT,
                    sender_name TEXT,
                    text TEXT,
                    direction TEXT,
                    is_otp INTEGER DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    return send_from_directory("public", "index.html")

# Endpoint Verifikasi Token Bot (Langsung Masuk Tanpa OTP)
@app.route("/api/verify-token", methods=["POST"])
def verify_token():
    data = request.get_json() or {}
    token = data.get("token", "").strip()
    
    if not token:
        return jsonify({"status": "failed", "message": "Token tidak boleh kosong!"}), 400

    # Test token ke Telegram API (getMe)
    test_resp = requests.get(f"https://api.telegram.org/bot{token}/getMe")
    if test_resp.status_code != 200:
        return jsonify({"status": "failed", "message": "Token Bot Telegram tidak valid!"}), 400

    return jsonify({"status": "success", "token": token})

# Webhook Telegram
@app.route(f"/webhook/{DEFAULT_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json() or {}
    if "message" in data:
        msg = data["message"]
        chat = msg["chat"]
        chat_id = chat["id"]
        sender = msg.get("from", {})
        sender_name = sender.get("first_name", "Unknown")
        text = msg.get("text", "[Media / Non-Text]")

        if chat_id == TARGET_GROUP_ID or sender.get("id") == OWNER_ID:
            save_message(chat_id, f"{sender_name} ({'Grup' if chat_id < 0 else 'Private'})", text, "in")

    return jsonify({"status": "ok"}), 200

def save_message(chat_id, sender_name, text, direction):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    match = re.search(r'\b\d{4,6}\b', text)
    is_otp = 1 if ('otp' in text.lower() or match) else 0
    c.execute("INSERT INTO messages (chat_id, sender_name, text, direction, is_otp) VALUES (?, ?, ?, ?, ?)",
              (str(chat_id), sender_name, text, direction, is_otp))
    conn.commit()
    conn.close()

@app.route("/api/chats", methods=["GET"])
def get_chats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT DISTINCT chat_id, sender_name FROM messages ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"chat_id": r[0], "name": r[1]} for r in rows])

@app.route("/api/messages/<chat_id>", methods=["GET"])
def get_messages(chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT text, direction, timestamp, sender_name, is_otp FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return jsonify([{"text": r[0], "direction": r[1], "time": r[2], "sender": r[3], "is_otp": r[4]} for r in rows])

@app.route("/api/send", methods=["POST"])
def send_message():
    data = request.get_json() or {}
    chat_id = data.get("chat_id")
    text = data.get("text")
    token = data.get("token", DEFAULT_BOT_TOKEN)

    payload = {"chat_id": chat_id, "text": text}
    resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)

    if resp.status_code == 200:
        save_message(chat_id, "Pinogram Admin", text, "out")
        return jsonify({"status": "success"})
    return jsonify({"status": "failed", "error": resp.text}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
