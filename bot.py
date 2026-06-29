import os
import logging
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import hashlib
import requests
import threading
import time

# ============ إعدادات البوت ============
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8937588348:AAFCpn3onbonlU_MCt6OqQxitFD-AA3kFS8')
WEBAPP_URL = os.environ.get('WEBAPP_URL', 'https://your-webapp-url.com')
ADMIN_IDS = [int(x) for x in os.environ.get('ADMIN_IDS', '1867486900').split(',')]

# ============ إعدادات الملفات ============
USER_DATA_FILE = 'users_data.json'
ACTIVITY_LOG_FILE = 'activity.log'

# ============ إعداد التسجيل ============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(ACTIVITY_LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============ دوال إدارة المستخدمين ============

def load_users_data():
    """تحميل بيانات المستخدمين"""
    try:
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_users_data(data):
    """حفظ بيانات المستخدمين"""
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_user_data(user_id):
    """الحصول على بيانات مستخدم معين"""
    users = load_users_data()
    user_id = str(user_id)
    
    if user_id not in users:
        users[user_id] = {
            'first_use': datetime.now().isoformat(),
            'total_operations': 0,
            'daily_operations': 0,
            'last_activity': datetime.now().isoformat(),
            'files_processed': 0,
            'is_admin': user_id in [str(uid) for uid in ADMIN_IDS],
            'is_banned': False,
            'username': '',
            'first_name': '',
            'last_name': ''
        }
        save_users_data(users)
    
    return users[user_id]

def update_user_activity(user_id, username="", first_name="", last_name=""):
    """تحديث نشاط المستخدم"""
    users = load_users_data()
    user_id = str(user_id)
    
    if user_id in users:
        users[user_id]['total_operations'] += 1
        users[user_id]['daily_operations'] += 1
        users[user_id]['last_activity'] = datetime.now().isoformat()
        if username:
            users[user_id]['username'] = username
        if first_name:
            users[user_id]['first_name'] = first_name
        if last_name:
            users[user_id]['last_name'] = last_name
        save_users_data(users)

def reset_daily_limits():
    """إعادة تعيين الحدود اليومية (تشغل كل يوم)"""
    users = load_users_data()
    for user_id in users:
        users[user_id]['daily_operations'] = 0
    save_users_data(users)

def is_user_allowed(user_id):
    """التحقق من صلاحية المستخدم"""
    user_data = get_user_data(user_id)
    if user_data.get('is_banned', False):
        return False, "🚫 تم حظرك من استخدام البوت. تواصل مع المشرف."
    
    # حد أقصى 50 عملية في اليوم
    if user_data.get('daily_operations', 0) >= 50:
        return False, "⏰ تجاوزت الحد اليومي (50 عملية). حاول غداً."
    
    return True, ""

def log_activity(user_id, action, details=""):
    """تسجيل النشاطات"""
    logger.info(f"User: {user_id} | Action: {action} | Details: {details}")

# ============ دوال تنظيف البطاقات ============

def clean_cards(file_content, user_id=None):
    """تنظيف البطاقات مع تسجيل النشاط"""
    lines = file_content.strip().split('\n')
    valid_cards = []
    seen = set()
    stats = {
        'total': len(lines),
        'duplicates': 0,
        'invalid': 0,
        'expired': 0,
        'valid': 0
    }
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        parts = line.split('|')
        if len(parts) >= 3:
            card_number = parts[0].strip()
            exp_month = parts[1].strip()
            exp_year = parts[2].strip()
            
            # التحقق من صحة رقم البطاقة
            if not is_valid_luhn(card_number):
                stats['invalid'] += 1
                continue
                
            # التحقق من الصلاحية
            if not is_valid_expiry(exp_month, exp_year):
                stats['expired'] += 1
                continue
                
            # التحقق من عدم التكرار
            if card_number in seen:
                stats['duplicates'] += 1
                continue
                
            seen.add(card_number)
            valid_cards.append(line)
            stats['valid'] += 1
    
    if user_id:
        log_activity(user_id, 'clean_cards', f"Processed: {stats['total']}, Valid: {stats['valid']}")
    
    return '\n'.join(valid_cards), stats

# ============ دوال الـ BIN ============

