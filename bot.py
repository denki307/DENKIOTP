import os
import io
import qrcode
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import database as db

API_ID = int(os.environ.get("API_ID", 1234567)) 
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH") 
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN") 
ADMIN_ID = int(os.environ.get("ADMIN_ID", 1234567890)) 

UPI_ID = "denkielangokey@fam"
UPI_NAME = "DENKI"

app = Client("resell_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_steps = {} 
pending_payments = {} 
admin_steps = {} 
temp_data = {} 
active_orders = {} # Auto OTP session save pandrathuku

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
        "🏷 Bot Status: ✅ Auto OTP Enabled"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Buy Accounts", callback_data="buy_accounts")],
        [InlineKeyboardButton("💰 Refill Wallet", callback_data="refill_wallet"), 
         InlineKeyboardButton("💳 Balance", callback_data="check_balance")],
        [InlineKeyboardButton("💬 Support", url="https://t.me/your_support")],
        [InlineKeyboardButton("📢 Channel", url="https://t.me/your_channel"), 
         InlineKeyboardButton("👑 Owner", url="https://t.me/your_owner_id")]
    ])
    await message.reply_text(text=welcome_text, reply_markup=keyboard)

@app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Active Session", callback_data="admin_add_acc")],
        [InlineKeyboardButton("📊 Manage Stock", callback_data="admin_view_stock")],
        [InlineKeyboardButton("💰 Edit Price", callback_data="admin_edit_price")]
    ])
    await message.reply_text("👑 **Admin Panel**\n\nWhat do you want to do?", reply_markup=keyboard)

# ==========================================
# 📝 MESSAGE HANDLER (Inputs)
# ==========================================

