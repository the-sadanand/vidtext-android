[app]
title = VidText
package.name = vidtext
package.domain = org.sada
source.dir = .
source.include_exts = py
version = 1.0
requirements = python3,kivy==2.3.0,pycryptodome,pyjnius,android,androidstorage4kivy
orientation = portrait
fullscreen = 0
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
