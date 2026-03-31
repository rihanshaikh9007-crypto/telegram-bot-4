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
TOKEN = '8677737410:AAE5w_R2FlugrQOM-zZ76UAcw-nAg8dRUok'
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
refs_col = db['completed_refs']

try:
    users_col.create_index("user_id", unique=True)
except: pass

if not settings_col.find_one({"name": "key_link"}):
    settings_col.insert_one({"name": "key_link", "value": "https://www.mediafire.com/file/if3uvvwjbj87lo2/DRIPCLIENT_v6.2_GLOBAL_AP.apks/file"})
if not settings_col.find_one({"name": "base_price"}):
    settings_col.insert_one({"name": "base_price", "value": "15"})

user_last_msg = {}
admin_temp_data = {}

def flood_check(user_id):
    now = time.time()
    if user_id in user_last_msg and now - user_last_msg[user_id] < 0.3: return True 
    user_last_msg[user_id] = now
    return False

def is_user_banned(user_id):
    user = users_col.find_one({"user_id": user_id})
    return user and user.get("is_banned", 0) == 1

# ================= 👨‍💻 ADVANCED ADMIN SYSTEM =================
@bot.message_handler(commands=['addcoins', 'setprice', 'promo', 'check', 'change', 'admin', 'addtask'])
def admin_super_commands(message):
    if message.chat.id != ADMIN_ID: return
    cmd = message.text.split()[0]
    
    if cmd == '/addcoins':
        try:
            _, uid, amt = message.text.split()
            users_col.update_one({"user_id": int(uid)}, {"$inc": {"coins": int(amt)}}, upsert=True)
            bot.reply_to(message, f"✅ {amt} Coins added to {uid}.")
            bot.send_message(int(uid), f"🎁 Admin ne aapko <b>{amt} Coins</b> bheje hain!")
        except: bot.reply_to(message, "❌ Format: `/addcoins USER_ID COINS`")

    elif cmd == '/setprice':
        try:
            price = message.text.split()[1]
            settings_col.update_one({"name": "base_price"}, {"$set": {"value": price}}, upsert=True)
            bot.reply_to(message, f"✅ Base Key Price set to {price} Coins.")
        except: bot.reply_to(message, "❌ Format: `/setprice 15`")

    elif cmd == '/promo':
        try:
            args = message.text.split()
            code, reward, max_u = args[1], int(args[2]), int(args[3])
            hours = int(args[4]) if len(args) > 4 else 87600 
            expiry = time.time() + (hours * 3600)
            promo_col.insert_one({"code": code, "reward": reward, "max_uses": max_u, "used_count": 0, "expiry": expiry})
            bot.reply_to(message, f"✅ <b>Promo Created!</b>\nCode: <code>{code}</code>\nReward: {reward}\nLimit: {max_u}\nValid for: {hours} Hours")
        except: bot.reply_to(message, "❌ Format: `/promo CODE REWARD LIMIT HOURS`")

    elif cmd == '/addtask':
        try:
            args = message.text.split()
            task_id, reward, secret, link = args[1], int(args[2]), args[3], args[4]
            tasks_col.update_one({"task_id": task_id}, {"$set": {"reward": reward, "secret": secret, "link": link}}, upsert=True)
            bot.reply_to(message, f"✅ <b>Task Added!</b>\nID: {task_id}\nReward: {reward}\nSecret: {secret}\nLink: {link}")
        except: bot.reply_to(message, "❌ Format: `/addtask TASK_ID REWARD SECRET_CODE LINK`")

    elif cmd == '/check':
        try:
            uid = int(message.text.split()[1])
            user = users_col.find_one({"user_id": uid})
            if not user: return bot.reply_to(message, "❌ User not found.")
            refs = refs_col.count_documents({"referrer_id": uid})
            status = "🔴 BANNED" if user.get("is_banned", 0) == 1 else "🟢 ACTIVE"
            bot.reply_to(message, f"🕵️ <b>User Info:</b>\n\n🆔 ID: {uid}\n💰 Coins: {user.get('coins', 0)}\n👥 Referrals: {refs}\n📅 Joined: {user.get('join_date', 'N/A')}\n📊 Status: {status}")
        except: bot.reply_to(message, "❌ Format: `/check USER_ID`")
        
    elif cmd == '/change':
        new_link = message.text.replace('/change', '').strip()
        if new_link:
            settings_col.update_one({"name": "key_link"}, {"$set": {"value": new_link}}, upsert=True)
            bot.reply_to(message, f"✅ <b>Link Updated!</b>\nNew link for keys:\n{new_link}")

    elif cmd == '/admin':
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(InlineKeyboardButton("➕ Add Bulk Channel", callback_data="add_bulk"),
                   InlineKeyboardButton("🗑️ Clear All Channels", callback_data="clear_channels"),
                   InlineKeyboardButton("📋 View Channels", callback_data="view_channels"),
                   InlineKeyboardButton("📊 Bot Stats", callback_data="adm_stats"))
        bot.send_message(message.chat.id, "💎 <b>Admin Customization Panel</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["add_bulk", "clear_channels", "view_channels", "adm_stats"] or call.data.startswith("setcol_"))
def admin_callbacks(call):
    uid = call.from_user.id
    if uid != ADMIN_ID: return
    
    if call.data == "add_bulk":
        msg = bot.send_message(call.message.chat.id, "🆔 <b>Saare Channel IDs bhejo (Space dekar):</b>")
        bot.register_next_step_handler(msg, get_bulk_ids)
    
    elif call.data.startswith("setcol_"):
        color = call.data.split("_")[1]
        admin_temp_data[uid]['color'] = color
        msg = bot.send_message(call.message.chat.id, "✨ <b>Ab Buttons ke liye koi ek Emoji bhejo:</b>")
        bot.register_next_step_handler(msg, finalize_bulk_add)

    elif call.data == "clear_channels":
        channels_col.delete_many({})
        bot.answer_callback_query(call.id, "✅ Saare channels delete ho gaye!")
        bot.send_message(call.message.chat.id, "🗑️ Saare channels database se hata diye gaye hain. Ab naye channels add karein.")
        
    elif call.data == "view_channels":
        chs = list(channels_col.find())
        text = "📋 <b>Channels List:</b>\n\n"
        for c in chs: text += f"ID: <code>{c['channel_id']}</code> | Style: {c.get('color', 'primary')} | Emoji: {c.get('emoji', '🚀')}\n"
        bot.send_message(call.message.chat.id, text if chs else "Khaali hai!")

def get_bulk_ids(message):
    ids = message.text.replace(',', ' ').split()
    if not ids: return bot.send_message(message.chat.id, "❌ Galat ID format!")
    admin_temp_data[message.from_user.id] = {'ids': ids}
    # 🔥 Telegram ki Nayi API ke 4 Asli Colors
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🔵 Blue (Primary)", callback_data="setcol_primary"),
               InlineKeyboardButton("🟢 Green (Success)", callback_data="setcol_success"),
               InlineKeyboardButton("🔴 Red (Danger)", callback_data="setcol_danger"),
               InlineKeyboardButton("⚪ Grey (Default)", callback_data="setcol_default"))
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
    
    bot.send_message(message.chat.id, f"✅ <b>Success!</b> {count} Channels add ho gaye.\nColor: {data['color']} | Emoji: {emoji}")
    if uid in admin_temp_data: del admin_temp_data[uid]

