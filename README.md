# MOSES Personal Assistant

MOSES is an agentic personal assistant powered by the Gemini API. It can chat,
remember preferences, manage todos, save notes, store reminders, check the
current time, and run safe calculations through local Python tools.

## Setup

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

On Windows, if `python` is not available but the Python launcher is installed:

```bash
py -m pip install -r requirements.txt
```

Create a `.env` file:

```bash
GEMINI_API_KEY=your_api_key_here
MOSES_MODEL=gemini-2.5-flash
MOSES_TIMEZONE=Asia/Kolkata
```

## Run

Interactive mode:

```bash
python moses.py
```

Or on Windows:

```bash
py moses.py
```

Jarvis-style browser GUI:

```bash
py moses_gui.py
```

Then open:

```text
http://127.0.0.1:8765
```

Gemini Live voice/camera script:

```bash
py gemini_live_assistant.py --mode camera
```

Modes:

```text
camera | screen | none
```

One-shot mode:

```bash
python moses.py "Add a high priority todo to revise math tomorrow at 6 PM"
```

Use a custom model:

```bash
python moses.py --model gemini-2.5-flash "What is on my todo list?"
```

## What MOSES Can Do

- Remember durable facts and preferences.
- Add, list, and complete todos.
- Save and search notes.
- Store reminder records.
- Check the current date and time for your timezone.
- Calculate math safely without using Python `eval`.
- Use a local browser GUI with animated assistant core, state panels, optional
  voice input, and optional spoken replies.
- Use browser voice commands. Spoken commands are sent automatically, and if
  camera or screen vision is active the command includes a fresh snapshot.
- Use computer vision from the browser with camera or screen sharing.
- Read text files inside the configured workspace.
- Stage text-file changes inside the configured workspace when Cowork mode is
  enabled.
- Review, apply, or reject staged Cowork changes from the GUI Changes tab.

Local assistant data is stored in `data/moses_state.json`.

## Android APK Deployment

MOSES can be deployed as an Android APK using BeeWare Briefcase. See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

### 🚀 One-Tap Build and Install

For maximum convenience, use the automated one-tap build scripts:

**Windows:**
```bash
build_apk.bat
```

**Linux/Mac:**
```bash
chmod +x build_apk.sh
./build_apk.sh
```

The script automatically handles everything: dependencies, build, signing, and installation on your connected device.

### Manual Build Steps

If you prefer manual control:

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create Android project:
```bash
briefcase create android
```

3. Build APK:
```bash
briefcase build android
```

4. Run on device:
```bash
briefcase run android
```

The APK will be built with the following permissions:
- Internet (for AI API calls)
- Camera (for vision features)
- Microphone (for voice input)
- Storage (for saving data)

## Important

Reminder support stores reminder records only. It does not create Windows,
Android, email, or calendar notifications yet.

Workspace file access is limited to the project folder by default. File changes
require Cowork mode, which can be toggled in the GUI. In Cowork mode, MOSES
stages proposed edits first; use the Changes tab to apply or reject them. MOSES
blocks `.env`, `.git`, virtual environments, local data, and common binary files.
