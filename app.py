from flask import Flask, render_template, request, jsonify, send_file
import os
import json
import io
from datetime import datetime
import requests
import threading
import time

app = Flask(__name__)

# ============ إعدادات ============
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# ============ دوال معلومات الـ BIN ============
def get_bin_info(bin_number):
    """الحصول على معلومات الـ BIN من API"""
    from bs4 import BeautifulSoup
    
    bin_number = str(bin_number)[:6]
    try:
        req = 'https://bins.antipublic.cc/bins/' + bin_number
        r = requests.get(req, timeout=10)
        
        try:
            data = r.json()
            fields = ['bin', 'brand', 'type', 'level', 'bank', 'country_name', 'country_flag']
            result = [data.get(field, "") for field in fields]
            
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
        print(f"Error: {e}")
        return None

# ============ دوال التحقق ============
def is_valid_luhn(card_number):
    if not card_number.isdigit():
        return False
    
    digits = [int(d) for d in card_number]
    checksum = 0
    
    for i in range(len(digits) - 2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] -= 9
    
    checksum = sum(digits)
    return checksum % 10 == 0

def is_valid_expiry(month, year):
    try:
        month = str(month).strip()
        year = str(year).strip()
        
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

# ============ Routes ============

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/filter', methods=['POST'])
def filter_cards():
    data = request.json
    cards = data.get('cards', '').split('\n')
    filters = data.get('filters', {})
    user_id = data.get('user_id', '')
    
    filtered = []
    stats = {
        'total': len(cards),
        'filtered': 0,
        'by_country': 0,
        'by_bank': 0,
        'by_type': 0,
        'by_level': 0,
        'by_bin': 0,
        'valid_only': 0
    }
    
    for card in cards:
        if not card.strip():
            continue
            
        parts = card.split('|')
        if len(parts) >= 3:
            card_number = parts[0].strip()
            exp_month = parts[1].strip()
            exp_year = parts[2].strip()
            cvv = parts[3].strip() if len(parts) > 3 else ''
            
            bin_info = get_bin_info(card_number[:6])
            
            include = True
            
            if filters.get('country'):
                if bin_info and filters['country'].lower() in bin_info.get('Country', '').lower():
                    stats['by_country'] += 1
                else:
                    include = False
            
            if filters.get('bank') and include:
                if bin_info and filters['bank'].lower() in bin_info.get('Bank', '').lower():
                    stats['by_bank'] += 1
                else:
                    include = False
            
            if filters.get('type') and include:
                if bin_info and filters['type'].lower() in bin_info.get('Type', '').lower():
                    stats['by_type'] += 1
                else:
                    include = False
            
            if filters.get('level') and include:
                if bin_info and filters['level'].lower() in bin_info.get('Level', '').lower():
                    stats['by_level'] += 1
                else:
                    include = False
            
            if filters.get('bin') and include:
                if card_number.startswith(filters['bin']):
                    stats['by_bin'] += 1
                else:
                    include = False
            
            if filters.get('valid_only') and include:
                if is_valid_expiry(exp_month, exp_year):
                    stats['valid_only'] += 1
                else:
                    include = False
            
            if include:
                enriched_card = card
                if bin_info:
                    enriched_card = f"{card} | {bin_info.get('Brand', '')} | {bin_info.get('Country', '')}"
                filtered.append(enriched_card)
    
    stats['filtered'] = len(filtered)
    
    return jsonify({
        'filtered': '\n'.join(filtered),
        'stats': stats,
        'count': len(filtered)
    })

@app.route('/send_to_bot', methods=['POST'])
def send_to_bot():
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
                'bin': '🔢 BIN',
                'valid_only': '✅ صالحة فقط'
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

@app.route('/bin_info', methods=['POST'])
def bin_info():
    data = request.json
    bin_number = data.get('bin', '')[:6]
    
    if not bin_number:
        return jsonify({'error': 'No BIN provided'}), 400
    
    info = get_bin_info(bin_number)
    if info:
        return jsonify(info)
    else:
        return jsonify({'error': 'BIN not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)