import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

# ============ ملفات التخزين المؤقت ============
CACHE_FILE = 'bin_cache.json'
CACHE_DURATION = 86400  # 24 ساعة

def _get_flag(flag_code):
    """تحويل كود الدولة إلى إيموجي العلم"""
    if not flag_code:
        return ""
    flag = ""
    for char in flag_code.upper():
        if char.isalpha():
            flag += chr(ord(char) + 0x1F1E6 - ord('A'))
    return flag

def load_cache():
    """تحميل الكاش"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
                now = datetime.now().timestamp()
                return {k: v for k, v in cache.items() 
                       if now - v.get('timestamp', 0) < CACHE_DURATION}
    except:
        pass
    return {}

def save_cache(cache):
    """حفظ الكاش"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=4)
    except:
        pass

def get_bin_info(bin_number):
    """الحصول على معلومات الـ BIN من API مع كاش"""
    bin_number = str(bin_number)[:6]
    
    # التحقق من الكاش أولاً
    cache = load_cache()
    if bin_number in cache:
        return cache[bin_number]['data']
    
    try:
        req = 'https://bins.antipublic.cc/bins/' + bin_number
        r = requests.get(req, timeout=10)
        
        # محاولة قراءة JSON
        try:
            data = r.json()
            fields = ['bin', 'brand', 'type', 'level', 'bank', 'country_name', 'country_flag']
            result = [data.get(field, "") for field in fields]
            
            flag = _get_flag(result[6]) if result[6] else ""
            
            info = {
                "Bin": result[0] or bin_number,
                "Brand": result[1] or "Unknown",
                "Type": result[2] or "Unknown",
                "Level": result[3] or "Unknown",
                "Bank": result[4] or "Unknown",
                "Country": f"{result[5]} {flag}" if flag else (result[5] or "Unknown")
            }
            
        except:
            # استخدام BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            info_data = {}
            
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    key = cells[0].text.strip().lower()
                    value = cells[1].text.strip()
                    info_data[key] = value
            
            flag = _get_flag(info_data.get('country_flag', ''))
            
            info = {
                "Bin": info_data.get('bin', bin_number),
                "Brand": info_data.get('brand', 'Unknown'),
                "Type": info_data.get('type', 'Unknown'),
                "Level": info_data.get('level', 'Unknown'),
                "Bank": info_data.get('bank', 'Unknown'),
                "Country": f"{info_data.get('country_name', '')} {flag}" if flag else (info_data.get('country_name', 'Unknown'))
            }
        
        # حفظ في الكاش
        cache[bin_number] = {
            'data': info,
            'timestamp': datetime.now().timestamp()
        }
        save_cache(cache)
        
        return info
        
    except Exception as e:
        print(f"Error fetching BIN {bin_number}: {e}")
        return {
            "Bin": bin_number,
            "Brand": "Unknown",
            "Type": "Unknown",
            "Level": "Unknown",
            "Bank": "Unknown",
            "Country": "Unknown"
        }

def get_bulk_bin_info(bins_list):
    """الحصول على معلومات مجموعة BINs دفعة واحدة"""
    results = {}
    for bin_num in bins_list:
        bin_num = str(bin_num)[:6]
        results[bin_num] = get_bin_info(bin_num)
    return results

def extract_all_info_from_cards(cards):
    """استخراج كل المعلومات من قائمة البطاقات"""
    countries = {}
    banks = {}
    brands = set()
    types = set()
    levels = set()
    bin_info_cache = {}
    
    for card in cards:
        if not card.strip():
            continue
        
        parts = card.split('|')
        if len(parts) < 3:
            continue
        
        card_number = parts[0].strip()
        bin_number = card_number[:6]
        
        # استخدام الكاش المحلي لتجنب الطلبات المتكررة
        if bin_number not in bin_info_cache:
            bin_info_cache[bin_number] = get_bin_info(bin_number)
        
        info = bin_info_cache[bin_number]
        
        if info:
            # الدول
            country = info.get('Country', 'Unknown')
            if country and country != 'Unknown':
                countries[country] = countries.get(country, 0) + 1
            
            # البنوك
            bank = info.get('Bank', 'Unknown')
            if bank and bank != 'Unknown':
                banks[bank] = banks.get(bank, 0) + 1
            
            # البراند
            brand = info.get('Brand', 'Unknown')
            if brand and brand != 'Unknown':
                brands.add(brand)
            
            # النوع
            card_type = info.get('Type', 'Unknown')
            if card_type and card_type != 'Unknown':
                types.add(card_type)
            
            # المستوى
            level = info.get('Level', 'Unknown')
            if level and level != 'Unknown':
                levels.add(level)
    
    # ترتيب النتائج
    countries = dict(sorted(countries.items(), key=lambda x: x[1], reverse=True))
    banks = dict(sorted(banks.items(), key=lambda x: x[1], reverse=True))
    brands = sorted(list(brands))
    types = sorted(list(types))
    levels = sorted(list(levels))
    
    return {
        'countries': countries,
        'banks': banks,
        'brands': brands,
        'types': types,
        'levels': levels,
        'total_cards': len(cards),
        'bin_info': bin_info_cache
    }

def filter_cards_by_criteria(cards, filters):
    """تصفية البطاقات حسب المعايير"""
    filtered = []
    bin_info_cache = {}
    
    for card in cards:
        if not card.strip():
            continue
        
        parts = card.split('|')
        if len(parts) < 3:
            continue
        
        card_number = parts[0].strip()
        bin_number = card_number[:6]
        
        if bin_number not in bin_info_cache:
            bin_info_cache[bin_number] = get_bin_info(bin_number)
        
        info = bin_info_cache[bin_number]
        include = True
        
        # فلتر الدولة
        if filters.get('country'):
            if not info or filters['country'] not in info.get('Country', ''):
                include = False
        
        # فلتر البنك
        if filters.get('bank') and include:
            if not info or filters['bank'] not in info.get('Bank', ''):
                include = False
        
        # فلتر البراند
        if filters.get('brand') and include:
            if not info or filters['brand'] != info.get('Brand', ''):
                include = False
        
        # فلتر النوع
        if filters.get('type') and include:
            if not info or filters['type'] != info.get('Type', ''):
                include = False
        
        # فلتر المستوى
        if filters.get('level') and include:
            if not info or filters['level'] != info.get('Level', ''):
                include = False
        
        if include:
            filtered.append(card)
    
    return filtered

# ============ اختبار ============
if __name__ == '__main__':
    # اختبار
    test_bin = '527515'
    info = get_bin_info(test_bin)
    print(f"BIN {test_bin}: {json.dumps(info, indent=2)}")