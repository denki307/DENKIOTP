import os
import io
import qrcode
import requests
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import database as db

# --- 1. BOT CREDENTIALS ---
API_ID = int(os.environ.get("API_ID", 1234567)) 
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH") 
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN") 
ADMIN_ID = int(os.environ.get("ADMIN_ID", 1234567890)) 

# --- 2. EXTERNAL API CONFIG (dgotp.shop) ---
EXTERNAL_API_KEY = os.environ.get("EXTERNAL_API_KEY", "c5bfcbc63c4e225a49fe64f4a1645f67") 
API_BASE_URL = "https://dgotp.shop/stubs/handler_api.php" 

# --- 3. PAYMENT CONFIG ---
UPI_ID = "denkielangokey@fam" # Unga GPay/PhonePe UPI ID inga podunga
UPI_NAME = "DENKI"

app = Client("resell_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 4. MEMORY STORAGE ---
user_steps = {} 
pending_payments = {} 
admin_steps = {} 
temp_data = {} 
active_orders = {} 

# ==========================================
# MAIN MENU
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_menu(client, message):
    user_id = message.from_user.id
    balance = db.get_balance(user_id)
        
    welcome_text = (
        "💪 Welcome ⇌ ≛ ₓWANTED™ ⋆ - ⭓ ≛ 👑 ⌜ 𝐎𝐩 ⌟\n"
        "[ DESTROYERS ]! (API Resell Center)\n\n"
        f"💳 Your Balance: ₹{balance}\n"
        "🏷 Bot Status: ✅ Auto API OTP Enabled (Telegram Only)"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Buy Accounts", callback_data="buy_accounts")],
        [InlineKeyboardButton("💰 Refill Wallet", callback_data="refill_wallet"), 
         InlineKeyboardButton("💳 Balance", callback_data="check_balance")],
        [InlineKeyboardButton("💬 Support", url="https://t.me/your_support")],
        [InlineKeyboardButton("📢 Channel", url="https://t.me/your_channel"), 
         InlineKeyboardButton("👑 Owner", url="tg://user?id=1234567890")] 
    ])
    await message.reply_text(text=welcome_text, reply_markup=keyboard)

# ==========================================
# ADMIN PANEL
# ==========================================
@app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add New Country", callback_data="admin_add_country")],
        [InlineKeyboardButton("💰 Edit Country Price", callback_data="admin_edit_price")],
        [InlineKeyboardButton("📊 Check API Balance", callback_data="admin_api_balance")]
    ])
    await message.reply_text("👑 Admin Panel\n\n(Stock is fully automated via API)", reply_markup=keyboard)

# ==========================================
# TEXT & PAYMENT HANDLER
# ==========================================
@app.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text

    # Wallet Refill Logic
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
        
        await message.reply_photo(photo=bio, caption=f"✅ QR Code for ₹{amount}.\n\n📲 UPI ID: `{UPI_ID}`\n\n👉 Send Payment Screenshot here.")
        return

    # Admin Logic: Add Country & Edit Price
    if user_id == ADMIN_ID:
        step = admin_steps.get(user_id)
        
        # Add New Country - Step 1: Name
        if step == "WAIT_NEW_COUNTRY":
            temp_data[user_id] = {"new_country": text}
            admin_steps[user_id] = "WAIT_NEW_PRICE"
            await message.reply_text(f"✅ Country '{text}' added.\n\n💰 Enter the price for {text} (e.g., 30):")
            
        # Add New Country - Step 2: Price
        elif step == "WAIT_NEW_PRICE":
            if not text.isdigit():
                return await message.reply_text("❌ Please enter a valid number for price.")
            country_name = temp_data[user_id]["new_country"]
            db.set_price(country_name, int(text))
            admin_steps[user_id] = None
            await message.reply_text(f"✅ Successfully added {country_name} with price ₹{text} to the menu!")

        # Edit Existing Price
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

# Screenshot Handler
@app.on_message(filters.photo & filters.private)
async def handle_screenshot(client, message):
    user_id = message.from_user.id
    if user_steps.get(user_id) == "WAITING_FOR_SCREENSHOT":
        amount = pending_payments.get(user_id, 0)
        admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")]])
        await client.send_photo(chat_id=ADMIN_ID, photo=message.photo.file_id, caption=f"🔔 Deposit Request\n👤 ID: `{user_id}`\n💰 Amount: ₹{amount}", reply_markup=admin_keyboard)
        await message.reply_text("⏳ Screenshot sent to admin. Please wait for approval.")
        user_steps[user_id] = None

