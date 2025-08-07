import websocket
import threading
import time
import json
import requests  # Added
from datetime import datetime
import html
import os
import logging
from flask import Flask, Response


# -------------------- CONFIG --------------------

WS_URL = "wss://ivasms.com:2087/socket.io/?token=eyJpdiI6InNIZVhWMEhpc0FZMG5SOWRjRjVuamc9PSIsInZhbHVlIjoiVTFQbTRlWVFDVUsvZFNhTS94QnozT0diRnA2QVh3ODVJdFExbDdha3ZXMTB4ZGJLUmNwd202NWpETDB3SzJpeWZtcTliZlRobmovKzZnWTJTVUI3eGJnczBvcUNQMC9hMmExVSsxNVlHaXp1SGx0NVdWTjNwd1FsUStOWThYc0NGVHRDcTNSaW94RVUwUjUzbWx3d0llN2lvYVBjbXBzYmNIMmlvcTBSTjBGQzFRd2NWN1huOW5vYjBPN25jSXlsSXBpV1I0ZmdVd25hemxoNFU2djRnMFBKYnNNaElueGVaT0lwMHlNYzhXQzNqVlRYajcxc080WjFsWUU5SkE3K1BmL2dQQWhKYzNZUFpWYWM0TXdhUmE4TXhKVXJCclg5Mk52WGpmWlpXaVJLTTMyaFdrbUtyNWUxVmNnSVU5NFpralBwc0pKeTdOWkJoU2ovQ2E3RTZ4VlVKYVJyaENjb0k4WHZuUDBMU011N0pFMG00WVJQZEVvdlVBcjd0ckNUaldPYWZQSmVWZUVnVUJJVWNUakxiYXFRQ2RRSytnSjZqTW5uZEpXeVNCb0FIK2lISVBPaXNGbkdmcndZU3RjN1VSV0JtL2hwdGk4NDhQekRrQ1VBRFJucklFL0pGczlUVlA0cU9NMmFwWnRJWWFDdzlwaUpFa29BTFMvcWh4OFp1bEdiRG1VMHBPaVFZRGo0ZnYxNGxnPT0iLCJtYWMiOiJmMDJhYWE0MmJiNzA5Y2JjNWNjZWUxNWM1MjllMmU0YTNhYjcwM2IzMzhmMTg3YzQ3Y2NmYzAwNjUwYzYwZGM4IiwidGFnIjoiIn0%3D&user=8d75eedc6d2833853cf8fea9790e711a&EIO=4&transport=websocket"  # replace this

AUTH_MESSAGE = '42/livesms,["eyJpdiI6..."]'  # ⚠️ YOUR LIVE TOKEN
PING_INTERVAL = 150
start_pinging = False
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("otp_forwarder")

# ------------------- TELEGRAM --------------------

BOT_TOKEN = "7905683098:AAGsm8_qFqxMcRYotSGZVXg0Ags6ZvueD20"
GROUP_ID = "-1002311125652"
CHANNEL_URL = "https://t.me/ddxotp"
DEV_URL = "https://t.me/Vxxwo"

def send_to_telegram(text):
    buttons = {
        "inline_keyboard": [
            [
                {"text": "📢 Channel", "url": CHANNEL_URL},
                {"text": "👨‍💻 Developer", "url": DEV_URL}
            ]
        ]
    }

    payload = {
        "chat_id": GROUP_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(buttons)
    }

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=payload
        )
        if response.status_code != 200:
            print("⚠️ Telegram Error:", response.text)
    except Exception as e:
        print("❌ Telegram Send Failed:", e)

# -------------------- FUNCTIONS --------------------

def send_ping(ws):
    global start_pinging
    while ws.keep_running:
        if start_pinging:
            try:
                ws.send("2")
                print("📡 Ping sent (2)")
            except Exception as e:
                print("❌ Failed to send ping:", e)
                break
        time.sleep(PING_INTERVAL)

def on_open(ws):
    global start_pinging
    start_pinging = False
    print("✅ WebSocket connected")

    time.sleep(0.5)
    ws.send("40/livesms")
    print("➡️ Sent: 40/livesms (namespace join)")

    time.sleep(0.5)
    ws.send(AUTH_MESSAGE)
    print(f"🔐 Sent auth: {AUTH_MESSAGE[:60]}...")

    threading.Thread(target=send_ping, args=(ws,), daemon=True).start()

