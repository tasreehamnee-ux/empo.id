# -*- coding: utf-8 -*-
"""
خادم الباك اند المتكامل لبوابة التصاريح الأمنية ونظام الموظفين
FastAPI + SQLite Backend Server
"""

import os
import sys
import json
import sqlite3
import shutil
from typing import Optional, List, Dict, Any
from datetime import datetime

# ضبط ترميز الكونسول في ويندوز
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import io
import pandas as pd

# مسار مجلد المشروع وقاعدة البيانات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# الكشف عما إذا كان الخادم يعمل في بيئة Vercel أو نظام ملفات للقراءة فقط
def get_writable_db_path():
    is_serverless = os.environ.get("VERCEL") == "1" or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
    local_db = os.path.join(BASE_DIR, "security_employees.db")
    
    if is_serverless or not os.access(BASE_DIR, os.W_OK):
        tmp_db = "/tmp/security_employees.db"
        try:
            if not os.path.exists(tmp_db) and os.path.exists(local_db):
                shutil.copy2(local_db, tmp_db)
        except Exception:
            pass
        return tmp_db
    return local_db

DB_PATH = get_writable_db_path()
BACKUPS_DIR = "/tmp/backups" if DB_PATH.startswith("/tmp") else os.path.join(BASE_DIR, "backups")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

try:
    os.makedirs(BACKUPS_DIR, exist_ok=True)
except Exception:
    pass

app = FastAPI(
    title="بوابة التصاريح الأمنية - نظام إدارة الموظفين API",
    description="واجهات برمجية متكاملة لربط استمارة التسجيل ولوحة المتابعة والمطابقة بقاعدة بيانات SQLite المحلية والسحابية",
    version="2.0.0"
)

# تمكين CORS للسماح بالاتصال من أي مصدر محلي أو شبكي
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# إدارة قاعدة البيانات (SQLite Helpers & Schema Initialization)
# ==========================================================