# ================= 💎 USER INTERFACE & FORCE SUB (COLORS ADDED) =================
def get_unjoined(uid):
    unjoined = []
    for ch in list(channels_col.find()):
        try:
            s = bot.get_chat_member(ch['channel_id'], uid).status
            if s not in ['member', 'administrator', 'creator'] and not join_reqs_col.find_one({"user_id": uid, "channel_id": ch['channel_id']}):
                unjoined.append(ch)
        except: unjoined.append(ch) 
    return unjoined

@bot.chat_join_request_handler()
def handle_join_request(message: telebot.types.ChatJoinRequest):
    join_reqs_col.insert_one({"user_id": message.from_user.id, "channel_id": str(message.chat.id)})
    try: bot.approve_chat_join_request(message.chat.id, message.from_user.id)
    except: pass

@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = message.from_user.id
    if flood_check(uid) or is_user_banned(uid): return
    
    if not users_col.find_one({"user_id": uid}):
        users_col.insert_one({"user_id": uid, "coins": 0, "streak": 0, "last_bonus": 0, "join_date": datetime.now().strftime("%Y-%m-%d")})
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
            if ref_id != uid and not refs_col.find_one({"user_id": uid}):
                users_col.update_one({"user_id": ref_id}, {"$inc": {"coins": 2}})
                refs_col.insert_one({"user_id": uid, "referrer_id": ref_id})
                try: bot.send_message(ref_id, "🎉 <b>Congrats!</b>\nKisi ne aapke link se bot start kiya hai. <b>+2 Coins</b> Added!")
                except: pass
    
    unjoined = get_unjoined(uid)
    if unjoined:
        show_force_sub(message.chat.id, uid)
    else:
        send_main_menu(message.chat.id)