def on_message(ws, message):
    global start_pinging
    if message == "3":
        print("✅ Pong received (3)")
    elif message.startswith("40/livesms"):
        print("✅ Namespace joined successfully — starting ping now")
        start_pinging = True
    elif message.startswith("42/livesms,"):
        try:
            payload = message[len("42/livesms,"):]
            data = json.loads(payload)

            if isinstance(data, list) and len(data) > 1 and isinstance(data[1], dict):
                sms = data[1]
                raw_msg = sms.get("message", "")
                originator = sms.get("originator", "Unknown")
                recipient = sms.get("recipient", "Unknown")
                country = sms.get("country_iso", "??").upper()
                revenue = sms.get("client_revenue", "N/A")

                import re
                otp_match = re.search(r'\b\d{3}[- ]?\d{3}\b|\b\d{6}\b', raw_msg)
                otp = otp_match.group(0) if otp_match else "N/A"

                formatted_number = recipient[:-4].replace(recipient[:-4], '⁕' * (len(recipient[:-4]))) + recipient[-4:]

                country_flags = {"CI": "🇨🇮", "IN": "🇮🇳", "US": "🇺🇸"}
                flag = country_flags.get(country, "🌐")

                now = datetime.now().strftime("%H:%M:%S")
                service = "WhatsApp" if "whatsapp" in raw_msg.lower() else "Unknown"

                # Print to console (unchanged)
                print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f"🔔 𝐎𝐓𝐏 𝐑𝐞𝐜𝐞𝐢𝐯𝐞𝐝...{country}")
                print()
                print(f"🔑 𝐘𝐨𝐮𝐫 𝐎𝐓𝐏 : {otp}")
                print(f"🕒 𝚃𝚒𝚖𝚎 : {now}")
                print(f"⚙️ 𝚂𝚎𝚛𝚟𝚒𝚌𝚎 : {originator}")
                print(f"☎️ 𝙽𝚞𝚖𝚋𝚎𝚛 : {recipient[:5]}{formatted_number}")
                print()
                print(f"{raw_msg}")
                print()
                print("📃 Yaara Teri Yaari ")
                print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print("👨🏾‍💻 Owner: Vasu🤖")
                print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

                # 📨 Send to Telegram
                telegram_msg = (
                    f"🔔 𝐎𝐓𝐏 𝐑𝐞𝐜𝐞𝐢𝐯𝐞𝐝...{country}\n"
                    f"🔑 <b>OTP</b>: <code>{otp}</code>\n"
                    f"🕒 <b>Time</b>: {now}\n"
                    f"⚙️ <b>Service</b>: {originator}\n"
                    f"☎️ <b>Number</b>: {recipient[:5]}{formatted_number}\n\n"
                    f"{html.escape(raw_msg)}"

                )
                send_to_telegram(telegram_msg)

            else:
                print("⚠️ Unknown data format:", data)

        except Exception as e:
            print("❌ Error parsing message:", e)
            print("Raw message:", message)

def on_error(ws, error):
    print("❌ WebSocket error:", error)

def on_close(ws, code, msg):
    global start_pinging
    start_pinging = False
    print("🔌 WebSocket closed")
    print(f"Reason: {msg}, Code: {code}")
    print("🔁 Reconnecting in q seconds...\n")
    time.sleep(1)
    connect()
    
    
# Health check endpoint
@app.route('/health')
def health():
    logger.info("Health check requested")
    return Response("OK", status=200)

# Fallback root endpoint for misconfigured health checks
@app.route('/')
def root():
    logger.info("Root endpoint requested (possible misconfigured health check)")
    return Response("OK", status=200)


def connect():
    print("🔄 Connecting to IVASMS WebSocket...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Origin": "https://ivasms.com",
        "Referer": "https://ivasms.com/",
        "Host": "ivasms.com"
    }

    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        header=[f"{k}: {v}" for k, v in headers.items()]
    )

    ws.run_forever()

# -------------------- START --------------------

if __name__ == "__main__":
    connect()

    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)