EMPLOYEE_COLUMNS = [
    'id', 'name', 'grade', 'stage', 'jobTitle', 'lastAllowanceDate', 'lastPromotionDate',
    'allowanceDueDate', 'promotionDuration', 'promotionDueDate', 'allowanceAmount',
    'appreciationLettersAllowance', 'appreciationLettersPromotion', 'remainingMonthsAllowance',
    'remainingMonthsPromotion', 'nominalSalary', 'commencementDate', 'yearsOfService',
    'monthsOfService', 'addedMonthsOfService', 'totalMonthsOfService', 'currentPosition',
    'phone', 'motherName', 'socialStatus', 'spouseName', 'placeOfBirth', 'ministerialId',
    'shift', 'workLocation', 'qualification', 'specialization', 'appointmentDate',
    'secondmentOrLeave', 'letterDateNumber', 'secondmentOrLeaveExpiry', 'dob', 'ageDays',
    'ageMonths', 'positionAssignmentDate', 'yearsOfServiceMonths', 'positionServiceDuration',
    'outgoingLetterNumber', 'email', 'sectionName', 'unitName', 'photo_path', 'photo_base64',
    'attachments', 'national_id', 'ration_card', 'createdAt', 'updatedAt'
]

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """تهيئة الجداول وفحص الأعمدة والتأكد من وجود جميع الحقول المطلوبة"""
    conn = get_db()
    cursor = conn.cursor()

    # 1. جدول الموظفين
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id TEXT PRIMARY KEY,
        name TEXT,
        grade TEXT,
        stage TEXT,
        jobTitle TEXT,
        lastAllowanceDate TEXT,
        lastPromotionDate TEXT,
        allowanceDueDate TEXT,
        promotionDuration TEXT,
        promotionDueDate TEXT,
        allowanceAmount TEXT,
        appreciationLettersAllowance TEXT,
        appreciationLettersPromotion TEXT,
        remainingMonthsAllowance TEXT,
        remainingMonthsPromotion TEXT,
        nominalSalary TEXT,
        commencementDate TEXT,
        yearsOfService TEXT,
        monthsOfService TEXT,
        addedMonthsOfService TEXT,
        totalMonthsOfService TEXT,
        currentPosition TEXT,
        phone TEXT,
        motherName TEXT,
        socialStatus TEXT,
        spouseName TEXT,
        placeOfBirth TEXT,
        ministerialId TEXT,
        shift TEXT,
        workLocation TEXT,
        qualification TEXT,
        specialization TEXT,
        appointmentDate TEXT,
        secondmentOrLeave TEXT,
        letterDateNumber TEXT,
        secondmentOrLeaveExpiry TEXT,
        dob TEXT,
        ageDays TEXT,
        ageMonths TEXT,
        positionAssignmentDate TEXT,
        yearsOfServiceMonths TEXT,
        positionServiceDuration TEXT,
        outgoingLetterNumber TEXT,
        email TEXT,
        sectionName TEXT,
        unitName TEXT,
        photo_path TEXT,
        photo_base64 TEXT,
        attachments TEXT,
        national_id TEXT,
        ration_card TEXT,
        createdAt TEXT,
        updatedAt TEXT
    );
    """)

    # فحص الأعمدة المفقودة وإضافتها ديناميكياً
    cursor.execute("PRAGMA table_info(employees);")
    existing_cols = [col[1] for col in cursor.fetchall()]
    for col in EMPLOYEE_COLUMNS:
        if col not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE employees ADD COLUMN {col} TEXT;")
            except Exception:
                pass

    # 2. جدول الإعدادات
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)

    # 3. جدول المستخدمين
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        role TEXT
    );
    """)

    # إدخال إعدادات ومستخدمين افتراضيين إن لم تكن موجودة
    cursor.execute("SELECT COUNT(*) FROM settings WHERE key = 'system_status';")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO settings (key, value) VALUES ('system_status', 'unlocked');")

    cursor.execute("SELECT COUNT(*) FROM users;")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'مدير النظام');")
    try:
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

try:
    init_db()
except Exception as e:
    print(f"⚠️ تحذير: تعذر تهيئة قاعدة البيانات المحلية: {e}")

# ==========================================================
# نماذج البيانات (Pydantic Models)
# ==========================================================

class EmployeeModel(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    grade: Optional[str] = None
    stage: Optional[str] = None
    jobTitle: Optional[str] = None
    lastAllowanceDate: Optional[str] = None
    lastPromotionDate: Optional[str] = None
    allowanceDueDate: Optional[str] = None
    promotionDuration: Optional[str] = None
    promotionDueDate: Optional[str] = None
    allowanceAmount: Optional[str] = None
    appreciationLettersAllowance: Optional[str] = None
    appreciationLettersPromotion: Optional[str] = None
    remainingMonthsAllowance: Optional[str] = None
    remainingMonthsPromotion: Optional[str] = None
    nominalSalary: Optional[str] = None
    commencementDate: Optional[str] = None
    yearsOfService: Optional[str] = None
    monthsOfService: Optional[str] = None
    addedMonthsOfService: Optional[str] = None
    totalMonthsOfService: Optional[str] = None
    currentPosition: Optional[str] = None
    phone: Optional[str] = None
    motherName: Optional[str] = None
    socialStatus: Optional[str] = None
    spouseName: Optional[str] = None
    placeOfBirth: Optional[str] = None
    ministerialId: Optional[str] = None
    shift: Optional[str] = None
    workLocation: Optional[str] = None
    qualification: Optional[str] = None
    specialization: Optional[str] = None
    appointmentDate: Optional[str] = None
    secondmentOrLeave: Optional[str] = None
    letterDateNumber: Optional[str] = None
    secondmentOrLeaveExpiry: Optional[str] = None
    dob: Optional[str] = None
    ageDays: Optional[str] = None
    ageMonths: Optional[str] = None
    positionAssignmentDate: Optional[str] = None
    yearsOfServiceMonths: Optional[str] = None
    positionServiceDuration: Optional[str] = None
    outgoingLetterNumber: Optional[str] = None
    email: Optional[str] = None
    sectionName: Optional[str] = None
    unitName: Optional[str] = None
    photo_path: Optional[str] = None
    photo_base64: Optional[str] = None
    attachments: Optional[Any] = None
    attachments_data: Optional[Any] = None
    national_id: Optional[str] = None
    ration_card: Optional[str] = None

class ChangeIdRequest(BaseModel):
    new_id: str

class SettingModel(BaseModel):
    key: str
    value: str

class UserModel(BaseModel):
    username: str
    password: str
    role: Optional[str] = "مستخدم"

# ==========================================================
# مسارات الواجهة الثابتة (Static & Frontend Routes)
# ==========================================================

@app.get("/", summary="لوحة التحكم والمتابعة الرئيسية")
def serve_index():
    index_file = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file, media_type="text/html")
    return JSONResponse(status_code=404, content={"message": "index.html not found"})

