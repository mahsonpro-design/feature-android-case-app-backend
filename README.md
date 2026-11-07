# محكمة البيضاء — التطبيق والخادم

تطبيق Android بواجهة عربية، ثيم كحلي وذهبي مستوحى من الصور، وخادم API خاص. الحسابات الجديدة تنتظر موافقة المسؤول. لا يحتوي APK على Telegram token أو أسرار الخادم.

## حالة التنفيذ

هذا المستودع ما يزال يحتوي على README فقط. لم تُرفع ملفات التطبيق أو الخادم بعد، ولم يُنشأ APK. يلزم تفعيل صلاحية الكتابة لمساعد GitHub على هذا المستودع أو إضافة الملفات يدويًا قبل أن يمكن تشغيل CI أو البناء.

## الخطة التقنية

- API: FastAPI، حسابات pending حتى موافقة المسؤول، كلمات مرور مخزنة بـ Argon2، JWT، وسجل تدقيق.
- Android: Kotlin/Jetpack Compose، واجهة عربية باتجاه RTL، ألوان كحلية وذهبية وبطاقات بيضاء.
- يتطلب API خادمًا دائمًا مع HTTPS وقرص دائم. لا تضع `TELEGRAM_BOT_TOKEN` أو أسرار الخادم داخل APK.

## الإعداد المطلوب عند إضافة الملفات

تُضبط أسرار API على الخادم فقط: `JWT_SECRET`, `APP_DATABASE_PATH`, `GOOGLE_DRIVE_FILE_ID`, `ADMIN_BOOTSTRAP_NAME`, `ADMIN_BOOTSTRAP_PHONE`, `ADMIN_BOOTSTRAP_PASSWORD`. يتطلب تنزيل البيانات أن يكون ملف CSV متاحًا وفق إعدادات `case_records.py`.

بعد نشر API على HTTPS، تُضبط قيمة `API_BASE_URL` في GitHub Actions Variables، ثم يبنى APK تجريبي من GitHub Actions ويُحمّل كـ artifact. لا يمكن إنشاء APK صالح قبل وجود ملفات المشروع وعنوان API الفعلي.
