from pymongo import MongoClient
from bson import ObjectId

# KANDIPPA INGA UNGA MONGODB ATLAS URL-A PODANUM
MONGO_URL = "mongodb+srv://Devilsirophai:devilbhaiontop@devil0.d9epxqw.mongodb.net/?appName=Devil0"

client = MongoClient(MONGO_URL)
db = client["TelegramStore"]

users_db = db["users"]
accounts_db = db["accounts"]
prices_db = db["prices"]

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

# --- Account Stock Functions (Session & OTP kaga update panniyachu) ---
def add_account(country, phone, session_string):
    accounts_db.insert_one({"country": country, "phone": phone, "session": session_string})

def get_stock_count(country):
    return accounts_db.count_documents({"country": country})

def get_all_countries():
    return accounts_db.distinct("country")

def get_and_remove_account(country):
    acc = accounts_db.find_one_and_delete({"country": country})
    # User buy pannum pothu muzhu data-vum anuppanum (Session string thevai)
    return acc if acc else None

# --- Manage Stock Functions (Number remove pandrathuku) ---
def remove_account_by_id(acc_id):
    accounts_db.delete_one({"_id": ObjectId(acc_id)})

def get_accounts_by_country(country):
    return list(accounts_db.find({"country": country}))

# --- Price Functions ---
def get_price(country):
    data = prices_db.find_one({"country": country})
    return data["price"] if data else 30  # Default price ₹30 aaga set aagum

def set_price(country, price):
    prices_db.update_one(
        {"country": country}, 
        {"$set": {"price": price}}, 
        upsert=True
    )