# ==========================================
# CALLBACK HANDLERS (INLINE BUTTONS)
# ==========================================
@app.on_callback_query()
async def button_handler(client, call: CallbackQuery):
    data = call.data
    user_id = call.from_user.id
    
    if data == "back_to_main":
        balance = db.get_balance(user_id)
        welcome_text = (
            "💪 Welcome ⇌ ≛ ₓWANTED™ ⋆ - ⭓ ≛ 👑 ⌜ 𝐎𝐩 ⌟\n"
            "[ DESTROYERS ]! (API Resell Center)\n\n"
            f"💳 Your Balance: ₹{balance}\n"
            "🏷 Bot Status: ✅ Auto API OTP Enabled"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Buy Accounts", callback_data="buy_accounts")],
            [InlineKeyboardButton("💰 Refill Wallet", callback_data="refill_wallet"), InlineKeyboardButton("💳 Balance", callback_data="check_balance")],
            [InlineKeyboardButton("💬 Support", url="https://t.me/your_support")],
            [InlineKeyboardButton("📢 Channel", url="https://t.me/your_channel")]
        ])
        await call.message.edit_text(text=welcome_text, reply_markup=keyboard)

    elif data == "check_balance":
        await call.answer(f"💳 Your balance is: ₹{db.get_balance(user_id)}", show_alert=True)

    elif data == "refill_wallet":
        user_steps[user_id] = "ENTER_AMOUNT"
        await call.message.edit_text("💰 Enter the amount to deposit (₹):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]))

    elif data == "buy_accounts":
        buttons = []
        for c in db.get_all_countries():
            buttons.append([InlineKeyboardButton(f"🌍 {c} - ₹{db.get_price(c)}", callback_data=f"view_{c}")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        
        if not db.get_all_countries():
            await call.message.edit_text("📭 No countries available right now. Admin needs to add them.", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await call.message.edit_text("🛒 Choose a Country (Delivered via API):", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("view_"):
        country = data.split("_")[1]
        price = db.get_price(country)
        await call.message.edit_text(f"🌍 {country} Telegram Accounts\n\n💵 Price: ₹{price}\n⚡ Fast Delivery", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"💸 Buy Now (₹{price})", callback_data=f"buy_confirm_{country}")], [InlineKeyboardButton("🔙 Back", callback_data="buy_accounts")]]))

    # ==========================================
    # CORE API: BUY NUMBER (TELEGRAM ONLY)
    # ==========================================
    elif data.startswith("buy_confirm_"):
        country = data.split("_")[2]
        price = db.get_price(country)
        current_bal = db.get_balance(user_id)
        
        if current_bal < price:
            return await call.answer(f"❌ Low Balance! Need ₹{price}.", show_alert=True)
            
        await call.message.edit_text("⏳ Requesting Telegram number from API... Please wait.")

        try:
            service_code = "tg" # Telegram service code
            
            # PERFECT UPDATE: Added your Server ID (91 for Indian Premium)
            # If user selects India it uses 91. If they select USA, it uses 187 (example). 0 is random.
            if country.lower() == "india":
                server_code = "91"  
            elif country.lower() == "usa":
                server_code = "187" # Example for USA, change if needed
            else:
                server_code = "0"
            
            get_num_url = f"{API_BASE_URL}?api_key={EXTERNAL_API_KEY}&action=getNumber&service={service_code}&server={server_code}"
            response = requests.get(get_num_url).text
            
            if "ACCESS_NUMBER" in response:
                parts = response.split(":")
                order_id = parts[1]
                phone_num = parts[2]
                
                # Deduct balance
                db.update_balance(user_id, -price)
                
                # Save active order
                active_orders[user_id] = {
                    "order_id": order_id,
                    "phone": phone_num,
                    "country": country
                }
                
                text = (
                    f"✅ Purchase Successful!\n\n"
                    f"📱 Telegram Number: `+{phone_num}`\n\n"
                    f"👉 Enter this number in your Telegram App.\n"
                    f"👉 Then click '📩 Get OTP' below."
                )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📩 Get OTP", callback_data="get_otp")],
                    [InlineKeyboardButton("🚫 Cancel & Refund", callback_data="cancel_order")]
                ])
                await call.message.edit_text(text, reply_markup=keyboard)
            else:
                await call.message.edit_text(f"❌ API Error: {response}\n\nTry again later.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="buy_accounts")]]))
                
        except Exception as e:
            await call.message.edit_text(f"❌ Server Error: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="buy_accounts")]]))

    # ==========================================
    # CORE API: GET OTP
    # ==========================================
    elif data == "get_otp":
        if user_id not in active_orders:
            return await call.answer("❌ No active order found.", show_alert=True)
            
        await call.answer("⏳ Fetching OTP from API... Please wait.", show_alert=False)
        order_id = active_orders[user_id]["order_id"]
        
        try:
            get_otp_url = f"{API_BASE_URL}?api_key={EXTERNAL_API_KEY}&action=getStatus&id={order_id}"
            response = requests.get(get_otp_url).text
            
            if "STATUS_OK" in response:
                otp_code = response.split(":")[1]
                await call.message.reply_text(f"🔢 Your OTP:\n`{otp_code}`\n\n✅ Login Successful!")
                del active_orders[user_id]
                
            elif response in ["STATUS_WAIT_CODE", "STATUS_WAIT_RETRY", "STATUS_WAIT_RESEND"]:
                await call.answer("⏳ OTP innum varala... Waiting. Oru 10s kalichu click pannunga.", show_alert=True)
                
            elif response == "STATUS_CANCEL":
                country = active_orders[user_id]["country"]
                price = db.get_price(country)
                db.update_balance(user_id, price)
                await call.message.reply_text(f"🚫 Number API aal cancel aagiduchu.\n💰 ₹{price} refunded.")
                del active_orders[user_id]
                
            else:
                await call.message.reply_text(f"⚠️ API Status: {response}")
                
        except Exception as e:
            await call.message.reply_text(f"❌ Error fetching OTP: {e}")

    # ==========================================
    # CORE API: CANCEL & REFUND
    # ==========================================
    elif data == "cancel_order":
        if user_id not in active_orders:
            return await call.answer("❌ No active order to cancel.", show_alert=True)
            
        order_id = active_orders[user_id]["order_id"]
        country = active_orders[user_id]["country"]
        price = db.get_price(country)
        
        try:
            cancel_url = f"{API_BASE_URL}?api_key={EXTERNAL_API_KEY}&action=setStatus&status=8&id={order_id}"
            requests.get(cancel_url)
            
            db.update_balance(user_id, price)
            del active_orders[user_id]
            
            await call.message.edit_text(f"🚫 Order Cancelled.\n💰 ₹{price} refunded to wallet.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]]))
        except Exception as e:
            await call.message.reply_text(f"❌ Error cancelling order: {e}")

    # ==========================================
    # ADMIN DEPOSIT APPROVALS & MISC
    # ==========================================
    elif data.startswith("approve_") or data.startswith("reject_"):
        if user_id != ADMIN_ID:
            return await call.answer("❌ You are not Admin!", show_alert=True)
        action, target_user = data.split("_")
        target_user = int(target_user)
        amount = pending_payments.get(target_user, 0)
        
        if action == "approve":
            db.update_balance(target_user, amount)
            await call.message.edit_caption(f"{call.message.caption}\n\nStatus: ✅ APPROVED")
            await client.send_message(target_user, f"✅ Deposit Approved! ₹{amount} added.")
        else:
            await call.message.edit_caption(f"{call.message.caption}\n\nStatus: ❌ REJECTED")
            await client.send_message(target_user, f"❌ Deposit Rejected!")
        if target_user in pending_payments:
            del pending_payments[target_user]

    elif data == "admin_add_country" and user_id == ADMIN_ID:
        admin_steps[user_id] = "WAIT_NEW_COUNTRY"
        await call.message.edit_text("🌍 Enter New Country Name (e.g., India):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="back_to_main")]]))

    elif data == "admin_edit_price" and user_id == ADMIN_ID:
        admin_steps[user_id] = "EDIT_PRICE_COUNTRY"
        await call.message.edit_text("💰 Which country's price to edit? (e.g., India):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="back_to_main")]]))

    elif data == "admin_api_balance" and user_id == ADMIN_ID:
        try:
            bal_url = f"{API_BASE_URL}?api_key={EXTERNAL_API_KEY}&action=getBalance"
            resp = requests.get(bal_url).text
            await call.answer(f"API Dashboard Balance: {resp}", show_alert=True)
        except:
            await call.answer("❌ Could not fetch API balance.", show_alert=True)

if __name__ == "__main__":
    print("🚀 API Bot is starting...")
    app.run()

