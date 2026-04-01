import logging
import re
import threading
import time
import io
import segno
from datetime import datetime
from bson import ObjectId
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

# --- ACCOUNT MANAGER IMPORT ---
try:
    from account import AccountManager
    account_manager = AccountManager(api_id=30050679, api_hash='2cb9702785f65b121db14181cb203cf4')
except ImportError:
    print("❌ Error: 'account.py' file-a same folder-la vaiyunga!")
    account_manager = None

# --- CONFIGURATION ---
BOT_TOKEN = '8498676621:AAGqBQu9ArEJ4v1D4n056uz8er7jHnydqNE'
ADMIN_ID = 6861240784
MONGO_URL = 'mongodb+srv://SMSOPROBOT:denki232007@smsoprobot.qkxfy8h.mongodb.net/?appName=SMSOPROBOT'
UPI_ID = "denkielangokey@fam"
API_ID = 30050679
API_HASH = '2cb9702785f65b121db14181cb203cf4'

# --- DATABASE INIT ---
client = MongoClient(MONGO_URL)
db = client['otp_bot']
users_col, wallets_col, countries_col = db['users'], db['wallets'], db['countries']
accounts_col, recharges_col = db['accounts'], db['recharges']

bot = telebot.TeleBot(BOT_TOKEN)
login_states = {} 

# --- UTILS ---
def get_balance(user_id):
    rec = wallets_col.find_one({"user_id": user_id})
    return float(rec.get("balance", 0.0)) if rec else 0.0

def format_currency(x):
    return f"₹{float(x):.2f}"

