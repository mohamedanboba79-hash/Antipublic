from flask import Flask, render_template, request, jsonify, send_file
import os
import json
import io
from datetime import datetime
import requests

# ============ استيراد bin_info ============
from bin_info import (
    get_bin_info, 
    get_bulk_bin_info, 
    extract_all_info_from_cards,
    filter_cards_by_criteria
)

app = Flask(__name__)

# ============ إعدادات ============
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8937588348:AAFCpn3onbonlU_MCt6OqQxitFD-AA3kFS8')

# ============ Routes ============

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return render_template('index.html')

@app.route('/extract_info', methods=['POST'])
def extract_info():
    """استخراج كل المعلومات من البطاقات"""
    data = request.json
    cards = data.get('cards', '').split('\n')
    
    if not cards:
        return jsonify({'error': 'No cards provided'}), 400
    
    # استخراج المعلومات
    result = extract_all_info_from_cards(cards)
    
    return jsonify(result)

@app.route('/filter', methods=['POST'])
def filter_cards():
    """تصفية البطاقات حسب المعايير"""
    data = request.json
    cards = data.get('cards', '').split('\n')
    filters = data.get('filters', {})
    
    if not cards:
        return jsonify({'error': 'No cards provided'}), 400
    
    # تصفية البطاقات
    filtered = filter_cards_by_criteria(cards, filters)
    
    # إحصائيات إضافية
    stats = {
        'total': len(cards),
        'filtered': len(filtered),
        'filters_applied': filters
    }
    
    return jsonify({
        'filtered': '\n'.join(filtered),
        'stats': stats,
        'count': len(filtered)
    })

@app.route('/bin_info', methods=['POST'])
def bin_info():
    """الحصول على معلومات BIN واحد"""
    data = request.json
    bin_number = data.get('bin', '')[:6]
    
    if not bin_number:
        return jsonify({'error': 'No BIN provided'}), 400
    
    info = get_bin_info(bin_number)
    if info:
        return jsonify(info)
    else:
        return jsonify({'error': 'BIN not found'}), 404

@app.route('/bulk_bin_info', methods=['POST'])
def bulk_bin_info():
    """الحصول على معلومات مجموعة BINs"""
    data = request.json
    bins = data.get('bins', [])
    
    if not bins:
        return jsonify({'error': 'No BINs provided'}), 400
    
    results = get_bulk_bin_info(bins)
    return jsonify(results)

@app.route('/send_to_bot', methods=['POST'])
def send_to_bot():
    """إرسال البطاقات المصفاة للبوت"""
    data = request.json
    cards = data.get('cards', '')
    user_id = data.get('user_id', '')
    filters_used = data.get('filters', {})
    
    if not cards or not user_id:
        return jsonify({'error': 'Missing data'}), 400
    
    filename = f"filtered_cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    temp_file = f"/tmp/{filename}"
    
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write(cards)
    
    try:
        bot_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        
        with open(temp_file, 'rb') as f:
            files = {'document': (filename, f, 'text/plain')}
            
            filter_text = ""
            filter_names = {
                'country': '🌍 الدولة',
                'bank': '🏦 البنك',
                'type': '💳 النوع',
                'level': '📊 المستوى',
                'brand': '💳 البراند'
            }
            for key, value in filters_used.items():
                if value:
                    name = filter_names.get(key, key)
                    filter_text += f"  • {name}: `{value}`\n"
            
            data = {
                'chat_id': user_id,
                'caption': f"✅ **تم التصفية بنجاح!**\n\n"
                          f"📊 **النتائج:**\n"
                          f"• عدد البطاقات: {len(cards.splitlines())}\n"
                          f"• الفلاتر المستخدمة:\n{filter_text if filter_text else '  • لا توجد فلاتر'}\n\n"
                          f"📁 الملف مرفق 👇",
                'parse_mode': 'Markdown'
            }
            response = requests.post(bot_file_url, files=files, data=data)
        
        os.remove(temp_file)
        
        if response.status_code == 200:
            return jsonify({'status': 'success', 'message': 'تم إرسال الملف للبوت'})
        else:
            return jsonify({'error': 'Failed to send to bot'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export', methods=['POST'])
def export_cards():
    """تصدير البطاقات كملف"""
    data = request.json
    cards = data.get('cards', '')
    filename = data.get('filename', f'cards_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
    
    if not cards:
        return jsonify({'error': 'No cards to export'}), 400
    
    file_obj = io.BytesIO()
    file_obj.write(cards.encode('utf-8'))
    file_obj.seek(0)
    
    return send_file(
        file_obj,
        as_attachment=True,
        download_name=filename,
        mimetype='text/plain'
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)