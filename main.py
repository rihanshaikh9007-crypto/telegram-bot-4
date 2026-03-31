import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from pymongo import MongoClient
import random
import os
import time
from datetime import datetime
from flask import Flask, request
import concurrent.futures

# ================= ⚡ SETTINGS =================
TOKEN = '8677737410:AAHiOAMo_JNS579A1uOsMFWYziecVSKkPnk'
WEBHOOK_URL = 'https://telegram-bot-4-sj6o.onrender.com' 

bot = telebot.TeleBot(TOKEN, parse_mode='HTML', threaded=False)

ADMIN_ID = 1484173564
APPROVAL_CHANNEL = "@ValiModes_key"

# ================= 💾 DATABASE =================
MONGO_URL = "mongodb+srv://rihanshaikh9007_db_user:Rihanshaikh123@cluster0.zinixku.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URL, maxPoolSize=200) 
db = client['webseries_bot']

channels_col = db['channels']
join_reqs_col = db['join_reqs']
users_col = db['users']
settings_col = db['settings']
task_users_col = db['task_users']
tasks_col = db['tasks']
promo_col = db['promo_codes']
promo_users_col = db['promo_users']

# Indexing for speed
try:
    users_col.create_index("user_id", unique=True)
except: pass

# ================= 🛡️ HELPERS =================
user_last_msg = {}
admin_temp_data = {}

def flood_check(user_id):
    now = time.time()
    if user_id in user_last_msg and now - user_last_msg[user_id] < 0.3: return True 
    user_last_msg[user_id] = now
    return False

# ================= 👨‍💻 ADVANCED ADMIN SYSTEM =================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID: return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("➕ Add Bulk Channel", callback_data="add_bulk"),
               InlineKeyboardButton("🗑️ Clear All Channels", callback_data="clear_channels"),
               InlineKeyboardButton("📋 View Channels", callback_data="view_channels"),
               InlineKeyboardButton("📊 Bot Stats", callback_data="adm_stats"))
    bot.send_message(message.chat.id, "💎 <b>Admin Customization Panel</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    
    # --- ADMIN ACTIONS ---
    if uid == ADMIN_ID:
        if call.data == "add_bulk":
            msg = bot.send_message(call.message.chat.id, "🆔 <b>Saare Channel IDs bhejo (Space dekar):</b>")
            bot.register_next_step_handler(msg, get_bulk_ids)
        
        elif call.data.startswith("setcol_"):
            color = call.data.split("_")[1]
            admin_temp_data[uid]['color'] = color
            msg = bot.send_message(call.message.chat.id, "✨ <b>Ab Buttons ke liye koi ek Emoji bhejo:</b>\n(Aap custom premium emoji bhi bhej sakte hain)")
            bot.register_next_step_handler(msg, finalize_bulk_add)

        elif call.data == "clear_channels":
            channels_col.delete_many({})
            bot.answer_callback_query(call.id, "✅ Saare channels delete ho gaye!")
            
        elif call.data == "view_channels":
            chs = list(channels_col.find())
            text = "📋 <b>Channels List:</b>\n\n"
            for c in chs: text += f"ID: <code>{c['channel_id']}</code> | Style: {c['color']} {c['emoji']}\n"
            bot.send_message(call.message.chat.id, text or "Khaali hai!")

    # --- USER ACTIONS ---
    if call.data == "verify":
        unjoined = get_unjoined(uid)
        if not unjoined:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            send_main_menu(call.message.chat.id)
        else:
            show_force_sub(call.message.chat.id, uid, is_retry=True, msg_id=call.message.message_id)

# Admin Step-by-Step Logic
def get_bulk_ids(message):
    ids = message.text.replace(',', ' ').split()
    if not ids: return bot.send_message(message.chat.id, "❌ Galat ID format!")
    admin_temp_data[message.from_user.id] = {'ids': ids}
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🔵 Blue", callback_data="setcol_primary"),
               InlineKeyboardButton("🟢 Green", callback_data="setcol_success"),
               InlineKeyboardButton("🔴 Red", callback_data="setcol_danger"),
               InlineKeyboardButton("🟡 Yellow", callback_data="setcol_warning"))
    bot.send_message(message.chat.id, "🎨 <b>Select Button Color Theme:</b>", reply_markup=markup)

def finalize_bulk_add(message):
    uid = message.from_user.id
    emoji = message.text.strip()
    data = admin_temp_data.get(uid)
    if not data: return

    count = 0
    for cid in data['ids']:
        try:
            link = bot.create_chat_invite_link(cid, creates_join_request=True).invite_link
            channels_col.update_one(
                {"channel_id": cid}, 
                {"$set": {"link": link, "color": data['color'], "emoji": emoji}}, 
                upsert=True
            )
            count += 1
        except: pass
    
    bot.send_message(message.chat.id, f"✅ <b>Success!</b> {count} Channels add ho gaye.\nStyle: {data['color']} with {emoji}")
    del admin_temp_data[uid]

