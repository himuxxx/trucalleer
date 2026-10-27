import os
import telebot
import requests
from flask import Flask
from threading import Thread

# ===== ক্রেডেনশিয়াল =====
BOT_TOKEN = "8426186448:AAGwsyr411H5f9rlEegnhCiXrMqk11B-eeo"
API_KEY = "c2695c3da9mshc4a38393870e76dp1dcdf4jsn0c9ff4634700"
API_HOST = "truecaller4.p.rapidapi.com"
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
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": API_HOST,
        "Content-Type": "application/json",
    }
    urls = [
        f"https://{API_HOST}/api/v1/getDetails?phone={number}",
        f"https://{API_HOST}/api/v1/getDetails?phone={number}&countryCode=BD",
    ]
    last = None
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            print(f"[TRY] {url} → {r.status_code}")
            if r.status_code == 200:
                return r
            last = r
        except Exception as e:
            print(f"[TRY] {url} → Error: {e}")
    return last


def extract_info(result):
    """truecaller4 স্ট্রাকচার অনুযায়ী ডেটা বের করে।"""
    info = {
        "name": "",
        "carrier": "",
        "location": "",
        "number_type": "",
        "e164": "",
        "tags": "",
        "fraud": False,
    }

    # data একটি লিস্ট
    data = result.get("data")
    record = None
    if isinstance(data, list) and data:
        record = data[0]
    elif isinstance(data, dict):
        record = data

    if not isinstance(record, dict):
        return info

    info["name"] = (record.get("name") or "").strip()
    info["fraud"] = bool(record.get("isFraud"))

    # tags
    tags = record.get("electedTags") or []
    tag_values = []
    for t in tags:
        if isinstance(t, dict) and t.get("value"):
            tag_values.append(t["value"])
        elif isinstance(t, str):
            tag_values.append(t)
    info["tags"] = ", ".join(tag_values)

    # phones[0]
    phones = record.get("phones") or []
    if phones and isinstance(phones[0], dict):
        p = phones[0]
        info["carrier"] = (p.get("carrier") or "").strip()
        info["number_type"] = (p.get("numberType") or "").strip()
        info["e164"] = (p.get("e164Format") or "").strip()

    # addresses[0]
    addresses = record.get("addresses") or []
    if addresses and isinstance(addresses[0], dict):
        a = addresses[0]
        country_code = (a.get("countryCode") or "").strip()
        city = (a.get("city") or "").strip()
        address = (a.get("address") or "").strip()
        parts = [x for x in [city, address, country_code] if x]
        info["location"] = ", ".join(parts)
    # countryCode fallback phones থেকে
    if not info["location"] and phones and isinstance(phones[0], dict):
        cc = (phones[0].get("countryCode") or "").strip()
        if cc:
            info["location"] = cc

    return info


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🤖 Welcome to Real Number Search Bot!\n\n"
        "🔍 যেকোনো মোবাইল নম্বরের অপারেটর ও লোকেশন জানতে দেশের কোড সহ নম্বরটি লিখে পাঠান।\n"
        "👉 উদাহরণ (India): +91XXXXXXXXXX\n"
        "👉 উদাহরণ (Bangladesh): +880XXXXXXXXXX\n\n"
        "🐞 ডিবাগ: `/debug 8801810766980`"
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown')


@bot.message_handler(commands=['debug'])
def debug_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: `/debug 8801810766980`", parse_mode='Markdown')
        return
    number = clean_number(parts[1])
    try:
        response = call_api(number)
        if response is None:
            bot.reply_to(message, "❌ কোনো endpoint-ই রেসপন্স দেয়নি।")
            return
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

        if response is None:
            bot.edit_message_text(
                f"❌ কোনো এন্ডপয়েন্টে কানেক্ট করা যায়নি। `/debug {number}` দিয়ে চেক করুন।",
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                parse_mode='Markdown'
            )
            return

        try:
            result = response.json()
        except Exception:
            bot.edit_message_text(
                f"❌ API থেকে JSON নয় এমন রেসপন্স (status `{response.status_code}`)\n"
                f"`{response.text[:300]}`",
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                parse_mode='Markdown'
            )
            return

        # status false হলে বা error message থাকলে
        if response.status_code in (401, 403, 429) or (
            isinstance(result, dict) and result.get("status") is False
        ) or (isinstance(result, dict) and result.get("message") and not result.get("data")):
            api_msg = (result.get("message") if isinstance(result, dict) else "") or "Unknown error"
            bot.edit_message_text(
                f"⚠️ **API সমস্যা** (status `{response.status_code}`)\n`{api_msg}`",
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                parse_mode='Markdown'
            )
            return

        info = extract_info(result)

        if info["name"] or info["carrier"] or info["location"]:
            fraud_line = "⚠️ **Fraud Flag:** হ্যাঁ\n" if info["fraud"] else ""
            tags_line = f"🏷️ **Tags:** {info['tags']}\n" if info["tags"] else ""
            reply_text = (
                f"🔍 **Real Result Found ✅**\n\n"
                f"📱 **Number:** {info['e164'] or '+' + number}\n"
                f"👤 **Name:** {info['name'] or 'পাওয়া যায়নি'}\n"
                f"📶 **SIM Operator:** {info['carrier'] or 'পাওয়া যায়নি'}\n"
                f"📍 **Location:** {info['location'] or 'পাওয়া যায়নি'}\n"
                f"📞 **Type:** {info['number_type'] or 'পাওয়া যায়নি'}\n"
                f"{tags_line}"
                f"{fraud_line}"
            )
        else:
            reply_text = (
                "🔍 কোনো নির্দিষ্ট তথ্য পাওয়া যায়নি।\n\n"
                f"**Debug:** status `{response.status_code}`, URL: `{response.url}`\n"
                f"বিস্তারিত দেখতে: `/debug {number}`"
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
