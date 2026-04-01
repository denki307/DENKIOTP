# Replace this part in verify_otp_and_save_async
async def verify_otp_and_save_async(login_states, accounts_col, user_id, otp_code):
    try:
        if user_id not in login_states:
            return False, "Session expired"
        
        state = login_states[user_id]
        client = state["client"]
        
        # dynamic api_id/hash from config or state
        api_id = state.get("api_id", 6435225) 
        api_hash = state.get("api_hash", "4e984ea35f854762dcde906dce426c2d")
        manager = state.get("manager") or PyrogramClientManager(api_id, api_hash)
        
        # Sign in
        success, status, error = await manager.sign_in_with_otp(
            client, state["phone"], state["phone_code_hash"], otp_code
        )
        
        if status == "password_required":
            return False, "password_required"

        if not success:
            return False, error or "OTP verification failed"
        
        session_string = await manager.get_session_string(client)
        
        # SAVE TO DB - Make sure this matches your 'Buy' logic
        account_data = {
            "country": state["country"], # Admin select panna country
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