@app.get("/index.html")
def serve_index_html():
    return serve_index()

@app.get("/form", summary="استمارة تسجيل بيانات موظف")
def serve_form():
    form_file = os.path.join(BASE_DIR, "form.html")
    if os.path.exists(form_file):
        return FileResponse(form_file, media_type="text/html")
    return JSONResponse(status_code=404, content={"message": "form.html not found"})

@app.get("/form.html")
def serve_form_html():
    return serve_form()

@app.get("/admin", summary="لوحة القفل المركزي")
def serve_admin():
    admin_file = os.path.join(BASE_DIR, "admin_lock.html")
    if os.path.exists(admin_file):
        return FileResponse(admin_file, media_type="text/html")
    return JSONResponse(status_code=404, content={"message": "admin_lock.html not found"})

@app.get("/admin_lock.html")
def serve_admin_html():
    return serve_admin()

@app.get("/logo.jpg")
def serve_logo():
    logo_file = os.path.join(BASE_DIR, "logo.jpg")
    if os.path.exists(logo_file):
        return FileResponse(logo_file, media_type="image/jpeg")
    return Response(status_code=404)

if os.path.exists(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

# ==========================================================
# واجهات الـ REST API للموظفين (Employees CRUD)
# ==========================================================

def format_employee_dict(row_dict: dict) -> dict:
    """تنسيق وتجهيز قاموس بيانات الموظف بما يتوافق مع الواجهات الأمامية"""
    # معالجة المرفقات
    attachments_val = row_dict.get('attachments')
    if attachments_val and isinstance(attachments_val, str):
        try:
            row_dict['attachments_data'] = json.loads(attachments_val)
        except Exception:
            row_dict['attachments_data'] = attachments_val
    elif attachments_val:
        row_dict['attachments_data'] = attachments_val
    else:
        row_dict['attachments_data'] = []

    # التأكد من توفر photo_base64
    if not row_dict.get('photo_base64') and row_dict.get('photo_path'):
        row_dict['photo_base64'] = row_dict.get('photo_path')

    # firestoreId للتوافق مع شفرة index.html السابقة
    row_dict['firestoreId'] = row_dict.get('id')
    return row_dict

@app.get("/api/employees", summary="جلب قائمة الموظفين مع البحث والفلترة")
def get_employees(
    q: Optional[str] = None,
    shift: Optional[str] = None,
    section: Optional[str] = None
):
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM employees WHERE 1=1"
    params = []

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query += " AND (name LIKE ? OR id LIKE ? OR jobTitle LIKE ? OR ministerialId LIKE ? OR national_id LIKE ? OR workLocation LIKE ? OR phone LIKE ?)"
        params.extend([search_term] * 7)

    if shift and shift.strip() and shift not in ['كلاهما', 'صباحي / مسائي', 'صباحي/ مسائي', 'الكل']:
        query += " AND shift = ?"
        params.append(shift.strip())

    if section and section.strip() and section != 'الكل':
        query += " AND sectionName LIKE ?"
        params.append(f"%{section.strip()}%")

    query += " ORDER BY name ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    employees = [format_employee_dict(dict(row)) for row in rows]
    conn.close()
    
    return employees

@app.get("/api/employees/{emp_id}", summary="جلب بيانات موظف محدد")
def get_employee(emp_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees WHERE id = ?;", (emp_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")

    return format_employee_dict(dict(row))

@app.post("/api/employees", summary="إضافة موظف جديد أو تحديث سجل استمارة")
def create_or_update_employee(emp: EmployeeModel):
    emp_dict = emp.model_dump(exclude_unset=True)
    
    # تحديد أو توليد الرقم الوظيفي
    emp_id = emp_dict.get('id')
    if not emp_id or not str(emp_id).strip():
        emp_id = f"EMP-{int(datetime.now().timestamp() * 1000)}"
        emp_dict['id'] = emp_id
    else:
        emp_id = str(emp_id).strip()
        emp_dict['id'] = emp_id

    # معالجة المرفقات
    attachments = emp_dict.get('attachments_data') or emp_dict.get('attachments')
    if attachments is not None and not isinstance(attachments, str):
        emp_dict['attachments'] = json.dumps(attachments, ensure_ascii=False)
    elif attachments is not None:
        emp_dict['attachments'] = str(attachments)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emp_dict['updatedAt'] = now_str

    conn = get_db()
    cursor = conn.cursor()

    # جلب الأعمدة الموجودة في الجدول
    cursor.execute("PRAGMA table_info(employees);")
    valid_cols = [c[1] for c in cursor.fetchall()]

    # التحقق من وجود الموظف مسبقاً
    cursor.execute("SELECT COUNT(*) FROM employees WHERE id = ?;", (emp_id,))
    exists = cursor.fetchone()[0] > 0

    filtered_data = {k: v for k, v in emp_dict.items() if k in valid_cols and k != 'attachments_data'}

    if exists:
        set_clause = ", ".join([f"{k} = ?" for k in filtered_data.keys() if k != 'id'])
        values = [v for k, v in filtered_data.items() if k != 'id'] + [emp_id]
        cursor.execute(f"UPDATE employees SET {set_clause} WHERE id = ?;", values)
    else:
        filtered_data['createdAt'] = now_str
        cols_clause = ", ".join(filtered_data.keys())
        placeholders = ", ".join(["?"] * len(filtered_data))
        values = list(filtered_data.values())
        cursor.execute(f"INSERT INTO employees ({cols_clause}) VALUES ({placeholders});", values)

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "تم حفظ بيانات الموظف بنجاح",
        "id": emp_id
    }

