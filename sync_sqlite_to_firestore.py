# -*- coding: utf-8 -*-
"""
سكربت مزامنة ورفع بيانات الموظفين من قواعد بيانات SQLite المحلية إلى Firestore
"""
import sqlite3
import requests
import json
import sys
import os
import time

# ضبط ترميز الكونسول في ويندوز
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    os.system('chcp 65001 >nul 2>&1')

PROJECT_ID = "empo-5992a"
API_KEY = "AIzaSyCZJQk8BSH41LWq81BZTMKp_WRo0lssVDc"
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

# مسارات قواعد البيانات المحلية
DB_EMPLOYEES = r"قاعدة بيانات الموظفين/security_employees.db"
DB_MINISTRY = r"قاعدة بيانات الموظفين/ministry_forms.db"

def val_to_firestore(val):
    """تحويل قيم بايثون لتنسيق Firestore JSON"""
    if val is None:
        return {"nullValue": None}
    elif isinstance(val, bool):
        return {"booleanValue": val}
    elif isinstance(val, (int, float)):
        # Firestore REST API يفضل إرسال الأرقام النصية للـ integer
        return {"stringValue": str(val)}
    else:
        return {"stringValue": str(val)}

def dict_to_firestore_fields(row_dict):
    """تحويل قاموس مسطح لقاموس حقول Firestore"""
    return {k: val_to_firestore(v) for k, v in row_dict.items() if v is not None}

def upload_document(collection, doc_id, fields):
    """رفع مستند واحد إلى Firestore"""
    url = f"{BASE_URL}/{collection}/{doc_id}?key={API_KEY}"
    payload = {"fields": fields}
    
    # محاولة الرفع مع إمكانية إعادة المحاولة عند حدوث ضغط معدل طلبات (Rate limiting)
    for attempt in range(5):
        try:
            # استخدام PATCH ليعمل كـ Set (إضافة أو دمج)
            resp = requests.patch(url, json=payload, timeout=15)
            if resp.status_code == 200:
                return True
            elif resp.status_code == 429:
                wait = (attempt + 1) * 2
                time.sleep(wait)
            else:
                print(f"  ❌ خطأ في رفع المستند {doc_id}: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"  ⚠️ استثناء أثناء رفع {doc_id}: {e}")
            time.sleep(1)
    return False

def sync_department_employees():
    print("\n" + "="*50)
    print("  ⏳ جاري مزامنة موظفي شعبة المتابعة (Employees)...")
    print("="*50)
    
    if not os.path.exists(DB_EMPLOYEES):
        print(f"  ❌ لم يتم العثور على قاعدة البيانات: {DB_EMPLOYEES}")
        return
        
    conn = sqlite3.connect(DB_EMPLOYEES)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM employees;")
        rows = cursor.fetchall()
        total = len(rows)
        print(f"  📊 تم العثور على {total} موظف في قاعدة البيانات المحلية.")
        
        success_count = 0
        for i, row in enumerate(rows, 1):
            row_dict = dict(row)
            doc_id = str(row_dict.get('id', '')).strip()
            
            if not doc_id or doc_id == 'None':
                print(f"  ⚠️ تخطي السجل {i}: رقم الموظف غير صالح")
                continue
                
            fields = dict_to_firestore_fields(row_dict)
            
            # رفع المستند
            if upload_document("employees", doc_id, fields):
                success_count += 1
                if success_count % 20 == 0 or success_count == total:
                    print(f"  🚀 تم رفع {success_count}/{total} موظف...")
            
            # تأخير خفيف لتفادي الـ rate limiting
            time.sleep(0.1)
            
        print(f"  ✅ اكتملت المزامنة بنجاح: تم رفع {success_count} موظف.")
    except Exception as e:
        print(f"  ❌ خطأ أثناء مزامنة الموظفين: {e}")
    finally:
        conn.close()

def sync_ministry_employees():
    print("\n" + "="*50)
    print("  ⏳ جاري مزامنة موظفي الوزارة عامة (Ministry Forms)...")
    print("="*50)
    
    if not os.path.exists(DB_MINISTRY):
        print(f"  ❌ لم يتم العثور على قاعدة البيانات: {DB_MINISTRY}")
        return
        
    conn = sqlite3.connect(DB_MINISTRY)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM forms;")
        rows = cursor.fetchall()
        total = len(rows)
        print(f"  📊 تم العثور على {total} استمارة في قاعدة البيانات المحلية.")
        
        success_count = 0
        for i, row in enumerate(rows, 1):
            row_dict = dict(row)
            # نستخدم البطاقة الموحدة أو رقم الهوية كمعرف فريد، وإذا لم تتوفر نستخدم الـ id كـ doc_id
            doc_id = str(row_dict.get('national_id', '')).strip()
            if not doc_id or doc_id == 'None':
                doc_id = str(row_dict.get('id_number', '')).strip()
            if not doc_id or doc_id == 'None':
                doc_id = str(row_dict.get('id', '')).strip()
                
            if not doc_id:
                print(f"  ⚠️ تخطي السجل {i}: لم يتم العثور على معرف فريد")
                continue
                
            # تحويل حقول الـ json المخزنة كنصوص إلى كائنات إن أمكن، أو تركها كنصوص
            fields = dict_to_firestore_fields(row_dict)
            
            # رفع المستند
            if upload_document("ministry_employees", doc_id, fields):
                success_count += 1
                if success_count % 20 == 0 or success_count == total:
                    print(f"  🚀 تم رفع {success_count}/{total} استمارة...")
                    
            time.sleep(0.1)
            
        print(f"  ✅ اكتملت المزامنة بنجاح: تم رفع {success_count} استمارة.")
    except Exception as e:
        print(f"  ❌ خطأ أثناء مزامنة موظفي الوزارة: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    start_time = time.time()
    print("🚀 بدء عملية المزامنة الشاملة إلى Firestore...")
    sync_department_employees()
    sync_ministry_employees()
    duration = time.time() - start_time
    print(f"\n✨ تمت عملية المزامنة بنجاح واستغرقت {duration:.2f} ثانية.")
