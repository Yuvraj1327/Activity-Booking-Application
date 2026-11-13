#!/usr/bin/env python3
"""Adds the native permissions the ZURUV mobile app needs (customer AND owner features) to the
Android/iOS runners that `flutter create` generated (run automatically by scripts/bootstrap_flutter.sh).

  * Android: ACCESS_COARSE_LOCATION / ACCESS_FINE_LOCATION (optional "venues near me"), INTERNET, and the auth deep link.
  * iOS: NSLocationWhenInUseUsageDescription, NSPhotoLibraryUsageDescription (profile picture and venue
    photos), and the auth URL scheme.

Idempotent: running it twice changes nothing. It only edits the two files named below.
"""

import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "apps" / "mobile_app"
SCHEME = "io.zuruv.app"  # must match AUTH_REDIRECT_URL (env/dev.example.json) and the Supabase allow-list

ANDROID_PERMISSIONS = [
    "android.permission.INTERNET",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_FINE_LOCATION",
]
ANDROID_INTENT_FILTER = f"""            <intent-filter>
                <action android:name="android.intent.action.VIEW"/>
                <category android:name="android.intent.category.DEFAULT"/>
                <category android:name="android.intent.category.BROWSABLE"/>
                <data android:scheme="{SCHEME}" android:host="login-callback"/>
            </intent-filter>
"""
IOS_STRINGS = {
    "NSLocationWhenInUseUsageDescription": "ZURUV uses your location to show venues near you. It is optional.",
    "NSPhotoLibraryUsageDescription": "ZURUV needs access to your photos so you can choose a profile picture or add venue photos.",
}


def patch_android() -> str:
    path = APP / "android/app/src/main/AndroidManifest.xml"
    if not path.exists():
        return f"skip: {path} not found (run scripts/bootstrap_flutter.sh first)"
    text = path.read_text()
    changed = False
    for perm in ANDROID_PERMISSIONS:
        if perm not in text:
            text = re.sub(r"(<manifest[^>]*>\n?)", rf'\1    <uses-permission android:name="{perm}"/>\n', text, count=1)
            changed = True
    if "<queries>" not in text:
        queries = (
            "    <queries>\n        <intent>\n            <action android:name=\"android.intent.action.VIEW\"/>\n"
            "            <data android:scheme=\"https\"/>\n        </intent>\n    </queries>\n"
        )
        text = text.replace("<application", queries + "    <application", 1)
        changed = True
    if SCHEME not in text:
        text = text.replace("</activity>", ANDROID_INTENT_FILTER + "        </activity>", 1)
        changed = True
    if 'android:label="zuruv"' in text:
        text = text.replace('android:label="zuruv"', 'android:label="ZURUV"')
        changed = True
    if changed:
        path.write_text(text)
    return "android: updated" if changed else "android: already configured"


def patch_ios() -> str:
    path = APP / "ios/Runner/Info.plist"
    if not path.exists():
        return f"skip: {path} not found (run scripts/bootstrap_flutter.sh first)"
    text = path.read_text()
    changed = False
    for key, value in IOS_STRINGS.items():
        if key not in text:
            text = text.replace("</dict>\n</plist>", f"\t<key>{key}</key>\n\t<string>{value}</string>\n</dict>\n</plist>")
            changed = True
    if SCHEME not in text:
        url_types = (
            "\t<key>CFBundleURLTypes</key>\n\t<array>\n\t\t<dict>\n\t\t\t<key>CFBundleURLSchemes</key>\n"
            f"\t\t\t<array>\n\t\t\t\t<string>{SCHEME}</string>\n\t\t\t</array>\n\t\t</dict>\n\t</array>\n"
        )
        text = text.replace("</dict>\n</plist>", url_types + "</dict>\n</plist>")
        changed = True
    text, n = re.subn(r"(<key>CFBundleDisplayName</key>\s*<string>)[^<]*(</string>)", r"\1ZURUV\2", text)
    changed = changed or (n > 0 and "ZURUV" not in path.read_text().split("CFBundleDisplayName")[1][:40])
    if changed:
        path.write_text(text)
    return "ios: updated" if changed else "ios: already configured"


if __name__ == "__main__":
    print(patch_android())
    print(patch_ios())
    sys.exit(0)
