"""
Account Management Module for OTP Bot
Handles Pyrogram login, OTP verification, and session management
"""

import logging
import re
import threading
import time
import asyncio
from datetime import datetime
from pyrogram import Client
from pyrogram.errors import (
    PhoneNumberInvalid, PhoneCodeInvalid,
    PhoneCodeExpired, SessionPasswordNeeded, PasswordHashInvalid,
    FloodWait, PhoneCodeEmpty
)

logger = logging.getLogger(__name__)

# Global event loop for async operations
_global_event_loop = None

def get_event_loop():
    """Get or create a global event loop"""
    global _global_event_loop
    if _global_event_loop is None:
        try:
            _global_event_loop = asyncio.get_running_loop()
        except RuntimeError:
            _global_event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_global_event_loop)
    return _global_event_loop

# -----------------------
# ASYNC MANAGEMENT
# -----------------------
class AsyncManager:
    """Manages async operations in sync context"""
    def __init__(self):
        self.lock = threading.Lock()
    
    def run_async(self, coro):
        """Run async coroutine from sync context"""
        try:
            loop = get_event_loop()
            if loop.is_running():
                return self._run_in_thread(coro)
            else:
                return loop.run_until_complete(coro)
        except Exception as e:
            logger.error(f"Async operation failed: {e}")
            raise
    
    def _run_in_thread(self, coro):
        """Run coroutine in a separate thread with its own event loop"""
        result = None
        exception = None
        
        def run():
            nonlocal result, exception
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result = new_loop.run_until_complete(coro)
                new_loop.close()
            except Exception as e:
                exception = e
        
        thread = threading.Thread(target=run)
        thread.start()
        thread.join()
        
        if exception:
            raise exception
        return result

# -----------------------
# PYROGRAM CLIENT MANAGER
# -----------------------
class PyrogramClientManager:
    """Fixed Pyrogram client management without ping issues"""
    def __init__(self, api_id, api_hash):
        self.api_id = api_id
        self.api_hash = api_hash
    
    async def create_client(self, session_string=None, name=None):
        """Create a Pyrogram client with proper settings"""
        if name is None:
            name = f"client_{int(time.time())}"
        
        client = Client(
            name=name,
            session_string=session_string,
            api_id=self.api_id,
            api_hash=self.api_hash,
            in_memory=True,
            no_updates=True,
            sleep_threshold=0
        )
        return client
    
    async def safe_disconnect(self, client):
        """Safely disconnect client"""
        try:
            if client and hasattr(client, 'is_connected') and client.is_connected:
                await client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting client: {e}")

# -----------------------
# ACCOUNT FUNCTIONS (UPDATED)
# -----------------------
async def pyrogram_login_flow_async(login_states, user_id, phone_number, country, api_id, api_hash):
    """Start login flow by sending OTP"""
    manager = PyrogramClientManager(api_id, api_hash)
    client = await manager.create_client()
    try:
        await client.connect()
        sent_code = await client.send_code(phone_number)
        login_states[user_id] = {
            "client": client,
            "phone": phone_number,
            "phone_code_hash": sent_code.phone_code_hash,
            "country": country,
            "api_id": api_id,
            "api_hash": api_hash,
            "manager": manager
        }
        return True, "OTP sent"
    except Exception as e:
        await manager.safe_disconnect(client)
        return False, str(e)

async def verify_otp_and_save_async(login_states, accounts_col, user_id, otp_code):
    """Verify OTP and save to MongoDB"""
    try:
        if user_id not in login_states: return False, "Session expired"
        
        state = login_states[user_id]
        client = state["client"]
        manager = state["manager"]
        
        try:
            await client.sign_in(state["phone"], state["phone_code_hash"], otp_code)
        except SessionPasswordNeeded:
            return False, "password_required"
        except Exception as e:
            return False, str(e)
        
        session_string = await client.export_session_string()
        
        account_data = {
            "country": state["country"],
            "phone": state["phone"],
            "session_string": session_string,
            "status": "active",
            "used": False,
            "created_at": datetime.utcnow()
        }
        
        if accounts_col is not None:
            accounts_col.insert_one(account_data)
            
        await manager.safe_disconnect(client)
        login_states.pop(user_id, None)
        return True, "Account added successfully"
    except Exception as e:
        return False, str(e)

async def verify_2fa_password_async(login_states, accounts_col, user_id, password):
    """Handle 2FA password and save"""
    state = login_states[user_id]
    client = state["client"]
    try:
        await client.check_password(password)
        session_string = await client.export_session_string()
        
        accounts_col.insert_one({
            "country": state["country"],
            "phone": state["phone"],
            "session_string": session_string,
            "status": "active",
            "used": False,
            "created_at": datetime.utcnow()
        })
        await state["manager"].safe_disconnect(client)
        login_states.pop(user_id, None)
        return True, "Account added"
    except Exception as e:
        return False, str(e)

# --- NEW: DEVICE & LOGOUT LOGIC ---

async def get_active_devices_async(session_string, api_id, api_hash):
    """Fetch all active sessions for a user"""
    client = Client("dev_check", session_string=session_string, api_id=api_id, api_hash=api_hash, in_memory=True)
    try:
        await client.connect()
        sessions = await client.get_sessions()
        devices = []
        for s in sessions:
            devices.append({
                "model": s.device_model,
                "system": s.system_version,
                "is_current": s.is_current,
                "type": "Bot Device 🤖" if s.is_current else "Mobile Device 📱"
            })
        await client.disconnect()
        return devices
    except: return []

async def logout_session_async(session_string, api_id, api_hash):
    """Force logout the bot's session (String session will be destroyed)"""
    client = Client("logout_task", session_string=session_string, api_id=api_id, api_hash=api_hash, in_memory=True)
    try:
        await client.connect()
        await client.log_out() # REAL LOGOUT FROM TELEGRAM SERVERS
        return True, "Logged out"
    except Exception as e:
        return False, str(e)

# -----------------------
# SYNC CLASS MANAGER
# -----------------------
class AccountManager:
    def __init__(self, api_id, api_hash):
        self.api_id = api_id
        self.api_hash = api_hash
        self.async_manager = AsyncManager()

    def pyrogram_login_flow_sync(self, login_states, accounts_col, user_id, phone, chat_id, msg_id, country):
        return self.async_manager.run_async(pyrogram_login_flow_async(login_states, user_id, phone, country, self.api_id, self.api_hash))

    def verify_otp_and_save_sync(self, login_states, accounts_col, user_id, otp):
        return self.async_manager.run_async(verify_otp_and_save_async(login_states, accounts_col, user_id, otp))

    def verify_2fa_password_sync(self, login_states, accounts_col, user_id, pwd):
        return self.async_manager.run_async(verify_2fa_password_async(login_states, accounts_col, user_id, pwd))

    def logout_session_sync(self, acc_id, user_id, sessions_col, accounts_col, orders_col):
        # Fetch session string from DB and logout
        from bson import ObjectId
        acc = accounts_col.find_one({"_id": ObjectId(acc_id)})
        if acc:
            return self.async_manager.run_async(logout_session_async(acc['session_string'], self.api_id, self.api_hash))
        return False, "Account not found"