@app.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text

    # --- REFILL ---
    if user_steps.get(user_id) == "ENTER_AMOUNT":
        if not text.isdigit() or int(text) <= 0:
            return await message.reply_text("❌ Invalid amount.")
            
        amount = int(text)
        pending_payments[user_id] = amount
        user_steps[user_id] = "WAITING_FOR_SCREENSHOT"
        
        upi_url = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount}&cu=INR"
        bio = io.BytesIO()
        bio.name = 'qr.png'
        qrcode.make(upi_url).save(bio, 'PNG')
        bio.seek(0)
        
        await message.reply_photo(photo=bio, caption=f"✅ QR Code for ₹{amount}.\n\n📲 UPI ID: `{UPI_ID}`\n\n👉 Send Screenshot here.")
        return

    # --- ADMIN ADD SESSION FLOW (Auto Login) ---
    if user_id == ADMIN_ID:
        step = admin_steps.get(user_id)
        
        if step == "WAIT_COUNTRY":
            temp_data[user_id] = {"country": text}
            admin_steps[user_id] = "WAIT_NUMBER"
            await message.reply_text(f"✅ Country: {text}\n\n📞 Enter Phone Number with country code (e.g., +918888888888):")
            
        elif step == "WAIT_NUMBER":
            phone = text
            temp_data[user_id]["phone"] = phone
            await message.reply_text("⏳ Generating Session... Please wait.")
            
            # Temporary Client
            temp_client = Client(f"temp_{user_id}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
            await temp_client.connect()
            try:
                sent_code = await temp_client.send_code(phone)
                temp_data[user_id]["phone_code_hash"] = sent_code.phone_code_hash
                temp_data[user_id]["client"] = temp_client
                admin_steps[user_id] = "WAIT_OTP"
                await message.reply_text(f"✅ Code sent to {phone}.\n🔢 Enter the OTP you received:")
            except Exception as e:
                await message.reply_text(f"❌ Error sending code: {e}")
                await temp_client.disconnect()
                admin_steps[user_id] = None
                
        elif step == "WAIT_OTP":
            otp = text
            temp_client = temp_data[user_id]["client"]
            phone = temp_data[user_id]["phone"]
            phone_code_hash = temp_data[user_id]["phone_code_hash"]
            country = temp_data[user_id]["country"]
            
            try:
                await temp_client.sign_in(phone, phone_code_hash, otp)
                session_string = await temp_client.export_session_string()
                db.add_account(country, phone, session_string)
                await message.reply_text(f"🚀 **Success!** Active Session added to {country} stock.\nTotal Stock: {db.get_stock_count(country)}")
            except Exception as e:
                await message.reply_text(f"❌ Login Failed: {e}. Check if 2FA is enabled or OTP is wrong.")
            finally:
                await temp_client.disconnect()
                admin_steps[user_id] = None
            
        elif step == "EDIT_PRICE_COUNTRY":
            temp_data[user_id] = {"edit_country": text}
            admin_steps[user_id] = "EDIT_PRICE_AMOUNT"
            await message.reply_text(f"✅ Country selected: {text}\n\n💰 Enter new price for {text}:")
        elif step == "EDIT_PRICE_AMOUNT":
            if not text.isdigit():
                return await message.reply_text("❌ Please enter a valid number.")
            db.set_price(temp_data[user_id]["edit_country"], int(text))
            admin_steps[user_id] = None
            await message.reply_text(f"✅ Price changed to ₹{text}.")

# ==========================================
# 📸 PHOTO HANDLER (Screenshots)
# ==========================================
@app.on_message(filters.photo & filters.private)
async def handle_screenshot(client, message):
    user_id = message.from_user.id
    if user_steps.get(user_id) == "WAITING_FOR_SCREENSHOT":
        amount = pending_payments.get(user_id, 0)
        admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")]])
        await client.send_photo(chat_id=ADMIN_ID, photo=message.photo.file_id, caption=f"🔔 Deposit Request\n👤 ID: `{user_id}`\n💰 Amount: ₹{amount}", reply_markup=admin_keyboard)
        await message.reply_text("⏳ Screenshot sent to admin.")
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
            "🏷 Bot Status: ✅ Auto OTP Enabled"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Buy Accounts", callback_data="buy_accounts")],
            [InlineKeyboardButton("💰 Refill Wallet", callback_data="refill_wallet"), InlineKeyboardButton("💳 Balance", callback_data="check_balance")],
            [InlineKeyboardButton("💬 Support", url="https://t.me/your_support")],
            [InlineKeyboardButton("📢 Channel", url="https://t.me/your_channel"), InlineKeyboardButton("👑 Owner", url="https://t.me/your_owner_id")]
        ])
        await call.message.edit_text(text=welcome_text, reply_markup=keyboard)

    elif data == "check_balance":
        await call.answer(f"💳 Your balance is: ₹{db.get_balance(user_id)}", show_alert=True)

    elif data == "refill_wallet":
        user_steps[user_id] = "ENTER_AMOUNT"
        await call.message.edit_text("💰 Enter the amount to deposit:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]))

    # --- BUY SYSTEM (Auto OTP Flow) ---
    elif data == "buy_accounts":
        buttons = []
        for c in db.get_all_countries():
            stock = db.get_stock_count(c)
            if stock > 0:
                buttons.append([InlineKeyboardButton(f"{c} - ₹{db.get_price(c)} (Stock: {stock})", callback_data=f"view_{c}")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        await call.message.edit_text("🛒 **Choose a Country:**", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("view_"):
        country = data.split("_")[1]
        price = db.get_price(country)
        await call.message.edit_text(f"🌍 **{country} Accounts**\n\n📦 Stock: {db.get_stock_count(country)}\n💵 Price: ₹{price}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"💸 Buy Now (₹{price})", callback_data=f"buy_confirm_{country}")], [InlineKeyboardButton("🔙 Back", callback_data="buy_accounts")]]))

    elif data.startswith("buy_confirm_"):
        country = data.split("_")[2]
        price = db.get_price(country)
        current_bal = db.get_balance(user_id)
        
        if db.get_stock_count(country) == 0:
            return await call.answer("❌ Out of stock.", show_alert=True)
        if current_bal < price:
            return await call.answer(f"❌ Low Balance! Need ₹{price}.", show_alert=True)
            
        acc_data = db.get_and_remove_account(country)
        db.update_balance(user_id, -price)
        
        # Save session to memory for OTP
        active_orders[user_id] = acc_data 
        
        text = (
            f"✅ **Purchase Successful!**\n\n"
            f"📱 **Number:** `{acc_data['phone']}`\n\n"
            f"👉 Enter this number in your Telegram App.\n"
            f"👉 Then click **'📩 Get OTP'** below."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📩 Get OTP", callback_data="get_otp")],
            [InlineKeyboardButton("🔄 Retry (Send again)", callback_data="retry_otp")],
            [InlineKeyboardButton("📱 Device -> Logout Bot", callback_data="logout_bot")]
        ])
        await call.message.edit_text(text, reply_markup=keyboard)

    # --- AUTO OTP FETCHING ---
    elif data == "get_otp":
        if user_id not in active_orders:
            return await call.answer("❌ No active order found.", show_alert=True)
            
        await call.answer("⏳ Fetching OTP... Please wait.", show_alert=False)
        session_str = active_orders[user_id]["session"]
        
        try:
            user_client = Client(f"user_{user_id}", api_id=API_ID, api_hash=API_HASH, session_string=session_str, in_memory=True)
            await user_client.connect()
            
            otp_msg = "No OTP received yet. Try again in 10s."
            async for msg in user_client.get_chat_history(777000, limit=1):
                otp_msg = msg.text
            await user_client.disconnect()
            
            # Extract 5 digit code
            code_match = re.search(r'\b(\d{5})\b', otp_msg)
            display_otp = code_match.group(1) if code_match else "Try again"
            
            await call.message.reply_text(f"🔢 **Your OTP:**\n`{display_otp}`\n\n_(If not received, wait 10s and click again)_")
        except Exception as e:
            await call.message.reply_text(f"❌ Error: {e}")

    elif data == "retry_otp":
        if user_id not in active_orders:
            return await call.answer("❌ No active order.", show_alert=True)
        await call.answer("⏳ Requesting code again...", show_alert=False)
        try:
            user_client = Client(f"user_{user_id}", api_id=API_ID, api_hash=API_HASH, session_string=active_orders[user_id]["session"], in_memory=True)
            await user_client.connect()
            await user_client.send_code(active_orders[user_id]["phone"]) 
            await user_client.disconnect()
            await call.message.reply_text("✅ Requested a new OTP. Wait 10s and click **Get OTP**.")
        except Exception as e:
            await call.message.reply_text(f"❌ Error: {e}")

    elif data == "logout_bot":
        if user_id not in active_orders:
            return await call.answer("❌ No active order.", show_alert=True)
        await call.answer("⏳ Logging out bot...", show_alert=False)
        try:
            user_client = Client(f"user_{user_id}", api_id=API_ID, api_hash=API_HASH, session_string=active_orders[user_id]["session"], in_memory=True)
            await user_client.connect()
            await user_client.log_out() 
            del active_orders[user_id] 
            await call.message.edit_text("✅ **Bot successfully logged out!**\n\nAccount is yours.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]]))
        except Exception as e:
            await call.message.reply_text(f"❌ Error: {e}")

    # --- ADMIN ACTIONS ---
    elif data.startswith("approve_") or data.startswith("reject_"):
        if user_id != ADMIN_ID:
            return await call.answer("❌ You are not Admin!", show_alert=True)
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

    elif data == "admin_edit_price" and user_id == ADMIN_ID:
        admin_steps[user_id] = "EDIT_PRICE_COUNTRY"
        await call.message.edit_text("💰 Which country's price to edit? (e.g., India):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="back_to_main")]]))

    # --- MANAGE STOCK / REMOVE ---
    elif data == "admin_view_stock" and user_id == ADMIN_ID:
        countries = db.get_all_countries()
        if not countries:
            return await call.message.edit_text("📭 Stock is empty.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]))
        
        buttons = [[InlineKeyboardButton(f"🌍 {c} (Stock: {db.get_stock_count(c)})", callback_data=f"manage_stock_{c}")] for c in countries]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        await call.message.edit_text("📊 **Select Country to Manage:**", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("manage_stock_") and user_id == ADMIN_ID:
        country = data.split("_", 2)[2]
        accounts = db.get_accounts_by_country(country)
        if not accounts:
            return await call.message.edit_text(f"❌ No stock in {country}.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_view_stock")]]))
        
        buttons = [[InlineKeyboardButton(f"📞 {acc['phone']}", callback_data="none"), InlineKeyboardButton("❌ Remove", callback_data=f"del_acc_{str(acc['_id'])}_{country}")] for acc in accounts]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_view_stock")])
        await call.message.edit_text(f"📱 **Managing {country} Stock:**", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("del_acc_") and user_id == ADMIN_ID:
        parts = data.split("_", 3)
        acc_id, country = parts[2], parts[3]
        
        try:
            db.remove_account_by_id(acc_id)
            await call.answer("✅ Account removed!", show_alert=True)
            accounts = db.get_accounts_by_country(country)
            if not accounts:
                await call.message.edit_text(f"✅ All removed from {country}.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_view_stock")]]))
            else:
                buttons = [[InlineKeyboardButton(f"📞 {acc['phone']}", callback_data="none"), InlineKeyboardButton("❌ Remove", callback_data=f"del_acc_{str(acc['_id'])}_{country}")] for acc in accounts]
                buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_view_stock")])
                await call.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            await call.answer(f"❌ Error: {e}", show_alert=True)

if __name__ == "__main__":
    print("🚀 Bot is starting...")
    app.run()

