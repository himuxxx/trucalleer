import os
import json
import telebot
import requests
from flask import Flask
from threading import Thread

# ===== ক্রেডেনশিয়াল =====
BOT_TOKEN = "8426186448:AAGwsyr411H5f9rlEegnhCiXrMqk11B-eeo"
API_KEY = "c2695c3da9mshc4a38393870e76dp1dcdf4jsn0c9ff4634700"
API_HOST = "truecaller-data2.p.rapidapi.com"
# =======================

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)


@app.route('/')
def home():
    return "Bot is alive and running 24/7!"


@app.route('/health')
def health():
    return "OK"


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)


def clean_number(text):
    return text.strip().replace("+", "").replace(" ", "").replace("-", "")


def call_api(number):
    url = f"https://{API_HOST}/search/{number}"
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": API_HOST,
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers, timeout=15)
    print(f"[API] {url} → {response.status_code}")
    print(f"[API] Response body (first 1000 chars): {response.text[:1000]}")
    return response


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🤖 Welcome to Real Number Search Bot!\n\n"
        "🔍 যেকোনো মোবাইল নম্বরের অপারেটর ও লোকেশন জানতে দেশের কোড সহ নম্বরটি লিখে পাঠান।\n"
        "👉 উদাহরণ (India): +91XXXXXXXXXX\n"
        "👉 উদাহরণ (Bangladesh): +880XXXXXXXXXX"
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['debug'])
def debug_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: `/debug 8801810766980`", parse_mode='Markdown')
        return
    number = clean_number(parts[1])
    try:
        response = call_api(number)
        text = response.text
        if len(text) > 3500:
            text = text[:3500] + "...(truncated)"
        bot.reply_to(
            message,
            f"**Status:** `{response.status_code}`\n**URL:** `{response.url}`\n\n"
            f"```json\n{text}\n```",
            parse_mode='Markdown'
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Error: `{e}`", parse_mode='Markdown')


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    number = clean_number(message.text)

    if not number.isdigit():
        bot.reply_to(message, "⚠️ অনুগ্রহ করে শুধুমাত্র একটি সঠিক নম্বর ইনপুট করুন!")
        return

    status_message = bot.reply_to(
        message, "🔍 লাইভ ডেটাবেসে খোঁজা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন..."
    )

    try:
        response = call_api(number)

        try:
            result = response.json()
        except Exception:
            bot.edit_message_text(
                f"❌ API থেকে ভুল রেসপন্স এসেছে (JSON নয়)।\nStatus: {response.status_code}\n"
                f"`{response.text[:300]}`",
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                parse_mode='Markdown'
            )
            return

        # API এরর চেক (তবে data থাকলে এরর হিসেবে ধরা হবে না)
        if response.status_code in (401, 403, 429) or (
            isinstance(result, dict) and "message" in result and not result.get("data")
        ):
            api_msg = (result.get("message") if isinstance(result, dict) else "") or "Unknown error"
            bot.edit_message_text(
                f"⚠️ **API সমস্যা** (status `{response.status_code}`)\n"
                f"`{api_msg}`",
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                parse_mode='Markdown'
            )
            return

        # ---- নেস্টেড স্ট্রাকচার থেকে ডেটা বের করা ----
        data = (result.get("data") if isinstance(result, dict) else None) or {}
        basic_info = data.get("basicInfo") or {}
        name_info = basic_info.get("name") or {}
        phone_info = data.get("phoneInfo") or {}
        address_info = data.get("addressInfo") or {}

        name = (name_info.get("fullName") or "").strip()
        carrier = (phone_info.get("carrier") or "").strip()
        country_code = (phone_info.get("countryCode") or address_info.get("countryCode") or "").strip()
        number_type = (phone_info.get("numberType") or "").strip()
        e164 = phone_info.get("e164Format") or f"+{number}"
        city = (address_info.get("city") or "").strip()
        address = (address_info.get("address") or "").strip()

        location_parts = [p for p in [city, address, country_code] if p]
        location = ", ".join(location_parts)

        if name or carrier or location:
            reply_text = (
                f"🔍 **Real Result Found ✅**\n\n"
                f"📱 **Number:** {e164}\n"
                f"👤 **Name:** {name or 'পাওয়া যায়নি'}\n"
                f"📶 **SIM Operator:** {carrier or 'পাওয়া যায়নি'}\n"
                f"📍 **Location:** {location or 'পাওয়া যায়নি'}\n"
                f"📞 **Type:** {number_type or 'পাওয়া যায়নি'}"
            )
        else:
            # ডিবাগ তথ্য — সাথে সাথে বুঝতে পারবেন কী এসেছে
            dbg_keys = list(data.keys()) if isinstance(data, dict) else "N/A"
            reply_text = (
                "🔍 কোনো নির্দিষ্ট তথ্য পাওয়া যায়নি।\n\n"
                f"**Debug:**\n"
                f"- Status: `{response.status_code}`\n"
                f"- `error`: `{result.get('error') if isinstance(result, dict) else 'N/A'}`\n"
                f"- `data` keys: `{dbg_keys}`\n"
                f"- `basicInfo` keys: `{list(basic_info.keys())}`\n\n"
                f"সঠিক ডিবাগ পেতে `/debug {number}` পাঠান।"
            )

        bot.edit_message_text(
            reply_text,
            chat_id=message.chat.id,
            message_id=status_message.message_id,
            parse_mode='Markdown'
        )

    except Exception as e:
        print("Error:", e)
        bot.edit_message_text(
            f"❌ এরর: `{e}`",
            chat_id=message.chat.id,
            message_id=status_message.message_id,
            parse_mode='Markdown'
        )


if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

    print("Bot is polling...")
    bot.polling(none_stop=True, interval=0, timeout=20)
