from bs4 import BeautifulSoup
import requests
import re

def _get_flag(flag_code):
    """تحويل كود الدولة إلى إيموجي العلم"""
    if not flag_code:
        return ""
    # تحويل كود الدولة (مثل US) إلى إيموجي العلم
    flag = ""
    for char in flag_code.upper():
        if char.isalpha():
            flag += chr(ord(char) + 0x1F1E6 - ord('A'))
    return flag

def get_bin_info(bin):
    """الحصول على معلومات الـ BIN من الموقع"""
    bin = str(bin)[:6]
    try:
        req = 'https://bins.antipublic.cc/bins/' + bin
        r = requests.get(req, timeout=10)
        
        # محاولة قراءة JSON
        try:
            data = r.json()
            fields = ['bin', 'brand', 'type', 'level', 'bank', 'country_name', 'country_flag']
            result = [data.get(field, "") for field in fields]
            
            return {
                "Bin": result[0],
                "Brand": result[1],
                "Type": result[2],
                "Level": result[3],
                "Bank": result[4],
                "Country": f"{result[5]} {_get_flag(result[6]) if result[6] else ''}"
            }
        except:
            # إذا لم يكن JSON، نحاول استخدام HTML
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # محاولة استخراج البيانات من HTML
            info = {}
            
            # البحث عن العناصر التي تحتوي على المعلومات
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    key = cells[0].text.strip()
                    value = cells[1].text.strip()
                    info[key.lower()] = value
            
            return {
                "Bin": bin,
                "Brand": info.get('brand', ''),
                "Type": info.get('type', ''),
                "Level": info.get('level', ''),
                "Bank": info.get('bank', ''),
                "Country": info.get('country', '')
            }
            
    except Exception as e:
        print(f"Error fetching BIN info: {e}")
        return None