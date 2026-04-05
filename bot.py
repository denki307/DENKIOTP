import os
import qrcode
import io
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ButtonStyle
import database as db  # Database file-a link pandrom

# ==========================================
# ⚙️ CONFIGURATION (Heroku-ku etha mathiri)
# ==========================================
# Heroku config vars-la irunthu automatic ah edukkum
API_ID = int(os.environ.get("API_ID", 1234567)) 
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH") 
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN") 
ADMIN_ID = int(os.environ.get("ADMIN_ID", 1234567890)) 

UPI_ID = "your_upi_id@ybl"
UPI_NAME = "Your Name"

app = Client("resell_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Temporary Memory (Current steps mattum track panna)
user_steps = {} 
pending_payments = {} 
admin_steps = {} 
temp_data = {} 

# Default Prices
country_prices = {"India": 36, "USA": 35, "Vietnam": 30} 

# ==========================================
# 🟢 START MENU & ADMIN PANEL
# ==========================================

@app.on_message(filters.command("start") & filters.private)
async def start_menu(client, message):
    user_id = message.from_user.id
    balance = db.get_balance(user_id)
        
    welcome_text = (
        "💪 Welcome ⇌ ≛ ₓWANTED™ ⋆ - ⭓ ≛ 👑 ⌜ 𝐎𝐩 ⌟\n"
        "[ DESTROYERS ]! (Resell Center)\n\n"
        f"💳 Your Balance: ₹{balance}\n"
        "🏷 Bot Status: ✅ Wholesale Enabled"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Buy Accounts", callback_data="buy_accounts")],
        [InlineKeyboardButton("💰 Refill Wallet", callback_data="refill_wallet"), 
         InlineKeyboardButton("💳 Balance", callback_data="check_balance")],
        [InlineKeyboardButton("💬 Support", url="https://t.me/your_support")],
        [InlineKeyboardButton("📢 Channel", url="https://t.me/your_channel"), 
         InlineKeyboardButton("👑 Owner", url="https://t.me/your_owner_id")]
    ])
    
    # Image illama verum text mattum send aagum
    await message.reply_text(text=welcome_text, reply_markup=keyboard)

@app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Account", callback_data="admin_add_acc")],
        [InlineKeyboardButton("📊 View Stock", callback_data="admin_view_stock")]
    ])
    await message.reply_text("👑 **Admin Panel**\n\nWhat do you want to do?", reply_markup=keyboard)

# ==========================================
# 📝 MESSAGE HANDLER (Inputs)
# ==========================================

@app.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text

    # --- REFILL AMOUNT INPUT ---
    if user_steps.get(user_id) == "ENTER_AMOUNT":
        if not text.isdigit() or int(text) <= 0:
            await message.reply_text("❌ Invalid amount. Enter a valid number.")
            return
            
        amount = int(text)
        pending_payments[user_id] = amount
        user_steps[user_id] = "WAITING_FOR_SCREENSHOT"
        
        upi_url = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount}&cu=INR"
        qr_img = qrcode.make(upi_url)
        bio = io.BytesIO()
        bio.name = 'qr.png'
        qr_img.save(bio, 'PNG')
        bio.seek(0)
        
        await message.reply_photo(
            photo=bio,
            caption=f"✅ QR Code generated for ₹{amount}.\n\n📲 UPI ID: `{UPI_ID}`\n\n👉 Pay exactly ₹{amount} and send the **Payment Screenshot** here."
        )
        return

    # --- ADMIN ADD ACCOUNT INPUTS ---
    if user_id == ADMIN_ID:
        step = admin_steps.get(user_id)
        if step == "WAIT_COUNTRY":
            temp_data[user_id] = {"country": text}
            admin_steps[user_id] = "WAIT_NUMBER"
            await message.reply_text(f"✅ Country: {text}\n\n📞 Enter Phone Number:")
        elif step == "WAIT_NUMBER":
            temp_data[user_id]["number"] = text
            admin_steps[user_id] = "WAIT_OTP"
            await message.reply_text("🔢 Enter OTP:")
        elif step == "WAIT_OTP":
            temp_data[user_id]["otp"] = text
            admin_steps[user_id] = "WAIT_PASS"
            await message.reply_text("🔐 Enter Password (or 'None'):")
        elif step == "WAIT_PASS":
            temp_data[user_id]["pass"] = text
            country = temp_data[user_id]["country"]
            acc_info = f"{temp_data[user_id]['number']}|{temp_data[user_id]['otp']}|{temp_data[user_id]['pass']}"
            
            db.add_account(country, acc_info) # Saving to MongoDB
            admin_steps[user_id] = None
            await message.reply_text(f"🚀 **Success!** Account added to {country}.\nTotal Stock: {db.get_stock_count(country)}")

# ==========================================
# 📸 PHOTO HANDLER (Screenshots)
# ==========================================

@app.on_message(filters.photo & filters.private)
async def handle_screenshot(client, message):
    user_id = message.from_user.id
    if user_steps.get(user_id) == "WAITING_FOR_SCREENSHOT":
        amount = pending_payments.get(user_id, 0)
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")]
        ])
        await client.send_photo(
            chat_id=ADMIN_ID,
            photo=message.photo.file_id,
            caption=f"🔔 **New Deposit Request**\n\n👤 User ID: `{user_id}`\n💰 Amount: ₹{amount}",
            reply_markup=admin_keyboard
        )
        await message.reply_text("⏳ Screenshot sent to admin. Please wait for approval.")
        user_steps[user_id] = None

