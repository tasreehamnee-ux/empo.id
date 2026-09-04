# -*- coding: utf-8 -*-
"""
أداة حذف بيانات الموظفين من لوحة تحكم Firestore (Vercel)
يمكنك تشغيل هذا الملف بشكل مستقل لحذف البيانات من السحابة
"""
import requests
import json
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    os.system('chcp 65001 >nul 2>&1')

PROJECT_ID = "empo-5992a"
API_KEY = "AIzaSyCZJQk8BSH41LWq81BZTMKp_WRo0lssVDc"
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"


def get_all_documents(collection_name):
    """جلب جميع المستندات من مجموعة معينة"""
    import time
    all_docs = []
    url = f"{BASE_URL}/{collection_name}?key={API_KEY}&pageSize=300"
    
    while url:
        for attempt in range(5):
            try:
                resp = requests.get(url, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    docs = data.get('documents', [])
                    all_docs.extend(docs)
                    next_page = data.get('nextPageToken')
                    if next_page:
                        url = f"{BASE_URL}/{collection_name}?key={API_KEY}&pageSize=300&pageToken={next_page}"
                    else:
                        url = None
                    break
                elif resp.status_code == 429:
                    wait_time = (attempt + 1) * 30
                    print(f"  ⏳ تم تجاوز الحد - انتظار {wait_time} ثانية...")
                    time.sleep(wait_time)
                else:
                    print(f"  ❌ خطأ: {resp.status_code}")
                    url = None
                    break
            except Exception as e:
                print(f"  ❌ استثناء: {e}")
                url = None
                break
        else:
            print(f"  ❌ فشل بعد 5 محاولات")
            url = None
    
    return all_docs


def delete_collection(collection_name, display_name):
    """حذف جميع المستندات من مجموعة"""
    import time
    print(f"\n{'='*50}")
    print(f"  📂 {display_name} ({collection_name})")
    print(f"{'='*50}")
    
    docs = get_all_documents(collection_name)
    total = len(docs)
    
    if total == 0:
        print(f"  ✅ المجموعة فارغة بالفعل - لا يوجد بيانات للحذف")
        return 0
    
    print(f"  📊 تم العثور على {total} سجل")
    
    deleted = 0
    for i, doc in enumerate(docs, 1):
        doc_name = doc.get("name", "")
        if doc_name:
            del_url = f"https://firestore.googleapis.com/v1/{doc_name}?key={API_KEY}"
            for attempt in range(5):
                try:
                    resp = requests.delete(del_url, timeout=10)
                    if resp.status_code == 200:
                        deleted += 1
                        if deleted % 10 == 0 or deleted == total:
                            print(f"  🗑️  تم حذف {deleted}/{total}...")
                        break
                    elif resp.status_code == 429:
                        wait_time = (attempt + 1) * 3
                        print(f"  ⏳ انتظار {wait_time} ثانية...")
                        time.sleep(wait_time)
                    else:
                        print(f"  ⚠️  فشل حذف سجل: {resp.status_code}")
                        break
                except Exception as e:
                    print(f"  ⚠️  خطأ: {e}")
                    break
            # Small delay between deletes to avoid rate limiting
            time.sleep(0.2)
    
    print(f"  ✅ تم حذف {deleted} من أصل {total} سجل بنجاح")
    return deleted


def main():
    print("\n" + "=" * 60)
    print("  🛡️  أداة حذف بيانات الموظفين من لوحة تحكم Firestore")
    print("=" * 60)
    
    print("\nاختر ما تريد حذفه:")
    print("  1️⃣  حذف موظفي القسم فقط (employees)")
    print("  2️⃣  حذف موظفي الوزارة فقط (ministry_employees)")
    print("  3️⃣  حذف الجميع (موظفي القسم + الوزارة)")
    print("  4️⃣  حذف المستخدمين (users)")
    print("  5️⃣  حذف كل شيء (موظفين + مستخدمين + إعدادات)")
    print("  0️⃣  إلغاء والخروج")
    
    choice = input("\n👉 اختيارك: ").strip()
    
    if choice == "0":
        print("\n  👋 تم الإلغاء. لم يتم حذف أي شيء.")
        return
    
    # Confirmation
    print("\n  ⚠️  تحذير: هذا الإجراء لا يمكن التراجع عنه!")
    confirm = input("  اكتب 'y' للتأكيد: ").strip().lower()
    
    if confirm not in ("y", "yes", "نعم"):
        print("\n  👋 تم الإلغاء. لم يتم حذف أي شيء.")
        return
    
    total_deleted = 0
    
    if choice in ["1", "3", "5"]:
        total_deleted += delete_collection("employees", "موظفي القسم")
    
    if choice in ["2", "3", "5"]:
        total_deleted += delete_collection("ministry_employees", "موظفي الوزارة")
    
    if choice in ["4", "5"]:
        total_deleted += delete_collection("users", "المستخدمين")
    
    if choice == "5":
        total_deleted += delete_collection("settings", "الإعدادات")
    
    print(f"\n{'='*60}")
    print(f"  🏁 انتهى! إجمالي السجلات المحذوفة: {total_deleted}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
    input("\nاضغط Enter للخروج...")