def show_force_sub(chat_id, uid, is_retry=False, msg_id=None):
    unjoined = get_unjoined(uid)
    markup = InlineKeyboardMarkup(row_width=3) 
    
    buttons = []
    for ch in unjoined:
        emoji = ch.get('emoji', '🚀') 
        btn_style = ch.get('color', 'primary') # 🔥 NAYI API KA JADOO
        # PyTelegramBotAPI me nayi styles kwargs ke through pass hoti hain
        buttons.append(InlineKeyboardButton(text=f"{emoji} Join", url=ch['link'], **{'style': btn_style}))
    
    markup.add(*buttons)
    btn_text = "🔄 Try Again" if is_retry else "✅ Done !!"
    markup.add(InlineKeyboardButton(text=btn_text, callback_data="verify", **{'style': 'success'})) # Done button hamesha Green!

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
        try: bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=markup)
        except: pass
    else:
        try: bot.send_video(chat_id, video_url, caption=caption, reply_markup=markup)
        except: bot.send_message(chat_id, caption, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "verify")
def verify_callback(call):
    uid = call.from_user.id
    unjoined = get_unjoined(uid)
    
    if not unjoined:
        bot.answer_callback_query(call.id, "✅ Verified Successfully!", show_alert=False)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_main_menu(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ Pehle bache hue channels join karo!", show_alert=True)
        show_force_sub(call.message.chat.id, uid, is_retry=True, msg_id=call.message.message_id)

def send_main_menu(chat_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🛒 VIP Key Shop", "🎁 Daily Streak Bonus", "📝 Earn Tasks", "🎲 Mini Games", "🔗 Refer & Earn", "👤 My Account")
    bot.send_message(chat_id, "🌟 <b>Welcome back! Aapka access unlock ho gaya hai.</b>", reply_markup=markup)

# ================= 📱 BAAKI MENU FEATURES =================
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    uid = message.from_user.id
    if flood_check(uid) or is_user_banned(uid): return
    if get_unjoined(uid): return start_handler(message)
    
    user = users_col.find_one({"user_id": uid})
    if not user: return
    coins = user.get('coins', 0)
    t = message.text

    if t == "👤 My Account": bot.send_message(uid, f"👤 <b>Account Stats</b>\n\n🆔 ID: <code>{uid}</code>\n💰 Coins: <b>{coins}</b>\n🔥 Streak: <b>{user.get('streak', 0)} Days</b>")
    elif t == "🔗 Refer & Earn": bot.send_message(uid, f"📢 <b>REFER & EARN</b>\nInvite friends & get <b>2 Coins</b> per join!\n\n🔗 Your Link:\nhttps://t.me/{bot.get_me().username}?start={uid}")
    elif t == "🎁 Daily Streak Bonus":
        last_bonus = user.get('last_bonus', 0)
        streak = user.get('streak', 0)
        now = time.time()
        if now - last_bonus < 86400: bot.send_message(uid, f"⏳ <b>Wait!</b>\nAapko agla bonus <b>{int((86400 - (now - last_bonus)) / 3600)} ghante</b> baad milega.")
        else:
            if now - last_bonus > 172800: streak = 1 
            else: streak = min(streak + 1, 7) 
            reward = streak * 2 
            users_col.update_one({"user_id": uid}, {"$inc": {"coins": reward}, "$set": {"last_bonus": now, "streak": streak}})
            bot.send_message(uid, f"🔥 <b>Day {streak} Streak Bonus!</b>\nAapko <b>{reward} Coins</b> mil gaye hain.\n\n<i>Kal aana mat bhoolna, streak tut jayegi!</i>")
    elif t == "📝 Earn Tasks":
        all_tasks = list(tasks_col.find())
        pending_tasks = [task for task in all_tasks if not task_users_col.find_one({"user_id": uid, "task_id": task['task_id']})]
        if not pending_tasks: return bot.send_message(uid, "🎉 Aapne saare tasks complete kar liye hain! Naye tasks ka wait karein.")
        markup = InlineKeyboardMarkup()
        for task in pending_tasks: markup.add(InlineKeyboardButton(f"Task: {task['task_id']} (+{task['reward']} Coins)", callback_data=f"task_{task['task_id']}"))
        bot.send_message(uid, "📝 <b>Available Tasks:</b>\nTask complete karein aur secret code lakar coins jeetein!", reply_markup=markup)
    elif t == "🎲 Mini Games":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🪙 Play 5 Coins", callback_data="game_5"), InlineKeyboardButton("🪙 Play 10 Coins", callback_data="game_10"))
        markup.add(InlineKeyboardButton("🪙 Play 20 Coins", callback_data="game_20"))
        bot.send_message(uid, f"🎲 <b>Coin Toss Game (Double or Nothing)</b>\nAapke Coins: <b>{coins}</b>\nKitne coins lagana chahte ho?", reply_markup=markup)
    elif t == "🏆 Leaderboard":
        top = list(refs_col.aggregate([{"$group": {"_id": "$referrer_id", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 5}]))
        msg = "🏆 <b>TOP REFERRERS</b> 🏆\n\n"
        for i, ref_data in enumerate(top): msg += f"{i+1}. User <code>{ref_data['_id']}</code> - {ref_data['count']} Invites\n"
        bot.send_message(uid, msg)
    elif t == "🎟️ Redeem Promo":
        msg = bot.send_message(uid, "🎫 Apna Promo Code enter karein:")
        bot.register_next_step_handler(msg, process_promo)
    elif t == "🛒 VIP Key Shop":
        setting = settings_col.find_one({"name": "base_price"})
        bp = int(setting['value']) if setting else 15
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton(text=f"🔑 1-Day VIP ({bp} Coins)", callback_data=f"buy_1_{bp}", **{'style': 'primary'}),
            InlineKeyboardButton(text=f"🔑 3-Day VIP ({bp*2} Coins)", callback_data=f"buy_3_{bp*2}", **{'style': 'primary'})
        )
        bot.send_message(uid, f"🛒 <b>VIP KEY SHOP</b>\nAapke Coins: <b>{coins}</b>", reply_markup=markup)

# ================= 🎲 TASKS & GAMES =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("task_"))
def handle_task(call):
    task_id = call.data.split("_")[1]
    task = tasks_col.find_one({"task_id": task_id})
    if not task: return bot.answer_callback_query(call.id, "❌ Task removed!")
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🌐 Open Task Link", url=task['link']))
    msg = bot.send_message(call.message.chat.id, f"📝 <b>Task ID:</b> {task_id}\n💰 <b>Reward:</b> {task['reward']} Coins\n\n1️⃣ Link open karein.\n2️⃣ Wahan diye gaye 'Secret Code' ko copy karein.\n3️⃣ Abhi yahan bot ko wo code message karein👇", reply_markup=markup)
    bot.register_next_step_handler(msg, lambda m: verify_task_code(m, task))

def verify_task_code(message, task):
    uid, code = message.from_user.id, message.text.strip()
    if task_users_col.find_one({"user_id": uid, "task_id": task['task_id']}): return bot.send_message(uid, "❌ Aap already ye task kar chuke hain.")
    if code == task['secret']:
        users_col.update_one({"user_id": uid}, {"$inc": {"coins": task['reward']}})
        task_users_col.insert_one({"user_id": uid, "task_id": task['task_id']})
        bot.send_message(uid, f"🎉 <b>Task Verified!</b>\nAapko <b>{task['reward']} Coins</b> mil gaye hain!")
    else: bot.send_message(uid, "❌ <b>Wrong Secret Code!</b> Try again.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("game_"))
def handle_game_setup(call):
    amt = int(call.data.split("_")[1])
    uid = call.from_user.id
    user = users_col.find_one({"user_id": uid})
    if user.get('coins', 0) < amt: return bot.answer_callback_query(call.id, f"❌ Aapke paas {amt} coins nahi hain!", show_alert=True)
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🗣️ Heads", callback_data=f"play_{amt}_Heads"), InlineKeyboardButton("🪙 Tails", callback_data=f"play_{amt}_Tails"))
    bot.edit_message_text(f"🎲 <b>Bet:</b> {amt} Coins\nChuno Heads ya Tails?", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("play_"))
def handle_game_play(call):
    parts = call.data.split("_")
    amt, choice = int(parts[1]), parts[2]
    uid = call.from_user.id
    user = users_col.find_one({"user_id": uid})
    if user.get('coins', 0) < amt: return bot.answer_callback_query(call.id, "❌ Not enough coins!", show_alert=True)
    users_col.update_one({"user_id": uid}, {"$inc": {"coins": -amt}}) 
    result = random.choice(["Heads", "Tails"])
    if choice == result:
        users_col.update_one({"user_id": uid}, {"$inc": {"coins": amt * 2}}) 
        bot.edit_message_text(f"🎲 Coin Flipping...\n\nResult: <b>{result}</b>\n🎉 <b>YOU WIN!</b> You got {amt*2} Coins!", chat_id=call.message.chat.id, message_id=call.message.message_id)
    else:
        bot.edit_message_text(f"🎲 Coin Flipping...\n\nResult: <b>{result}</b>\n😢 <b>YOU LOSE!</b> Better luck next time.", chat_id=call.message.chat.id, message_id=call.message.message_id)

# ================= 🛒 PROMO & SHOP =================
def process_promo(message):
    uid, code = message.from_user.id, message.text.strip().upper()
    promo = promo_col.find_one({"code": code})
    if not promo: return bot.send_message(uid, "❌ Invalid Promo Code!")
    if time.time() > promo.get('expiry', 0): return bot.send_message(uid, "❌ Ye Promo Code Expire ho chuka hai!")
    if promo.get('used_count', 0) >= promo['max_uses']: return bot.send_message(uid, "❌ Ye code ki limit khatam ho chuki hai!")
    if promo_users_col.find_one({"user_id": uid, "code": code}): return bot.send_message(uid, "❌ Aapne ye code pehle hi use kar liya hai!")
    users_col.update_one({"user_id": uid}, {"$inc": {"coins": promo['reward']}})
    promo_col.update_one({"code": code}, {"$inc": {"used_count": 1}})
    promo_users_col.insert_one({"user_id": uid, "code": code})
    bot.send_message(uid, f"🎉 <b>Success!</b>\nPromo Code se <b>{promo['reward']} Coins</b> mil gaye!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_shop_buy(call):
    uid, parts = call.from_user.id, call.data.split("_")
    days, price = int(parts[1]), int(parts[2])
    if get_unjoined(uid): return bot.answer_callback_query(call.id, "❌ Pehle channels join karo!", show_alert=True)
    user = users_col.find_one({"user_id": uid})
    if user.get('coins', 0) >= price:
        users_col.update_one({"user_id": uid}, {"$inc": {"coins": -price}})
        bot.delete_message(call.message.chat.id, call.message.message_id)
        req_text = f"🆕 <b>Key Request ({days}-Day)</b>\n👤 {call.from_user.first_name}\n🆔 <code>{uid}</code>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ APPROVE", callback_data=f"app_{uid}_{price}"), InlineKeyboardButton("❌ REJECT", callback_data=f"rej_{uid}_{price}"))
        try:
            bot.send_message(APPROVAL_CHANNEL, req_text, reply_markup=markup)
            bot.send_message(uid, "⏳ <b>Request Sent!</b>\nAdmin approval ka wait karein.")
        except:
            users_col.update_one({"user_id": uid}, {"$inc": {"coins": price}})
            bot.send_message(uid, "❌ Setup Error. Coins refunded.")
    else: bot.answer_callback_query(call.id, f"❌ Not enough coins!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("app_") or call.data.startswith("rej_"))
def handle_approval(call):
    if call.from_user.id != ADMIN_ID: return bot.answer_callback_query(call.id, "❌ Admin Only", show_alert=True)
    parts = call.data.split("_")
    action, uid, refund = parts[0], int(parts[1]), int(parts[2])
    if action == "app":
        try: bot.edit_message_text(f"{call.message.text}\n\n✅ <b>APPROVED</b>", chat_id=call.message.chat.id, message_id=call.message.message_id)
        except: pass
        key = f"{random.randint(1000000000, 9999999999)}"
        setting = settings_col.find_one({"name": "key_link"})
        link = setting['value'] if setting else "No link"
        try: bot.send_message(uid, f"🎉 <b>Approved!</b>\n\nKey - <code>{key}</code>\nAPK - {link}", disable_web_page_preview=True)
        except: pass
    elif action == "rej":
        try: bot.edit_message_text(f"{call.message.text}\n\n❌ <b>REJECTED</b>", chat_id=call.message.chat.id, message_id=call.message.message_id)
        except: pass
        users_col.update_one({"user_id": uid}, {"$inc": {"coins": refund}})
        try: bot.send_message(uid, "❌ <b>Request Rejected!</b> Coins refunded.")
        except: pass

# ================= 🚀 FAST WEBHOOK SERVER =================
app = Flask(__name__)
executor = concurrent.futures.ThreadPoolExecutor(max_workers=100)

@app.route('/')
def home(): return "Bot is Online! 🚀", 200

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
