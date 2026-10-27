import os
import telebot
import requests
from flask import Flask
from threading import Thread

# ===== সব ক্রেডেনশিয়াল কোডেই হার্ডকোড =====
BOT_TOKEN = "8426186448:AAGwsyr411H5f9rlEegnhCiXrMqk11B-eeo"
API_KEY = "d07fab1250mshc9767ae002ca827p1e76a6jsn32e608140359"
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
    number = message.text.strip().replace("+", "")

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

        name = result.get("name") or result.get("fullName") or result.get("owner")
        carrier = result.get("carrier") or result.get("operator")
        location = result.get("location") or result.get("country") or result.get("address")

        if name or carrier or location:
            reply_text = (
                f"🔍 **Real Result Found ✅**\n\n"
                f"📱 **Number:** +{number}\n"
                f"👤 **Name:** {name or 'পাওয়া যায়নি'}\n"
                f"📶 **SIM Operator:** {carrier or 'পাওয়া যায়নি'}\n"
                f"📍 **Location/State:** {location or 'পাওয়া যায়নি'}"
            )
        else:
            reply_text = "🔍 কোনো নির্দিষ্ট তথ্য পাওয়া যায়নি। নম্বরটি সঠিক কিনা চেক করুন।"

        bot.edit_message_text(
            reply_text,
            chat_id=message.chat.id,
            message_id=status_message.message_id,
            parse_mode='Markdown'
        )

    except Exception:
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
