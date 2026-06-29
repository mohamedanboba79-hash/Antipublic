from flask import Flask, render_template, request, jsonify
import os
import sys
import json
import pandas as pd

# إضافة المجلد الحالي للمسار
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from functions import parse_card_file, get_bin_info, clean_cards, export_cards

app = Flask(__name__)

# تخزين مؤقت للبيانات
session_data = {}

@app.route('/')
def index():
    return render_template('index.html')

# عشان النماذج في نفس المجلد
@app.route('/templates/index.html')
def serve_index():
    with open('index.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/load_cards', methods=['POST'])
def load_cards():
    """استقبال البطاقات من البوت"""
    try:
        data = request.get_json()
        cards_text = data.get('cards', '')
        
        if not cards_text:
            return jsonify({'success': False, 'error': 'No cards data'})
        
        df = parse_card_file(cards_text)
        
        if df.empty:
            return jsonify({'success': False, 'error': 'Invalid cards data'})
        
        cards = []
        for _, row in df.iterrows():
            bin_code = str(row['card'])[:6]
            info = get_bin_info(bin_code)
            cards.append({
                'card': str(row['card']),
                'month': str(row['month']).zfill(2),
                'year': str(row['year']),
                'cvv': str(row['cvv']).zfill(3),
                'bin': bin_code,
                'brand': info.get('Brand', 'Unknown'),
                'type': info.get('Type', 'Unknown'),
                'level': info.get('Level', 'Unknown'),
                'bank': info.get('Bank', 'Unknown'),
                'country': info.get('Country', 'Unknown')
            })
        
        session_data['cards'] = cards
        session_data['raw_text'] = cards_text
        
        return jsonify({
            'success': True,
            'cards': cards,
            'total': len(cards)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/apply_filters', methods=['POST'])
def apply_filters():
    """تطبيق الفلاتر وإرجاع النتيجة"""
    try:
        data = request.get_json()
        filters = data.get('filters', {})
        cards = session_data.get('cards', [])
        
        if not cards:
            return jsonify({'success': False, 'error': 'No cards loaded'})
        
        filtered = cards
        for key, values in filters.items():
            if values and len(values) > 0:
                filtered = [c for c in filtered if c.get(key) in values]
        
        result_text = '\n'.join([
            f"{c['card']}|{c['month']}|{c['year'][-2:]}|{c['cvv']}"
            for c in filtered
        ])
        
        return jsonify({
            'success': True,
            'cards': filtered,
            'total': len(filtered),
            'text': result_text
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/export', methods=['POST'])
def export():
    """تصدير البطاقات"""
    try:
        data = request.get_json()
        cards = data.get('cards', [])
        
        if not cards:
            return jsonify({'success': False, 'error': 'No cards to export'})
        
        text = '\n'.join([
            f"{c['card']}|{c['month']}|{c['year'][-2:]}|{c['cvv']}"
            for c in cards
        ])
        
        return jsonify({'success': True, 'text': text})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/check_bins', methods=['POST'])
def check_bins():
    """فحص معلومات BINs متعددة"""
    try:
        data = request.get_json()
        bins = data.get('bins', [])
        results = {}
        
        for bin_code in bins:
            info = get_bin_info(bin_code[:6])
            results[bin_code] = info
        
        return jsonify({'success': True, 'data': results})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/health', methods=['GET'])
def health():
    """فحص صحة السيرفر"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)