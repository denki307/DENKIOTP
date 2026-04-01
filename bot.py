# Intha code-a oru .py file-a save panni run pannunga.
# Mukkiyamaana note: 'account.py' and 'logs.py' unga folder-la irukanum.

import logging
import re
import threading
import time
import io
import segno
from datetime import datetime
from bson import ObjectId
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from pyrogram import Client
import os

# --- CONFIGURATION ---
BOT_TOKEN = '8732475484:AAFiZSDGzA_fbQbArVEmQMaY_UfRWXh53ZU'
ADMIN_ID = 6861240784
MONGO_URL = 'mongodb+srv://SMSOPROBOT:denki232007@smsoprobot.qkxfy8h.mongodb.net/?appName=SMSOPROBOT'
API_ID = 30050679
API_HASH = '2cb9702785f65b121db14181cb203cf4'
MUST_JOIN_CHANNEL = "@TG_WANTED_STORE"
UPI_ID = "denkielangokey@fam"

# --- DATABASE INIT ---
client = MongoClient(MONGO_URL)
db = client['otp_bot']
users_col = db['users']
wallets_col = db['wallets']
countries_col = db['countries']
accounts_col = db['accounts']
recharges_col = db['recharges']

bot = telebot.TeleBot(BOT_TOKEN)

# -----------------------
# START MENU (SCREENSHOT 1)
# -----------------------
@bot.message_handler(commands=['start'])
def start(msg):
    user_id = msg.from_user.id
    # Ensure user & wallet exists
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id, "name": msg.from_user.first_name})
        wallets_col.update_one({"user_id": user_id}, {"$setOnInsert": {"balance": 0.0}}, upsert=True)
    
    balance = float(wallets_col.find_one({"user_id": user_id}).get("balance", 0.0))
    
    caption = f"""💪 **Welcome ═🏹×<u>WANTED</u>™ ٭-🏹═👑⌜ Op ⌟ [#DESTROYERS]! (Resell Center)**

💳 **Your Balance:** ₹{balance:.2f}
🏷️ **Bot Status:** ✅ Wholesale Enabled"""

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔥 Buy Accounts", callback_data="buy_account"))
    markup.row(
        InlineKeyboardButton("💰 Refill Wallet", callback_data="recharge"),
        InlineKeyboardButton("💳 Balance", callback_data="balance")
    )
    markup.row(InlineKeyboardButton("📋 My Orders", callback_data="my_orders"))
    markup.row(InlineKeyboardButton("💬 Support ↗️", url="https://t.me/DevilComingSoon"))
    
    if user_id == ADMIN_ID:
        markup.row(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"))

    bot.send_photo(msg.chat.id, "https://graph.org/file/cd2c651b9329efacea55b-6b9934c74f4f28902a.jpg", 
                   caption=caption, parse_mode="HTML", reply_markup=markup)

# -----------------------
# BUY MENU (CATEGORIES)
# -----------------------
@bot.callback_query_handler(func=lambda call: call.data == "buy_account")
def buy_categories(call):
    text = "📱 **TG Accounts**\n\n1️⃣ **Cheap Acc** — All origins, lowest price\n2️⃣ **Good Quality Acc** — Autoreg/Personal only\n\n⚠️ **NO REFUNDS IN ANY CASE.**"
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🎣 Cheap Acc", callback_data="view_cheap"))
    markup.row(InlineKeyboardButton("🌟 Good Quality Acc", callback_data="view_good"))
    markup.row(InlineKeyboardButton("🔙 Back", callback_data="back_to_menu"))
    bot.edit_message_caption(caption=text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

# -----------------------
# PRICE LIST (SCREENSHOT 3 & 4)
# -----------------------
@bot.callback_query_handler(func=lambda call: call.data == "view_cheap")
def cheap_list(call):
    # Fetch all countries to show price list
    countries = list(countries_col.find({"status": "active"}))
    if not countries:
        bot.answer_callback_query(call.id, "❌ No countries added yet!", show_alert=True)
        return

    # For India example (Screenshot setup)
    india = countries_col.find_one({"name": {"$regex": "India", "$options": "i"}})
    price = india['price'] if india else 36.0

    text = "📱 **TG Accounts — Cheap | IN**\n\nShowing 6 accounts. Tap to buy 👇"
    markup = InlineKeyboardMarkup()
    for i in range(6):
        markup.row(InlineKeyboardButton(f"🇮🇳 ₹{price:.2f} IN", callback_data=f"purchase_india_{i}"))
    
    markup.row(InlineKeyboardButton("Next ➡️", callback_data="next_page"))
    markup.row(InlineKeyboardButton("🔄 Refresh", callback_data="view_cheap"), InlineKeyboardButton("🔙 Menu", callback_data="back_to_menu"))
    bot.edit_message_caption(caption=text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

# -----------------------
# DEDUCTION & PURCHASE LOGIC
# -----------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("purchase_"))
def process_deduction(call):
    user_id = call.from_user.id
    country_name = call.data.split("_")[1]
    
    # 1. Price check
    country = countries_col.find_one({"name": {"$regex": country_name, "$options": "i"}})
    price = country['price'] if country else 36.0
    
    # 2. Balance check
    balance = float(wallets_col.find_one({"user_id": user_id}).get("balance", 0.0))
    if balance < price:
        bot.answer_callback_query(call.id, f"❌ Insufficient Balance! Need ₹{price}", show_alert=True)
        return

    # 3. Stock check
    acc = accounts_col.find_one({"country": {"$regex": country_name, "$options": "i"}, "used": False})
    if not acc:
        bot.answer_callback_query(call.id, "❌ Out of Stock!", show_alert=True)
        return

    # 4. Deduct Balance
    wallets_col.update_one({"user_id": user_id}, {"$inc": {"balance": -float(price)}})
    accounts_col.update_one({"_id": acc['_id']}, {"$set": {"used": True, "buyer": user_id}})
    
    bot.answer_callback_query(call.id, f"✅ ₹{price} Deducted!", show_alert=False)
    bot.send_message(user_id, f"✅ **Purchase Success!**\n📱 Number: `{acc['phone']}`\n\nClick 'Get OTP' button.")

# -----------------------
# DYNAMIC QR RECHARGE
# -----------------------
@bot.callback_query_handler(func=lambda call: call.data == "recharge")
def start_recharge(call):
    msg = bot.send_message(call.message.chat.id, "💳 **Enter amount to recharge (₹):**")
    bot.register_next_step_handler(msg, gen_qr)

def gen_qr(msg):
    try:
        amt = float(msg.text)
        upi_url = f"upi://pay?pa={UPI_ID}&pn=WANTED&am={amt}&cu=INR"
        qr = segno.make(upi_url)
        buf = io.BytesIO()
        qr.save(buf, kind='png', scale=10)
        buf.seek(0)
        
        cap = f"<blockquote>💳 <b>Pay ₹{amt:.2f}</b>\nUPI ID: <code>{UPI_ID}</code></blockquote>\n\nClick Deposited after paying."
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("💰 Deposited ✅", callback_data=f"dep_{amt}"))
        bot.send_photo(msg.chat.id, buf, caption=cap, parse_mode="HTML", reply_markup=markup)
    except: bot.send_message(msg.chat.id, "❌ Invalid Amount.")

# -----------------------
# ADMIN PANEL
# -----------------------
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel(call):
    if call.from_user.id != ADMIN_ID: return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🌍 Add Country", callback_data="adm_add_ctry"),
        InlineKeyboardButton("📱 Add Account", callback_data="adm_add_acc"),
        InlineKeyboardButton("📢 Broadcast", callback_data="adm_bc")
    )
    bot.send_message(ADMIN_ID, "👑 **Admin Panel**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "adm_add_ctry")
def adm_ctry(call):
    msg = bot.send_message(ADMIN_ID, "🌍 Enter Country Name:")
    bot.register_next_step_handler(msg, save_ctry_name)

def save_ctry_name(msg):
    name = msg.text
    p_msg = bot.send_message(ADMIN_ID, f"💰 Enter price for {name}:")
    bot.register_next_step_handler(p_msg, lambda m: countries_col.update_one({"name": name}, {"$set": {"price": float(m.text), "status": "active"}}, upsert=True) or bot.send_message(ADMIN_ID, "✅ Added!"))

# -----------------------
# APP RUN
# -----------------------
@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    start(call)

if __name__ == "__main__":
    print("🤖 Bot is live with your Custom UI...")
    bot.infinity_polling()

