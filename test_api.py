from fastapi.testclient import TestClient
from api import app  # استيراد تطبيق FastAPI من ملف api.py الخاص بك

# إنشاء عميل اختبار مرتبط بالتطبيق
client = TestClient(app)

def test_read_root():
    # قم بتغيير "/" إلى أحد المسارات (Endpoints) الموجودة في تطبيقك
    response = client.get("/")
    
    # التحقق من أن حالة الاستجابة هي 200 (نجاح)
    assert response.status_code == 200
    
    # يمكنك أيضاً التحقق من محتوى الرد (JSON) إذا كان يرجع بيانات محددة
    # assert response.json() == {"status": "success"}

def test_admin_features():
    # مثال لاختبار مسار آخر (مثل ميزات المشرف إن وجدت)
    response = client.get("/admin") # استبدل المسار بما يناسب مشروعك
    # يمكنك توقع 200 أو 401/403 إذا كان المسار يتطلب مصادقة
    assert response.status_code in [200, 401, 403]
  