@app.put("/api/employees/{emp_id}", summary="تعديل بيانات موظف")
def update_employee(emp_id: str, emp: EmployeeModel):
    emp_dict = emp.model_dump(exclude_unset=True)
    emp_dict['id'] = emp_id

    attachments = emp_dict.get('attachments_data') or emp_dict.get('attachments')
    if attachments is not None and not isinstance(attachments, str):
        emp_dict['attachments'] = json.dumps(attachments, ensure_ascii=False)
    elif attachments is not None:
        emp_dict['attachments'] = str(attachments)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emp_dict['updatedAt'] = now_str

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM employees WHERE id = ?;", (emp_id,))
    if cursor.fetchone()[0] == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="الموظف غير موجود")

    cursor.execute("PRAGMA table_info(employees);")
    valid_cols = [c[1] for c in cursor.fetchall()]

    filtered_data = {k: v for k, v in emp_dict.items() if k in valid_cols and k not in ['id', 'attachments_data']}

    if filtered_data:
        set_clause = ", ".join([f"{k} = ?" for k in filtered_data.keys()])
        values = list(filtered_data.values()) + [emp_id]
        cursor.execute(f"UPDATE employees SET {set_clause} WHERE id = ?;", values)

    conn.commit()
    conn.close()

    return {"success": True, "message": "تم تحديث بيانات الموظف بنجاح", "id": emp_id}

