import os
import telebot
import requests
from flask import Flask
from threading import Thread

# ===== সব ক্রেডেনশিয়াল কোডেই হার্ডকোড =====
BOT_TOKEN = "8426186448:AAGwsyr411H5f9rlEegnhCiXrMqk11B-eeo"
API_KEY = "c2695c3da9mshc4a38393870e76dp1dcdf4jsn0c9ff4634700"
API_HOST = "truecaller-data2.p.rapidapi.com"
# ==========================================

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


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🤖 Welcome to Real Number Search Bot!\n\n"
        "🔍 যেকোনো মোবাইল নম্বরের অপারেটর ও লোকেশন জানতে দেশের কোড সহ নম্বরটি লিখে পাঠান।\n"
        "👉 উদাহরণ (India): +91XXXXXXXXXX\n"
        "👉 উদাহরণ (Bangladesh): +880XXXXXXXXXX"
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    number = message.text.strip().replace("+", "").replace(" ", "").replace("-", "")

    if not number.isdigit():
        bot.reply_to(message, "⚠️ অনুগ্রহ করে শুধুমাত্র একটি সঠিক নম্বর ইনপুট করুন!")
        return

    status_message = bot.reply_to(
        message, "🔍 লাইভ ডেটাবেসে খোঁজা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন..."
    )

    url = f"https://{API_HOST}/search/{number}"
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": API_HOST,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        result = response.json()

        # ---- API এরর চেক ----
        if response.status_code in (401, 403) or "message" in result:
            api_msg = result.get("message", "Limit Exceeded or Unauthorized")
            bot.edit_message_text(
                f"⚠️ **API সমস্যা:** আপনার RapidAPI-এর ফ্রি লিমিট শেষ অথবা কি (Key) ব্লক হয়েছে।\n"
                f"`সার্ভার মেসেজ: {api_msg}`",
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                parse_mode='Markdown'
            )
            return

        # ---- আসল নেস্টেড স্ট্রাকচার থেকে ডেটা বের করা ----
        data = result.get("data") or {}
        basic_info = data.get("basicInfo") or {}
        name_info = basic_info.get("name") or {}
        phone_info = data.get("phoneInfo") or {}
        address_info = data.get("addressInfo") or {}

        name = name_info.get("fullName") or ""
        carrier = phone_info.get("carrier") or ""
        country_code = phone_info.get("countryCode") or address_info.get("countryCode") or ""
        number_type = phone_info.get("numberType") or ""
        e164 = phone_info.get("e164Format") or f"+{number}"
        city = address_info.get("city") or ""
        address = address_info.get("address") or ""

        location_parts = [p for p in [city, address, country_code] if p]
        location = ", ".join(location_parts)

        # ---- রেজাল্ট তৈরি ----
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
            reply_text = "🔍 কোনো নির্দিষ্ট তথ্য পাওয়া যায়নি। নম্বরটি সঠিক কিনা চেক করুন।"

        bot.edit_message_text(
            reply_text,
            chat_id=message.chat.id,
            message_id=status_message.message_id,
            parse_mode='Markdown'
        )

    except Exception as e:
        print("Error:", e)  # Render log-এ দেখতে পাবেন
        bot.edit_message_text(
            "❌ এপিআই সার্ভারে কানেক্ট করতে সমস্যা হচ্ছে। দয়া করে একটু পর চেষ্টা করুন।",
            chat_id=message.chat.id,
            message_id=status_message.message_id
        )


if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

    print("Bot is polling...")
    bot.polling(none_stop=True, interval=0, timeout=20)