def extract_bins_from_cards(cards_content, target_bins):
    """استخراج البطاقات حسب الـ BINs"""
    lines = cards_content.strip().split('\n')
    result = []
    target_bins_set = set(bin.strip() for bin in target_bins if bin.strip())
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        parts = line.split('|')
        if len(parts) >= 1:
            card_number = parts[0].strip()
            bin_prefix = card_number[:6]
            if bin_prefix in target_bins_set:
                result.append(line)
    
    return '\n'.join(result)

def remove_bins_from_cards(cards_content, target_bins):
    """حذف البطاقات حسب الـ BINs"""
    lines = cards_content.strip().split('\n')
    result = []
    target_bins_set = set(bin.strip() for bin in target_bins if bin.strip())
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        parts = line.split('|')
        if len(parts) >= 1:
            card_number = parts[0].strip()
            bin_prefix = card_number[:6]
            if bin_prefix not in target_bins_set:
                result.append(line)
    
    return '\n'.join(result)

def sort_cards(cards_content):
    """ترتيب البطاقات"""
    lines = cards_content.strip().split('\n')
    lines = [line for line in lines if line.strip()]
    lines.sort()
    return '\n'.join(lines)

# ============ دوال التحقق ============

def is_valid_luhn(card_number):
    """التحقق من صحة رقم البطاقة باستخدام خوارزمية Luhn"""
    if not card_number.isdigit():
        return False
    
    digits = [int(d) for d in card_number]
    checksum = 0
    
    # البدء من اليمين
    for i in range(len(digits) - 2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] -= 9
    
    checksum = sum(digits)
    return checksum % 10 == 0

def is_valid_expiry(month, year):
    """التحقق من صلاحية البطاقة"""
    try:
        month = str(month).strip()
        year = str(year).strip()
        
        # تحويل السنة إلى 4 أرقام
        if len(year) == 2:
            year = '20' + year
        
        month_int = int(month)
        if month_int < 1 or month_int > 12:
            return False
        
        year_int = int(year)
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        if year_int < current_year:
            return False
        elif year_int == current_year and month_int < current_month:
            return False
        
        return True
    except:
        return False

# ============ دوال معلومات الـ BIN ============

def get_bin_info(bin_number):
    """الحصول على معلومات الـ BIN من API"""
    from bs4 import BeautifulSoup
    
    bin_number = str(bin_number)[:6]
    try:
        req = 'https://bins.antipublic.cc/bins/' + bin_number
        r = requests.get(req, timeout=10)
        
        # محاولة قراءة JSON
        try:
            data = r.json()
            fields = ['bin', 'brand', 'type', 'level', 'bank', 'country_name', 'country_flag']
            result = [data.get(field, "") for field in fields]
            
            # تحويل كود العلم إلى إيموجي
            flag = ""
            if result[6]:
                for char in result[6].upper():
                    if char.isalpha():
                        flag += chr(ord(char) + 0x1F1E6 - ord('A'))
            
            return {
                "Bin": result[0],
                "Brand": result[1],
                "Type": result[2],
                "Level": result[3],
                "Bank": result[4],
                "Country": f"{result[5]} {flag}" if flag else result[5]
            }
        except:
            # إذا لم يكن JSON، نحاول استخدام HTML
            soup = BeautifulSoup(r.text, 'html.parser')
            info = {}
            
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    key = cells[0].text.strip().lower()
                    value = cells[1].text.strip()
                    info[key] = value
            
            return {
                "Bin": bin_number,
                "Brand": info.get('brand', ''),
                "Type": info.get('type', ''),
                "Level": info.get('level', ''),
                "Bank": info.get('bank', ''),
                "Country": info.get('country', '')
            }
            
    except Exception as e:
        logger.error(f"Error fetching BIN info: {e}")
        return None

# ============ دالة Keep Alive ============

def keep_alive():
    """إبقاء البوت شغال على Render"""
    url = os.environ.get('WEBAPP_URL', 'https://bin-bot.onrender.com')
    while True:
        try:
            requests.get(url, timeout=5)
            print("🔄 Keep alive ping sent")
        except:
            pass
        time.sleep(300)  # كل 5 دقائق