@app.post("/api/employees/{old_id}/change-id", summary="تغيير الرقم الوظيفي لموظف")
@app.put("/api/employees/{old_id}/change-id", summary="تغيير الرقم الوظيفي لموظف")
def change_employee_id(old_id: str, req: ChangeIdRequest):
    new_id = req.new_id.strip()
    if not new_id:
        raise HTTPException(status_code=400, detail="الرقم الوظيفي الجديد غير صالح")

    if new_id == old_id:
        return {"success": True, "message": "الرقم الوظيفي مطابق للحالي"}

    conn = get_db()
    cursor = conn.cursor()

    # التحقق من وجود الموظف القديم
    cursor.execute("SELECT * FROM employees WHERE id = ?;", (old_id,))
    emp_row = cursor.fetchone()
    if not emp_row:
        conn.close()
        raise HTTPException(status_code=404, detail="الموظف الأصلي غير موجود")

    # التحقق من عدم استخدام الرقم الجديد
    cursor.execute("SELECT COUNT(*) FROM employees WHERE id = ?;", (new_id,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        raise HTTPException(status_code=400, detail="الرقم الوظيفي الجديد مستخدم بالفعل لموظف آخر")

    emp_data = dict(emp_row)
    emp_data['id'] = new_id
    emp_data['updatedAt'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # إدراج السجل بالرقم الجديد وحذف القديم
    cols = ", ".join(emp_data.keys())
    placeholders = ", ".join(["?"] * len(emp_data))
    cursor.execute(f"INSERT INTO employees ({cols}) VALUES ({placeholders});", list(emp_data.values()))
    cursor.execute("DELETE FROM employees WHERE id = ?;", (old_id,))

    conn.commit()
    conn.close()

    return {"success": True, "message": "تم تعديل الرقم الوظيفي بنجاح", "new_id": new_id}

@app.delete("/api/employees/{emp_id}", summary="حذف موظف نهائياً")
def delete_employee(emp_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM employees WHERE id = ?;", (emp_id,))
    if cursor.fetchone()[0] == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="الموظف غير موجود")

    cursor.execute("DELETE FROM employees WHERE id = ?;", (emp_id,))
    conn.commit()
    conn.close()

    return {"success": True, "message": "تم حذف الموظف بنجاح"}

# ==========================================================
# واجهات الإحصائيات والتصدير (Stats & Exports)
# ==========================================================

@app.get("/api/stats", summary="إحصائيات شاملة للموظفين")
def get_stats():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM employees;")
    total_count = cursor.fetchone()[0]

    cursor.execute("SELECT shift, COUNT(*) FROM employees GROUP BY shift;")
    shift_counts = {row[0] or "غير محدد": row[1] for row in cursor.fetchall()}

    cursor.execute("SELECT sectionName, COUNT(*) FROM employees GROUP BY sectionName;")
    section_counts = {row[0] or "شعبة المتابعة": row[1] for row in cursor.fetchall()}

    conn.close()

    return {
        "total": total_count,
        "by_shift": shift_counts,
        "by_section": section_counts
    }

@app.get("/api/export/excel", summary="تصدير قاعدة بيانات الموظفين لملف Excel منسق")
def export_excel():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees ORDER BY name ASC;")
    rows = cursor.fetchall()
    conn.close()

    data = []
    for idx, r in enumerate(rows, 1):
        emp = dict(r)
        data.append({
            "ت": idx,
            "الاسم الكامل الرباعي": emp.get("name", ""),
            "الرقم الوظيفي": emp.get("id", ""),
            "رقم البطاقة الوطنية": emp.get("national_id", ""),
            "رقم البطاقة التموينية": emp.get("ration_card", ""),
            "تاريخ الميلاد": emp.get("dob", ""),
            "مكان الولادة": emp.get("placeOfBirth", ""),
            "الحالة الاجتماعية": emp.get("socialStatus", ""),
            "اسم الأم الكامل": emp.get("motherName", ""),
            "اسم الزوج / الزوجة": emp.get("spouseName", ""),
            "رقم الموبايل": emp.get("phone", ""),
            "البريد الإلكتروني": emp.get("email", ""),
            "التحصيل الدراسي": emp.get("qualification", ""),
            "التخصص الدراسي الدقيق": emp.get("specialization", ""),
            "العنوان الوظيفي": emp.get("jobTitle", ""),
            "الدرجة الوظيفية": emp.get("grade", ""),
            "المرحلة": emp.get("stage", ""),
            "الدوام": emp.get("shift", ""),
            "موقع العمل": emp.get("workLocation", ""),
            "المنصب الحالي": emp.get("currentPosition", ""),
            "رقم الهوية الوزارية": emp.get("ministerialId", ""),
            "تاريخ التعيين": emp.get("appointmentDate", ""),
            "تاريخ المباشرة بالعمل": emp.get("commencementDate", ""),
            "اسم الشعبة / الوحدة": emp.get("sectionName", ""),
            "اسم الوحدة الفرعية": emp.get("unitName", "")
        })

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="الموظفين")
    output.seek(0)

    filename = f"employees_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/backup", summary="تنزيل نسخة احتياطية من قاعدة البيانات")
def download_backup():
    if os.path.exists(DB_PATH):
        backup_filename = f"security_employees_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        return FileResponse(DB_PATH, filename=backup_filename, media_type="application/x-sqlite3")
    raise HTTPException(status_code=404, detail="قاعدة البيانات غير موجودة")

# ==========================================================
# واجهات الإعدادات والمستخدمين (Settings & Users)
# ==========================================================

@app.get("/api/settings", summary="جلب جميع الإعدادات")
def get_settings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings;")
    settings = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return settings

@app.post("/api/settings", summary="تحديث أو إضافة إعداد")
def set_setting(item: SettingModel):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?);", (item.key, item.value))
    conn.commit()
    conn.close()
    return {"success": True, "key": item.key, "value": item.value}

