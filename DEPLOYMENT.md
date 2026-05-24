# MOSES Android APK Deployment Guide

This guide will help you build and deploy the MOSES Personal Assistant as an Android APK.

## 🚀 One-Tap Build and Install

For maximum convenience, use the automated one-tap build scripts that handle everything:

### Windows
```bash
build_apk.bat
```

### Linux/Mac
```bash
chmod +x build_apk.sh
./build_apk.sh
```

**The one-tap script automatically:**
- ✅ Checks for required dependencies (Python, Java, ADB)
- ✅ Installs all Python packages
- ✅ Creates the Android project
- ✅ Builds the APK
- ✅ Generates signing keystore
- ✅ Signs and zipaligns the APK
- ✅ Installs on connected Android device (if ADB available)
- ✅ Launches the app automatically

**Prerequisites for one-tap install:**
- Python 3.8+ installed
- Java JDK 11+ installed
- Android device connected with USB debugging enabled (optional, for auto-install)
- Android SDK Platform Tools (for ADB, optional)

That's it! Just run the script and wait for the build to complete.

## Prerequisites

### For Windows
- Python 3.8 or higher
- Java JDK 11 or higher
- Android SDK (installed via Android Studio or separately)
- Set `ANDROID_HOME` environment variable to your Android SDK path
- Set `JAVA_HOME` environment variable to your JDK path

### For Linux/Mac
- Python 3.8 or higher
- Java JDK 11 or higher
- Android SDK
- Set `ANDROID_HOME` and `JAVA_HOME` environment variables

## Installation Steps

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install BeeWare

```bash
pip install briefcase
```

### 3. Create Android Project

```bash
briefcase create android
```

This will create the Android project structure with all necessary files.

### 4. Build the APK

```bash
briefcase build android
```

This will compile the Python code and build the Android APK.

### 5. Run on Device (Optional)

```bash
briefcase run android
```

This will install and run the app on a connected Android device.

### 6. Package for Distribution

```bash
briefcase package android
```

This will create a distributable APK file.

## Quick Build Scripts

### Windows
```bash
build_apk.bat
```

### Linux/Mac
```bash
chmod +x build_apk.sh
./build_apk.sh
```

## APK Location

After building, the APK will be located at:
```
build/moses/android/gradle/app/build/outputs/apk/release/app-release-unsigned.apk
```

## Signing the APK

The built APK is unsigned. To distribute it, you need to sign it:

### 1. Generate a Keystore

```bash
keytool -genkey -v -keystore moses-release.keystore -alias moses-key-alias -keyalg RSA -keysize 2048 -validity 10000
```

### 2. Sign the APK

```bash
jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 -keystore moses-release.keystore app-release-unsigned.apk moses-key-alias
```

### 3. Zipalign the APK

```bash
zipalign -v 4 app-release-unsigned.apk moses-release.apk
```

## Android Permissions

The app requests the following permissions:
- **INTERNET**: Required for API calls to AI services
- **CAMERA**: Required for vision features
- **RECORD_AUDIO**: Required for voice input
- **READ/WRITE_EXTERNAL_STORAGE**: Required for saving data
- **WAKE_LOCK**: Required for keeping the service alive
- **FOREGROUND_SERVICE**: Required for background operations

## Troubleshooting

### Build Fails with "ANDROID_HOME not set"
Set the `ANDROID_HOME` environment variable to your Android SDK path.

### Build Fails with "JAVA_HOME not set"
Set the `JAVA_HOME` environment variable to your JDK path.

### App Crashes on Startup
- Check if all dependencies are properly installed
- Verify API keys are set in the `.env` file
- Check logcat for detailed error messages

### Camera/Vision Not Working
- Ensure camera permissions are granted
- Check if the device has a working camera
- Verify the app has the necessary runtime permissions

### Voice Input Not Working
- Ensure microphone permissions are granted
- Check if the device has a working microphone
- Verify the app has the necessary runtime permissions

## Environment Variables

Create a `.env` file in the app's data directory with:
```
GEMINI_API_KEY=your_api_key_here
MOSES_MODEL=gemini-2.5-flash
MOSES_TIMEZONE=Asia/Kolkata
```

Note: On Android, the `.env` file should be placed in the app's internal storage directory. You may need to modify the code to load environment variables from a different location on Android.

## Distribution

### Google Play Store
To publish on Google Play Store:
1. Sign the APK with your release keystore
2. Create a Google Play Developer account ($25 one-time fee)
3. Follow the Play Console upload process
4. Provide screenshots, descriptions, and privacy policy

### Direct Distribution
You can distribute the signed APK directly:
- Upload to your website
- Send via email
- Distribute through third-party app stores

## Performance Optimization

For better performance on Android:
- The app uses a web-based GUI served locally
- Consider using a native GUI framework like Toga for better performance
- Optimize image sizes and resources
- Minimize network calls

## Notes

- The current implementation uses a web-based GUI served on localhost
- For production, consider implementing a native Android UI
- The app requires an active internet connection for AI features
- Local data is stored in the app's internal storage

## Support

For issues and questions:
- Check the BeeWare documentation: https://beeware.org/
- Check the project repository for updates
- Review the main README.md for general usage information
