@echo off
REM One-Tap Build and Install Script for MOSES Android APK

echo ========================================
echo MOSES One-Tap APK Build and Install
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if Java is installed
java -version >nul 2>&1
if errorlevel 1 (
    echo Error: Java is not installed or not in PATH
    echo Please install Java JDK 11 or higher
    pause
    exit /b 1
)

REM Check if ADB is available
adb version >nul 2>&1
if errorlevel 1 (
    echo Warning: ADB not found. Installation will skip device deployment.
    echo Please install Android SDK Platform Tools for device installation.
    set HAS_ADB=0
) else (
    set HAS_ADB=1
)

REM Install dependencies
echo [1/6] Installing Python dependencies...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

REM Create Briefcase project
echo [2/6] Creating Briefcase Android project...
briefcase create android
if errorlevel 1 (
    echo Error: Failed to create Briefcase project
    pause
    exit /b 1
)

REM Build the APK
echo [3/6] Building APK (this may take several minutes)...
briefcase build android
if errorlevel 1 (
    echo Error: Failed to build APK
    pause
    exit /b 1
)

REM Generate keystore if it doesn't exist
echo [4/6] Setting up APK signing...
if not exist "moses-release.keystore" (
    echo Generating keystore...
    keytool -genkey -v -keystore moses-release.keystore -alias moses-key-alias -keyalg RSA -keysize 2048 -validity 10000 -storepass moses123 -keypass moses123 -dname "CN=MOSES, OU=Development, O=MOSES AI, L=City, ST=State, C=US"
    if errorlevel 1 (
        echo Warning: Failed to generate keystore, using unsigned APK
        set SIGNED=0
    ) else (
        set SIGNED=1
    )
) else (
    set SIGNED=1
)

REM Sign the APK if keystore exists
if %SIGNED%==1 (
    echo Signing APK...
    jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 -keystore moses-release.keystore -storepass moses123 -keypass moses123 build\moses\android\gradle\app\build\outputs\apk\release\app-release-unsigned.apk moses-key-alias
    if errorlevel 1 (
        echo Warning: Failed to sign APK, using unsigned version
        set SIGNED=0
    ) else (
        echo Zipaligning APK...
        zipalign -v 4 build\moses\android\gradle\app\build\outputs\apk\release\app-release-unsigned.apk moses-release.apk
        if errorlevel 1 (
            echo Warning: Failed to zipalign, using signed APK
            set FINAL_APK=build\moses\android\gradle\app\build\outputs\apk\release\app-release-unsigned.apk
        ) else (
            set FINAL_APK=moses-release.apk
        )
    )
)

if %SIGNED%==0 (
    set FINAL_APK=build\moses\android\gradle\app\build\outputs\apk\release\app-release-unsigned.apk
)

REM Install on connected device if ADB is available
if %HAS_ADB%==1 (
    echo [5/6] Checking for connected devices...
    adb devices
    echo.
    echo Attempting to install on connected device...
    adb install -r %FINAL_APK%
    if errorlevel 1 (
        echo Warning: Failed to install on device. You can install manually.
    ) else (
        echo [6/6] Installation successful!
        echo Launching MOSES...
        adb shell am start -n com.mosesassistant.moses/.MainActivity
    )
) else (
    echo [5/6] Skipping device installation (ADB not available)
)

echo.
echo ========================================
echo BUILD COMPLETE!
echo ========================================
echo.
if %SIGNED%==1 (
    echo Signed APK: %FINAL_APK%
) else (
    echo Unsigned APK: %FINAL_APK%
)
echo.
if %HAS_ADB%==1 (
    echo The app has been installed on your connected device.
) else (
    echo To install manually:
    echo 1. Enable USB debugging on your Android device
    echo 2. Connect device via USB
    echo 3. Run: adb install -r %FINAL_APK%
)
echo.
echo For Google Play distribution, see DEPLOYMENT.md
echo.

pause
