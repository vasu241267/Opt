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
from datetime import datetime
import logging
import os
from collections import deque
from time import monotonic

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
LOGIN_URL = "https://www.imssms.org/signin"
BASE_XHR_URL = "https://www.imssms.org/client/res/data_smscdr.php?fdate1={}%2000:00:00&fdate2={}%2023:59:59&frange=&fnum=&fcli=&fgdate=&fgmonth=&fgrange=&fgnumber=&fgcli=&fg=0&sEcho=1&iColumns=7&sColumns=%2C%2C%2C%2C%2C%2C&iDisplayStart=0&iDisplayLength=25&mDataProp_0=0&sSearch_0=&bRegex_0=false&bSearchable_0=true&bSortable_0=true&mDataProp_1=1&sSearch_1=&bRegex_1=false&bSearchable_1=true&bSortable_1=true&mDataProp_2=2&sSearch_2=&bRegex_2=false&bSearchable_2=true&bSortable_2=true&mDataProp_3=3&sSearch_3=&bRegex_3=false&bSearchable_3=true&bSortable_3=true&mDataProp_4=4&sSearch_4=&bRegex_4=false&bSearchable_4=true&bSortable_4=true&mDataProp_5=5&sSearch_5=&bRegex_5=false&bSearchable_5=true&bSortable_5=true&mDataProp_6=6&sSearch_6=&bRegex_6=false&bSearchable_6=true&bSortable_6=true&sSearch=&bRegex=false&iSortCol_0=0&sSortDir_0=desc&iSortingCols=1&_=1754455568096"
USERNAME = os.getenv("USERNAME", "Panels")
PASSWORD = os.getenv("PASSWORD", "12341234")
BOT_TOKEN = os.getenv("BOT_TOKEN", "7905683098:AAGsm8_qFqxMcRYotSGZVXg0Ags6ZvueD20")
CHAT_ID = os.getenv("CHAT_ID", "-1002311125652")
DEVELOPER_ID = os.getenv("DEVELOPER_ID", "@YourDeveloperID")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "@YourChannel")

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
try:
    bot = telegram.Bot(token=BOT_TOKEN)
    logger.info("Telegram bot initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Telegram bot: {e}")
    bot = None

# Session and state
session = requests.Session()
seen = set()
login_attempts = deque(maxlen=3)  # Track last 3 login attempts
LOGIN_WINDOW = 300  # 5 minutes in seconds
LOGIN_MAX_ATTEMPTS = 3

