# -*- coding: utf-8 -*-
"""
سكربت المزامنة العكسية: قراءة البيانات الجديدة من Firestore وتحديث قاعدة البيانات المحلية للتطبيق المكتبي تلقائياً
"""
import sqlite3
import requests
import time
import os
import sys

# ضبط ترميز الكونسول في ويندوز
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    os.system('chcp 65001 >nul 2>&1')

PROJECT_ID = "empo-5992a"
API_KEY = "AIzaSyCZJQk8BSH41LWq81BZTMKp_WRo0lssVDc"
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

# مسارات قواعد البيانات المحلية
DB_PATHS = [
    r"قاعدة بيانات الموظفين/security_employees.db",
    r"security_employees.db"
]

def parse_firestore_value(val_dict):
    """تحويل قيم Firestore JSON إلى قيم بايثون المناسبة"""
    if not val_dict:
        return None
    if "stringValue" in val_dict:
        return val_dict["stringValue"]
    elif "integerValue" in val_dict:
        return int(val_dict["integerValue"])
    elif "doubleValue" in val_dict:
        return float(val_dict["doubleValue"])
    elif "booleanValue" in val_dict:
        return val_dict["booleanValue"]
    elif "nullValue" in val_dict:
        return None
    return str(val_dict)

def doc_to_dict(doc_json):
    """تحويل مستند Firestore إلى قاموس بايثون مسطح"""
    fields = doc_json.get("fields", {})
    parsed = {}
    for k, v in fields.items():
        parsed[k] = parse_firestore_value(v)
    return parsed

def get_firestore_employees():
    """جلب جميع موظفي شعبة المتابعة من Firestore"""
    url = f"{BASE_URL}/employees?key={API_KEY}&pageSize=300"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            docs = data.get("documents", [])
            employees = []
            for doc in docs:
                emp = doc_to_dict(doc)
                if emp.get("id"):
                    employees.append(emp)
            return employees
        else:
            print(f"  ❌ خطأ في جلب بيانات Firestore: {resp.status_code}")
    except Exception as e:
        print(f"  ⚠️ استثناء أثناء جلب بيانات Firestore: {e}")
    return []

def get_sqlite_columns(db_path):
    """جلب أسماء الأعمدة في جدول الموظفين بقاعدة البيانات المحلية"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(employees);")
        cols = [c[1] for c in cursor.fetchall()]
        conn.close()
        return cols
    except Exception as e:
        print(f"  ⚠️ خطأ في قراءة أعمدة SQLite لقاعدة {db_path}: {e}")
        return []

def update_local_db(db_path, firestore_employees):
    """تحديث قاعدة البيانات المحلية بالبيانات المستلمة من السحاب"""
    if not os.path.exists(db_path):
        return
    
    # جلب الأعمدة المدعومة محلياً لمنع الأخطاء في حال اختلاف هيكلية الجداول
    db_cols = get_sqlite_columns(db_path)
    if not db_cols:
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    updated_count = 0
    inserted_count = 0
    
    for emp in firestore_employees:
        emp_id = emp.get("id")
        
        # تصفية الحقول لتشمل فقط الأعمدة الموجودة في قاعدة البيانات المحلية
        # وخرائط الحقول المخصصة (مثل attachments_data إلى attachments)
        row_data = {}
        for col in db_cols:
            if col in emp:
                row_data[col] = emp[col]
            elif col == "attachments" and "attachments_data" in emp:
                row_data[col] = emp["attachments_data"]
            else:
                row_data[col] = None
        
        # نضمن كتابة الـ id بشكل صحيح
        row_data["id"] = emp_id

        # التحقق من وجود الموظف مسبقاً
        cursor.execute("SELECT COUNT(*) FROM employees WHERE id = ?;", (emp_id,))
        exists = cursor.fetchone()[0] > 0
        
        # إعداد عبارة SQL ديناميكية
        cols_str = ", ".join(row_data.keys())
        placeholders = ", ".join(["?"] * len(row_data))
        values = tuple(row_data.values())
        
        if exists:
            # تحديث
            # ننشئ عبارة UPDATE
            set_str = ", ".join([f"{col} = ?" for col in row_data.keys() if col != "id"])
            update_values = tuple(v for k, v in row_data.items() if k != "id") + (emp_id,)
            cursor.execute(f"UPDATE employees SET {set_str} WHERE id = ?;", update_values)
            updated_count += 1
        else:
            # إدراج جديد
            cursor.execute(f"INSERT INTO employees ({cols_str}) VALUES ({placeholders});", values)
            inserted_count += 1
            
    conn.commit()
    conn.close()
    
    if inserted_count > 0 or updated_count > 0:
        print(f"  💾 تم تحديث القاعدة [{db_path}]: إدراج جديد: {inserted_count} | تحديث سجلات: {updated_count}")

def main():
    print("="*60)
    print("  🔄 بدء تشغيل خدمة المزامنة العكسية (السحاب ⬅️ المكتبي)...")
    print("  📂 قواعد البيانات المستهدفة:")
    for path in DB_PATHS:
        if os.path.exists(path):
            print(f"    - {path}")
    print("="*60)
    
    # حلقة تكرارية للتشغيل المستمر كل 10 ثوانٍ
    # (يمكن للمستخدم تركها تعمل في كونسول منفصل)
    try:
        while True:
            # 1. جلب البيانات من السحاب
            firestore_employees = get_firestore_employees()
            
            if firestore_employees:
                # 2. تحديث كل قاعدة بيانات موجودة محلياً
                for db_path in DB_PATHS:
                    if os.path.exists(db_path):
                        update_local_db(db_path, firestore_employees)
            
            # الانتظار 10 ثوانٍ قبل المزامنة التالية
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n👋 تم إيقاف خدمة المزامنة بنجاح.")

if __name__ == "__main__":
    main()
