# Razorpay checkout SDK (razorpay_flutter): referenced reflectively, and uses an annotation
# from a library that is not bundled. Without these rules R8 fails the release build.
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
-keepattributes JavascriptInterface
-keepattributes *Annotation*
-dontwarn com.razorpay.**
-keep class com.razorpay.** {*;}
-optimizations !method/inlining/*
-keepclasseswithmembers class * {
    public void onPayment*(...);
}
-dontwarn proguard.annotation.Keep
-dontwarn proguard.annotation.KeepClassMembers

# Google Play Core (referenced by the Flutter engine for deferred components, not used here).
-dontwarn com.google.android.play.core.**
