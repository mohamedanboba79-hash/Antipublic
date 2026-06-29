import re
import pandas as pd
from datetime import datetime
from io import BytesIO, StringIO
import requests
from bs4 import BeautifulSoup

def _info_bin(bin):
    """جلب معلومات الـ BIN من الموقع"""
    bin = str(bin)[:6]
    try:
        req = 'https://bins.antipublic.cc/bins/' + bin
        r = requests.get(req)
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
    except Exception as e:
        print(e)
        return {
            "Bin": "",
            "Brand": "",
            "Type": "",
            "Level": "",
            "Bank": "",
            "Country": ""
        }

def _get_flag(flag_code):
    """تحويل كود الدولة إلى إيموجي علم"""
    return flag_code.upper() if flag_code else ""

def parse_card_file(content):
    """قراءة ملف البطاقات وتحويله إلى DataFrame"""
    lines = content.strip().split('\n')
    data = []
    for line in lines:
        match = re.match(r'^(\d+)\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})$', line.strip())
        if match:
            card, month, year, cvv = match.groups()
            if len(year) == 2:
                year = '20' + year
            data.append([card, month, year, cvv])
        else:
            parts = re.split(r'[|:;,\t\s]+', line.strip())
            if len(parts) >= 4:
                card = parts[0]
                month = parts[1]
                year = parts[2]
                cvv = parts[3]
                if len(year) == 2:
                    year = '20' + year
                data.append([card, month, year, cvv])
    
    df = pd.DataFrame(data, columns=['card', 'month', 'year', 'cvv'])
    df['card'] = df['card'].str.replace(r'\s+', '', regex=True)
    df = df[df['card'].str.isdigit()]
    df['month'] = df['month'].str.zfill(2)
    df['year'] = df['year'].str[:4]
    df['cvv'] = df['cvv'].str.zfill(3)
    return df

def validate_card(card):
    """التحقق من صحة رقم البطاقة باستخدام Luhn Algorithm"""
    def luhn_checksum(card_number):
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10
    return luhn_checksum(card) == 0

def clean_cards(df):
    """تنظيف البطاقات: إزالة التكرارات، التحقق من الصلاحية، التحقق من Luhn"""
    df = df.drop_duplicates(subset=['card']).copy()
    df['valid_luhn'] = df['card'].apply(validate_card)
    df = df[df['valid_luhn']].copy()
    current_year = datetime.now().year
    current_month = datetime.now().month
    df['year'] = df['year'].astype(int)
    df['month'] = df['month'].astype(int)
    df = df[(df['year'] > current_year) | ((df['year'] == current_year) & (df['month'] >= current_month))]
    df = df.drop(columns=['valid_luhn'])
    return df

def extract_bins(df, bin_list):
    """استخراج البطاقات التي تبدأ بـ BINs محددة"""
    bin_patterns = [str(b).strip() for b in bin_list]
    mask = df['card'].str.startswith(tuple(bin_patterns))
    return df[mask].copy()

def remove_bins(df, bin_list):
    """حذف البطاقات التي تبدأ بـ BINs محددة"""
    bin_patterns = [str(b).strip() for b in bin_list]
    mask = ~df['card'].str.startswith(tuple(bin_patterns))
    return df[mask].copy()

def sort_cards(df, by='card'):
    """ترتيب البطاقات حسب الحقل المطلوب"""
    return df.sort_values(by=by).copy()

def export_cards(df):
    """تصدير البطاقات إلى نص بنفس التنسيق: رقم|شهر|سنة|CVV"""
    df['year_short'] = df['year'].astype(str).str[2:]
    lines = df.apply(lambda x: f"{x['card']}|{str(x['month']).zfill(2)}|{x['year_short']}|{str(x['cvv']).zfill(3)}", axis=1)
    return '\n'.join(lines)

def get_bin_info(bin):
    """جلب معلومات الـ BIN مع معالجة الأخطاء"""
    return _info_bin(bin)