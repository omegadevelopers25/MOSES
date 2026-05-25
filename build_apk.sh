#!/bin/bash
# One-Tap Build and Install Script for MOSES Android APK

echo "========================================"
echo "MOSES One-Tap APK Build and Install"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python is not installed or not in PATH"
    exit 1
fi

# Check if Java is installed
if ! command -v java &> /dev/null; then
    echo "Error: Java is not installed or not in PATH"
    echo "Please install Java JDK 11 or higher"
    exit 1
fi

# Check if ADB is available
if command -v adb &> /dev/null; then
    HAS_ADB=1
else
    echo "Warning: ADB not found. Installation will skip device deployment."
    echo "Please install Android SDK Platform Tools for device installation."
    HAS_ADB=0
fi

# Install dependencies
echo "[1/6] Installing Python dependencies..."
python3 -m pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies"
    exit 1
fi

# Create Briefcase project
echo "[2/6] Creating Briefcase Android project..."
briefcase create android
if [ $? -ne 0 ]; then
    echo "Error: Failed to create Briefcase project"
    exit 1
fi

# Build the APK
echo "[3/6] Building APK (this may take several minutes)..."
briefcase build android
if [ $? -ne 0 ]; then
    echo "Error: Failed to build APK"
    exit 1
fi

# Generate keystore if it doesn't exist
echo "[4/6] Setting up APK signing..."
if [ ! -f "moses-release.keystore" ]; then
    echo "Generating keystore..."
    keytool -genkey -v -keystore moses-release.keystore -alias moses-key-alias -keyalg RSA -keysize 2048 -validity 10000 -storepass moses123 -keypass moses123 -dname "CN=MOSES, OU=Development, O=MOSES AI, L=City, ST=State, C=US"
    if [ $? -ne 0 ]; then
        echo "Warning: Failed to generate keystore, using unsigned APK"
        SIGNED=0
    else
        SIGNED=1
    fi
else
    SIGNED=1
fi

# Sign the APK if keystore exists
if [ $SIGNED -eq 1 ]; then
    echo "Signing APK..."
    jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 -keystore moses-release.keystore -storepass moses123 -keypass moses123 build/moses/android/gradle/app/build/outputs/apk/release/app-release-unsigned.apk moses-key-alias
    if [ $? -ne 0 ]; then
        echo "Warning: Failed to sign APK, using unsigned version"
        SIGNED=0
    else
        echo "Zipaligning APK..."
        zipalign -v 4 build/moses/android/gradle/app/build/outputs/apk/release/app-release-unsigned.apk moses-release.apk
        if [ $? -ne 0 ]; then
            echo "Warning: Failed to zipalign, using signed APK"
            FINAL_APK="build/moses/android/gradle/app/build/outputs/apk/release/app-release-unsigned.apk"
        else
            FINAL_APK="moses-release.apk"
        fi
    fi
fi

if [ $SIGNED -eq 0 ]; then
    FINAL_APK="build/moses/android/gradle/app/build/outputs/apk/release/app-release-unsigned.apk"
fi

# Install on connected device if ADB is available
if [ $HAS_ADB -eq 1 ]; then
    echo "[5/6] Checking for connected devices..."
    adb devices
    echo ""
    echo "Attempting to install on connected device..."
    adb install -r $FINAL_APK
    if [ $? -ne 0 ]; then
        echo "Warning: Failed to install on device. You can install manually."
    else
        echo "[6/6] Installation successful!"
        echo "Launching MOSES..."
        adb shell am start -n com.mosesassistant.moses/.MainActivity
    fi
else
    echo "[5/6] Skipping device installation (ADB not available)"
fi

echo ""
echo "========================================"
echo "BUILD COMPLETE!"
echo "========================================"
echo ""
if [ $SIGNED -eq 1 ]; then
    echo "Signed APK: $FINAL_APK"
else
    echo "Unsigned APK: $FINAL_APK"
fi
echo ""
if [ $HAS_ADB -eq 1 ]; then
    echo "The app has been installed on your connected device."
else
    echo "To install manually:"
    echo "1. Enable USB debugging on your Android device"
    echo "2. Connect device via USB"
    echo "3. Run: adb install -r $FINAL_APK"
fi
echo ""
echo "For Google Play distribution, see DEPLOYMENT.md"
echo ""