# ==========================================
# 🔘 CALLBACK HANDLER (Buttons)
# ==========================================

@app.on_callback_query()
async def button_handler(client, call: CallbackQuery):
    data = call.data
    user_id = call.from_user.id
    
    if data == "back_to_main":
        balance = db.get_balance(user_id)
        welcome_text = (
            "💪 Welcome ⇌ ≛ ₓWANTED™ ⋆ - ⭓ ≛ 👑 ⌜ 𝐎𝐩 ⌟\n"
            "[ DESTROYERS ]! (Resell Center)\n\n"
            f"💳 Your Balance: ₹{balance}\n"
            "🏷 Bot Status: ✅ Wholesale Enabled"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Buy Accounts", callback_data="buy_accounts")],
            [InlineKeyboardButton("💰 Refill Wallet", callback_data="refill_wallet"), InlineKeyboardButton("💳 Balance", callback_data="check_balance")],
            [InlineKeyboardButton("💬 Support", url="https://t.me/your_support")],
            [InlineKeyboardButton("📢 Channel", url="https://t.me/your_channel"), InlineKeyboardButton("👑 Owner", url="https://t.me/your_owner_id")]
        ])
        # Text-a mattum edit pandrom (Image illatha naala edit_text use pandrom)
        await call.message.edit_text(text=welcome_text, reply_markup=keyboard)

    elif data == "check_balance":
        await call.answer(f"💳 Your balance is: ₹{db.get_balance(user_id)}", show_alert=True)

    elif data == "refill_wallet":
        user_steps[user_id] = "ENTER_AMOUNT"
        await call.message.edit_text(
            "💰 Enter the amount to deposit:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]])
        )

    # --- BUY SYSTEM ---
    elif data == "buy_accounts":
        buttons = []
        countries = db.get_all_countries()
        for c in countries:
            stock = db.get_stock_count(c)
            price = country_prices.get(c, 30)
            if stock > 0:
                buttons.append([InlineKeyboardButton(f"{c} - ₹{price} (Stock: {stock})", callback_data=f"view_{c}")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        await call.message.edit_text("🛒 **Choose a Country:**", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("view_"):
        country = data.split("_")[1]
        stock = db.get_stock_count(country)
        price = country_prices.get(country, 30)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💸 Buy Now (₹{price})", callback_data=f"buy_confirm_{country}")],
            [InlineKeyboardButton("🔙 Back", callback_data="buy_accounts")]
        ])
        await call.message.edit_text(f"🌍 **{country} Accounts**\n\n📦 Stock: {stock}\n💵 Price: ₹{price}", reply_markup=keyboard)

    elif data.startswith("buy_confirm_"):
        country = data.split("_")[2]
        price = country_prices.get(country, 30)
        current_bal = db.get_balance(user_id)
        
        if db.get_stock_count(country) == 0:
            await call.answer("❌ Out of stock.", show_alert=True)
            return
        if current_bal < price:
            await call.answer(f"❌ Low Balance! Need ₹{price}.", show_alert=True)
            return
            
        db.update_balance(user_id, -price)
        acc_details = db.get_and_remove_account(country)
        
        await call.message.edit_text(
            f"✅ **Purchase Successful!**\n\n🌍 {country}\n💰 Paid: ₹{price}\n💳 Balance: ₹{db.get_balance(user_id)}\n\n📦 **Account Details:**\n`{acc_details}`\n\n⚠️ No refunds!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]])
        )

    # --- ADMIN APPROVAL ---
    elif data.startswith("approve_") or data.startswith("reject_"):
        if user_id != ADMIN_ID:
            await call.answer("❌ You are not Admin!", show_alert=True)
            return
            
        action, target_user = data.split("_")
        target_user = int(target_user)
        amount = pending_payments.get(target_user, 0)
        
        if action == "approve":
            db.update_balance(target_user, amount)
            await call.message.edit_caption(f"{call.message.caption}\n\n**Status: ✅ APPROVED**")
            await client.send_message(target_user, f"✅ **Deposit Approved!** ₹{amount} added.")
        else:
            await call.message.edit_caption(f"{call.message.caption}\n\n**Status: ❌ REJECTED**")
            await client.send_message(target_user, f"❌ **Deposit Rejected!**")
            
        if target_user in pending_payments:
            del pending_payments[target_user]

    elif data == "admin_add_acc" and user_id == ADMIN_ID:
        admin_steps[user_id] = "WAIT_COUNTRY"
        await call.message.edit_text("🌍 Enter Country Name (e.g., India):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="back_to_main")]]))

    elif data == "admin_view_stock" and user_id == ADMIN_ID:
        countries = db.get_all_countries()
        text = "📊 **Current Stock:**\n\n"
        for c in countries:
            text += f"- {c}: {db.get_stock_count(c)} accounts\n"
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Close", callback_data="back_to_main")]]))

if __name__ == "__main__":
    print("🚀 Bot is starting...")
    app.run()
