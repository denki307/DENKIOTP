import os
import sqlite3
import qrcode
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- CONFIGURATION (Heroku Config Vars-la irunthu edukkum) ---
TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', 0))
UPI_ID = os.getenv('UPI_ID', 'denkielangokey@fam')

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('otp_store.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0.0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, country TEXT, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)''')
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('otp_store.db')
    cursor = conn.cursor()
    stats = {
        "users": cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "accs": cursor.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
        "ords": cursor.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "countries": cursor.execute("SELECT COUNT(DISTINCT country) FROM accounts").fetchone()[0]
    }
    conn.close()
    return stats

# --- START MENU ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('otp_store.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username))
    balance = cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user.id,)).fetchone()[0]
    conn.close()

    keyboard = [
        [InlineKeyboardButton("🛒 Buy Account", callback_query_data='buy_acc'),
         InlineKeyboardButton("💰 Balance", callback_query_data='check_bal')],
        [InlineKeyboardButton("💳 Recharge", callback_query_data='refill_menu'),
         InlineKeyboardButton("👥 Refer Friends", callback_query_data='refer')],
        [InlineKeyboardButton("🎁 Redeem", callback_query_data='redeem'),
         InlineKeyboardButton("🛠️ Support", url='https://t.me/your_support')]
    ]
    if user.id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_query_data='admin_panel')])

    welcome_text = (
        "🥂 **Welcome To OTP Bot By Wanted** 🥂\n\n"
        f"💳 Your Balance: ₹{balance}\n"
        "✨ Features:\n• Automatic OTPs 📍\n• Instant Payment Approvals 🧾"
    )
    
    markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=markup, parse_mode='Markdown')

# --- REFILL FLOW ---
async def refill_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("💸 **Enter Deposit Amount (₹)**\n\nExample: 500", parse_mode='Markdown')
    context.user_data['state'] = 'AWAITING_AMOUNT'

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') == 'AWAITING_AMOUNT':
        amount = update.message.text
        if not amount.isdigit() or int(amount) < 10:
            await update.message.reply_text("❌ Minimum deposit is ₹10. Enter again:")
            return
        
        amt = int(amount)
        upi_url = f"upi://pay?pa={UPI_ID}&pn=OTPStore&am={amt}&cu=INR"
        qr = qrcode.make(upi_url)
        qr_path = f"qr_{update.effective_user.id}.png"
        qr.save(qr_path)
        
        caption = f"✅ **Amount: ₹{amt}**\n📲 Pay to: `{UPI_ID}`\n\n📸 Now send the **payment screenshot**."
        await update.message.reply_photo(photo=open(qr_path, 'rb'), caption=caption, parse_mode='Markdown')
        os.remove(qr_path)
        
        context.user_data['state'] = 'AWAITING_PHOTO'
        context.user_data['temp_amt'] = amt

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') == 'AWAITING_PHOTO':
        user = update.effective_user
        amt = context.user_data.get('temp_amt')
        photo = update.message.photo[-1].file_id
        
        keyboard = [[InlineKeyboardButton(f"✅ Approve ₹{amt}", callback_query_data=f"adm_pay_{user.id}_{amt}"),
                     InlineKeyboardButton("❌ Reject", callback_query_data=f"adm_rej_{user.id}")]]
        
        await context.bot.send_photo(chat_id=OWNER_ID, photo=photo, 
                                     caption=f"📩 **Deposit Proof**\nUser: {user.first_name}\nID: `{user.id}`\nAmount: ₹{amt}",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
        await update.message.reply_text("⏳ Screenshot sent to Admin! Wait for approval.")
        context.user_data['state'] = None

# --- ADMIN PANEL ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    s = get_stats()
    text = (f"👑 **Admin Panel**\n\n📊 **Statistics:**\n• Total Accounts: {s['accs']}\n"
            f"• Total Users: {s['users']}\n• Total Orders: {s['ords']}\n"
            f"• Active Countries: {s['countries']}\n\n⚒ **Management Tools:**")
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Account", callback_query_data='null'), InlineKeyboardButton("📢 Broadcast", callback_query_data='null')],
        [InlineKeyboardButton("💸 Refund", callback_query_data='null'), InlineKeyboardButton("🚫 Ban User", callback_query_data='null')],
        [InlineKeyboardButton("⬅️ Back", callback_query_data='start_over')]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- ADMIN ACTIONS ---
async def admin_pay_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split('_')
    
    if data[1] == "pay":
        uid, amt = int(data[2]), float(data[3])
        conn = sqlite3.connect('otp_store.db')
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, uid))
        conn.commit()
        conn.close()
        await context.bot.send_message(uid, f"✅ **Deposit Approved!** ₹{amt} added.")
        await query.edit_message_caption("✅ Status: APPROVED")
    else:
        await context.bot.send_message(int(data[2]), "❌ **Deposit Rejected.**")
        await query.edit_message_caption("❌ Status: REJECTED")

# --- MAIN RUN ---
def main():
    if not TOKEN:
        print("❌ BOT_TOKEN missing in Environment!")
        return
    
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern='start_over'))
    app.add_handler(CallbackQueryHandler(refill_start, pattern='refill_menu'))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern='admin_panel'))
    app.add_handler(CallbackQueryHandler(admin_pay_actions, pattern='^adm_'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    app.run_polling()

if __name__ == '__main__':
    main()

