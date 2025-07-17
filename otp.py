import requests
import html
import threading
import time
from flask import Flask
from datetime import datetime

bot_token = "7311288614:AAHecPFp5NnBrs4dJiR_l9lh1GB3zBAP_Yo"
chat_id = "-1002445692794"

api_url = f"https://api.telegram.org/bot{bot_token}"
otp_url = "https://raazit.acchub.io/api/"
headers = {
    "auth-token": "dc2f1c99-1804-4a87-81aa-4d57a77d3a8d",
    "auth-role": "Freelancer",
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://raazit.acchub.io",
    "Referer": "https://raazit.acchub.io/",
    "Cookie": "authToken=dc2f1c99-1804-4a87-81aa-4d57a77d3a8d; authRole=Freelancer"
}

otp_data = {}  # { number: {otp, app, country, created} }
total_pages = 100

app = Flask(__name__)

def send_message(text):
    try:
        res = requests.post(f"{api_url}/sendMessage", data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        })
        print("Telegram response:", res.status_code)
    except Exception as e:
        print("Telegram send error:", e)

def fetch_all_numbers():
    print("🔁 Fetching number list...")
    seen_ids = set()
    count = 0
    for page in range(1, total_pages + 1):
        data = {
            "page_no": str(page),
            "filter[0][name]": "filter_status",
            "filter[0][value]": "",
            "filter[1][name]": "filter_items",
            "filter[1][value]": "100",
            "filter[2][name]": "app_id",
            "filter[2][value]": "0",
            "filter[3][name]": "countries",
            "filter[3][value]": "0",
            "search": ""
        }
        try:
            res = requests.post(otp_url, headers=headers, data=data)
            if res.status_code != 200:
                print("❌ Failed to fetch page", page)
                continue
            json_data = res.json()
            for row in json_data.get("data", []):
                otp_id = row.get("id")
                if otp_id in seen_ids:
                    continue
                seen_ids.add(otp_id)
                number = row.get("did")
                otp_data[number] = {
                    "otp": row.get("otp"),
                    "app": row.get("apps_name"),
                    "country": row.get("country_name"),
                    "created": row.get("created")
                }
                count += 1
        except Exception as e:
            print("❌ Error in page fetch:", e)
    print(f"✅ Loaded {count} numbers.")
    send_summary_to_group()

import math

def send_summary_to_group():
    count = len(otp_data)
    all_numbers = list(otp_data.items())
    chunk_size = 20

    total_chunks = math.ceil(len(all_numbers) / chunk_size)
    send_message(f"📋 <b>Total Numbers Loaded: {count}</b> — Sending in {total_chunks} chunks...")

    for i in range(0, len(all_numbers), chunk_size):
        chunk = all_numbers[i:i + chunk_size]
        msg_lines = []
        for number, info in chunk:
            app = html.escape(info.get("app", "-"))
            country = html.escape(info.get("country", "-"))
            msg_lines.append(f"📞 {number} | {app} | {country}")

        message = "\n".join(msg_lines)
        send_message(message)
        time.sleep(3)  # 3 sec delay between chunks


# === Polling Thread ===
def telegram_polling():
    print("📡 Telegram polling started...")
    offset = None
    while True:
        try:
            res = requests.get(f"{api_url}/getUpdates", params={"timeout": 30, "offset": offset})
            if res.status_code != 200:
                time.sleep(2)
                continue
            updates = res.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "")
                sender_chat = msg.get("chat", {}).get("id", "")
                if str(sender_chat) != chat_id:
                    continue

                number = text.strip()
                if number in otp_data:
                    # Fetch latest OTP for this number
                    data = {
                        "page_no": "1",
                        "filter[0][name]": "filter_status",
                        "filter[0][value]": "",
                        "filter[1][name]": "filter_items",
                        "filter[1][value]": "100",
                        "filter[2][name]": "app_id",
                        "filter[2][value]": "0",
                        "filter[3][name]": "countries",
                        "filter[3][value]": "0",
                        "search": number
                    }
                    try:
                        res = requests.post(otp_url, headers=headers, data=data)
                        found = False
                        if res.status_code == 200:
                            for row in res.json().get("data", []):
                                if row.get("did") == number:
                                    msg = (
                                        f"<b>📞 Number:</b> {html.escape(number)}\n"
                                        f"<b>📱 App:</b> {html.escape(str(row.get('apps_name')))}\n"
                                        f"<b>🌍 Country:</b> {html.escape(str(row.get('country_name')))}\n"
                                        f"<b>🕒 Time:</b> {html.escape(str(row.get('created')))}\n"
                                        f"<b>🔐 OTP:</b> <code>{html.escape(str(row.get('otp')))}</code>"
                                    )
                                    send_message(msg)
                                    found = True
                                    break
                        if not found:
                            send_message(f"⚠️ No OTP found for <b>{html.escape(number)}</b>")
                    except Exception as e:
                        send_message(f"❌ Error checking OTP for {html.escape(number)}")
                else:
                    send_message(f"❌ Number <b>{html.escape(number)}</b> not tracked.")
        except Exception as e:
            print("Polling error:", e)
        time.sleep(2)

@app.route('/')
def index():
    return "✅ OTP Bot Running!"

if __name__ == "__main__":
    fetch_all_numbers()
    threading.Thread(target=telegram_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
