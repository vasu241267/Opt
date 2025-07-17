import threading
import time
import requests
from flask import Flask
from datetime import datetime

# === Telegram Bot Config ===
bot_token = "7311288614:AAHecPFp5NnBrs4dJiR_l9lh1GB3zBAP_Yo"
chat_id = "-1002445692794"

# === OTP API Config ===
url = "https://raazit.acchub.io/api/"
headers = {
    "auth-token": "dc2f1c99-1804-4a87-81aa-4d57a77d3a8d",
    "auth-role": "Freelancer",
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://raazit.acchub.io",
    "Referer": "https://raazit.acchub.io/",
    "Cookie": "authToken=dc2f1c99-1804-4a87-81aa-4d57a77d3a8d; authRole=Freelancer"
}
total_pages = 7
loop_delay = 30

# === Tracking Sets ===
seen_ids = set()
seen_otp_map = {}

# === Flask App ===
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ OTP Monitor is Running on Koyeb!"

# === Telegram Send Function ===
def send_telegram_message(text):
    try:
        api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        requests.post(api, data=payload)
    except Exception as e:
        print(f"⚠️ Telegram Error: {e}")

# === OTP Fetcher ===
def fetch_otps_forever():
    print("🔁 Background OTP Fetcher Started...")

    while True:
        total_new = 0
        active_numbers = set()

        print(f"\n⏳ [{datetime.now().strftime('%H:%M:%S')}] Fetching OTPs...\n")

        for page in range(1, total_pages + 1):
            data = {
                "page_no": str(page),
                "filter[0][name]": "filter_status",
                "filter[0][value]": "",
                "filter[1][name]": "filter_items",
                "filter[1][value]": "20",
                "filter[2][name]": "app_id",
                "filter[2][value]": "0",
                "filter[3][name]": "countries",
                "filter[3][value]": "0",
                "search": ""
            }

            try:
                res = requests.post(url, headers=headers, data=data)
                if res.status_code != 200:
                    print(f"❌ Page {page} failed! Status: {res.status_code}")
                    continue

                json_data = res.json()
                for row in json_data.get("data", []):
                    otp_id = row.get("id")
                    number = row.get("did")
                    otp = row.get("otp")
                    app = row.get("apps_name")
                    country = row.get("country_name")
                    created = row.get("created")

                    active_numbers.add(number)

                    if otp_id not in seen_ids:
                        seen_ids.add(otp_id)

                        if number not in seen_otp_map or seen_otp_map[number] != otp:
                            seen_otp_map[number] = otp
                            total_new += 1
                            msg = (
                                f"<b>🔐 NEW OTP RECEIVED</b>\n\n"
                                f"<b>📞 Number:</b> {number}\n"
                                f"<b>📱 App:</b> {app}\n"
                                f"<b>🌍 Country:</b> {country}\n"
                                f"<b>🕒 Time:</b> {created}\n"
                                f"<b>🔑 OTP:</b> <code>{otp}</code>"
                            )
                            print(msg)
                            send_telegram_message(msg)

            except Exception as e:
                print(f"⚠️ Error on page {page}: {e}")

        print(f"✅ Total New OTPs This Round: {total_new}")
        time.sleep(loop_delay)

# === Background Thread Start ===
threading.Thread(target=fetch_otps_forever, daemon=True).start()

# === Run Flask App ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