# ================= 💎 USER INTERFACE (FAST & COLORFUL) =================
def get_unjoined(uid):
    unjoined = []
    for ch in list(channels_col.find()):
        try:
            s = bot.get_chat_member(ch['channel_id'], uid).status
            if s not in ['member', 'administrator', 'creator'] and not join_reqs_col.find_one({"user_id": uid, "channel_id": ch['channel_id']}):
                unjoined.append(ch)
        except: unjoined.append(ch) 
    return unjoined

@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = message.from_user.id
    if flood_check(uid): return
    
    if not users_col.find_one({"user_id": uid}):
        users_col.insert_one({"user_id": uid, "coins": 0, "streak": 0, "last_bonus": 0, "join_date": datetime.now().strftime("%Y-%m-%d")})
    
    unjoined = get_unjoined(uid)
    if unjoined:
        show_force_sub(message.chat.id, uid)
    else:
        send_main_menu(message.chat.id)

def show_force_sub(chat_id, uid, is_retry=False, msg_id=None):
    unjoined = get_unjoined(uid)
    markup = InlineKeyboardMarkup(row_width=3) # 1 Line mein 3 buttons
    
    buttons = []
    for ch in unjoined:
        emoji = ch.get('emoji', '🚀')
        buttons.append(InlineKeyboardButton(f"{emoji} Join", url=ch['link']))
    
    markup.add(*buttons)
    # Bada Done/Try Again Button
    btn_text = "🔄 Try Again" if is_retry else "✅ Done !!"
    markup.add(InlineKeyboardButton(btn_text, callback_data="verify"))

    caption = """💎 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗩𝗔𝗟𝗜 𝗠𝗢𝗗𝗦 𝗗𝗥𝗜𝗣 𝗞𝗘𝗬 

🎮 𝗬𝗼𝘂𝗿 𝗙𝗥𝗘𝗘 𝗙𝗜𝗥𝗘 𝗔𝗣𝗞𝗠𝗢𝗗 𝗞𝗘𝗬 𝗶𝘀 𝗷𝘂𝘀𝘁 𝗼𝗻𝗲 𝘀𝘁𝗲𝗽 𝗮𝘄𝗮𝘆! 🔥
━━━━━━━━━━━━━━━
🛠️ 𝗠𝗢𝗗 𝗙𝗘𝗔𝗧𝗨𝗥𝗘𝗦:
✅ 𝗦𝗶𝗹𝗲𝗻𝘁 𝗞𝗶𝗹𝗹 / 𝗦𝗶𝗹𝗲𝗻𝘁 𝗔𝗶𝗺
✅ 𝗠𝗮𝗴𝗻𝗲𝘁𝗶𝗰 𝗔𝗶𝗺
✅ 𝗔𝗻𝘁𝗶-𝗧𝗮𝘁𝘂
✅ 𝗚𝗵𝗼𝘀𝘁 𝗛𝗮𝗰𝗸 / 𝗦𝗽𝗲𝗲𝗱 𝗛𝗮𝗰𝗸
✅ 𝗘𝗦𝗣 (𝗡𝗮𝗺𝗲, 𝗟𝗶𝗻𝗲, 𝗕𝗼𝘅)
━━━━━━━━━━━━━━━
🚨 𝗔𝗖𝗖𝗘𝗦𝗦 𝗚𝗘𝗧 𝗞𝗔𝗥𝗡𝗘 𝗞𝗘 𝗟𝗜𝗬𝗘
📢 𝗡𝗶𝗰𝗵𝗲 𝗱𝗶𝘆𝗲 𝗴𝗮𝘆𝗲 𝘀𝗮𝗿𝗲 𝗰𝗵𝗮𝗻𝗻𝗲𝗹𝘀 𝗝𝗢𝗜𝗡 𝗸𝗮𝗿𝗻𝗮 𝗭𝗔𝗥𝗨𝗥𝗜 𝗵𝗮𝗶
━━━━━━━━━━━━━━━"""

    video_url = "https://files.catbox.moe/4hbu2q.mp4"
    
    if is_retry:
        bot.answer_callback_query(callback_query_id=uid, text="❌ Pehle bache hue channels join karo!", show_alert=True)
        try: bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=markup)
        except: pass
    else:
        try: bot.send_video(chat_id, video_url, caption=caption, reply_markup=markup)
        except: bot.send_message(chat_id, caption, reply_markup=markup)

def send_main_menu(chat_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🛒 VIP Key Shop", "🎁 Daily Streak Bonus", "📝 Earn Tasks", "🎲 Mini Games", "🔗 Refer & Earn", "👤 My Account")
    bot.send_message(chat_id, "🌟 <b>Welcome back! Aapka access unlock ho gaya hai.</b>", reply_markup=markup)

# ================= 🚀 WEBHOOK SERVER =================
app = Flask(__name__)
executor = concurrent.futures.ThreadPoolExecutor(max_workers=100)

@app.route('/')
def home(): return "Bot is Online with Custom Emojis! 🚀", 200

@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        executor.submit(bot.process_new_updates, [update])
        return "OK", 200
    return "Forbidden", 403

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL + '/' + TOKEN)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), threaded=True)