# Login function with retries
def login(max_retries=3):
    # Check login attempt rate
    now = monotonic()
    login_attempts.append(now)
    recent_attempts = sum(1 for t in login_attempts if now - t < LOGIN_WINDOW)
    if recent_attempts > LOGIN_MAX_ATTEMPTS:
        logger.error(f"Too many login attempts ({recent_attempts}) in last {LOGIN_WINDOW} seconds. Pausing for {LOGIN_WINDOW} seconds.")
        time.sleep(LOGIN_WINDOW)
        login_attempts.clear()

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Login attempt {attempt}/{max_retries}")
            res = session.get("https://www.imssms.org/login", headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")

            captcha_text = None
            for string in soup.stripped_strings:
                if "What is" in string and "+" in string:
                    captcha_text = string.strip()
                    break

            if not captcha_text:
                logger.error("Captcha not found in page")
                continue

            match = re.search(r"What is\s*(\d+)\s*\+\s*(\d+)", captcha_text)
            if not match:
                logger.error(f"Invalid captcha format: {captcha_text}")
                continue

            a, b = int(match.group(1)), int(match.group(2))
            captcha_answer = str(a + b)
            logger.info(f"Captcha solved: {a} + {b} = {captcha_answer}")

            payload = {
                "username": USERNAME,
                "password": PASSWORD,
                "capt": captcha_answer
            }

            res = session.post(LOGIN_URL, data=payload, headers=HEADERS, timeout=10)
            if "SMSCDRStats" not in res.text:
                logger.error(f"Login failed, SMSCDRStats not found in response")
                continue

            logger.info("Logged in successfully")
            return True
        except Exception as e:
            logger.error(f"Login attempt {attempt} failed: {e}")
            if attempt == max_retries:
                logger.error("Max login retries reached")
                return False
            time.sleep(5)
    return False

# Mask phone number (show first 4 and last 3 digits)
def mask_number(number):
    if len(number) < 7:
        return number
    return f"{number[:4]}{'*' * (len(number) - 7)}{number[-3:]}"

# Check if message is an OTP
def is_otp_message(message):
    # Require both a 6-digit code and keywords like OTP, code, or verification
    return bool(re.search(r'\b\d{6}\b', message) and re.search(r'OTP|code|verification', message, re.IGNORECASE))

# Send message to Telegram with retries
async def send_telegram_message(number, sender, message, max_retries=3):
    if not bot:
        logger.error("Cannot send Telegram message: bot not initialized")
        return
    for attempt in range(1, max_retries + 1):
        try:
            formatted = (
                f"📩 *OTP Alert* 📩\n\n"
                f"📱 *Number*: `{mask_number(number)}`\n"
                f"🏷️ *Sender*: `{sender}`\n"
                f"🔐 *OTP*: `{message}`\n"
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
            logger.info(f"Sent Telegram message for number {mask_number(number)}")
            return
        except Exception as e:
            logger.error(f"Failed to send Telegram message (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(5)
    logger.error("Max retries reached for sending Telegram message")

# Fetch OTPs and send to Telegram
def fetch_otp_loop():
    logger.info("Starting OTP fetch loop")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            # Generate current date for XHR_URL
            current_date = datetime.now().strftime("%Y-%m-%d")
            xhr_url = BASE_XHR_URL.format(current_date, current_date)
            logger.info(f"Fetching OTPs from {xhr_url}")
            
            res = session.get(xhr_url, headers=AJAX_HEADERS, timeout=10)
            data = res.json()
            otps = data.get("aaData", [])
            logger.info(f"Received {len(otps)} OTP records")

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
                    logger.info(f"New message: {log_formatted}")
                    f.write(log_formatted + "\n")

                    # Send only OTP-like messages to Telegram
                    if is_otp_message(message):
                        loop.run_until_complete(send_telegram_message(number, sender, message))
                    else:
                        logger.info(f"Skipped non-OTP message: {message}")

            if not new_found:
                logger.info("No new OTPs found")
        except Exception as e:
            logger.error(f"Error fetching OTPs: {e}")
            logger.info("Attempting re-login after 10-second delay")
            time.sleep(10)  # Delay before re-login
            if not login():
                logger.error("Re-login failed, continuing to next iteration")
        
        time.sleep(30)  # Increased interval to avoid rate limiting

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

# Start the OTP fetching loop in a separate thread
def start_otp_loop():
    logger.info("Starting OTP loop thread")
    if login():
        fetch_otp_loop()
    else:
        logger.error("Initial login failed, OTP loop not started")

if __name__ == '__main__':
    logger.info("Starting application")
    # Start the OTP loop in a background thread
    otp_thread = threading.Thread(target=start_otp_loop, daemon=True)
    otp_thread.start()
    
    # Start the Flask web server
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)HEADERS = {
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
try:
    bot = telegram.Bot(token=BOT_TOKEN)
    logger.info("Telegram bot initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Telegram bot: {e}")
    bot = None

# Session and state
session = requests.Session()
seen = set()

# Login function with retries
def login(max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Login attempt {attempt}/{max_retries}")
            res = session.get("https://www.imssms.org/login", headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")

            captcha_text = None
            for string in soup.stripped_strings:
                if "What is" in string and "+" in string:
                    captcha_text = string.strip()
                    break

            if not captcha_text:
                logger.error("Captcha not found in page")
                continue

            match = re.search(r"What is\s*(\d+)\s*\+\s*(\d+)", captcha_text)
            if not match:
                logger.error(f"Invalid captcha format: {captcha_text}")
                continue

            a, b = int(match.group(1)), int(match.group(2))
            captcha_answer = str(a + b)
            logger.info(f"Captcha solved: {a} + {b} = {captcha_answer}")

            payload = {
                "username": USERNAME,
                "password": PASSWORD,
                "capt": captcha_answer
            }

            res = session.post(LOGIN_URL, data=payload, headers=HEADERS, timeout=10)
            if "SMSCDRStats" not in res.text:
                logger.error(f"Login failed, SMSCDRStats not found in response")
                continue

            logger.info("Logged in successfully")
            return True
        except Exception as e:
            logger.error(f"Login attempt {attempt} failed: {e}")
            if attempt == max_retries:
                logger.error("Max login retries reached")
                return False
            time.sleep(5)
    return False

# Mask phone number (show first 4 and last 3 digits)
def mask_number(number):
    if len(number) < 7:
        return number
    return f"{number[:4]}{'*' * (len(number) - 7)}{number[-3:]}"

# Check if message is an OTP
def is_otp_message(message):
    # Require both a 6-digit code and keywords like OTP, code, or verification
    return bool(re.search(r'\b\d{6}\b', message) and re.search(r'OTP|code|verification', message, re.IGNORECASE))

# Send message to Telegram with inline buttons
async def send_telegram_message(number, sender, message):
    if not bot:
        logger.error("Cannot send Telegram message: bot not initialized")
        return
    try:
        formatted = (
            f"📩 *OTP Alert* 📩\n\n"
            f"📱 *Number*: `{mask_number(number)}`\n"
            f"🏷️ *Sender*: `{sender}`\n"
            f"🔐 *OTP*: `{message}`\n"
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
        logger.info(f"Sent Telegram message for number {mask_number(number)}")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")

# Fetch OTPs and send to Telegram
def fetch_otp_loop():
    logger.info("Starting OTP fetch loop")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            # Generate current date for XHR_URL
            current_date = datetime.now().strftime("%Y-%m-%d")
            xhr_url = BASE_XHR_URL.format(current_date, current_date)
            logger.info(f"Fetching OTPs from {xhr_url}")
            
            res = session.get(xhr_url, headers=AJAX_HEADERS, timeout=10)
            data = res.json()
            otps = data.get("aaData", [])
            logger.info(f"Received {len(otps)} OTP records")

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
                    logger.info(f"New message: {log_formatted}")
                    f.write(log_formatted + "\n")

                    # Send only OTP-like messages to Telegram
                    if is_otp_message(message):
                        loop.run_until_complete(send_telegram_message(number, sender, message))
                    else:
                        logger.info(f"Skipped non-OTP message: {message}")

            if not new_found:
                logger.info("No new OTPs found")
        except Exception as e:
            logger.error(f"Error fetching OTPs: {e}")
            logger.info("Attempting re-login")
            if not login():
                logger.error("Re-login failed, continuing to next iteration")
        
        time.sleep(5)

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

# Start the OTP fetching loop in a separate thread
def start_otp_loop():
    logger.info("Starting OTP loop thread")
    if login():
        fetch_otp_loop()
    else:
        logger.error("Initial login failed, OTP loop not started")

if __name__ == '__main__':
    logger.info("Starting application")
    # Start the OTP loop in a background thread
    otp_thread = threading.Thread(target=start_otp_loop, daemon=True)
    otp_thread.start()
    
    # Start the Flask web server
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)