# ============ أوامر البوت ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # تسجيل المستخدم
    get_user_data(user_id)
    update_user_activity(user_id, user.username, user.first_name, user.last_name)
    log_activity(user_id, 'start', f"User: {user.first_name}")
    
    # التحقق من الصلاحية
    allowed, message = is_user_allowed(user_id)
    if not allowed:
        await update.message.reply_text(f"❌ {message}")
        return
    
    # أزرار حسب الصلاحية
    keyboard = [
        [
            InlineKeyboardButton("🧹 Clean", callback_data='clean'),
            InlineKeyboardButton("🎯 BIN manipulations", callback_data='bin_manipulations'),
        ],
        [
            InlineKeyboardButton("🔍 Filter", callback_data='filter'),
            InlineKeyboardButton("ℹ️ Check BIN", callback_data='check_bin'),
        ]
    ]
    
    # أزرار إضافية للأدمن
    if str(user_id) in [str(uid) for uid in ADMIN_IDS]:
        keyboard.append([
            InlineKeyboardButton("⚙️ Admin Panel", callback_data='admin_panel')
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_data = get_user_data(user_id)
    await update.message.reply_text(
        f"👋 مرحباً {user.first_name}!\n\n"
        f"📊 **إحصائياتك اليومية:**\n"
        f"• العمليات اليوم: {user_data.get('daily_operations', 0)}/50\n"
        f"• إجمالي العمليات: {user_data.get('total_operations', 0)}\n"
        f"• الملفات المعالجة: {user_data.get('files_processed', 0)}\n\n"
        "اختر العملية التي تريد القيام بها:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأزرار"""
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()
    
    # التحقق من الصلاحية
    allowed, message = is_user_allowed(user_id)
    if not allowed:
        await query.edit_message_text(f"❌ {message}")
        return
    
    # تحديث النشاط
    update_user_activity(user_id)
    
    if query.data == 'clean':
        await query.edit_message_text(
            "🧹 **أرسل لي ملف البطاقات**\n\n"
            "يمكنك إرسال ملف بصيغة TXT أو CSV أو Excel، أو لصق النص مباشرة.\n\n"
            "**صيغة البطاقات المطلوبة:**\n"
            "`رقم_البطاقة|شهر_الصلاحية|سنة_الصلاحية|cvv`\n\n"
            "**مثال:**\n"
            "`5275150064733918|09|27|728`\n"
            "`5207378365309277|08|2029|559`\n\n"
            "📌 الشهر: رقم (01-12)\n"
            "📌 السنة: رقم (24 أو 2024)",
            parse_mode='Markdown'
        )
        context.user_data['action'] = 'clean'
        
    elif query.data == 'bin_manipulations':
        keyboard = [
            [InlineKeyboardButton("📤 Extract BINs", callback_data='extract_bins')],
            [InlineKeyboardButton("🗑️ Remove BINs", callback_data='remove_bins')],
            [InlineKeyboardButton("📊 Sort", callback_data='sort_cards')],
            [InlineKeyboardButton("🌍 Extract By Country", callback_data='extract_country')],
            [InlineKeyboardButton("🔍 Mass BIN Check", callback_data='mass_bin_check')],
            [InlineKeyboardButton("🔙 Back", callback_data='back_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎯 **اختر عملية من عمليات الـ BIN:**\n\n"
            "• **Extract BINs**: استخراج بطاقات من BINs محددة\n"
            "• **Remove BINs**: حذف بطاقات من BINs محددة\n"
            "• **Sort**: ترتيب البطاقات\n"
            "• **Extract By Country**: استخراج حسب الدولة\n"
            "• **Mass BIN Check**: التحقق من مجموعة BINs",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        context.user_data['action'] = 'bin_manipulations'
        
    elif query.data == 'filter':
        user_id = query.from_user.id
        context.user_data['user_id'] = user_id
        
        # رابط الـ Web App مع user_id
        webapp_url = f"{WEBAPP_URL}?user_id={user_id}"
        
        keyboard = [[
            InlineKeyboardButton("🚀 Open Filter App", web_app=WebAppInfo(url=webapp_url))
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔍 **واجهة التصفية المتقدمة**\n\n"
            "اضغط على الزر لفتح واجهة التصفية.\n\n"
            "📋 **الخطوات:**\n"
            "1️⃣ ارفع ملف البطاقات\n"
            "2️⃣ اختر الفلاتر المناسبة\n"
            "3️⃣ اضغط 'تطبيق الفلاتر'\n"
            "4️⃣ اضغط '📤 إرسال للبوت'\n\n"
            "⚠️ تأكد من رفع الملف أولاً!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        context.user_data['action'] = 'filter'
        
    elif query.data == 'check_bin':
        await query.edit_message_text(
            "ℹ️ **أرسل الـ BIN للتحقق**\n\n"
            "الـ BIN هو أول 6 أرقام من رقم البطاقة.\n\n"
            "**مثال:** `440393` أو `510404`",
            parse_mode='Markdown'
        )
        context.user_data['action'] = 'check_bin'
        
    elif query.data == 'back_main':
        keyboard = [
            [
                InlineKeyboardButton("🧹 Clean", callback_data='clean'),
                InlineKeyboardButton("🎯 BIN manipulations", callback_data='bin_manipulations'),
            ],
            [
                InlineKeyboardButton("🔍 Filter", callback_data='filter'),
                InlineKeyboardButton("ℹ️ Check BIN", callback_data='check_bin'),
            ]
        ]
        if str(user_id) in [str(uid) for uid in ADMIN_IDS]:
            keyboard.append([
                InlineKeyboardButton("⚙️ Admin Panel", callback_data='admin_panel')
            ])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        user_data = get_user_data(user_id)
        await query.edit_message_text(
            f"👋 مرحباً بك في بوت البطاقات!\n\n"
            f"📊 **إحصائياتك:**\n"
            f"• العمليات اليوم: {user_data.get('daily_operations', 0)}/50\n"
            f"• إجمالي العمليات: {user_data.get('total_operations', 0)}\n\n"
            "اختر العملية:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        context.user_data.clear()
        
    # ===== عمليات BIN =====
    elif query.data == 'extract_bins':
        await query.edit_message_text(
            "📤 **أرسل ملف البطاقات**\n\n"
            "سأطلب منك الـ BINs بعد استلام الملف."
        )
        context.user_data['bin_action'] = 'extract_bins'
        
    elif query.data == 'remove_bins':
        await query.edit_message_text(
            "🗑️ **أرسل ملف البطاقات**\n\n"
            "سأطلب منك الـ BINs المراد حذفها بعد استلام الملف."
        )
        context.user_data['bin_action'] = 'remove_bins'
        
    elif query.data == 'sort_cards':
        await query.edit_message_text(
            "📊 **أرسل ملف البطاقات للترتيب**\n\n"
            "سيتم ترتيب البطاقات تصاعدياً حسب رقم البطاقة."
        )
        context.user_data['bin_action'] = 'sort_cards'
        
    elif query.data == 'extract_country':
        await query.edit_message_text(
            "🌍 **أرسل ملف البطاقات**\n\n"
            "سأطلب منك الدولة بعد استلام الملف."
        )
        context.user_data['bin_action'] = 'extract_country'
        
    elif query.data == 'mass_bin_check':
        await query.edit_message_text(
            "🔍 **أرسل ملف البطاقات للتحقق**\n\n"
            "سيتم التحقق من جميع الـ BINs في الملف."
        )
        context.user_data['bin_action'] = 'mass_bin_check'
        
    # ===== لوحة تحكم الأدمن =====
    elif query.data == 'admin_panel':
        if str(user_id) not in [str(uid) for uid in ADMIN_IDS]:
            await query.edit_message_text("❌ غير مصرح لك")
            return
            
        users = load_users_data()
        total_users = len(users)
        total_ops = sum(u.get('total_operations', 0) for u in users.values())
        banned_users = sum(1 for u in users.values() if u.get('is_banned', False))
        
        keyboard = [
            [InlineKeyboardButton("📊 عرض الإحصائيات", callback_data='admin_stats')],
            [InlineKeyboardButton("🚫 حظر مستخدم", callback_data='admin_ban')],
            [InlineKeyboardButton("✅ إلغاء حظر", callback_data='admin_unban')],
            [InlineKeyboardButton("📢 إرسال رسالة للجميع", callback_data='admin_broadcast')],
            [InlineKeyboardButton("📁 سجل النشاطات", callback_data='admin_logs')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='back_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⚙️ **لوحة التحكم**\n\n"
            f"👥 عدد المستخدمين: {total_users}\n"
            f"🚫 محظورين: {banned_users}\n"
            f"🔄 إجمالي العمليات: {total_ops}\n"
            f"👤 أنت: {'✅ أدمن' if str(user_id) in [str(uid) for uid in ADMIN_IDS] else '❌ مستخدم عادي'}\n\n"
            "اختر الإجراء المناسب:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    elif query.data == 'admin_stats':
        if str(user_id) not in [str(uid) for uid in ADMIN_IDS]:
            await query.edit_message_text("❌ غير مصرح لك")
            return
            
        users = load_users_data()
        today = datetime.now().date().isoformat()
        
        # إحصائيات اليوم
        today_users = sum(1 for u in users.values() if u.get('last_activity', '').startswith(today))
        
        stats_text = "📊 **إحصائيات البوت**\n\n"
        stats_text += f"👥 إجمالي المستخدمين: {len(users)}\n"
        stats_text += f"🔄 إجمالي العمليات: {sum(u.get('total_operations', 0) for u in users.values())}\n"
        stats_text += f"📅 مستخدمين اليوم: {today_users}\n"
        stats_text += f"📁 ملفات معالجة: {sum(u.get('files_processed', 0) for u in users.values())}\n"
        stats_text += f"🚫 محظورين: {sum(1 for u in users.values() if u.get('is_banned', False))}\n"
        
        # ترتيب أكثر المستخدمين نشاطاً
        top_users = sorted(users.items(), key=lambda x: x[1].get('total_operations', 0), reverse=True)[:5]
        stats_text += "\n🏆 **أكثر المستخدمين نشاطاً:**\n"
        for i, (uid, data) in enumerate(top_users, 1):
            name = data.get('first_name', uid)[:15]
            ops = data.get('total_operations', 0)
            stats_text += f"{i}. {name} - {ops} عملية\n"
        
        await query.edit_message_text(stats_text, parse_mode='Markdown')

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الملفات"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # التحقق من الصلاحية
    allowed, message = is_user_allowed(user_id)
    if not allowed:
        await update.message.reply_text(f"❌ {message}")
        return
    
    document = update.message.document
    file = await document.get_file()
    file_content = await file.download_as_bytearray()
    content = file_content.decode('utf-8')
    
    action = context.user_data.get('action')
    bin_action = context.user_data.get('bin_action')
    
    if action == 'clean':
        # تنظيف البطاقات
        cleaned, stats = clean_cards(content, user_id)
        
        # تحديث إحصائيات المستخدم
        users = load_users_data()
        if str(user_id) in users:
            users[str(user_id)]['files_processed'] = users[str(user_id)].get('files_processed', 0) + 1
            save_users_data(users)
        
        if cleaned:
            output_file = f"cleaned_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(cleaned)
            
            with open(output_file, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=output_file,
                    caption=(
                        f"✅ **تم التنظيف بنجاح!**\n\n"
                        f"📊 **الإحصائيات:**\n"
                        f"• إجمالي البطاقات: {stats['total']}\n"
                        f"• ✅ صالحة: {stats['valid']}\n"
                        f"• ❌ مكررة: {stats['duplicates']}\n"
                        f"• ⏰ منتهية الصلاحية: {stats['expired']}\n"
                        f"• 🚫 غير صحيحة: {stats['invalid']}"
                    ),
                    parse_mode='Markdown'
                )
            os.remove(output_file)
        else:
            await update.message.reply_text(
                "❌ **لا توجد بطاقات صالحة في الملف!**\n\n"
                f"📊 الإحصائيات:\n"
                f"• إجمالي البطاقات: {stats['total']}\n"
                f"• ❌ مكررة: {stats['duplicates']}\n"
                f"• ⏰ منتهية: {stats['expired']}\n"
                f"• 🚫 غير صحيحة: {stats['invalid']}",
                parse_mode='Markdown'
            )
        
        update_user_activity(user_id)
        log_activity(user_id, 'clean_complete', f"Valid: {stats['valid']}")
        
    elif action == 'bin_manipulations':
        if bin_action == 'extract_bins':
            context.user_data['cards_content'] = content
            await update.message.reply_text(
                "📤 **أرسل الـ BINs المطلوبة**\n\n"
                "يمكنك إرسالها مفصولة بفواصل أو كل BIN في سطر.\n\n"
                "**مثال:** `440393, 510404, 420767`\n"
                "أو:\n"
                "`440393`\n`510404`\n`420767`"
            )
            context.user_data['bin_action'] = 'extract_bins_confirm'
            
        elif bin_action == 'remove_bins':
            context.user_data['cards_content'] = content
            await update.message.reply_text(
                "🗑️ **أرسل الـ BINs التي تريد حذفها**\n\n"
                "مثال: `440393, 510404, 420767`"
            )
            context.user_data['bin_action'] = 'remove_bins_confirm'
            
        elif bin_action == 'sort_cards':
            sorted_content = sort_cards(content)
            lines = sorted_content.strip().split('\n')
            
            if lines and lines[0]:
                output_file = f"sorted_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(sorted_content)
                
                with open(output_file, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=output_file,
                        caption=f"📊 **تم الترتيب!** \nعدد البطاقات: {len(lines)}"
                    )
                os.remove(output_file)
            else:
                await update.message.reply_text("❌ الملف فارغ أو غير صحيح")
            
            update_user_activity(user_id)
            
        elif bin_action == 'extract_country':
            context.user_data['cards_content'] = content
            await update.message.reply_text(
                "🌍 **أرسل اسم الدولة**\n\n"
                "مثال: `United States` أو `Egypt` أو `Saudi Arabia`"
            )
            context.user_data['bin_action'] = 'extract_country_confirm'
            
        elif bin_action == 'mass_bin_check':
            # التحقق من جميع الـ BINs
            lines = content.strip().split('\n')
            checked = []
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split('|')
                if len(parts) >= 1:
                    bin_number = parts[0].strip()[:6]
                    bin_info = get_bin_info(bin_number)
                    if bin_info:
                        checked.append(f"{bin_number} | {bin_info.get('Brand', '')} | {bin_info.get('Country', '')}")
                    else:
                        checked.append(f"{bin_number} | Unknown | Unknown")
            
            if checked:
                output_file = f"bin_check_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(checked))
                
                with open(output_file, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=output_file,
                        caption=f"🔍 **تم التحقق من {len(checked)} BIN**"
                    )
                os.remove(output_file)
            else:
                await update.message.reply_text("❌ لم يتم العثور على BINs صالحة")
            
            update_user_activity(user_id)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة النصوص"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # التحقق من الصلاحية
    allowed, message = is_user_allowed(user_id)
    if not allowed:
        await update.message.reply_text(f"❌ {message}")
        return
    
    action = context.user_data.get('action')
    bin_action = context.user_data.get('bin_action')
    
    if action == 'clean':
        cleaned, stats = clean_cards(text, user_id)
        
        if cleaned:
            # تحديث إحصائيات المستخدم
            users = load_users_data()
            if str(user_id) in users:
                users[str(user_id)]['files_processed'] = users[str(user_id)].get('files_processed', 0) + 1
                save_users_data(users)
            
            await update.message.reply_text(
                f"✅ **تم التنظيف!**\n\n"
                f"📊 **الإحصائيات:**\n"
                f"• ✅ صالحة: {stats['valid']}\n"
                f"• ❌ مكررة: {stats['duplicates']}\n"
                f"• ⏰ منتهية: {stats['expired']}\n"
                f"• 🚫 غير صحيحة: {stats['invalid']}\n\n"
                f"📝 **البطاقات الصالحة:**\n`{cleaned[:1000]}`"
                f"{'...' if len(cleaned) > 1000 else ''}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ **لا توجد بطاقات صالحة!**\n\n"
                f"📊 الإحصائيات:\n"
                f"• إجمالي البطاقات: {stats['total']}\n"
                f"• ❌ مكررة: {stats['duplicates']}\n"
                f"• ⏰ منتهية: {stats['expired']}\n"
                f"• 🚫 غير صحيحة: {stats['invalid']}",
                parse_mode='Markdown'
            )
        
        update_user_activity(user_id)
        
    elif action == 'check_bin':
        bin_info = get_bin_info(text[:6])
        if bin_info and bin_info.get('Bin'):
            info_text = "ℹ️ **معلومات الـ BIN**\n\n"
            for key, value in bin_info.items():
                if value:
                    info_text += f"• **{key}**: `{value}`\n"
            await update.message.reply_text(info_text, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ لم يتم العثور على معلومات لهذا الـ BIN")
        update_user_activity(user_id)
        
    elif bin_action == 'extract_bins_confirm':
        cards_content = context.user_data.get('cards_content', '')
        target_bins = [b.strip() for b in text.replace(',', ' ').split() if b.strip()]
        
        if not target_bins:
            await update.message.reply_text("❌ لم يتم إرسال أي BINs صحيحة")
            return
            
        extracted = extract_bins_from_cards(cards_content, target_bins)
        
        if extracted:
            output_file = f"extracted_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(extracted)
            
            with open(output_file, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=output_file,
                    caption=f"📤 **تم الاستخراج!**\nعدد البطاقات: {len(extracted.splitlines())}"
                )
            os.remove(output_file)
            update_user_activity(user_id)
        else:
            await update.message.reply_text("❌ لم يتم العثور على بطاقات تطابق الـ BINs المطلوبة")
            
        context.user_data.pop('bin_action', None)
        context.user_data.pop('cards_content', None)
        
    elif bin_action == 'remove_bins_confirm':
        cards_content = context.user_data.get('cards_content', '')
        target_bins = [b.strip() for b in text.replace(',', ' ').split() if b.strip()]
        
        if not target_bins:
            await update.message.reply_text("❌ لم يتم إرسال أي BINs صحيحة")
            return
            
        removed = remove_bins_from_cards(cards_content, target_bins)
        
        if removed:
            output_file = f"removed_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(removed)
            
            with open(output_file, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=output_file,
                    caption=f"🗑️ **تم الحذف!**\nالمتبقي: {len(removed.splitlines())} بطاقة"
                )
            os.remove(output_file)
            update_user_activity(user_id)
        else:
            await update.message.reply_text("❌ لم يتم العثور على بطاقات من الـ BINs المطلوبة للحذف")
            
        context.user_data.pop('bin_action', None)
        context.user_data.pop('cards_content', None)
        
    elif bin_action == 'extract_country_confirm':
        cards_content = context.user_data.get('cards_content', '')
        country = text.strip()
        
        if not country:
            await update.message.reply_text("❌ لم يتم إرسال اسم الدولة")
            return
        
        # البحث عن البطاقات من الدولة المطلوبة
        lines = cards_content.strip().split('\n')
        result = []
        
        for line in lines:
            if not line.strip():
                continue
            parts = line.split('|')
            if len(parts) >= 1:
                bin_number = parts[0].strip()[:6]
                bin_info = get_bin_info(bin_number)
                if bin_info and country.lower() in bin_info.get('Country', '').lower():
                    result.append(line)
        
        if result:
            output_file = f"country_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(result))
            
            with open(output_file, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=output_file,
                    caption=f"🌍 **تم الاستخراج!**\nالدولة: {country}\nعدد البطاقات: {len(result)}"
                )
            os.remove(output_file)
            update_user_activity(user_id)
        else:
            await update.message.reply_text(f"❌ لم يتم العثور على بطاقات من دولة {country}")
            
        context.user_data.pop('bin_action', None)
        context.user_data.pop('cards_content', None)

async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال البيانات من Web App"""
    user_id = update.effective_user.id
    data = update.message.web_app_data
    
    if data:
        try:
            await update.message.reply_text(
                "✅ تم استلام طلبك من الويب اب!\n"
                "سيتم إرسال الملف خلال لحظات..."
            )
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

def main():
    """تشغيل البوت"""
    if not BOT_TOKEN or BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("❌ BOT_TOKEN not set! Please set it in environment variables.")
        return
    
    # تشغيل Keep Alive على Render
    if os.environ.get('RENDER', ''):
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
        print("🔄 Keep alive thread started")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data_handler))
    
    # تشغيل البوت
    print(f"🚀 Bot is starting...")
    print(f"📱 WebApp URL: {WEBAPP_URL}")
    print(f"👑 Admins: {ADMIN_IDS}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()