@app.get("/api/users", summary="جلب قائمة المستخدمين المصرح لهم")
def get_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username, password, role FROM users;")
    users = [{"username": row[0], "password": row[1], "role": row[2]} for row in cursor.fetchall()]
    conn.close()
    return users

@app.post("/api/users", summary="إضافة أو تعديل مستخدم")
def save_user(user: UserModel):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (username, password, role) VALUES (?, ?, ?);", (user.username, user.password, user.role))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"تم حفظ المستخدم {user.username} بنجاح"}

# ==========================================================
# نقطة التشغيل الرئيسية (Main Server Runner)
# ==========================================================

if __name__ == "__main__":
    import socket

    def is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    selected_port = 8000
    if is_port_in_use(selected_port):
        print(f"⚠️ تنبيه: المنفذ {selected_port} مشغول، سيتم تجربة المنفذ 8080...")
        selected_port = 8080 if not is_port_in_use(8080) else 8001

    print("=" * 60)
    print("🚀 جاري تشغيل خادم بوابة التصاريح الأمنية (FastAPI Backend)...")
    print(f"📁 قاعدة البيانات المحلية: {DB_PATH}")
    print("🌐 روابط النظام:")
    print(f"   - لوحة المتابعة الرئيسية: http://localhost:{selected_port}")
    print(f"   - استمارة تسجيل الموظفين: http://localhost:{selected_port}/form")
    print(f"   - لوحة القفل السري:      http://localhost:{selected_port}/admin")
    print(f"   - توثيق الـ API (Swagger): http://localhost:{selected_port}/docs")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=selected_port, log_level="info")
