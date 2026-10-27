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
    """
    প্রথমে /api/v1/getDetails চেষ্টা করে (query param সহ)।
    실패하면 অন্যান্য সম্ভাব্য path-ও ট্রাই করে।
    """
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": API_HOST,
        "Content-Type": "application/json",
    }

    # --- প্রধান চেষ্টা: /api/v1/getDetails ---
    # countryCode ছাড়া এবং BD সহ দুভাবেই চেষ্টা করি
    candidate_urls = [
        f"https://{API_HOST}/api/v1/getDetails?phone={number}",
        f"https://{API_HOST}/api/v1/getDetails?phone={number}&countryCode=BD",
    ]

    # --- ব্যাকআপ প্যাটার্ন (যদি উপরেরটা কাজ না করে) ---
    backup_patterns = [
        "/api/v1/search?phone={number}",
        "/api/v1/search?number={number}",
        "/search/{number}",
    ]
    for p in backup_patterns:
        candidate_urls.append(f"https://{API_HOST}{p.format(number=number)}")

    last_response = None
    for url in candidate_urls:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            print(f"[TRY] {url} → {r.status_code}")
            if r.status_code == 200:
                try:
                    body = r.json()
                except Exception:
                    continue
                if isinstance(body, dict) and body.get("message") and not body.get("data"):
                    # স্পষ্ট error message, পরেরটা চেষ্টা করি
                    last_response = r
                    continue
                return r
            else:
                last_response = r
        except Exception as e:
            print(f"[TRY] {url} → Error: {e}")
            continue
    return last_response


def deep_get(obj, path, default=None):
    cur = obj
    for k in path:
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return default
        if cur is None:
            return default
    return cur


def extract_info(result):
    """বিভিন্ন সম্ভাব্য JSON স্ট্রাকচার থেকে তথ্য বের করার চেষ্টা।"""
    roots = [result]
    if isinstance(result, dict):
        for key in ("data", "result", "results", "record", "phoneInfo"):
            if isinstance(result.get(key), dict):
                roots.append(result[key])

    def find(paths):
        for root in roots:
            for p in paths:
                v = deep_get(root, p)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return ""

    name = find([
        ("basicInfo", "name", "fullName"),
        ("basicInfo", "name"),
        ("name", "fullName"),
        ("fullName",),
        ("name",),
    ])
    carrier = find([
        ("phoneInfo", "carrier"),
        ("carrier",),
        ("operator",),
    ])
    country_code = find([
        ("phoneInfo", "countryCode"),
        ("addressInfo", "countryCode"),
        ("countryCode",),
    ])
    number_type = find([
        ("phoneInfo", "numberType"),
        ("numberType",),
        ("type",),
    ])
    e164 = find([
        ("phoneInfo", "e164Format"),
        ("e164Format",),
        ("number",),
    ])
    city = find([("addressInfo", "city"), ("city",)])
    address = find([("addressInfo", "address"), ("address",)])
    location_parts = [p for p in [city, address, country_code] if p]
    location = ", ".join(location_parts)

    return {
        "name": name,
        "carrier": carrier,
        "location": location,
        "number_type": number_type,
        "e164": e164,
    }


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

        # API এরর (401/403/429 বা message-only)
        if response.status_code in (401, 403, 429) or (
            isinstance(result, dict) and result.get("message") and not result.get("data")
        ):
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
            reply_text = (
                f"🔍 **Real Result Found ✅**\n\n"
                f"📱 **Number:** {info['e164'] or '+' + number}\n"
                f"👤 **Name:** {info['name'] or 'পাওয়া যায়নি'}\n"
                f"📶 **SIM Operator:** {info['carrier'] or 'পাওয়া যায়নি'}\n"
                f"📍 **Location:** {info['location'] or 'পাওয়া যায়নি'}\n"
                f"📞 **Type:** {info['number_type'] or 'পাওয়া যায়নি'}"
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
