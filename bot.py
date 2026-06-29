import logging
import re
import pandas as pd
from io import BytesIO
from datetime import datetime
import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import TOKEN, WEBAPP_URL
from functions import *

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

user_data = {}

MAIN_KEYBOARD = [
    [InlineKeyboardButton("🧹 Clean", callback_data="clean")],
    [InlineKeyboardButton("🔧 BIN manipulations", callback_data="bin_manip")],
    [InlineKeyboardButton("🔍 Filter", callback_data="filter")]
]
MAIN_MARKUP = InlineKeyboardMarkup(MAIN_KEYBOARD)

BIN_MANIP_KEYBOARD = [
    [InlineKeyboardButton("📤 Extract BINs", callback_data="extract_bins")],
    [InlineKeyboardButton("🗑 Remove BINs", callback_data="remove_bins")],
    [InlineKeyboardButton("📊 Sort", callback_data="sort_cards")],
    [InlineKeyboardButton("🌍 Extract By Country", callback_data="extract_by_country")],
    [InlineKeyboardButton("🔎 Mass BIN check", callback_data="mass_bin_check")],
    [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
]
BIN_MANIP_MARKUP = InlineKeyboardMarkup(BIN_MANIP_KEYBOARD)

FILTER_KEYBOARD = [
    [InlineKeyboardButton("🚀 Open Filter Web App", web_app=WebAppInfo(url=WEBAPP_URL))],
    [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
]
FILTER_MARKUP = InlineKeyboardMarkup(FILTER_KEYBOARD)

async def send_file(update, content, filename):
    try:
        bio = BytesIO()
        bio.write(content.encode('utf-8'))
        bio.seek(0)
        await update.message.reply_document(document=bio, filename=filename, caption=f"✅ تم التصدير بنجاح! عدد البطاقات: {len(content.splitlines())}")
    except Exception as e:
        logger.error(f"Error sending file: {e}")
        await update.message.reply_text(f"❌ حدث خطأ في إرسال الملف: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data: user_data[user_id] = {}
    welcome_message = "👋 **مرحباً! أنا بوت تنظيم البطاقات.**\n\n📌 **العمليات المتاحة:**\n• 🧹 **Clean**: تنظيف الملف من التكرارات والبطاقات منتهية الصلاحية وغير الصحيحة\n• 🔧 **BIN manipulations**: عمليات متقدمة على الـ BINs\n• 🔍 **Filter**: فتح واجهة ويب لتصفية البطاقات\n\n📤 **أرسل ملف** بالشكل: `رقم|شهر|سنة|CVV`\nمثال: `5275150064733918|09|27|728`"
    await update.message.reply_text(welcome_message, reply_markup=MAIN_MARKUP, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    if user_id not in user_data: user_data[user_id] = {}

    if data == "back_main":
        await query.edit_message_text("👋 **اختر العملية المطلوبة:**", reply_markup=MAIN_MARKUP, parse_mode='Markdown')
        user_data[user_id] = {}
    elif data == "clean":
        user_data[user_id]['action'] = 'clean'
        await query.edit_message_text("🧹 **Clean**\n\n📤 أرسل لي ملف البطاقات (txt أو csv) بالشكل:\n`رقم|شهر|سنة|CVV`\n\nمثال: `5275150064733918|09|27|728`", parse_mode='Markdown')
    elif data == "bin_manip":
        await query.edit_message_text("🔧 **BIN manipulations**\n\nاختر العملية المطلوبة:", reply_markup=BIN_MANIP_MARKUP, parse_mode='Markdown')
    elif data == "filter":
        user_data[user_id]['action'] = 'filter'
        await query.edit_message_text("🔍 **Filter**\n\n📤 أرسل لي ملف البطاقات أولاً، ثم اضغط الزر لفتح الـ Web App.", reply_markup=FILTER_MARKUP, parse_mode='Markdown')
    elif data == "extract_bins":
        user_data[user_id]['action'] = 'extract_bins'
        await query.edit_message_text("📤 **Extract BINs**\n\nأرسل لي ملف البطاقات.", parse_mode='Markdown')
    elif data == "remove_bins":
        user_data[user_id]['action'] = 'remove_bins'
        await query.edit_message_text("📤 **Remove BINs**\n\nأرسل لي ملف البطاقات.", parse_mode='Markdown')
    elif data == "sort_cards":
        user_data[user_id]['action'] = 'sort_cards'
        await query.edit_message_text("📤 **Sort**\n\nأرسل لي ملف البطاقات للترتيب.", parse_mode='Markdown')
    elif data == "extract_by_country":
        user_data[user_id]['action'] = 'extract_by_country'
        await query.edit_message_text("📤 **Extract By Country**\n\nأرسل لي ملف البطاقات.", parse_mode='Markdown')
    elif data == "mass_bin_check":
        user_data[user_id]['action'] = 'mass_bin_check'
        await query.edit_message_text("📤 **Mass BIN check**\n\nأرسل لي ملف البطاقات.", parse_mode='Markdown')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    document = update.message.document
    if not document:
        await update.message.reply_text("⚠️ من فضلك أرسل ملف.")
        return
    if not document.file_name.endswith(('.txt', '.csv')):
        await update.message.reply_text("⚠️ من فضلك أرسل ملف بصيغة .txt أو .csv")
        return
    try:
        file = await context.bot.get_file(document.file_id)
        content = await file.download_as_bytearray()
        content = content.decode('utf-8')
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        await update.message.reply_text(f"❌ حدث خطأ في تحميل الملف: {str(e)}")
        return
    try:
        df = parse_card_file(content)
        if df.empty:
            await update.message.reply_text("❌ الملف فارغ أو غير صالح! تأكد من التنسيق.")
            return
        if user_id not in user_data: user_data[user_id] = {}
        user_data[user_id]['df'] = df
        user_data[user_id]['content'] = content
        user_data[user_id]['file_name'] = document.file_name
        action = user_data[user_id].get('action', '')

        if action == 'clean':
            await update.message.reply_text("🔄 جاري التنظيف...")
            cleaned_df = clean_cards(df.copy())
            total_before = len(df)
            total_after = len(cleaned_df)
            removed_duplicates = len(df) - len(df.drop_duplicates(subset=['card']))
            removed_expired = total_before - total_after - removed_duplicates
            result = export_cards(cleaned_df)
            await send_file(update, result, "cleaned_cards.txt")
            report = f"✅ **تم التنظيف بنجاح!**\n\n📊 **الإحصائيات:**\n• إجمالي البطاقات قبل التنظيف: `{total_before}`\n• البطاقات الصالحة بعد التنظيف: `{total_after}`\n• تم إزالة التكرارات: `{removed_duplicates}`\n• تم إزالة البطاقات منتهية الصلاحية: `{removed_expired}`\n• تم إزالة البطاقات غير الصحيحة: `{total_before - total_after - removed_duplicates - removed_expired}`"
            await update.message.reply_text(report, parse_mode='Markdown')

        elif action == 'extract_bins':
            user_data[user_id]['waiting_for_bins'] = True
            await update.message.reply_text("✏️ **أرسل الـ BINs المطلوبة**\n\nافصل بينهم بفاصلة أو مسافة:\nمثال: `440393, 510404, 414720`\n\n📌 **ملاحظة:** سيتم استخراج كل البطاقات التي تبدأ بهذه الـ BINs.")

        elif action == 'remove_bins':
            user_data[user_id]['waiting_for_bins'] = True
            await update.message.reply_text("✏️ **أرسل الـ BINs المطلوب حذفها**\n\nافصل بينهم بفاصلة أو مسافة:\nمثال: `440393, 510404`\n\n📌 **ملاحظة:** سيتم حذف كل البطاقات التي تبدأ بهذه الـ BINs.")

        elif action == 'sort_cards':
            await update.message.reply_text("🔄 جاري الترتيب...")
            sorted_df = df.sort_values(by='card')
            result = export_cards(sorted_df)
            await send_file(update, result, "sorted_cards.txt")
            await update.message.reply_text(f"✅ تم الترتيب! عدد البطاقات: `{len(sorted_df)}`", parse_mode='Markdown')

        elif action == 'extract_by_country':
            user_data[user_id]['waiting_for_country'] = True
            await update.message.reply_text("✏️ **أرسل اسم الدولة**\n\nمثال: `United States` أو `Egypt` أو `Saudi Arabia`\n\n📌 **ملاحظة:** سيتم استخراج البطاقات من هذه الدولة فقط.")

        elif action == 'mass_bin_check':
            await update.message.reply_text("🔄 جاري فحص الـ BINs...")
            unique_bins = df['card'].str[:6].unique()
            total_bins = len(unique_bins)
            results = []
            for i, bin in enumerate(unique_bins[:20]):
                info = get_bin_info(bin)
                results.append(f"🔹 **{bin}**: {info.get('Brand', 'Unknown')} - {info.get('Bank', 'Unknown')} - {info.get('Country', 'Unknown')}")
            if total_bins > 20: results.append(f"\n📌 ... و {total_bins - 20} BINs أخرى")
            message = f"🔎 **نتيجة فحص الـ BINs**\n\n📊 إجمالي BINs فريدة: `{total_bins}`\n\n**أول 20 BIN:**\n" + '\n'.join(results)
            await update.message.reply_text(message, parse_mode='Markdown')

        elif action == 'filter':
            cards_json = df.to_json(orient='records')
            user_data[user_id]['cards_json'] = cards_json
            await update.message.reply_text("✅ **تم استلام الملف بنجاح!**\n\n📌 اضغط على الزر أدناه لفتح واجهة التصفية.", reply_markup=FILTER_MARKUP, parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ عملية غير معروفة. من فضلك اختر عملية من الأزرار أولاً.")
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        await update.message.reply_text(f"❌ حدث خطأ في معالجة الملف: {str(e)}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if user_id not in user_data:
        await update.message.reply_text("⚠️ من فضلك اختر عملية أولاً من الأزرار.")
        return
    df = user_data[user_id].get('df')
    action = user_data[user_id].get('action', '')
    if df is None:
        await update.message.reply_text("⚠️ من فضلك أرسل ملف البطاقات أولاً.")
        return
    if user_data[user_id].get('waiting_for_bins', False):
        bin_list = re.findall(r'\d{6}', text)
        if not bin_list:
            await update.message.reply_text("❌ لم يتم العثور على BINs صحيحة (6 أرقام).\nمثال: `440393, 510404, 414720`")
            return
        bin_list = list(set(bin_list))
        if action == 'extract_bins':
            await update.message.reply_text(f"🔄 جاري استخراج البطاقات من BINs: {', '.join(bin_list)}...")
            extracted = extract_bins(df, bin_list)
            result = export_cards(extracted)
            if len(extracted) == 0:
                await update.message.reply_text("❌ لم يتم العثور على بطاقات من الـ BINs المطلوبة.")
            else:
                await send_file(update, result, "extracted_cards.txt")
                await update.message.reply_text(f"✅ **تم الاستخراج!**\n\n• عدد البطاقات المستخرجة: `{len(extracted)}`\n• الـ BINs المطلوبة: `{', '.join(bin_list)}`", parse_mode='Markdown')
        elif action == 'remove_bins':
            await update.message.reply_text(f"🔄 جاري حذف البطاقات من BINs: {', '.join(bin_list)}...")
            removed = remove_bins(df, bin_list)
            result = export_cards(removed)
            deleted_count = len(df) - len(removed)
            if deleted_count == 0:
                await update.message.reply_text("❌ لم يتم العثور على بطاقات من الـ BINs المطلوبة للحذف.")
            else:
                await send_file(update, result, "removed_cards.txt")
                await update.message.reply_text(f"✅ **تم الحذف!**\n\n• عدد البطاقات المحذوفة: `{deleted_count}`\n• عدد البطاقات المتبقية: `{len(removed)}`\n• الـ BINs المحذوفة: `{', '.join(bin_list)}`", parse_mode='Markdown')
        user_data[user_id]['waiting_for_bins'] = False
        user_data[user_id]['action'] = None
    elif user_data[user_id].get('waiting_for_country', False):
        country = text.strip()
        if not country:
            await update.message.reply_text("❌ من فضلك أدخل اسم دولة صحيح.")
            return
        await update.message.reply_text(f"🔄 جاري استخراج البطاقات من دولة: {country}...")
        extracted_rows = []
        for idx, row in df.iterrows():
            bin = row['card'][:6]
            info = get_bin_info(bin)
            if country.lower() in info.get('Country', '').lower():
                extracted_rows.append(row)
        if extracted_rows:
            extracted_df = pd.DataFrame(extracted_rows)
            result = export_cards(extracted_df)
            await send_file(update, result, f"country_{country.replace(' ', '_')}_cards.txt")
            await update.message.reply_text(f"✅ **تم الاستخراج!**\n\n• الدولة: `{country}`\n• عدد البطاقات: `{len(extracted_df)}`", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ لم يتم العثور على بطاقات من دولة: `{country}`", parse_mode='Markdown')
        user_data[user_id]['waiting_for_country'] = False
        user_data[user_id]['action'] = None
    else:
        await update.message.reply_text("⚠️ لم يتم التعرف على طلبك. من فضلك استخدم الأزرار للتنقل.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🚀 البوت يعمل...")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف البوت.")

if __name__ == "__main__":
    main()