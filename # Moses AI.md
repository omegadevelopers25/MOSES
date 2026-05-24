# Moses AI

Moses is a wise and helpful AI assistant powered by the Google Gemini API.

## Prerequisites

- Python 3.9+
- A Google Gemini API Key. You can get one from the [Google AI Studio](https://aistudio.google.com/app/apikey).

## Setup

1. Clone this repository (if applicable).
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your Gemini API key as an environment variable:
   ```bash
   export GEMINI_API_KEY='your_api_key_here'
   ```

## Usage

### Interactive Mode
To start a chat with Moses, simply run:
```bash
python moses.py
```

### Command-line Mode
To send a single prompt to Moses:
```bash
python moses.py "Your question or task here"
```

### Custom System Instruction
You can also provide a custom system instruction to change Moses's personality or behavior:
```bash
python moses.py --system "You are a very concise assistant." "How are you?"
```
