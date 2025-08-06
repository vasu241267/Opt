import requests
import re
import time
import hashlib
from bs4 import BeautifulSoup
from flask import Flask, Response
import threading
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio

# Configuration
LOGIN_URL = "https://www.imssms.org/signin"
XHR_URL = "https://www.imssms.org/client/res/data_smscdr.php?fdate1=2025-08-06%2000:00:00&fdate2=2025-08-06%2023:59:59&frange=&fnum=&fcli=&fgdate=&fgmonth=&fgrange=&fgnumber=&fgcli=&fg=0&sEcho=1&iColumns=7&sColumns=%2C%2C%2C%2C%2C%2C&iDisplayStart=0&iDisplayLength=25&mDataProp_0=0&sSearch_0=&bRegex_0=false&bSearchable_0=true&bSortable_0=true&mDataProp_1=1&sSearch_1=&bRegex_1=false&bSearchable_1=true&bSortable_1=true&mDataProp_2=2&sSearch_2=&bRegex_2=false&bSearchable_2=true&bSortable_2=true&mDataProp_3=3&sSearch_3=&bRegex_3=false&bSearchable_3=true&bSortable_3=true&mDataProp_4=4&sSearch_4=&bRegex_4=false&bSearchable_4=true&bSortable_4=true&mDataProp_5=5&sSearch_5=&bRegex_5=false&bSearchable_5=true&bSortable_5=true&mDataProp_6=6&sSearch_6=&bRegex_6=false&bSearchable_6=true&bSortable_6=true&sSearch=&bRegex=false&iSortCol_0=0&sSortDir_0=desc&iSortingCols=1&_=1754455568096"
USERNAME = "Panels"
PASSWORD = "12341234"
BOT_TOKEN = "7905683098:AAGsm8_qFqxMcRYotSGZVXg0Ags6ZvueD20"
CHAT_ID = "-1002311125652"
DEVELOPER_ID = "@Vxxwo"  # Replace with your Telegram ID
CHANNEL_LINK = "@DDXOTP"  # Replace with your Telegram channel ID

# Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.imssms.org/login"
}
AJAX_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.imssms.org/client/SMSCDRStats"
}

# Initialize Flask app
app = Flask(__name__)

# Initialize Telegram bot
bot = telegram.Bot(token=BOT_TOKEN)

# Session and state
session = requests.Session()
seen = set()

# Login function
def login():
    res = session.get("https://www.imssms.org/login", headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    captcha_text = None
    for string in soup.stripped_strings:
        if "What is" in string and "+" in string:
            captcha_text = string.strip()
            break

    match = re.search(r"What is\s*(\d+)\s*\+\s*(\d+)", captcha_text or "")
    if not match:
        print("❌ Captcha not found.")
        return False

    a, b = int(match.group(1)), int(match.group(2))
    captcha_answer = str(a + b)
    print(f"✅ Captcha solved: {a} + {b} = {captcha_answer}")

    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "capt": captcha_answer
    }

    res = session.post(LOGIN_URL, data=payload, headers=HEADERS)
    if "SMSCDRStats" not in res.text:
        print("❌ Login failed.")
        return False

    print("✅ Logged in successfully.")
    return True

# Mask phone number (show first 4 and last 3 digits)
def mask_number(number):
    if len(number) < 7:
        return number  # Return as-is if too short to mask
    return f"{number[:4]}{'*' * (len(number) - 7)}{number[-3:]}"

# Send message to Telegram with inline buttons
async def send_telegram_message(number, sender, message):
    formatted = (
        f"📨 *New OTP Message* 📨\n\n"
        f"📱 *Number*: `{mask_number(number)}`\n"
        f"🏷️ *Sender*: `{sender}`\n"
        f"💬 *Message*: `{message}`\n"
        f"{'─' * 30}"
    )
    keyboard = [
        [
            InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{DEVELOPER_ID.lstrip('@')}"),
            InlineKeyboardButton("📢 Channel", url=f"https://t.me/{CHANNEL_LINK.lstrip('@')}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await bot.send_message(chat_id=CHAT_ID, text=formatted, reply_markup=reply_markup, parse_mode='Markdown')

# Fetch OTPs and send to Telegram
def fetch_otp_loop():
    print("\n🔄 Starting OTP fetch loop...\n")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            res = session.get(XHR_URL, headers=AJAX_HEADERS)
            data = res.json()
            otps = data.get("aaData", [])

            # Remove the last summary row
            otps = [row for row in otps if isinstance(row[0], str) and ":" in row[0]]

            new_found = False
            with open("otp_logs.txt", "a", encoding="utf-8") as f:
                for row in otps:
                    time_ = row[0]
                    operator = row[1]
                    number = row[2]
                    sender = row[3]
                    message = row[4]

                    # Unique message hash
                    hash_id = hashlib.md5((number + time_ + message).encode()).hexdigest()
                    if hash_id in seen:
                        continue
                    seen.add(hash_id)
                    new_found = True

                    # Log full details to file
                    log_formatted = (
                        f"📅 Date:        {time_}\n"
                        f"🌐 Operator:    {operator}\n"
                        f"📱 Number:      {number}\n"
                        f"🏷️ Sender ID:   {sender}\n"
                        f"💬 Message:     {message}\n"
                        f"{'-'*60}"
                    )
                    print(log_formatted)
                    f.write(log_formatted + "\n")

                    # Send masked and formatted message to Telegram
                    loop.run_until_complete(send_telegram_message(number, sender, message))

            if not new_found:
                print("⏳ No new OTPs.")
        except Exception as e:
            print("❌ Error fetching OTPs:", e)

        time.sleep(5)

# Health check endpoint
@app.route('/health')
def health():
    return Response("OK", status=200)

# Start the OTP fetching loop in a separate thread
def start_otp_loop():
    if login():
        fetch_otp_loop()

if __name__ == '__main__':
    # Start the OTP loop in a background thread
    otp_thread = threading.Thread(target=start_otp_loop, daemon=True)
    otp_thread.start()
    
    # Start the Flask web server
    app.run(host='0.0.0.0', port=5000)