# 1. START MENU
@bot.message_handler(commands=['start'])
def start(msg):
    user_id = msg.from_user.id
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id, "name": msg.from_user.first_name})
        wallets_col.update_one({"user_id": user_id}, {"$setOnInsert": {"balance": 0.0}}, upsert=True)
    
    balance = get_balance(user_id)
    caption = f"""💪 **Welcome ═🏹×<u>WANTED</u>™ ٭-🏹═👑⌜ Op ⌟ [#DESTROYERS]! (Resell Center)**\n\n💳 **Your Balance:** {format_currency(balance)}\n🏷️ **Bot Status:** ✅ Wholesale Enabled"""

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔥 Buy Accounts", callback_data="buy_account"))
    markup.row(InlineKeyboardButton("💰 Refill Wallet", callback_data="recharge"), InlineKeyboardButton("💳 Balance", callback_data="balance"))
    markup.row(InlineKeyboardButton("📋 My Orders", callback_data="my_orders"))
    markup.row(InlineKeyboardButton("💬 Support ↗️", url="https://t.me/DevilComingSoon"))
    if user_id == ADMIN_ID: markup.row(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"))

    bot.send_photo(msg.chat.id, "https://graph.org/file/cd2c651b9329efacea55b-6b9934c74f4f28902a.jpg", caption=caption, parse_mode="HTML", reply_markup=markup)

# 2. BUY CATEGORY
@bot.callback_query_handler(func=lambda call: call.data == "buy_account")
def buy_categories(call):
    text = "📱 **TG Accounts**\n\n1️⃣ **Cheap Acc**\n2️⃣ **Good Quality Acc**\n\n⚠️ **NO REFUNDS.**"
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🎣 Cheap Acc", callback_data="view_cheap"))
    markup.row(InlineKeyboardButton("🌟 Good Quality Acc", callback_data="view_good"))
    markup.row(InlineKeyboardButton("🔙 Back", callback_data="back_to_menu"))
    bot.edit_message_caption(caption=text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

# 3. PRICE LIST
@bot.callback_query_handler(func=lambda call: call.data == "view_cheap")
def cheap_list(call):
    country = countries_col.find_one({"name": {"$regex": "India", "$options": "i"}})
    price = country['price'] if country else 36.0
    text = "📱 **TG Accounts — Cheap | IN**\n\nShowing 6 accounts. Tap to buy 👇"
    markup = InlineKeyboardMarkup()
    for i in range(6):
        markup.row(InlineKeyboardButton(f"🇮🇳 {format_currency(price)} IN", callback_data=f"purchase_India_{i}"))
    markup.row(InlineKeyboardButton("Next ➡️", callback_data="next_page"), InlineKeyboardButton("🔙 Menu", callback_data="back_to_menu"))
    bot.edit_message_caption(caption=text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

# 4. BALANCE DEDUCTION & DEVICES BUTTON
@bot.callback_query_handler(func=lambda call: call.data.startswith("purchase_"))
def process_purchase(call):
    user_id = call.from_user.id
    country_name = call.data.split("_")[1]
    country = countries_col.find_one({"name": {"$regex": country_name, "$options": "i"}})
    price = country['price'] if country else 36.0
    
    if get_balance(user_id) < price:
        bot.answer_callback_query(call.id, f"❌ No Balance! Need {format_currency(price)}", show_alert=True)
        return

    acc = accounts_col.find_one({"country": {"$regex": country_name, "$options": "i"}, "used": False})
    if not acc:
        bot.answer_callback_query(call.id, "❌ Out of Stock!", show_alert=True)
        return

    wallets_col.update_one({"user_id": user_id}, {"$inc": {"balance": -float(price)}})
    accounts_col.update_one({"_id": acc['_id']}, {"$set": {"used": True, "buyer": user_id}})
    
    # Successful Purchase Markup
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🔢 Get OTP", callback_data=f"get_otp_{acc['_id']}"),
        InlineKeyboardButton("📱 Devices", callback_data=f"view_devices_{acc['_id']}")
    )
    
    bot.answer_callback_query(call.id, "✅ Amount Deducted!", show_alert=False)
    bot.send_message(user_id, f"✅ **Purchase Successful!**\n🌍 Country: {country_name}\n📱 Number: `{acc['phone']}`\n\nManage your session below:", reply_markup=markup)

# 5. DEVICE CHECKER & LOGOUT LOGIC
@bot.callback_query_handler(func=lambda call: call.data.startswith("view_devices_"))
def show_devices_list(call):
    acc_id = call.data.split("_")[2]
    acc = accounts_col.find_one({"_id": ObjectId(acc_id)})
    
    if not acc or 'session_string' not in acc:
        bot.answer_callback_query(call.id, "❌ Session error!", show_alert=True)
        return

    bot.answer_callback_query(call.id, "🔍 Fetching active sessions...", show_alert=False)
    
    # account_manager kulla irukura get_active_devices use panrom
    try:
        from pyrogram import Client
        temp_client = Client("device_check", session_string=acc['session_string'], api_id=API_ID, api_hash=API_HASH, in_memory=True)
        
        def get_sessions_sync():
            with temp_client:
                return list(temp_client.get_sessions())
        
        sessions = get_sessions_sync()
        text = "📱 **Active Devices on this Account:**\n\n"
        markup = InlineKeyboardMarkup()

        for s in sessions:
            dtype = "🤖 **Bot Device (Current)**" if s.is_current else "📱 **Mobile/Other Device**"
            text += f"{dtype}\nModel: {s.device_model}\nSystem: {s.system_version}\n\n"
            
            if s.is_current:
                markup.row(InlineKeyboardButton("🚫 Logout Bot Session", callback_data=f"force_logout_{acc_id}"))
        
        markup.row(InlineKeyboardButton("🔙 Back", callback_data="back_to_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Session Expired or Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("force_logout_"))
def force_logout_session(call):
    acc_id = call.data.split("_")[2]
    acc = accounts_col.find_one({"_id": ObjectId(acc_id)})
    
    if account_manager:
        success, msg = account_manager.logout_session_sync(acc_id, call.from_user.id, db['otp_sessions'], accounts_col, db['orders'])
        if success:
            bot.edit_message_text("✅ **Bot Device Logged Out Successfully!**\n\nString session invalid aagiduchi. Safe login guarantee.", call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, f"❌ {msg}", show_alert=True)

# 6. ADMIN & RECHARGE (Existing)
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel(call):
    if call.from_user.id != ADMIN_ID: return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🌍 Add Country", callback_data="adm_add_ctry"), InlineKeyboardButton("📱 Add Account", callback_data="adm_add_acc"))
    bot.send_message(ADMIN_ID, "👑 **Admin Panel**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "recharge")
def recharge(call):
    msg = bot.send_message(call.message.chat.id, "💳 **Enter amount:**")
    bot.register_next_step_handler(msg, gen_qr_code)

def gen_qr_code(msg):
    try:
        amt = float(msg.text)
        url = f"upi://pay?pa={UPI_ID}&pn=WANTED&am={amt}&cu=INR"
        qr = segno.make(url)
        buf = io.BytesIO(); qr.save(buf, kind='png', scale=10); buf.seek(0)
        bot.send_photo(msg.chat.id, buf, caption=f"Pay ₹{amt}", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("💰 Deposited ✅", callback_data=f"dep_{amt}")))
    except: bot.send_message(msg.chat.id, "❌ Error.")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    start(call)

if __name__ == "__main__":
    bot.infinity_polling()

