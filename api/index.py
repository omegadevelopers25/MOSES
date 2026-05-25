import os
import sys
from pathlib import Path

# Add project root to sys.path so we can import moses and moses_gui
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from moses import AssistantStore, WorkspaceAccess, DEFAULT_MODEL, DEFAULT_TIMEZONE, SYSTEM_INSTRUCTION
from moses_gui import GuiState, HTML

app = Flask(__name__)
CORS(app)

# Use /tmp for state on Vercel as it is the only writable directory
DATA_FILE = os.getenv("MOSES_DATA_FILE", "/tmp/moses_state.json")
WORKSPACE_DIR = os.getenv("MOSES_WORKSPACE", os.getcwd())

# Initialize state
store = AssistantStore(Path(DATA_FILE), timezone=os.getenv("MOSES_TIMEZONE", DEFAULT_TIMEZONE))
workspace = WorkspaceAccess(Path(WORKSPACE_DIR))
gui_state = GuiState(store, os.getenv("MOSES_MODEL", DEFAULT_MODEL), SYSTEM_INSTRUCTION, workspace)

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_gui(path):
    if path == "api/state":
        return jsonify(gui_state.snapshot())
    return Response(HTML, mimetype="text/html")

@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.json or {}
    message = payload.get("message", "").strip()
    backend = payload.get("backend", "gemini").strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400
    try:
        reply = gui_state.ask(message, backend)
        return jsonify({"reply": reply})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.route("/api/vision", methods=["POST"])
def vision():
    payload = request.json or {}
    message = payload.get("message", "").strip() or "What do you see right now?"
    image = payload.get("image", "").strip()
    backend = payload.get("backend", "gemini").strip()
    if not image:
        return jsonify({"error": "Image is required."}), 400
    try:
        reply = gui_state.ask_vision(message, image, backend)
        return jsonify({"reply": reply})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.route("/api/cowork", methods=["POST"])
def cowork():
    payload = request.json or {}
    enabled = bool(payload.get("enabled", False))
    try:
        return jsonify(gui_state.set_cowork_mode(enabled))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.route("/api/cowork-change", methods=["POST"])
def cowork_change():
    payload = request.json or {}
    change_id = payload.get("id", "").strip()
    action = payload.get("action", "").strip().lower()
    if not change_id:
        return jsonify({"error": "Change id is required."}), 400
    try:
        result = gui_state.update_cowork_change(change_id, action)
        status = 400 if result.get("error") else 200
        return jsonify(result), status
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.route("/api/state", methods=["GET"])
def get_state():
    try:
        return jsonify(gui_state.snapshot())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# Entry point for Vercel
handler = app
