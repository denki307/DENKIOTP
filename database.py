from pymongo import MongoClient

# KANDIPPA INGA UNGA MONGODB ATLAS URL-A PODANUM
MONGO_URL = "mongodb+srv://Devilsirophai:devilbhaiontop@devil0.d9epxqw.mongodb.net/?appName=Devil0"

client = MongoClient(MONGO_URL)
db = client["TelegramStore"]

users_db = db["users"]
accounts_db = db["accounts"]

# --- User Balance Functions ---
def get_balance(user_id):
    user = users_db.find_one({"user_id": user_id})
    return user["balance"] if user else 0.0

def update_balance(user_id, amount):
    users_db.update_one(
        {"user_id": user_id}, 
        {"$inc": {"balance": amount}}, 
        upsert=True
    )

def set_balance(user_id, amount):
    users_db.update_one(
        {"user_id": user_id}, 
        {"$set": {"balance": amount}}, 
        upsert=True
    )

# --- Account Stock Functions ---
def add_account(country, acc_details):
    accounts_db.insert_one({"country": country, "details": acc_details})

def get_stock_count(country):
    return accounts_db.count_documents({"country": country})

def get_all_countries():
    # Ethana countries stock la irukku nu list edukkum
    return accounts_db.distinct("country")

def get_and_remove_account(country):
    acc = accounts_db.find_one_and_delete({"country": country})
    return acc["details"] if acc else None

