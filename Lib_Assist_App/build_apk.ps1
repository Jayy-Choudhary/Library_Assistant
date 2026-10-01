$projectDir = "D:\Python\@_Projects_For_2026\06_Library_Assistant"
$appDir = "$projectDir\Lib_Assist_App"
$sdkDir = "D:\Python\@_Projects_For_2026\02_YT_Downloader\mobile_app"

$env:JAVA_HOME = "$sdkDir\jdk"
$env:ANDROID_HOME = "$sdkDir\android_sdk"
$env:ANDROID_SDK_ROOT = "$sdkDir\android_sdk"
$env:PATH = "$env:JAVA_HOME\bin;$sdkDir\flutter\bin;$env:ANDROID_HOME\cmdline-tools\latest\bin;$env:ANDROID_HOME\platform-tools;" + $env:PATH

Set-Location $appDir
Write-Host "Configuring Flutter Android SDK..."
& "$sdkDir\flutter\bin\flutter.bat" config --android-sdk "$env:ANDROID_HOME" --no-analytics

if (Test-Path "$appDir\build\app\outputs\flutter-apk\app-release.apk") {
    Remove-Item "$appDir\build\app\outputs\flutter-apk\app-release.apk" -Force
}

Write-Host "Building Release APK..."
& "$sdkDir\flutter\bin\flutter.bat" build apk --release --no-tree-shake-icons

if (Test-Path "$appDir\build\app\outputs\flutter-apk\app-release.apk") {
    Copy-Item "$appDir\build\app\outputs\flutter-apk\app-release.apk" "$projectDir\Lib_Assist_App_release.apk" -Force
    Write-Host "SUCCESS: Copied updated APK to $projectDir\Lib_Assist_App_release.apk"
} else {
    Write-Host "ERROR: app-release.apk not found after build"
}
