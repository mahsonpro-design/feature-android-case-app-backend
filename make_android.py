import os
from pathlib import Path

def create_android_project():
    base = Path("android")
    base.mkdir(exist_ok=True)
    
    # settings.gradle
    (base / "settings.gradle").write_text(
        "rootProject.name = 'AlbaydaCourt'\ninclude ':app'\n", encoding="utf-8"
    )
    
    # build.gradle الرئيسي
    (base / "build.gradle").write_text(
        """buildscript {
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath 'com.android.tools.build:gradle:8.3.2'
    }
}
allprojects {
    repositories {
        google()
        mavenCentral()
    }
}
task clean(type: Delete) {
    delete rootProject.buildDir
}
""", encoding="utf-8"
    )
    
    # app/build.gradle
    app_dir = base / "app"
    app_dir.mkdir(exist_ok=True)
    (app_dir / "build.gradle").write_text(
        """plugins {
    id 'com.android.application'
}
android {
    namespace 'com.albayda.court'
    compileSdk 34
    defaultConfig {
        applicationId "com.albayda.court"
        minSdk 24
        targetSdk 34
        versionCode 1
        versionName "1.0"
    }
    buildTypes {
        release {
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
}
dependencies {
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.9.0'
}
""", encoding="utf-8"
    )
    
    # AndroidManifest.xml
    manifest_dir = app_dir / "src" / "main"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "AndroidManifest.xml").write_text(
        """<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="محكمة البيضاء"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.AppCompat.Light.NoActionBar">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
""", encoding="utf-8"
    )
    
    # MainActivity.java (رابط الموقع)
    java_dir = manifest_dir / "java" / "com" / "albayda" / "court"
    java_dir.mkdir(parents=True, exist_ok=True)
    
    target_url = os.getenv("APP_URL", "https://huggingface.co")
    
    (java_dir / "MainActivity.java").write_text(
        f"""package com.albayda.court;

import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {{
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        setContentView(webView);

        WebSettings webSettings = webView.getSettings();
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);
        webSettings.setLoadWithOverviewMode(true);
        webSettings.setUseWideViewPort(true);

        webView.setWebViewClient(new WebViewClient());
        webView.loadUrl("{target_url}");
    }}

    @Override
    public void onBackPressed() {{
        if (webView.canGoBack()) {{
            webView.goBack();
        }} else {{
            super.onBackPressed();
        }}
    }}
}}
""", encoding="utf-8"
    )
    print("تم توليد ملفات الأندرويد بنجاح!")

if __name__ == "__main__":
    create_android_project()
